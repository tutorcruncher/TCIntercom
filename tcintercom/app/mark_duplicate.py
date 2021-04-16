import logging
from typing import Optional
import time
import requests
import schedule

from settings import Settings

session = requests.Session()
logger = logging.getLogger('tc-intercom.views')

conf = Settings()


def intercom_request(url: str, data: Optional[dict] = None, method: str = 'GET'):
    data = data or {}
    headers = {
        'Authorization': 'Bearer ' + conf.ic_token,
        'Accept': 'application/json',
    }
    if not (method == 'POST' and not conf.ic_token):
        r = session.request(method, 'https://api.intercom.io' + url, json=data, headers=headers)
        r.raise_for_status()
        return r.json()


def run():
    contacts = list_all_contacts()
    mark_duplicate, mark_not_dupe = get_relevant_accounts(contacts)
    update_intercom(mark_duplicate)
    mark_not_dupe_update_intercom(mark_not_dupe)
    return 'success'


def mark_not_dupe_update_intercom(mark_duplicate: list):
    for contact in mark_duplicate:
        if contact['custom_attributes'].get('is_duplicate') is not False:
            url = f'/contacts/{contact["id"]}'
            data = {'role': contact['role'], 'email': contact['email'], 'custom_attributes': {'is_duplicate': False}}
            intercom_request(url, method='PUT', data=data)


def list_all_contacts():
    response = intercom_request('/contacts?per_page=150')
    contacts = response['data']
    # - 91 days
    active_time = int(time.time()) - 7862400
    # number seen in last 90 days/ 10
    for i in range(1, response['pages']['total_pages']):
        response = intercom_request(
            f'/contacts?per_page=150&starting_after={response["pages"]["next"]["starting_after"]}'
        )
        contacts += response['data']

        if response['data'][0].get('last_seen_at') and response['data'][0].get('last_seen_at') < active_time:
            break

    return contacts


def get_relevant_accounts(recently_active: list):
    keep_contacts = {}
    mark_dupe_contacts = []

    for contact in recently_active:
        if contact['email'] not in keep_contacts.keys():
            keep_contacts[contact['email']] = contact
        elif (
            contact['email'] in keep_contacts.keys()
            and contact.get('session_count')
            and keep_contacts[contact['email']].get('session_count') < contact['session_count']
        ):
            mark_dupe_contacts.append(keep_contacts[contact['email']])
            keep_contacts[contact['email']] = contact
        elif (
            contact['email'] in keep_contacts.keys()
            and keep_contacts[contact['email']]['last_seen_at']
            and keep_contacts[contact['email']]['last_seen_at'] < contact['last_seen_at']
        ):
            mark_dupe_contacts.append(keep_contacts[contact['email']])
            keep_contacts[contact['email']] = contact
        elif (
            contact['email'] in keep_contacts.keys()
            and not keep_contacts[contact['email']]['last_seen_at']
            and keep_contacts[contact['email']]['created_at'] < contact['created_at']
        ):
            mark_dupe_contacts.append(keep_contacts[contact['email']])
            keep_contacts[contact['email']] = contact
        else:
            mark_dupe_contacts.append(contact)

    keep_con_list = [v for k, v in keep_contacts.items()]

    return mark_dupe_contacts, keep_con_list


def update_intercom(mark_duplicate: list):
    for contact in mark_duplicate:
        if contact['custom_attributes'].get('is_duplicate') is not True:
            url = f'/contacts/{contact["id"]}'
            data = {'role': contact['role'], 'email': contact['email'], 'custom_attributes': {'is_duplicate': True}}
            intercom_request(url, method='PUT', data=data)


if __name__ == '__main__':
    schedule.every().friday.at("23:00").do(run())
