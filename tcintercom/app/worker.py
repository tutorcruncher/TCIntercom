import logging
from io import BytesIO
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from .settings import Settings

session = requests.session()

logger = logging.getLogger('default')


class KareClient:
    token = None

    def __init__(self, settings: Settings):
        self.settings = settings
        r = session.post(
            f'{settings.kare_url}/oauth/token',
            json={
                'client_id': settings.kare_id,
                'client_secret': settings.kare_secret,
                'grant_type': 'client_credentials',
            },
            headers={'Content-Type': 'application/json'},
        )
        r.raise_for_status()
        self.token = r.json()['access_token']
        self.entries = []

    def kare_request(self, url, method='GET', data=None, files=None):
        headers = {'Authorization': f'Bearer {self.token}', 'Kare-Content-Locale': 'en-GB'}
        url = f'{self.settings.kare_url}/v2.2/{url}'
        if method == 'POST':
            if files:
                r = session.post(url, headers=headers, files=files)
            else:
                r = session.post(url, headers=headers, json=data)
        else:
            get_args = {'token': self.token, **(data or {})}
            r = session.get(url=f'{url}?{urlencode(get_args)}', headers=headers)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return r.text

    def _get_node(self, id) -> dict:
        return self.kare_request(f'kbm/nodes/{id}/')

    def _get_node_content(self, id) -> dict:
        return self.kare_request(f'kbm/nodes/{id}/content/public')

    def _update_knowledge(self, cursor=None):
        new_data: dict = self.kare_request('kbm/nodes', data={'type': 'content', 'limit': 100, 'status': 'published'})
        self.entries += new_data['entries']
        while len(new_data['entries']) == 100 and (cursor := new_data.get('next_cursor')):
            new_data = self.kare_request(
                'kbm/nodes', data={'type': 'content', 'limit': 10, 'status': 'published', 'cursor': cursor}
            )
            self.entries += new_data['entries']

    def _upload_node_content(self, id, content):
        with BytesIO() as file:
            file.write(content.encode())
            file.seek(0)
            self.kare_request(
                f'kbm/nodes/{id}/content', method='POST', data={'mime_type': 'text/html'}, files={'content': file}
            )

    def create_nodes(self, tc_data: dict):
        for url, tc_item in tc_data.items():
            create_node_data = {
                'status': 'published',
                'type': 'content',
                'title': tc_item['title'],
                'content': {
                    'source': 'tutorcruncher.com',
                    'external_id': tc_item['title'],
                    'mime_type': 'text/html',
                    'url': url,
                },
            }
            node_data: dict = self.kare_request('kbm/nodes', method='POST', data=create_node_data)
            logger.info('Creating content for %s', url)
            self._upload_node_content(node_data['id'], tc_item['content'])

    def update_nodes(self):
        tc_data = build_tc_knowledge()
        self._update_knowledge()
        for entry in self.entries:
            node_id = entry['id']
            node = self._get_node(node_id)
            if not (url := node['content'].get('url')):
                continue
            kare_content = self._get_node_content(node_id)
            tc_content = tc_data.pop(url)
            if kare_content != tc_content:
                logger.info('Updating node %s for url %s', node_id, url)
                self._upload_node_content(node_id, tc_content['content'])
        # Then we need to add the new items that are in the help site but not in Kare
        self.create_nodes(tc_data)


def parse_contents(contents):
    return (
        ''.join([str(x) for x in contents])
        .replace('src="/', 'src="https://tutorcruncher.com/')
        .replace('href="/', 'href="https://tutorcruncher.com/')
    )


def build_tc_knowledge() -> dict:
    logger.info('Downloading TC knowledge')
    r = session.get('https://tutorcruncher.com/sitemap.xml')
    r.raise_for_status()
    bs = BeautifulSoup(r.content.decode(), features='html.parser')
    urls = []
    tc_data = {}
    for url in bs.find_all('loc'):
        url = url.get_text()
        if '/help/' in url and not url.endswith('/help/') and not url.endswith('/api/'):
            urls.append(url)
    for url in urls:
        r = session.get(url)
        r.raise_for_status()
        bs = BeautifulSoup(r.content.decode(), features='html.parser')
        help_content = bs.find_all('div', class_='help-content')
        if not help_content:
            continue
        tc_data[url] = {
            'title': bs.title.get_text().replace(' • TutorCruncher', ''),
            'content': '<html><body>' + parse_contents(help_content[0].contents) + '</body></html>',
        }

    logger.info('Found %s pages of TC help knowledge', len(tc_data))
    return tc_data


def check_kare_data(ctx):
    logger.info('Callback received from a successful deploy. Updating help content')
    kare = KareClient(settings=ctx['settings'])
    kare.update_nodes()


class WorkerSettings:
    functions = [check_kare_data]
