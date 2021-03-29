from datetime import datetime, timedelta

from requests import RequestException

from tcintercom.app.views import session


def test_index(client):
    r = client.get('/')
    assert r.content.decode() == "TutorCruncher's service for managing Intercom is Online"


def test_no_action_needed(client):
    data = {'data': {'item': {'id': 500}}}
    r = client.post('/callback/', json=data)
    assert r.json() == {'message': 'No action required'}


def test_callback_invalid_json(client):
    r = client.post('/callback/', data='{invalid}')
    assert r.status_code == 400


def get_mock_response(test, error=False):
    class MockResponse:
        def __init__(self, method, url, *args, **kwargs):
            self.url = url

        def json(self):
            now = datetime.now()
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
            elif test == 'close_after_snooze' and 'close' not in self.url:
                return {
                    'id': 123,
                    'statistics': {
                        'last_contact_reply_at': round((now - timedelta(days=8)).timestamp()),
                        'last_admin_reply_at': round((now - timedelta(days=9)).timestamp()),
                    },
                }
            elif test == 'dont_close_after_snooze' and 'close' not in self.url:
                return {
                    'id': 123,
                    'statistics': {
                        'last_contact_reply_at': round((now - timedelta(days=5)).timestamp()),
                        'last_admin_reply_at': round((now - timedelta(days=9)).timestamp()),
                    },
                }
            elif test in return_dict:
                return return_dict[test]

        def raise_for_status(self):
            if error:
                raise RequestException('Bad request')

    return MockResponse


return_dict = {
    'no_dupe_email': {
        'item': {'role': 'user', 'id': 123, 'email': 'test1@test', 'custom_attributes': {}},
        'total_count': 0,
    },
    'dupe_email': {
        'item': {'role': 'user', 'id': 123, 'email': 'test@test', 'custom_attributes': {}},
        'total_count': 1,
    },
    'no_companies': {'companies': {'type': 'list', 'data': []}},
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


def test_message_tagged_new_article(client):
    ic_data = {
        'topic': 'conversation_part.tag.created',
        'data': {
            'item': {
                'id': 123,
                'tags_added': {'type': 'tag.list', 'tags': [{'name': 'Update help article'}]},
                'conversation_parts': {
                    'type': 'conversation_part.list',
                    'conversation_parts': [{'body': 'A new issue please'}],
                },
            }
        },
    }
    r = client.post('/callback/', json=ic_data)
    assert r.json() == {'message': 'Issue created with tags'}


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


def test_message_tagged_snooze(client):
    ic_data = {
        'topic': 'conversation_part.tag.created',
        'data': {
            'item': {
                'id': 123,
                'assignee': {'type': 'admin', 'id': None},
                'tags_added': {'type': 'tag.list', 'tags': [{'name': 'Snooze then close'}]},
                'conversation_parts': {
                    'type': 'conversation_part.list',
                    'conversation_parts': [{'body': 'A new issue please'}],
                },
            }
        },
    }
    r = client.post('/callback/', json=ic_data)
    assert r.json() == {'message': 'Conversation snoozed while waiting for reply'}


def test_message_unsnooze_close(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('close_after_snooze'))
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
    assert r.json() == {'message': 'Conversation closed because of inactivity'}


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


def test_new_user_no_dupe_email(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('no_dupe_email'))

    ic_data = {
        'topic': 'user.created',
        'data': {'item': {'role': 'user', 'id': 1234, 'email': 'test2@test.com', 'custom_attributes': {}}},
    }
    r = client.post('/callback/', json=ic_data)
    assert r.json() == {'message': 'Email is not a duplicate.'}


def test_new_user_no_email(client):
    ic_data = {
        'topic': 'user.created',
        'data': {'item': {'role': 'user', 'id': 123, 'email': None, 'custom_attributes': {}}},
    }
    r = client.post('/callback/', json=ic_data)
    assert r.json() == {'message': 'No email provided.'}


def test_new_user_dupe_email(monkeypatch, client):
    monkeypatch.setattr(session, 'request', get_mock_response('dupe_email'))

    ic_data = {
        'topic': 'user.created',
        'data': {'item': {'role': 'user', 'id': 123, 'email': 'test@test', 'custom_attributes': {}}},
    }
    r = client.post('/callback/', json=ic_data)
    assert r.json() == {'message': 'Email is a duplicate.'}
