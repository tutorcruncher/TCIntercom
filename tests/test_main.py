from requests import RequestException

from app.main import session


def test_index(client):
    r = client.get('/')
    assert r.content.decode() == "TutorCruncher's service for managing Intercom is Online"


def test_no_action_needed(client):
    data = {'data': {'item': {'Foo': 'Bar'}}}
    r = client.get('/callback/', json=data)
    assert r.json() == {'message': 'No action required'}


def test_callback_invalid_json(client):
    r = client.get('/callback/', data='{invalid}')
    assert r.status_code == 400


def get_mock_response(test, error=False):
    class MockResponse:
        def __init__(self, method, url, *args, **kwargs):
            self.url = url

        def json(self):
            if test == 'no_companies':
                return {'companies': {'type': 'list', 'data': []}}
            elif test == 'no_support':
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

        def raise_for_status(self):
            if error:
                raise RequestException('Bad request')

    return MockResponse


def test_conv_created_user_no_companies(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('no_companies'))

    ic_data = {
        'topic': 'conversation.user.created',
        'data': {'item': {'user': {'user_id': 123}, 'id': 123}},
    }
    r = client.get('/callback/', json=ic_data)
    assert r.json() == {'message': 'User has no companies'}


def test_conv_created_no_support(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('no_support'))
    ic_data = {
        'topic': 'conversation.user.created',
        'data': {'item': {'user': {'user_id': 123}, 'id': 123}},
    }
    r = client.get('/callback/', json=ic_data)
    assert r.json() == {'message': 'Reply successfully posted'}


def test_conv_created_has_support(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('has_support'))
    ic_data = {
        'topic': 'conversation.user.created',
        'data': {'item': {'user': {'user_id': 123}, 'id': 123}},
    }
    r = client.get('/callback/', json=ic_data)
    assert r.json() == {'message': 'Company has support'}


def test_message_tagged(client):
    ic_data = {
        'topic': 'conversation_part.tag.created',
        'data': {
            'item': {
                'tags_added': [{'name': 'Update help article'}],
                'conversation_parts': [{'body': 'A new issue please'}],
            }
        },
    }
    r = client.get('/callback/', json=ic_data)
    assert r.json() == {'message': 'Issue created with tags'}


def test_message_tagged_wrong_tag(client):
    ic_data = {
        'topic': 'conversation_part.tag.created',
        'data': {
            'item': {'tags_added': [{'name': 'Not right tag'}], 'conversation_parts': [{'body': 'A new issue please'}]}
        },
    }
    r = client.get('/callback/', json=ic_data)
    assert r.json() == {'message': 'No action required'}
