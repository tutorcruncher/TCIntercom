import json
import logging
import os

import requests
from bs4 import BeautifulSoup

session = requests.session()

logger = logging.getLogger('tc-intercom.worker')

EXCLUDED_HELP_PAGES = ['/api/', '/tutors/', '/help-videos/', '/pdf-guides/']

auth_key = os.getenv('TC_TEST_KEY')
live_auth_key = os.getenv('LIVE_TC_KEY')

intercom_headers = {
    'Authorization': f'Bearer {auth_key}',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
}
live_intercom_headers = {
    'Authorization': f'Bearer {live_auth_key}',
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


def remove_articles():
    r = session.get(
        'https://api.intercom.io/articles',
        headers=live_intercom_headers,
    )
    x = r.json()
    for item in x['data']:
        r = session.delete(
            f"https://api.intercom.io/articles/{item['id']}",
            headers=live_intercom_headers,
        )
        r.raise_for_status()
    count = 1
    while count != x['pages']['total_pages']:
        r = session.get(x['pages']['next'], headers=live_intercom_headers)
        x = r.json()
        for item in x['data']:
            r = session.delete(
                f"https://api.intercom.io/articles/{item['id']}",
                headers=live_intercom_headers,
            )
            r.raise_for_status()
        count += 1


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
    print(x)
    count = 1
    while count != x['pages']['total_pages']:
        r = session.get(x['pages']['next'], headers=intercom_headers)
        x = r.json()
        print(x)
        count += 1


def format_name_url(name):
    name = name.translate({ord(c): " " for c in "!@#$£%^&*()[]{};:,./<>?|`~=_+"})
    name = name.replace(' ', '-')
    name = name.lower()
    if name.endswith('-'):
        return name[:-1]
    else:
        return name


def get_article_urls():
    r = session.get(
        'https://api.intercom.io/articles',
        headers=live_intercom_headers,
    )
    x = r.json()
    base_url = "https://help.tutorcruncher.com/"
    urls = {}
    for i in x['data']:
        lowered_title = format_name_url(i['title'])
        urls[i['title']] = {'new_url': f"{base_url}en/articles/{i['id']}-{lowered_title}"}
    count = 1
    while count != x['pages']['total_pages']:
        r = session.get(x['pages']['next'], headers=live_intercom_headers)
        x = r.json()
        for i in x['data']:
            lowered_title = format_name_url(i['title'])
            urls[i['title']] = {'new_url': f"{base_url}en/articles/{i['id']}-{lowered_title}"}
        count += 1
    return urls


def get_section_urls():
    r = session.get('https://api.intercom.io/help_center/sections', headers=live_intercom_headers)
    x = r.json()
    base_url = "https://help.tutorcruncher.com/"
    section_urls = {}
    count = 1
    for i in x['data']:
        lowered_name = format_name_url(i['name'])
        r = session.get(
            f"https://api.intercom.io/help_center/collections/{i['parent_id']}", headers=live_intercom_headers
        )
        y = r.json()
        lowered_parent_title = format_name_url(y['name'])
        section_urls[i['name']] = f"{base_url}en/collections/{i['parent_id']}-{lowered_parent_title}#{lowered_name}"
    while count != x['pages']['total_pages']:
        r = session.get(x['pages']['next'], headers=live_intercom_headers)
        x = r.json()
        for i in x['data']:
            lowered_name = format_name_url(i['name'])
            r = session.get(
                f"https://api.intercom.io/help_center/collections/{i['parent_id']}", headers=live_intercom_headers
            )
            y = r.json()
            lowered_parent_title = format_name_url(y['name'])
            section_urls[i['name']] = f"{base_url}en/collections/{i['parent_id']}-{lowered_parent_title}#{lowered_name}"
        count += 1
    return section_urls


def get_collection_urls():
    r = session.get('https://api.intercom.io/help_center/collections', headers=live_intercom_headers)
    x = r.json()
    base_url = "https://help.tutorcruncher.com/"
    collection_urls = {}
    count = 1
    for i in x['data']:
        lowered_name = format_name_url(i['name'])
        collection_urls[i['name']] = f"{base_url}en/collections/{i['id']}-{lowered_name}"
    while count != x['pages']['total_pages']:
        r = session.get(x['pages']['next'], headers=live_intercom_headers)
        x = r.json()
        for i in x['data']:
            lowered_name = format_name_url(i['name'])
            collection_urls[i['name']] = f"{base_url}en/collections/{i['id']}-{lowered_name}"
        count += 1
    return collection_urls


old_section_urls = {
    'Brand Management': '/business-growth/help/brand-management/',
    'Email': '/business-growth/help/email/',
    'Find A Tutor': '/business-growth/help/find-a-tutor/',
    'Sms': '/business-growth/help/sms/',
    'System Customisation': '/business-growth/help/system-customisation/',
    'Administrator': '/crm/help/administrator/',
    'Affiliate': '/crm/help/affiliate/',
    'Client': '/crm/help/client/',
    'General': '/crm/help/general/',
    'Student': '/crm/help/student/',
    'Tutor': '/crm/help/tutor/',
    'Accounting Setup And Autocharge': '/getting-paid/help/accounting-setup-and-autocharge/',
    'Ad Hoc Charges': '/getting-paid/help/ad-hoc-charges/',
    'Client Balances': '/getting-paid/help/client-balances/',
    'Direct Debit': '/getting-paid/help/direct-debit/',
    'Invoicing': '/getting-paid/help/invoicing/',
    'Paying Out To Tutors': '/getting-paid/help/paying-out-to-tutors/',
    'Payment In Advance': '/getting-paid/help/payment-in-advance/',
    'Quick Payments': '/getting-paid/help/quick-payments/',
    'Taking Debit And Credit Card Payments': '/getting-paid/help/taking-debit-and-credit-card-payments/',
    'Tutorcruncher Fees And Charges': '/getting-paid/help/tutorcruncher-fees-and-charges/',
    'Calendar': '/tutor-management-software/help/calendar/',
    'Jobs': '/tutor-management-software/help/jobs/',
    'Labels': '/tutor-management-software/help/labels/',
    'Lessons': '/tutor-management-software/help/lessons/',
    'Tutorcruncher Video': '/tutor-management-software/help/tutorcruncher-video/',
    'Whiteboard Integration': '/tutor-management-software/help/whiteboard-integration/',
    'Advanced Website Integration With Socket': '/tutoring-online/help/advanced-website-integration-with-socket/',
    'Domain Masking': '/tutoring-online/help/domain-masking/',
    'Website Integration': '/tutoring-online/help/linking-my-website-with-tutorcruncher/',
    'Outside Integrations': '/tutoring-online/help/outside-integrations/',
}
old_collection_urls = {
    'Users': '/crm/help/',
    'Scheduling': '/tutor-management-software/help/',
    'Marketing': '/business-growth/help/',
    'Payments': '/getting-paid/help/',
    'Website': '/tutoring-online/help/',
}
extra_urls = {
    '/getting-paid/help/paying-out-to-tutors/what-are-automated-payouts-with-telleroo/': 'https://help.tutorcruncher.'
    'com/',
    '/help': 'https://help.tutorcruncher.com/',
    '/help/': 'https://help.tutorcruncher.com/',
    '/help/help-videos/': 'https://help.tutorcruncher.com/en/collections/2743038-help-tutorials',
    '/help/pdf-guides/': 'https://help.tutorcruncher.com/en/articles/4838197-beginner-user-guides',
    '/help/tutors/': 'https://help.tutorcruncher.com/en/articles/4838317-tutors-guide',
    '/help/api/': 'https://help.tutorcruncher.com/en/articles/4843200-api-documentation',
}


def collect_urls():
    article_urls = get_article_urls()
    section_urls = get_section_urls()
    collection_urls = get_collection_urls()

    with open('helpdocs/wholeProf.json') as read_file:
        data = json.load(read_file)

    f = open("helpdocs/redirect_articles.txt", 'w+')

    new_json_dump = {}

    for i, j in extra_urls.items():
        f.write(i + '        ' + j + '\n')
        new_json_dump[i] = j

    for i in old_collection_urls.keys():
        if i in collection_urls.keys():
            f.write(old_collection_urls[i] + '        ' + collection_urls[i] + '\n')
            new_json_dump[old_collection_urls[i]] = collection_urls[i]

    for i in old_section_urls.keys():
        if i in section_urls.keys():
            f.write(old_section_urls[i] + '        ' + section_urls[i] + '\n')
            new_json_dump[old_section_urls[i]] = section_urls[i]

    for i, j in data.items():
        if j['title'] in article_urls.keys():
            cut_url = i.replace('https://tutorcruncher.com', '')
            article_urls[j['title']]['old_url'] = cut_url
            f.write(article_urls[j['title']]['old_url'] + '        ' + article_urls[j['title']]['new_url'] + '\n')
            new_json_dump[article_urls[j['title']]['old_url']] = article_urls[j['title']]['new_url']
    f.close()

    with open('helpdocs/helpdoc_redirects.json', 'w') as outfile:
        json.dump(new_json_dump, outfile, indent=2)


def help_collections_live():
    r = session.get('https://api.intercom.io/help_center/collections', headers=intercom_headers)
    x = r.json()
    new_collection_ids = {}
    for item in x['data']:
        r = session.post(
            'https://api.intercom.io/help_center/collections',
            json={
                'name': item['name'],
                'description': item['description'],
                'icon': item['icon'],
                'order': item['order'],
            },
            headers=live_intercom_headers,
        )
        y = r.json()
        new_collection_ids[item['id']] = y['id']
    return new_collection_ids


def help_sections_live(new_collection_ids):
    r = session.get('https://api.intercom.io/help_center/sections', headers=intercom_headers)
    x = r.json()
    new_section_ids = {}
    for item in x['data']:
        temp_id = str(item['parent_id'])
        if temp_id in new_collection_ids.keys():
            parent_id = new_collection_ids[temp_id]
            r = session.post(
                'https://api.intercom.io/help_center/sections',
                json={'name': item['name'], 'parent_id': parent_id, 'order': item['order']},
                headers=live_intercom_headers,
            )
            y = r.json()
            new_section_ids[item['id']] = y['id']

    r = session.get(x['pages']['next'], headers=intercom_headers)
    x = r.json()
    for item in x['data']:
        temp_id = str(item['parent_id'])
        if temp_id in new_collection_ids.keys():
            parent_id = new_collection_ids[temp_id]
            r = session.post(
                'https://api.intercom.io/help_center/sections',
                json={'name': item['name'], 'parent_id': parent_id, 'order': item['order']},
                headers=live_intercom_headers,
            )
            y = r.json()
            new_section_ids[item['id']] = y['id']
    return new_section_ids


def help_docs_live():
    new_collection_ids = help_collections_live()
    new_section_ids = help_sections_live(new_collection_ids)

    r = session.get('https://api.intercom.io/articles', headers=intercom_headers)
    x = r.json()
    for item in x['data']:
        temp_id = str(item['parent_id'])
        if temp_id in new_section_ids.keys():
            parent_id = new_section_ids[temp_id]
        if temp_id in new_collection_ids.keys():
            parent_id = new_collection_ids[temp_id]
        description = ''
        if temp_id in ['2743038', '2743053', '2743054']:
            description = item['description']
        r = session.post(
            'https://api.intercom.io/articles',
            json={
                'title': item['title'],
                'description': description,
                'author_id': 4241273,
                'parent_id': parent_id,
                'parent_type': item['parent_type'],
                'body': item['body'],
                'state': 'published',
            },
            headers=live_intercom_headers,
        )
    count = 1
    while count != x['pages']['total_pages']:
        r = session.get(x['pages']['next'], headers=intercom_headers)
        x = r.json()
        for item in x['data']:
            temp_id = str(item['parent_id'])
            if temp_id in new_section_ids.keys():
                parent_id = new_section_ids[temp_id]
            if temp_id in new_collection_ids.keys():
                parent_id = new_collection_ids[temp_id]
            description = ''
            if temp_id in ['2743038', '2743053', '2743054']:
                description = item['description']
            r = session.post(
                'https://api.intercom.io/articles',
                json={
                    'title': item['title'],
                    'description': description,
                    'author_id': 4241273,
                    'parent_id': parent_id,
                    'parent_type': item['parent_type'],
                    'body': item['body'],
                    'state': 'published',
                },
                headers=live_intercom_headers,
            )
        count += 1


if __name__ == '__main__':
    collect_urls()
