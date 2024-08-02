from datetime import datetime
from unittest import mock

import pytest
from requests import RequestException

from tcintercom.app.routers.worker import WorkerSettings, update_duplicate_contacts
from tcintercom.app.settings import Settings
from tcintercom.run import create_worker

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
            if test == 'duplicate_contacts_basic':
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


@pytest.mark.asyncio
class TestWorkerJobs:
    @mock.patch('tcintercom.run.logfire.span')
    @mock.patch('tcintercom.run.TCIntercomWorker.run')
    @mock.patch('tcintercom.run.Worker.run_job')
    async def test_worker_logfire(self, mock_run_job, mock_worker_run, mock_logfire):
        mock_run_job.return_value = True
        settings = Settings()
        worker = create_worker(WorkerSettings, redis_settings=settings.redis_settings, ctx={'settings': settings})
        assert mock_worker_run.called
        assert mock_worker_run.call_count == 1

        await worker.run_job('123:test_function:456', 1)
        assert mock_logfire.call_args_list[0]
        assert mock_logfire.call_args_list[0][0][0] == 'test_function'

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
