from typing import List

from tcsupport.help_feedback.github import ISSUE_BODY


def create_fake_github(repo_name, create_issues: List[dict] = None):  # noqa: C901
    class MockIssue:
        title = None
        body = None
        number = None
        comments = []
        labels = []

        def __init__(self, title, body, number, labels):
            self.title = title
            self.body = body
            self.number = number
            self.labels = labels or []

        def create_comment(self, message, *args, **kwargs):
            self.comments.append(message)

        def edit(self, body, *args, **kwargs):
            repo = gh.get_repo(repo_name, do_create_issue=False)
            for index, issue in enumerate(repo.issues):
                if issue.number == self.number:
                    self.body = body
                    repo.issues[index] = self

    class MockRepo:
        issues: List[MockIssue] = []

        def create_issue(self, title, body, labels=None, *args, **kwargs):
            new_issue = MockIssue(title=title, body=body, number=len(self.issues), labels=labels)
            self.issues.append(new_issue)
            return new_issue

        def get_issues(self, labels=None, *args, **kwargs):
            if not labels:
                return self.issues
            for issue in self.issues:
                if any(label in labels for label in issue.labels):
                    yield issue

    class MockGithub:
        repo: MockRepo = None

        def get_repo(self, name, do_create_issue=True, *args, **kwargs):
            if not self.repo:
                self.repo = MockRepo()
            if repo_name == 'tutorcruncher/tutorcruncher.com':
                return self.repo
            elif repo_name == 'tutorcruncher/help-feedback':
                if create_issues and do_create_issue:
                    for issue in create_issues:
                        issue_count = len(self.repo.issues)
                        title = issue.get('title', f'Issue Title {issue_count}')
                        body = issue.get('body', ISSUE_BODY.format(page_url='http://example.com', likes=1, dislikes=0))
                        labels = issue.get('labels', [])
                        new_issue = self.repo.create_issue(title=title, body=body, labels=labels)
                        comments = issue.get('comments', [])
                        for comment in comments:
                            new_issue.create_comment(comment)
                return self.repo

    gh = MockGithub()
    return gh
