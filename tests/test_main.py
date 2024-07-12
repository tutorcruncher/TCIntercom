import jwt
from requests import RequestException

from tcintercom.app.views import conf, session


def test_index(client):
    r = client.get('/')
    assert r.content.decode() == '{"message":"TutorCruncher\'s service for managing Intercom is Online"}'


def test_robots(client):
    r = client.get('/robots.txt')
    assert r.status_code == 200
    assert b'User-agent: *' in r.content


def test_no_action_needed(client):
    data = {'data': {'item': {'id': 500}}}
    r = client.post('/callback/', json=data)
    assert r.json() == {'message': 'No action required'}


def test_callback_invalid_json(client):
    r = client.post('/callback/', content='{invalid}')
    assert r.status_code == 400


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


def test_conv_created_user_no_companies(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('no_companies'))

    ic_data = {
        'topic': 'conversation.user.created',
        'data': {'item': {'user': {'id': 123}, 'id': 123}},
    }
    r = client.post('/callback/', json=ic_data)
    assert r.json() == {'message': 'User has no companies'}


def test_conv_created_no_support(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('no_support'))
    ic_data = {
        'topic': 'conversation.user.created',
        'data': {'item': {'user': {'id': 123}, 'id': 123}},
    }
    r = client.post('/callback/', json=ic_data)
    assert r.json() == {'message': 'Reply successfully posted'}


def test_conv_created_has_support(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('has_support'))
    ic_data = {
        'topic': 'conversation.user.created',
        'data': {'item': {'user': {'id': 123}, 'id': 123}},
    }
    r = client.post('/callback/', json=ic_data)
    assert r.json() == {'message': 'Company has support'}


def test_message_tagged_wrong_tag(client):
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
    r = client.post('/callback/', json=ic_data)
    assert r.json() == {'message': 'No action required'}


def test_message_unsnooze_dont_close(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('dont_close_after_snooze'))
    ic_data = {
        'topic': 'conversation.admin.unsnoozed',
        'data': {
            'item': {
                'id': 123,
                'assignee': {'type': 'admin', 'id': None},
                'tags': {'type': 'tag.list', 'tags': [{'name': 'Snooze then close'}]},
                'conversation_parts': {
                    'type': 'conversation_part.list',
                    'conversation_parts': [{'body': 'A new issue please'}],
                },
            }
        },
    }
    r = client.post('/callback/', json=ic_data)
    assert r.json() == {'message': 'No action required'}


def test_blog_sub_new_user(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('blog_new_user'))
    monkeypatch.setattr(conf, 'ic_token', 'TESTKEY')
    monkeypatch.setattr(conf, 'netlify_key', 'TESTKEY')
    encoded_jwt = jwt.encode({"some": "payload"}, conf.netlify_key, algorithm="HS256")

    form_data = {'data': {'email': 'test@testing.com'}}
    r = client.post('/blog-callback/', json=form_data, headers={'x-webhook-signature': encoded_jwt})
    assert r.json() == {'message': 'Blog subscription added to a new user'}


def test_blog_sub_existing_user(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('blog_existing_user'))
    monkeypatch.setattr(conf, 'ic_token', 'TESTKEY')
    monkeypatch.setattr(conf, 'netlify_key', 'TESTKEY')
    encoded_jwt = jwt.encode({"some": "payload"}, conf.netlify_key, algorithm="HS256")

    form_data = {'data': {'email': 'test@testing.com'}}
    r = client.post('/blog-callback/', json=form_data, headers={'x-webhook-signature': encoded_jwt})
    assert r.json() == {'message': 'Blog subscription added to existing user'}


def test_incorrect_key(monkeypatch, client):
    monkeypatch.setattr(conf, 'netlify_key', 'TESTKEY')
    encoded_jwt = jwt.encode({"some": "payload"}, 'incorrect_key', algorithm="HS256")

    form_data = {'data': {'email': 'test@testing.com'}}
    r = client.post('/blog-callback/', json=form_data, headers={'x-webhook-signature': encoded_jwt})
    assert r.json() == {'error': 'Invalid Signature'}
