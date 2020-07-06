import logging
import os
import tempfile
from io import BytesIO

import requests
from bs4 import BeautifulSoup

KARE_SECRET = os.getenv('KARE_SECRET')
KARE_ID = os.getenv('KARE_ID')
KARE_URL = os.getenv('KARE_URL', 'https://api.eu.karehq.com')
TC_BASE_URL = os.getenv('TC_HELP_URL', 'http://localhost:8000')


session = requests.session()

logger = logging.getLogger('default')


class KareClient:
    token = None

    def __init__(self):
        r = session.post(f'{KARE_URL}/oauth/token', json={
            'client_id': KARE_ID, 'client_secret': KARE_SECRET, 'grant_type': 'client_credentials'
        }, headers={'Content-Type': 'application/json'})
        r.raise_for_status()
        self.token = r.json()['access_token']
        self.entries = []

    def kare_request(self, url, method='GET', data=None, files=None):
        headers = {
            'Authorization': f'Bearer {self.token}', 'Content-Type': 'application/json', 'Kare-Content-Locale': 'en-GB'
        }
        if files:
            headers.pop('Content-Type')
            r = session.post(url=f'{KARE_URL}/v2.2/{url}', headers=headers, files=files)
        elif method == 'POST':
            r = session.post(url=f'{KARE_URL}/v2.2/{url}', headers=headers, json=data)
        else:
            r = session.get(url=f'{KARE_URL}/v2.2/{url}?token={self.token}', headers=headers)
        try:
            r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            return r.text

    def get_node(self, id):
        return self.kare_request(f'kbm/nodes/{id}/content/raw')

    def get_knowledge(self, cursor=None):
        if cursor:
            data = self.kare_request(
                'kbm/nodes', data={'type': 'content', 'limit': 10, 'status': 'published', 'cursor': cursor}
            )
        else:
            data = self.kare_request('kbm/nodes', data={'type': 'content', 'limit': 10, 'status': 'published'})
        self.entries += data['entries']
        # if cursor := data.get('next_cursor'):
        #     self.get_knowledge(cursor)

    def create_nodes(self, tc_knowledge: iter):
        for item in tc_knowledge:
            create_node_data = {
                'status': 'published',
                'type': 'content',
                'title': item['title'],
                'content': {
                    'source': item['url'], 'external_id': item['title'], 'mime_type': 'text/html'
                }
            }
            node_id = self.kare_request('kbm/nodes', method='POST', data=create_node_data)['id']
            with BytesIO() as file:
                file.write(item['content'].encode())
                file.seek(0)
                logger.info(f'Creating file {item["url"]}')
                self.kare_request(f'kbm/nodes/{node_id}/content', method='POST', files={'content': file})


def parse_contents(contents):
    return (
        ''.join([str(x) for x in contents])
        .replace('src="/', f'src="https://tutorcruncher.com/')
        .replace('href="/', f'href="https://tutorcruncher.com/')
    )


def build_tc_knowledge():
    r = session.get('https://tutorcruncher.com/sitemap.xml')
    r.raise_for_status()
    bs = BeautifulSoup(r.content.decode(), features='html.parser')
    urls = []
    for url in bs.find_all('loc'):
        url = url.get_text()
        if '/help/' in url and not url.endswith('/help/'):
            urls.append(url)
    for url in urls[:5]:
        r = session.get(url)
        r.raise_for_status()
        bs = BeautifulSoup(r.content.decode(), features='html.parser')
        help_content = bs.find_all('div', class_='help-content')
        if not help_content:
            continue
        yield {
            'url': url,
            'title': f"Content from {url.replace(TC_BASE_URL, '')}",
            'content': parse_contents(help_content[0].contents),
        }


# def callback(request: requests.Request):
#     logger.info('Callback received from a successful deploy. Updating help content')
#     kare = KareClient()
#     kare.get_knowledge()
#     tc_knowledge = build_tc_knowledge()


if __name__ == '__main__':
    tc_knowledge = build_tc_knowledge()
    kare = KareClient()
    kare.create_nodes(tc_knowledge)
    # kare.update_nodes(tc_knowledge)
