from unittest import mock

from tcsupport.help_feedback.github import ISSUE_BODY, process_feedback
from tests.mock_github import create_fake_github


@mock.patch('tcsupport.help_feedback.github.Github')
def test_get_submit_feedback(mock_github, client):
    mock_github.return_value = create_fake_github('tutorcruncher/help-feedback')
    r = client.get('/submit-feedback/')
    assert r.status_code == 405


@mock.patch('tcsupport.help_feedback.github.Github')
def test_correct_origin(mock_github, client):
    mock_github.return_value = create_fake_github('tutorcruncher/help-feedback')
    r = client.post('/submit-feedback/', headers={'Origin': 'https://tutorcruncher.com'})
    assert r.status_code == 400


@mock.patch('tcsupport.help_feedback.github.Github')
def test_no_origin(mock_github, client):
    mock_github.return_value = create_fake_github('tutorcruncher/help-feedback')
    r = client.post('/submit-feedback/')
    assert r.status_code == 403
    assert r.json() == {'error': 'The current Origin, None, does not match the allowed domains'}


@mock.patch('tcsupport.help_feedback.github.Github')
def test_incorrect_origin(mock_github, client):
    mock_github.return_value = create_fake_github('tutorcruncher/help-feedback')
    r = client.post('/submit-feedback/', headers={'Origin': 'http://example.com'})
    assert r.status_code == 403
    assert r.json() == {'error': 'The current Origin, http://example.com, does not match the allowed domains'}


@mock.patch('tcsupport.help_feedback.github.Github')
def test_invalid_json(mock_github, client):
    mock_github.return_value = create_fake_github('tutorcruncher/help-feedback')
    r = client.post('/submit-feedback/', headers={'Origin': 'https://tutorcruncher.com'})
    assert r.status_code == 400
    assert r.json() == {'error': 'Invalid JSON'}


@mock.patch('tcsupport.help_feedback.github.Github')
def test_correct_json(mock_github, client):
    mock_github.return_value = create_fake_github('tutorcruncher/help-feedback')
    r = client.post('/submit-feedback/', json={'test': 'test'}, headers={'Origin': 'https://tutorcruncher.com'})
    assert r.status_code == 200
    assert r.content.decode() == 'OK'


@mock.patch('tcsupport.help_feedback.github.logger.error')
@mock.patch('tcsupport.help_feedback.github.Github')
def test_missing_required_data(mock_github, mock_logger, loop):
    mock_github.return_value = create_fake_github('tutorcruncher/help-feedback')
    loop.run_until_complete(process_feedback(feedback_data={'test': 'test'}))
    assert mock_logger.called
    assert 'page_title, page_url, page_category, type was missing in the data' in mock_logger.call_args[0][0]


@mock.patch('tcsupport.help_feedback.github.logger.error')
@mock.patch('tcsupport.help_feedback.github.Github')
def test_missing_some_required_data(mock_github, mock_logger, loop):
    mock_github.return_value = create_fake_github('tutorcruncher/help-feedback')
    data = {
        'page_url': 'http://example.com',
        'page_category': 'testing',
        'type': 'like',
    }
    loop.run_until_complete(process_feedback(feedback_data=data))
    assert mock_logger.called
    assert 'page_title was missing in the data' in mock_logger.call_args[0][0]


@mock.patch('tcsupport.help_feedback.github.logger.error')
@mock.patch('tcsupport.help_feedback.github.Github')
def test_incorrect_type_value(mock_github, mock_logger, loop):
    mock_github.return_value = create_fake_github('tutorcruncher/help-feedback')
    data = {
        'page_title': 'Test Help Article',
        'page_url': 'http://example.com',
        'page_category': 'testing',
        'type': 'just wrong',
    }
    loop.run_until_complete(process_feedback(feedback_data=data))
    assert mock_logger.called
    assert 'type value was not "like" or "dislike"' in mock_logger.call_args[0][0]


@mock.patch('tcsupport.help_feedback.github.logger.error')
@mock.patch('tcsupport.help_feedback.github.Github')
def test_missing_message_for_dislike_type(mock_github, mock_logger, loop):
    mock_github.return_value = create_fake_github('tutorcruncher/help-feedback')
    data = {
        'page_title': 'Test Help Article',
        'page_url': 'http://example.com',
        'page_category': 'testing',
        'type': 'dislike',
    }
    loop.run_until_complete(process_feedback(feedback_data=data))
    assert mock_logger.called
    assert 'message was missing in the data' in mock_logger.call_args[0][0]


@mock.patch('tcsupport.help_feedback.github.logger.info')
@mock.patch('tcsupport.help_feedback.github.Github')
def test_create_new_issue_for_type_like(mock_github, mock_logger, loop):
    fake_github = create_fake_github('tutorcruncher/help-feedback')
    mock_github.return_value = fake_github
    data = {
        'page_title': 'Test Help Article',
        'page_url': 'http://example.com',
        'page_category': 'testing',
        'type': 'like',
    }
    loop.run_until_complete(process_feedback(feedback_data=data))
    assert len(fake_github.repo.issues) == 1
    assert len(fake_github.repo.issues[0].comments) == 0
    assert '_Likes_: 1' in fake_github.repo.issues[0].body
    assert '_Dislikes_: 0' in fake_github.repo.issues[0].body
    assert mock_logger.called
    assert 'Created issue (#0) with feedback' in mock_logger.call_args[0][0]


@mock.patch('tcsupport.help_feedback.github.logger.info')
@mock.patch('tcsupport.help_feedback.github.Github')
def test_create_new_issue_for_type_dislike(mock_github, mock_logger, loop):
    fake_github = create_fake_github('tutorcruncher/help-feedback')
    mock_github.return_value = fake_github
    data = {
        'page_title': 'Test Help Article',
        'page_url': 'http://example.com',
        'page_category': 'testing',
        'type': 'dislike',
        'message': 'This help page is awful!',
    }
    loop.run_until_complete(process_feedback(feedback_data=data))
    assert len(fake_github.repo.issues) == 1
    assert len(fake_github.repo.issues[0].comments) == 1
    assert '_Likes_: 0' in fake_github.repo.issues[0].body
    assert '_Dislikes_: 1' in fake_github.repo.issues[0].body
    assert mock_logger.called
    assert 'Created issue (#0) with feedback' in mock_logger.call_args[0][0]


@mock.patch('tcsupport.help_feedback.github.logger.info')
@mock.patch('tcsupport.help_feedback.github.Github')
def test_create_new_issue_same_category_different_title(mock_github, mock_logger, loop):
    fake_github = create_fake_github('tutorcruncher/help-feedback', create_issues=[{'labels': ['testing']}])
    mock_github.return_value = fake_github
    data = {
        'page_title': 'Test Help Article',
        'page_url': 'http://example.com',
        'page_category': 'testing',
        'type': 'like',
    }
    loop.run_until_complete(process_feedback(feedback_data=data))
    assert len(fake_github.repo.issues) == 2
    assert mock_logger.called
    assert 'Created issue (#1) with feedback' in mock_logger.call_args[0][0]


@mock.patch('tcsupport.help_feedback.github.logger.info')
@mock.patch('tcsupport.help_feedback.github.Github')
def test_create_new_issue_same_category_same_title(mock_github, mock_logger, loop):
    fake_github = create_fake_github(
        'tutorcruncher/help-feedback', create_issues=[{'title': 'Test Help Article', 'labels': ['testing']}]
    )
    mock_github.return_value = fake_github
    data = {
        'page_title': 'Test Help Article',
        'page_url': 'http://example.com',
        'page_category': 'testing',
        'type': 'like',
    }
    loop.run_until_complete(process_feedback(feedback_data=data))
    assert len(fake_github.repo.issues) == 1
    assert mock_logger.called
    assert 'Updated issue (#0) with feedback' in mock_logger.call_args[0][0]


@mock.patch('tcsupport.help_feedback.github.logger.info')
@mock.patch('tcsupport.help_feedback.github.Github')
def test_create_new_issue_different_category_same_title(mock_github, mock_logger, loop):
    fake_github = create_fake_github(
        'tutorcruncher/help-feedback', create_issues=[{'title': 'Test Help Article', 'labels': ['testing']}]
    )
    mock_github.return_value = fake_github
    data = {'page_title': 'Test Help Article', 'page_url': 'http://example.com', 'page_category': 'xxx', 'type': 'like'}
    loop.run_until_complete(process_feedback(feedback_data=data))
    assert len(fake_github.repo.issues) == 2
    assert mock_logger.called
    assert 'Created issue (#1) with feedback' in mock_logger.call_args[0][0]


@mock.patch('tcsupport.help_feedback.github.logger.info')
@mock.patch('tcsupport.help_feedback.github.Github')
def test_update_new_issue_for_type_dislike(mock_github, mock_logger, loop):
    body = ISSUE_BODY.format(page_url='http://example.com', likes=0, dislikes=1)
    fake_github = create_fake_github(
        'tutorcruncher/help-feedback',
        create_issues=[
            {'title': 'Test Help Article', 'labels': ['testing'], 'comments': ['this page is great!'], 'body': body}
        ],
    )
    mock_github.return_value = fake_github
    data = {
        'page_title': 'Test Help Article',
        'page_url': 'http://example.com',
        'page_category': 'testing',
        'type': 'dislike',
        'message': 'This help page is awful!',
    }
    loop.run_until_complete(process_feedback(feedback_data=data))
    print([i.title for i in fake_github.repo.issues])
    assert len(fake_github.repo.issues) == 1
    assert len(fake_github.repo.issues[0].comments) == 2
    assert '_Likes_: 0' in fake_github.repo.issues[0].body
    assert '_Dislikes_: 2' in fake_github.repo.issues[0].body
    assert mock_logger.called
    assert 'Updated issue (#0) with feedback' in mock_logger.call_args[0][0]
