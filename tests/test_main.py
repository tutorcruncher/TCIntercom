import os
from datetime import datetime
from unittest import TestCase, mock

import jwt
import pytest
from click.testing import CliRunner
from fastapi import FastAPI
from fastapi.testclient import TestClient
from requests import RequestException

from tcintercom.app.logs import logfire_setup
from tcintercom.app.main import create_app
from tcintercom.app.routers.worker import update_duplicate_contacts
from tcintercom.app.views import SUPPORT_TEMPLATE, conf
from tcintercom.run import cli

TEST_CONTACTS = {
    'main_contact': {
        'type': 'contact',
        'id': 'main_contact',
        'role': 'user',
        'email': 'test_main@test.com',
        'phone': '0123456789',
        'created_at': datetime.timestamp(datetime(2023, 6, 1)),
        'last_seen_at': datetime.timestamp(datetime(2023, 6, 15)),
        'custom_attributes': {'is_duplicate': False},
    },
    'not_marked_duplicate_contact': {
        'type': 'contact',
        'id': 'duplicate_contact',
        'role': 'user',
        'email': 'test_main@test.com',
        'phone': '0123456789',
        'created_at': datetime.timestamp(datetime(2023, 6, 2)),
        'last_seen_at': datetime.timestamp(datetime(2023, 6, 3)),
        'custom_attributes': {'is_duplicate': False},
    },
    'marked_duplicate_contact': {
        'type': 'contact',
        'id': 'incorrect_mark_duplicate',
        'role': 'user',
        'email': 'test_main@test.com',
        'phone': '0123456789',
        'created_at': datetime.timestamp(datetime(2023, 6, 2)),
        'last_seen_at': datetime.timestamp(datetime(2023, 6, 3)),
        'custom_attributes': {'is_duplicate': True},
    },
    'created_later_contact': {
        'type': 'contact',
        'id': 'created_later_contact',
        'role': 'user',
        'email': 'test_main@test.com',
        'phone': '0123456789',
        'created_at': datetime.timestamp(datetime(2023, 6, 4)),
        'last_seen_at': None,
        'custom_attributes': {'is_duplicate': False},
    },
}


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
            elif test == 'duplicate_contacts_basic':
                if 'contacts?' in self.url:
                    return {'data': [TEST_CONTACTS['main_contact'], TEST_CONTACTS['not_marked_duplicate_contact']]}
            elif test == 'more_recent_not_duplicate_contact':
                if 'contacts?' in self.url:
                    return {'data': [TEST_CONTACTS['marked_duplicate_contact'], TEST_CONTACTS['main_contact']]}
            elif test == 'more_recently_active_duplicate_contact':
                if 'contacts?' in self.url:
                    return {'data': [TEST_CONTACTS['not_marked_duplicate_contact'], TEST_CONTACTS['main_contact']]}
            elif test == 'most_recent_created_at_duplicate_contact':
                if self.url.endswith('/contacts?per_page=150'):
                    return {
                        'data': [TEST_CONTACTS['created_later_contact'], TEST_CONTACTS['main_contact']],
                        'pages': {'next': {'starting_after': TEST_CONTACTS['main_contact'].get('id')}},
                    }
                elif '/contacts?per_page=150&starting_after' in self.url:
                    return {'data': [TEST_CONTACTS['marked_duplicate_contact']]}
            elif test == 'mark_not_duplicate_contact':
                if 'contacts?' in self.url:
                    return {'data': [TEST_CONTACTS['marked_duplicate_contact']]}
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
        Tests that the app is created correctly.
        """
        os.environ['DYNO'] = 'web123'
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


@pytest.mark.asyncio
class TestWorker:
    @mock.patch('tcintercom.app.views.session.request')
    async def test_mark_duplicate_contacts(self, mock_request):
        """
        Tests that the correct contacts are marked as duplicate.
        """
        mock_request.side_effect = get_mock_response('duplicate_contacts_basic')
        await update_duplicate_contacts({})

        dup_contact = TEST_CONTACTS['not_marked_duplicate_contact']
        assert mock_request.call_args_list[-1][0][0] == 'PUT'
        assert mock_request.call_args_list[-1][0][1] == f'https://api.intercom.io/contacts/{dup_contact["id"]}'
        assert mock_request.call_args_list[-1][1]['json']['email'] == dup_contact['email']
        assert (
            mock_request.call_args_list[-1][1]['json']['custom_attributes']['is_duplicate']
            != dup_contact['custom_attributes']['is_duplicate']
        )

    @mock.patch('tcintercom.app.views.session.request')
    async def test_more_recent_not_duplicate_contact(self, mock_request):
        """
        Tests that a more recent contact with the same email isn't incorrectly marked as duplicate due to the order
        the contacts list is in. We assert this by checking that no calls are made to update contacts are made as they
        are already in their correct state.
        """
        mock_request.side_effect = get_mock_response('more_recent_not_duplicate_contact')
        await update_duplicate_contacts({})
        assert mock_request.call_args_list[-1][0][0] == 'GET'

    @mock.patch('tcintercom.app.views.session.request')
    async def test_more_recently_active_contact(self, mock_request):
        """
        Tests that the contact who was more recently active is not marked as the duplicate contact.
        """
        mock_request.side_effect = get_mock_response('more_recently_active_duplicate_contact')
        await update_duplicate_contacts({})

        dup_contact = TEST_CONTACTS['not_marked_duplicate_contact']
        assert mock_request.call_args_list[-1][0][0] == 'PUT'
        assert mock_request.call_args_list[-1][0][1] == f'https://api.intercom.io/contacts/{dup_contact["id"]}'
        assert mock_request.call_args_list[-1][1]['json']['email'] == dup_contact['email']
        assert (
            mock_request.call_args_list[-1][1]['json']['custom_attributes']['is_duplicate']
            != dup_contact['custom_attributes']['is_duplicate']
        )

    @mock.patch('tcintercom.app.views.session.request')
    async def test_most_recent_created_at_contact(self, mock_request):
        """
        Tests that a contact that a contact that was created at a later date than the original contact, gets
        marked as the duplicate contact. Also tests the pagination of the contacts list.
        """
        mock_request.side_effect = get_mock_response('most_recent_created_at_duplicate_contact')
        await update_duplicate_contacts({})

        main_contact = TEST_CONTACTS['main_contact']
        assert mock_request.call_args_list[-2][0][0] == 'GET'
        assert (
            mock_request.call_args_list[-2][0][1]
            == f'https://api.intercom.io/contacts?per_page=150&starting_after={main_contact.get("id")}'
        )

        created_at_contact = TEST_CONTACTS['created_later_contact']
        assert mock_request.call_args_list[-1][0][0] == 'PUT'
        assert mock_request.call_args_list[-1][0][1] == f'https://api.intercom.io/contacts/{created_at_contact["id"]}'
        assert mock_request.call_args_list[-1][1]['json']['email'] == created_at_contact['email']
        assert (
            mock_request.call_args_list[-1][1]['json']['custom_attributes']['is_duplicate']
            != created_at_contact['custom_attributes']['is_duplicate']
        )

    @mock.patch('tcintercom.app.views.session.request')
    async def test_mark_not_duplicate_contacts(self, mock_request):
        """
        Tests that if there is only one contact with that email address and they are marked as a duplicate,
        we update them to be marked as not duplicate.
        """
        mock_request.side_effect = get_mock_response('mark_not_duplicate_contact')
        await update_duplicate_contacts({})

        dup_contact = TEST_CONTACTS['marked_duplicate_contact']
        assert mock_request.call_args_list[-1][0][0] == 'PUT'
        assert mock_request.call_args_list[-1][0][1] == f'https://api.intercom.io/contacts/{dup_contact["id"]}'
        assert mock_request.call_args_list[-1][1]['json']['email'] == dup_contact['email']
        assert (
            mock_request.call_args_list[-1][1]['json']['custom_attributes']['is_duplicate']
            != dup_contact['custom_attributes']['is_duplicate']
        )
