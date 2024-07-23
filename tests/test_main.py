import os
from unittest import TestCase, mock

import jwt
from click.testing import CliRunner
from fastapi import FastAPI
from fastapi.testclient import TestClient
from requests import RequestException

from tcintercom.app.logs import logfire_setup
from tcintercom.app.main import create_app
from tcintercom.app.views import SUPPORT_TEMPLATE, conf
from tcintercom.run import cli


def get_mock_response(test, error=False):
    class MockResponse:
        def __init__(self, method, url, *args, **kwargs):
            self.url = url
            self.return_company = {
                'companies': {
                    'type': 'list',
                    'data': [{'id': '123', 'name': 'Foo company', 'url': '/companies/123'}],
                }
            }
            self.return_dict = {
                'no_companies': {'companies': {'type': 'list', 'data': []}},
                'blog_new_user': {'data': []},
                'blog_existing_user': {'data': [{'id': 123}]},
            }

        def json(self):
            if test == 'no_support':
                if 'contacts/' in self.url:
                    return self.return_company
                else:
                    return {'custom_attributes': {'support_plan': 'No Support'}}
            elif test == 'has_support':
                if 'contacts/' in self.url:
                    return self.return_company
                else:
                    return {'custom_attributes': {'support_plan': 'Support plan'}}
            elif test in self.return_dict:
                return self.return_dict[test]

        def raise_for_status(self):
            if error:
                raise RequestException('Bad request')

    return MockResponse


class TCIntercomSetup(TestCase):
    """
    Tests for running the web and worker apps, and the setup of the app (settings, logging, etc).
    """

    @mock.patch('tcintercom.run.uvicorn.run')
    def test_create_app(self, mock_uvicorn):
        """
        Tests that the app is created correctly when the DYNO starts with web.
        """
        os.environ['DYNO'] = 'web123'
        runner = CliRunner()
        result = runner.invoke(cli, 'auto')
        assert result.exit_code == 0

        assert mock_uvicorn.called
        assert mock_uvicorn.call_count == 1
        assert isinstance(mock_uvicorn.call_args_list[0][0][0], FastAPI)

    @mock.patch('tcintercom.run.uvicorn.run')
    def test_create_app_with_port(self, mock_uvicorn):
        """
        Tests that the app is created correctly when only a port is supplied.
        """
        os.environ['PORT'] = '8000'
        runner = CliRunner()
        result = runner.invoke(cli, 'auto')
        assert result.exit_code == 0

        assert mock_uvicorn.called
        assert mock_uvicorn.call_count == 1
        assert isinstance(mock_uvicorn.call_args_list[0][0][0], FastAPI)

    @mock.patch('tcintercom.run.TCIntercomWorker.run')
    def test_create_worker(self, mock_worker):
        """
        Tests that the worker is created correctly.
        """
        os.environ['DYNO'] = 'worker123'
        runner = CliRunner()
        result = runner.invoke(cli, 'auto')
        assert result.exit_code == 0

        assert mock_worker.called
        assert mock_worker.call_count == 1

    @mock.patch('tcintercom.app.main.app_settings')
    @mock.patch('tcintercom.app.logs.logfire.configure')
    def test_setup_logfire(self, mock_configure, mock_app_settings):
        """
        Tests that logfire configure is called under the correct conditions.
        """
        mock_app_settings.testing = True
        mock_app_settings.logfire_token = 'mock_token'

        logfire_setup('test')
        assert not mock_configure.called
        assert not mock_configure.call_count

        mock_app_settings.testing = False
        mock_app_settings.logfire_token = ''

        logfire_setup('test')
        assert not mock_configure.called
        assert not mock_configure.call_count

        mock_app_settings.testing = False
        mock_app_settings.logfire_token = 'mock_token'

        logfire_setup('test')
        assert mock_configure.called
        assert mock_configure.call_count == 1

    @mock.patch('tcintercom.app.main.app_settings')
    @mock.patch('tcintercom.app.main.sentry_sdk.init')
    def test_setup_sentry_dsn(self, mock_sentry, mock_app_settings):
        """
        Tests that sentry is setup correctly.
        """
        mock_app_settings.raven_dsn = 'http://foo@sentry.io/123'

        TestClient(create_app())
        assert mock_sentry.called
        assert mock_sentry.call_count == 1


class BasicEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_index(self):
        """
        Test the index endpoint returns the correct content.
        """
        r = self.client.get('/')
        assert r.content.decode() == '{"message":"TutorCruncher\'s service for managing Intercom is Online"}'

    def test_purposeful_error(self):
        """
        Test the purposeful error endpoint raises a RuntimeError.
        """
        with self.assertRaises(RuntimeError):
            self.client.get('/error/')

    def test_robots(self):
        """
        Test the endpoint robots.txt returns the correct content.
        """
        r = self.client.get('/robots.txt')
        assert r.status_code == 200
        assert b'User-agent: *' in r.content


class IntercomCallbackTestCase(TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_no_action_needed(self):
        """
        Test that if no action is needed, we return 'No action required'.
        """
        data = {'data': {'item': {'id': 500}}}
        r = self.client.post('/callback/', json=data)
        assert r.json() == {'message': 'No action required'}

    def test_callback_invalid_json(self):
        """
        Test that if the JSON is invalid, we return 'Invalid JSON'.
        """
        r = self.client.post('/callback/', content='{invalid}')
        assert r.status_code == 400
        assert r.content.decode() == '{"error":"Invalid JSON"}'

    @mock.patch('tcintercom.app.views.session.request')
    def test_conv_created_user_no_companies(self, mock_request):
        """
        Test that if a user has no companies, we return 'User has no companies'.
        """
        mock_request.side_effect = get_mock_response('no_companies')

        ic_data = {
            'topic': 'conversation.user.created',
            'data': {'item': {'user': {'id': 123}, 'id': 123}},
        }
        r = self.client.post('/callback/', json=ic_data)
        assert r.json() == {'message': 'User has no companies'}

    @mock.patch('tcintercom.app.views.session.request')
    @mock.patch('tcintercom.app.views.conf.ic_token', 'TESTKEY')
    def test_conv_created_no_support(self, mock_request):
        """
        Test that if a user has no support, the bot posts the SUPPORT_TEMPLATE reply to the conversation.
        """
        mock_request.side_effect = get_mock_response('no_support')
        ic_data = {
            'topic': 'conversation.user.created',
            'data': {'item': {'user': {'id': 123}, 'id': 123}},
        }
        r = self.client.post('/callback/', json=ic_data)
        assert r.json() == {'message': 'Reply successfully posted'}
        assert mock_request.call_args_list[-1][1]['json']['body'] == SUPPORT_TEMPLATE

    @mock.patch('tcintercom.app.views.session.request')
    def test_conv_created_has_support(self, mock_request):
        """
        Test that if a company has support, we return 'Company has support'.
        """
        mock_request.side_effect = get_mock_response('has_support')
        ic_data = {
            'topic': 'conversation.user.created',
            'data': {'item': {'user': {'id': 123}, 'id': 123}},
        }
        r = self.client.post('/callback/', json=ic_data)
        assert r.json() == {'message': 'Company has support'}

    def test_message_tagged_wrong_tag(self):
        """
        Test that if a tag is applied that we don't want to act on, we return 'No action required'.
        """
        ic_data = {
            'topic': 'conversation_part.tag.created',
            'data': {
                'item': {
                    'id': 123,
                    'tags_added': {'type': 'tag.list', 'tags': [{'name': 'Wrong tag'}]},
                    'conversation_parts': {
                        'type': 'conversation_part.list',
                        'conversation_parts': [{'body': 'A new issue please'}],
                    },
                }
            },
        }
        r = self.client.post('/callback/', json=ic_data)
        assert r.json() == {'message': 'No action required'}


@mock.patch('tcintercom.app.views.conf.ic_token', 'TESTKEY')
@mock.patch('tcintercom.app.views.conf.netlify_key', 'TESTKEY')
class BlogCallbackTestCase(TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    @mock.patch('tcintercom.app.views.session.request')
    def test_blog_sub_new_user(self, mock_request):
        """
        Tests when a new user subscribes to the blog that we create a new user and add the
        blog-subscribe True attribute.
        """
        mock_request.side_effect = get_mock_response('blog_new_user')
        encoded_jwt = jwt.encode({'some': 'payload'}, conf.netlify_key, algorithm='HS256')

        form_data = {'data': {'email': 'test@testing.com'}}
        r = self.client.post('/blog-callback/', json=form_data, headers={'x-webhook-signature': encoded_jwt})
        assert r.json() == {'message': 'Blog subscription added to a new user'}
        assert mock_request.call_args_list[-1][0][0] == 'POST'  # Assert POST request (creating rather than updating)
        assert mock_request.call_args_list[-1][1]['json']['custom_attributes']['blog-subscribe']

    @mock.patch('tcintercom.app.views.session.request')
    def test_blog_sub_existing_user(self, mock_request):
        """
        Tests when an existing user subscribes to the blog that we don't create a new user, but do add the
        blog-subscribe True attribute to them.
        """
        mock_request.side_effect = get_mock_response('blog_existing_user')
        encoded_jwt = jwt.encode({'some': 'payload'}, conf.netlify_key, algorithm='HS256')

        form_data = {'data': {'email': 'test@testing.com'}}
        r = self.client.post('/blog-callback/', json=form_data, headers={'x-webhook-signature': encoded_jwt})
        assert r.json() == {'message': 'Blog subscription added to existing user'}
        assert mock_request.call_args_list[-1][0][0] == 'PUT'  # Assert PUT request (updating rather than creating)
        assert mock_request.call_args_list[-1][1]['json']['custom_attributes']['blog-subscribe']

    def test_incorrect_key(self):
        """
        Test that if the signature is incorrect we return an incorrect signature error.
        """
        encoded_jwt = jwt.encode({'some': 'payload'}, 'incorrect_key', algorithm='HS256')

        form_data = {'data': {'email': 'test@testing.com'}}
        r = self.client.post('/blog-callback/', json=form_data, headers={'x-webhook-signature': encoded_jwt})
        assert r.json() == {'error': 'Invalid Signature'}
