import logging
import re

from github import Github
from github.Issue import Issue
from github.Repository import Repository

from tcsupport.app.settings import Settings

conf = Settings()
logger = logging.getLogger('tc-support.help-feedback.github')

ISSUE_BODY = """\
_Link_: {page_url}
_Likes_: {likes}
_Dislikes_: {dislikes}
"""
ISSUE_COMMENT = """_Message_: {message}"""


def get_attr(term, body):
    try:
        return re.search(term, body).group(1).strip()
    except (AttributeError, TypeError) as e:
        raise RuntimeError(f'Cannot find or parse term "{term}" in issue. ({e})')


class FeedbackData:
    LIKE = 'like'
    DISLIKE = 'dislike'
    errors = {}
    required_fields = ('page_title', 'page_url', 'page_category', 'type')

    def __init__(self, data):
        self.page_title = data.get('page_title')
        self.page_url = data.get('page_url')
        self.page_category = data.get('page_category')
        self.type = data.get('type')
        self.message = data.get('message')

    @property
    def is_like(self):
        return self.type == self.LIKE

    def is_valid(self):
        required_fields_data = [(field, getattr(self, field)) for field in self.required_fields]
        if all(bool(value) for _, value in required_fields_data):
            if self.type not in [self.LIKE, self.DISLIKE]:
                self.errors.update({'incorrect_value': 'type value was not "like" or "dislike".'})
                return False
            elif not self.is_like and not self.message:
                self.errors.update({'missing_fields': 'message was missing in the data.'})
                return False
            else:
                return True
        else:
            missing_fields = (field for field, data in required_fields_data if not data)
            missing_fields_str = ', '.join(missing_fields)
            self.errors.update({'missing_fields': f'{missing_fields_str} was missing in the data.'})
            return False


def add_feedback_message(fd: FeedbackData, issue: Issue):
    comment = ISSUE_COMMENT.format(message=fd.message)
    issue.create_comment(comment)


def create_new_issue(fd: FeedbackData, repo: Repository):
    likes = 1 if fd.is_like else 0
    dislikes = 0 if fd.is_like else 1
    issue_body = ISSUE_BODY.format(page_url=fd.page_url, likes=likes, dislikes=dislikes)
    issue = repo.create_issue(fd.page_title, body=issue_body, labels=[fd.page_category])
    if not fd.is_like:
        add_feedback_message(fd, issue)
    logger.info(f'Created issue (#{issue.number}) with feedback')


def update_issue(fd: FeedbackData, issue: Issue):
    likes = int(get_attr('_Likes_:(.*)', issue.body))
    dislikes = int(get_attr('_Dislikes_:(.*)', issue.body))
    if fd.is_like:
        likes += 1
    else:
        dislikes += 1
        add_feedback_message(fd, issue)
    issue_body = ISSUE_BODY.format(page_url=fd.page_url, likes=likes, dislikes=dislikes)
    issue.edit(body=issue_body)
    logger.info(f'Updated issue (#{issue.number}) with feedback')


async def process_feedback(feedback_data: dict):
    fd = FeedbackData(feedback_data)
    if fd.is_valid():
        gh = Github(conf.gh_token)
        help_article_repo = gh.get_repo('tutorcruncher/help-feedback')
        issues = list(help_article_repo.get_issues(labels=[fd.page_category]))
        issue_updated = False
        if issues:
            print(issues)
            for issue in issues:
                if fd.page_title == issue.title:
                    update_issue(fd, issue)
                    issue_updated = True
                    break
        if not issue_updated:
            create_new_issue(fd, help_article_repo)
    else:
        logger.error(f'Feedback data validation error: {fd.errors}')
