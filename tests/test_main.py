import hashlib
import hmac
import json
from unittest import TestCase, mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tcintercom.app.logs import logfire_setup
from tcintercom.app.main import create_app
from tcintercom.run import main


def get_mock_response(test):
    class MockResponse:
        def __init__(self, method, url, *args, **kwargs):
            self.url = url
            self.return_dict = {
                'blog_new_user': {'data': []},
                'blog_existing_user': {'data': [{'id': 123}]},
            }

        def json(self):
            if test in self.return_dict:
                return self.return_dict[test]

        def raise_for_status(self):
            pass

    return MockResponse


class TCIntercomSetup(TestCase):
    """
    Tests for running the web and worker apps, and the setup of the app (settings, logging, etc).
    """

    @mock.patch('tcintercom.run.uvicorn.run')
    @mock.patch('sys.argv', ['run.py', 'web'])
    def test_create_app(self, mock_uvicorn):
        """
        Tests that the app is created correctly when the DYNO starts with web.
        """
        main()

        assert mock_uvicorn.called
        assert mock_uvicorn.call_count == 1
        assert isinstance(mock_uvicorn.call_args_list[0][0][0], FastAPI)

    @mock.patch('tcintercom.run.logger.error')
    @mock.patch('sys.argv', ['run.py', 'test'])
    def test_create_with_nothing_specified(self, mock_logger):
        """
        Tests calling the main function with invalid arguments.
        """
        main()

        assert mock_logger.called
        assert 'Invalid command test' in mock_logger.call_args_list[-1][0][0]

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

    def test_lifespan_setup(self):
        """
        Tests that the lifespan context manager sets up the app correctly. We have to use with TestClient to test
        this.

        https://stackoverflow.com/questions/75714883/how-to-test-a-fastapi-endpoint-that-uses-lifespan-function
        """
        app = create_app()
        index_url = app.url_path_for('index')
        with TestClient(app) as client:
            response = client.get(index_url)
            assert response.status_code == 200


class BasicEndpointsTestCase(TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_index(self):
        """
        Test the index endpoint returns the correct content and only allows a GET request.
        """
        index_url = self.app.url_path_for('index')
        r = self.client.get(index_url)
        assert r.content.decode() == '{"message":"TutorCruncher\'s service for managing Intercom is Online"}'

        r = self.client.post(index_url, data={})
        assert r.status_code == 405
        assert r.content.decode() == '{"detail":"Method Not Allowed"}'

    def test_purposeful_error(self):
        """
        Test the purposeful error endpoint raises a RuntimeError and only allows a GET request.
        """
        error_url = self.app.url_path_for('error')
        with self.assertRaises(RuntimeError):
            self.client.get(error_url)

        r = self.client.post(error_url, data={})
        assert r.status_code == 405
        assert r.content.decode() == '{"detail":"Method Not Allowed"}'

    def test_robots(self):
        """
        Test the endpoint robots.txt returns the correct content and only allows a GET request.
        """
        robots_url = self.app.url_path_for('robots')
        r = self.client.get(robots_url)
        assert r.status_code == 200
        assert b'User-agent: *' in r.content

        r = self.client.post(robots_url, data={})
        assert r.status_code == 405
        assert r.content.decode() == '{"detail":"Method Not Allowed"}'


class IntercomCallbackTestCase(TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        self.callback_url = self.app.url_path_for('callback')

    def test_no_action_needed(self):
        """
        Test that if no action is needed, we return 'No action required'.
        """
        data = {'data': {'item': {'id': 500}}}
        r = self.client.post(self.callback_url, json=data)
        assert r.json() == {'message': 'No action required'}

    def test_invalid_method(self):
        """
        Tests that only POST requests are allowed to the intercom callback endpoint.
        """
        r = self.client.get(self.callback_url)
        assert r.status_code == 405
        assert r.content.decode() == '{"detail":"Method Not Allowed"}'

    @mock.patch('tcintercom.app.settings.app_settings.testing', False)
    @mock.patch('tcintercom.app.settings.app_settings.ic_client_secret', 'TESTKEY')
    def test_validated_webhook_sig(self):
        """
        Tests that the webhook signature is valid and from Intercom.
        """
        test_secret_key = 'TESTKEY'
        data = {'data': {'item': {'id': 500}}}
        signature = f'sha1={hmac.new(test_secret_key.encode(), json.dumps(data).replace(" ", "").encode(), hashlib.sha1).hexdigest()}'

        r = self.client.post(self.callback_url, json=data, headers={'X-Hub-Signature': signature})
        assert r.status_code == 200
        assert r.json() == {'message': 'No action required'}

        with self.assertRaises(AssertionError):
            self.client.post(self.callback_url, json={}, headers={'X-Hub-Signature': 'invalid_signature'})

    def test_callback_invalid_json(self):
        """
        Test that if the JSON is invalid, we return 'Invalid JSON'.
        """
        r = self.client.post(self.callback_url, content='{invalid}')
        assert r.status_code == 400
        assert r.content.decode() == '{"error":"Invalid JSON"}'

    def test_conversation_user_created(self):
        """
        Test that conversation.user.created topic returns 'No action required' (no auto-reply).
        """
        ic_data = {
            'topic': 'conversation.user.created',
            'data': {'item': {'user': {'id': 123}, 'id': 123}},
        }
        r = self.client.post(self.callback_url, json=ic_data)
        assert r.json() == {'message': 'No action required'}


@mock.patch('tcintercom.app.settings.app_settings.ic_secret_token', 'TESTKEY')
@mock.patch('tcintercom.app.settings.app_settings.netlify_key', 'TESTKEY')
class BlogCallbackTestCase(TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        self.blog_callback_url = self.app.url_path_for('blog-callback')

    def test_invalid_method(self):
        """
        Tests that only POST requests are allowed to the blog callback endpoint.
        """
        r = self.client.get(self.blog_callback_url)
        assert r.status_code == 405
        assert r.content.decode() == '{"detail":"Method Not Allowed"}'

    @mock.patch('tcintercom.app.views.session.request')
    def test_blog_sub_new_user(self, mock_request):
        """
        Tests when a new user subscribes to the blog that we create a new user and add the
        blog-subscribe True attribute.
        """
        mock_request.side_effect = get_mock_response('blog_new_user')

        form_data = {'email': 'test@testing.com'}
        r = self.client.post(self.blog_callback_url, json=form_data)
        assert r.json() == {'message': 'Blog subscription added to a new user'}
        assert mock_request.call_args_list[-1][0][0] == 'POST'  # Assert POST request (creating rather than updating)
        assert mock_request.call_args_list[-1][1]['json']['custom_attributes']['blog-subscribe']

    def test_blank_email_address(self):
        """
        Tests when we submit a blank email address, we return 'Email address is required'.
        """

        form_data = {'email': ''}
        r = self.client.post(self.blog_callback_url, json=form_data)
        assert r.status_code == 400

    @mock.patch('tcintercom.app.views.session.request')
    def test_blog_sub_existing_user(self, mock_request):
        """
        Tests when an existing user subscribes to the blog that we don't create a new user, but do add the
        blog-subscribe True attribute to them.
        """
        mock_request.side_effect = get_mock_response('blog_existing_user')

        form_data = {'email': 'test@testing.com'}
        r = self.client.post(self.blog_callback_url, json=form_data)
        assert r.json() == {'message': 'Blog subscription added to existing user'}
        assert mock_request.call_args_list[-1][0][0] == 'PUT'  # Assert PUT request (updating rather than creating)
        assert mock_request.call_args_list[-1][1]['json']['custom_attributes']['blog-subscribe']
