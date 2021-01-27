import json
import logging
import os

import requests
from bs4 import BeautifulSoup

session = requests.session()

logger = logging.getLogger('tc-intercom.worker')


EXCLUDED_HELP_PAGES = ['/api/', '/tutors/', '/help-videos/', '/pdf-guides/']

auth_key = os.getenv('TC_TEST_KEY')
intercom_headers = {
    'Authorization': f'Bearer {auth_key}',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
}
list_of_pages_of_error = []

online_collections = {
    'crm': {
        'name': 'Users',
        'description': 'Find information about your different Administrators,'
        'Tutors, Clients, Students and Affiliates here.',
    },
    'tutor-management-software': {
        'name': 'Scheduling',
        'description': 'This section contains information on creating Jobs,'
        'planning lessons and anything else calendar related.',
    },
    'business-growth': {
        'name': 'Marketing',
        'description': 'Here you can find out about the tools TutorCruncher gives you to market to your clients.',
    },
    'getting-paid': {
        'name': 'Payments',
        'description': 'Guides on taking payments from clients via Direct Debit,'
        'ACH and Credit/Debit cards are all available here.',
    },
    'tutoring-online': {
        'name': 'Website',
        'description': 'Learn about the tools TutorCruncher gives you that integrate into your own website here.',
    },
}


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
            'content': parse_contents(help_content[0].contents),
        }

    logger.info('Found %s pages of TC help knowledge', len(tc_data))
    return tc_data


def parse_contents(contents):
    return (
        ''.join([str(x) for x in contents])
        .replace('src="/', 'src="https://tutorcruncher.com/')
        .replace('href="/', 'href="https://tutorcruncher.com/')
    )


def build_collections(collections):
    for i, j in collections.items():
        r = session.post(
            'https://api.intercom.io/help_center/collections',
            json={
                'name': j['name'],
                'description': j['description'],
            },
            headers=intercom_headers,
        )
        r.raise_for_status()
        r_data = r.json()
        j['collection_id'] = r_data['id']
    return collections


def format_section_name(name):
    x = name.replace('-', ' ')
    formatted_name = x.title()
    return formatted_name


def build_section(name, parent_id):
    name = format_section_name(name)
    r = session.post(
        'https://api.intercom.io/help_center/sections',
        json={
            'name': name,
            'author_id': 4569924,
            'parent_id': parent_id,
        },
        headers=intercom_headers,
    )
    r.raise_for_status()
    r_data = r.json()
    return r_data['id']


def build_data(all_data, collections):
    collection_data = build_collections(collections)

    with open(all_data) as read_file:
        data = json.load(read_file)

    sections_data = {}
    for i, j in data.items():
        remove_base_url = i.split('https://tutorcruncher.com/', 1)
        collection_split = remove_base_url[1].split('/help/', 1)
        section_split = collection_split[1].split('/', 1)

        if not section_split[0] in sections_data.keys():
            collection_id = collection_data[collection_split[0]]['collection_id']
            sections_data[section_split[0]] = build_section(section_split[0], collection_id)

        parent_id = sections_data[section_split[0]]

        j['parent_id'] = parent_id
        build_article(j)


def build_article(data):
    split = data['content'].split('\n<div class="help-feedback">', 1)
    data['content'] = f'{split[0]}</body></html>'

    r = session.post(
        'https://api.intercom.io/articles',
        json={
            'title': data['title'],
            'body': data['content'],
            'author_id': 4569924,
            'parent_id': data['parent_id'],
            'parent_type': 'section',
            'state': 'draft',
        },
        headers=intercom_headers,
    )
    if r.status_code != 200:
        print(data['title'])
        list_of_pages_of_error.append(data['title'])


# Deletes all articles on Intercom app
def remove_articles():
    r = session.get(
        'https://api.intercom.io/articles',
        headers=intercom_headers,
    )
    x = r.json()
    while x['total_count'] > 0:
        for item in x['data']:
            r = session.delete(
                f"https://api.intercom.io/articles/{item['id']}",
                headers=intercom_headers,
            )
            r.raise_for_status()


def single_article(file, parent_id):
    with open(file) as read_file:
        data = json.load(read_file)
    data['parent_id'] = parent_id
    build_article(data)


def print_pages():
    r = session.get(
        'https://api.intercom.io/help_center/sections',
        headers=intercom_headers,
    )
    x = r.json()
    count = 1
    while count != x['pages']['total_pages']:
        r = session.get(x['pages']['next'], headers=intercom_headers)
        x = r.json()
        print(x)
        count += 1


def get_article_urls():
    r = session.get(
        'https://api.intercom.io/articles',
        headers=intercom_headers,
    )
    x = r.json()
    count = 0
    urls = {}
    while count != x['pages']['total_pages']:
        count += 1
        for i in x['data']:
            urls[i['title']] = f"https://app.intercom.com/a/apps/u6r3i73k/articles/articles/{i['id']}/show"
            print(urls[i['title']])
        if count != x['pages']['total_pages']:
            r = session.get(x['pages']['next'], headers=intercom_headers)
            x = r.json()


# The following pages error because of nested lists but have worked around
# ['Guide to Writing in Markdown and Editing…', 'Creating and Editing Students',
# 'Subscriptions', 'Integrating Your Calendar Externally']

# So far 1 other page has always errored due to timeout but can be found and added on its own easily enoughs
# Most commonly 'Client Pipeline'

if __name__ == '__main__':
    get_article_urls()
# tc_data = build_tc_knowledge()            # Gets data from TC help doc pages
# build_data(tc_data, online_collections)   # Starts a run of all data and pre-defined collections
# print(list_of_pages_of_error)             # Prints pages that errored
# single_article('29.json', 2740108)        # Used for posting single pages from file and parent_id
# get_pages_object()                        # Prints all sections to console, section
# id is needed as parent_id for articles
