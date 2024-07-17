from unittest import TestCase, mock

import jwt
from fastapi.testclient import TestClient
from requests import RequestException

from tcintercom.app.main import create_app
from tcintercom.app.views import conf


def get_mock_response(test, error=False):
    class MockResponse:
        def __init__(self, method, url, *args, **kwargs):
            self.url = url

        def json(self):
            if test == 'no_support':
                if 'contacts/' in self.url:
                    return {
                        'companies': {
                            'type': 'list',
                            'data': [{'id': '123', 'name': 'Foo company', 'url': '/companies/123'}],
                        }
                    }
                else:
                    return {'custom_attributes': {'support_plan': 'No Support'}}
            elif test == 'has_support':
                if 'contacts/' in self.url:
                    return {
                        'companies': {
                            'type': 'list',
                            'data': [{'id': '123', 'name': 'Foo company', 'url': '/companies/123'}],
                        }
                    }
                else:
                    return {'custom_attributes': {'support_plan': 'Support plan'}}
            elif test in return_dict:
                return return_dict[test]

        def raise_for_status(self):
            if error:
                raise RequestException('Bad request')

    return MockResponse


return_dict = {
    'no_companies': {'companies': {'type': 'list', 'data': []}},
    'blog_new_user': {'data': []},
    'blog_existing_user': {'data': [{'id': 123}]},
}


class IntercomCallbackTestCase(TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_index(self):
        r = self.client.get('/')
        assert r.content.decode() == '{"message":"TutorCruncher\'s service for managing Intercom is Online"}'

    def test_purposeful_error(self):
        with self.assertRaises(RuntimeError):
            self.client.get('/error/')

    def test_robots(self):
        r = self.client.get('/robots.txt')
        assert r.status_code == 200
        assert b'User-agent: *' in r.content

    def test_no_action_needed(self):
        data = {'data': {'item': {'id': 500}}}
        r = self.client.post('/callback/', json=data)
        assert r.json() == {'message': 'No action required'}

    def test_callback_invalid_json(self):
        r = self.client.post('/callback/', content='{invalid}')
        assert r.status_code == 400

    @mock.patch('tcintercom.app.views.session.request')
    def test_conv_created_user_no_companies(self, mock_request):
        mock_request.side_effect = get_mock_response('no_companies')

        ic_data = {
            'topic': 'conversation.user.created',
            'data': {'item': {'user': {'id': 123}, 'id': 123}},
        }
        r = self.client.post('/callback/', json=ic_data)
        assert r.json() == {'message': 'User has no companies'}

    @mock.patch('tcintercom.app.views.session.request')
    def test_conv_created_no_support(self, mock_request):
        mock_request.side_effect = get_mock_response('no_support')
        ic_data = {
            'topic': 'conversation.user.created',
            'data': {'item': {'user': {'id': 123}, 'id': 123}},
        }
        r = self.client.post('/callback/', json=ic_data)
        assert r.json() == {'message': 'Reply successfully posted'}

    @mock.patch('tcintercom.app.views.session.request')
    def test_conv_created_has_support(self, mock_request):
        mock_request.side_effect = get_mock_response('has_support')
        ic_data = {
            'topic': 'conversation.user.created',
            'data': {'item': {'user': {'id': 123}, 'id': 123}},
        }
        r = self.client.post('/callback/', json=ic_data)
        assert r.json() == {'message': 'Company has support'}

    def test_message_tagged_wrong_tag(self):
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


class BlogCallbackTestCase(TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    @mock.patch('tcintercom.app.views.intercom_request')
    @mock.patch('tcintercom.app.views.conf.ic_bot_id', 'TESTKEY')
    @mock.patch('tcintercom.app.views.conf.netlify_key', 'TESTKEY')
    def test_blog_sub_new_user(self, mock_request):
        mock_request.return_value = return_dict.get('blog_new_user')
        encoded_jwt = jwt.encode({'some': 'payload'}, conf.netlify_key, algorithm='HS256')

        form_data = {'data': {'email': 'test@testing.com'}}
        r = self.client.post('/blog-callback/', json=form_data, headers={'x-webhook-signature': encoded_jwt})
        assert r.json() == {'message': 'Blog subscription added to a new user'}

    @mock.patch('tcintercom.app.views.intercom_request')
    @mock.patch('tcintercom.app.views.conf.ic_bot_id', 'TESTKEY')
    @mock.patch('tcintercom.app.views.conf.netlify_key', 'TESTKEY')
    def test_blog_sub_existing_user(self, mock_request):
        mock_request.return_value = return_dict.get('blog_existing_user')
        encoded_jwt = jwt.encode({'some': 'payload'}, conf.netlify_key, algorithm='HS256')

        form_data = {'data': {'email': 'test@testing.com'}}
        r = self.client.post('/blog-callback/', json=form_data, headers={'x-webhook-signature': encoded_jwt})
        assert r.json() == {'message': 'Blog subscription added to existing user'}

    @mock.patch('tcintercom.app.views.conf.netlify_key', 'TESTKEY')
    def test_incorrect_key(self):
        encoded_jwt = jwt.encode({'some': 'payload'}, 'incorrect_key', algorithm='HS256')

        form_data = {'data': {'email': 'test@testing.com'}}
        r = self.client.post('/blog-callback/', json=form_data, headers={'x-webhook-signature': encoded_jwt})
        assert r.json() == {'error': 'Invalid Signature'}


class WorkerTestCase(TestCase):
    pass
