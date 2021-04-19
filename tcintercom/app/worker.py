import logging

import requests
from arq import cron
from bs4 import BeautifulSoup

from .mark_duplicate import run

session = requests.session()

logger = logging.getLogger('tc-intercom.worker')


def parse_contents(contents):
    return (
        ''.join([str(x) for x in contents])
        .replace('src="/', 'src="https://tutorcruncher.com/')
        .replace('href="/', 'href="https://tutorcruncher.com/')
    )


EXCLUDED_HELP_PAGES = ['/help/', '/api/', '/tutors/', '/help-videos/', '/pdf-guides/']


def build_tc_knowledge() -> dict:
    logger.info('Downloading TC knowledge')
    r = session.get('https://tutorcruncher.com/sitemap.xml')
    r.raise_for_status()
    bs = BeautifulSoup(r.content.decode(), features='html.parser')
    urls = []
    tc_data = {}
    for url in bs.find_all('loc'):
        url = url.get_text()
        if '/help/' in url and not any(url.endswith(page_url) for page_url in EXCLUDED_HELP_PAGES):
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


class WorkerSettings:
    cron_jobs = [cron(run, hour=1, timeout=600)]
