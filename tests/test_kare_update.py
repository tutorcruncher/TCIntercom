import asyncio
import copy
import re

from tcintercom.app.settings import Settings
from tcintercom.app.worker import check_kare_data, session

FOO_CONTENT = (
    '<html><body>'
    '<h2 id="foo-question-1">How do I foo?</h2>'
    '<p>This is how you foo</p>'
    '<h2 id="foo-question-2">Where do I foo?</h2>'
    '<p>This is where you foo</p>'
    '</body></html>'
)
BAR_CONTENT = (
    '<html><body>'
    '<h2 id="bar-question-1">How do I bar?</h2>'
    '<p>This is how you bar</p>'
    '<h2 id="bar-question-2">Where do I bar?</h2>'
    '<p>This is where you bar</p>'
    '</body></html>'
)
NEW_CONTENT = (
    '<html><body>'
    '<h2 id="new-question-1">How do I new?</h2>'
    '<p>This is how you new</p>'
    '<h2 id="new-question-2">Where do I new?</h2>'
    '<a src="/content_link/">This is where you new</a>'
    '</body></html>'
)
FAKE_KARE_DB = {
    'entries': [
        {
            'id': 'node_foo',
            'content': {'url': 'https://tutorcruncher.com/crm/help/general/foo/', 'content': FOO_CONTENT},
        },
        {
            'id': 'node_bar',
            'content': {'url': 'https://tutorcruncher.com/crm/help/general/bar/', 'content': BAR_CONTENT},
        },
    ],
}


def make_tc_content(s, t):
    return s.replace(
        '<html>', f'<html><head><title>{t} Questions • TutorCruncher</title></head><div class="help-content"'
    ).replace('</body', '</div></body')


def mock_responses(fake_kare_db, error=False, method='GET', full=False):  # noqa C901
    class MockResponse:
        def __init__(self, url, json=None, files=None, *args, **kwargs):
            self.url = url
            self.content = self.set_content().encode()
            self.method = method
            self.json_data = json
            self.files = files

        def raise_for_status(self):
            if error:
                raise RuntimeError

        def set_content(self):
            if 'sitemap.xml' in self.url:
                return (
                    '<urlset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><script/>'
                    '<url><loc>https://tutorcruncher.com/404.html</loc><lastmod>2020-07-15</lastmod></url>'
                    '<url><loc>https://tutorcruncher.com/crm/help/general/foo/</loc></url>'
                    '<url><loc>https://tutorcruncher.com/crm/help/general/bar/</loc></url>'
                    '<url><loc>https://tutorcruncher.com/crm/help/general/new/</loc></url>'
                    '<url><loc>https://tutorcruncher.com/crm/help/general/empty/</loc></url>'
                    '</urlset>'
                )
            elif self.url == 'https://tutorcruncher.com/crm/help/general/foo/' and full:
                return make_tc_content(FOO_CONTENT, 'Foo')
            elif self.url == 'https://tutorcruncher.com/crm/help/general/bar/' and full:
                return make_tc_content(BAR_CONTENT, 'Bar')
            elif self.url == 'https://tutorcruncher.com/crm/help/general/new/' and full:
                return make_tc_content(NEW_CONTENT, 'New')
            elif self.url == 'https://tutorcruncher.com/crm/help/general/new/':
                return '<html><body></body></html>'
            return ''

        def json(self):
            if self.url.endswith('/oauth/token'):
                return {'access_token': '123ABC'}
            elif '/kbm/nodes?token' in self.url:
                if self.method == 'GET':
                    return {'entries': fake_kare_db['entries']}
            elif self.url.endswith('kbm/nodes'):
                # Creating a new node
                fake_kare_db['entries'].append({'id': 'node_new', **self.json_data})
                return {'id': 'node_new'}
            elif 'kbm/nodes/node_' in self.url:
                node_id = re.search(r'nodes/(node_.*?)/', self.url).group(1)
                node = next(n for n in fake_kare_db['entries'] if n['id'] == node_id)
                if self.url.endswith('content/public'):
                    if node_id == 'node_bar':
                        return node['content']['content'].replace('This is where you bar', 'This is not where you bar')
                    return node['content']['content']
                elif self.method == 'GET':
                    return node
                else:
                    # Updating knowledge
                    new_content = self.files['content'].read()
                    node['content']['content'] = new_content.decode()

    return MockResponse


def test_run_update(monkeypatch, client):
    """
    Should create one node with NEW_CONTENT, update node with BAR_CONTENT, and not do anything to FOO_CONTENT
    """
    fake_kare_db = copy.deepcopy(FAKE_KARE_DB)
    monkeypatch.setattr(session, 'get', mock_responses(fake_kare_db, full=True))
    monkeypatch.setattr(session, 'post', mock_responses(fake_kare_db, method='POST', full=True))
    assert len(fake_kare_db['entries']) == 2
    r = client.get('/deploy-hook/')
    assert r.status_code == 200
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check_kare_data({'settings': Settings()}))
    assert len(fake_kare_db['entries']) == 3
    foo_node = next(n for n in fake_kare_db['entries'] if n['id'] == 'node_foo')
    bar_node = next(n for n in fake_kare_db['entries'] if n['id'] == 'node_bar')
    new_node = next(n for n in fake_kare_db['entries'] if n['id'] == 'node_new')
    assert foo_node['content']['content'] == FOO_CONTENT.format('')
    assert bar_node['content']['content'] == BAR_CONTENT.format('')
    assert new_node['content']['content'] == NEW_CONTENT.replace(
        'src="/content_link/"', 'src="https://tutorcruncher.com/content_link/"'
    ).format('')
    assert new_node['status'] == 'published'
    assert new_node['title'] == 'New Questions'
    assert new_node['content']['url'] == 'https://tutorcruncher.com/crm/help/general/new/'


def test_page_no_content(client, monkeypatch):
    fake_kare_db = {'entries': []}
    monkeypatch.setattr(session, 'get', mock_responses(fake_kare_db))
    monkeypatch.setattr(session, 'post', mock_responses(fake_kare_db, method='POST'))
    r = client.get('/deploy-hook/')
    assert r.status_code == 200
    assert len(fake_kare_db['entries']) == 0
