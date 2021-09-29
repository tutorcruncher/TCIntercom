import logging
import time
from typing import Optional

import requests

from .settings import Settings

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


async def run(ctx):
    contacts = list_all_contacts()
    mark_duplicate, mark_not_dupe = get_relevant_accounts(contacts)
    update_intercom(mark_duplicate)
    mark_not_dupe_update_intercom(mark_not_dupe)


# Returns a list of all contacts that were active in the last 91 days
def list_all_contacts():
    response = intercom_request('/contacts?per_page=150')
    contacts = response['data']
    # - 91 days
    active_time = int(time.time()) - 7862400
    # number seen in last 90 days/ 10
    while not (response['data'][0].get('last_seen_at') and response['data'][0].get('last_seen_at') < active_time):
        response = intercom_request(
            f'/contacts?per_page=150&starting_after={response["pages"]["next"]["starting_after"]}'
        )
        contacts += response['data']

    return contacts


# Filters through and assigns contacts as either duplicate or not
def get_relevant_accounts(recently_active: list):
    keep_contacts = {}
    mark_dupe_contacts = []

    for contact in recently_active:
        if contact['email'] not in keep_contacts.keys():
            # If contact email has not been seen before, add it to the dictionary of unique contacts
            keep_contacts[contact['email']] = contact
        elif (
            contact['email'] in keep_contacts.keys()
            and keep_contacts[contact['email']].get('is_duplicate')
            and contact.get('is_duplicate') is False
        ):
            # If more recent is not duplicate and original is
            mark_dupe_contacts.append(keep_contacts[contact['email']])
            keep_contacts[contact['email']] = contact
        elif (
            contact['email'] in keep_contacts.keys()
            and contact.get('session_count')
            and keep_contacts[contact['email']].get('session_count') < contact['session_count']
        ):
            # If this new contact has a larger session count replace the existing contact and add it to duplicates
            mark_dupe_contacts.append(keep_contacts[contact['email']])
            keep_contacts[contact['email']] = contact
        elif (
            contact['email'] in keep_contacts.keys()
            and keep_contacts[contact['email']]['last_seen_at']
            and keep_contacts[contact['email']]['last_seen_at'] < contact['last_seen_at']
        ):
            # Take the most recently active contact to be the unique contact
            mark_dupe_contacts.append(keep_contacts[contact['email']])
            keep_contacts[contact['email']] = contact
        elif (
            contact['email'] in keep_contacts.keys()
            and not keep_contacts[contact['email']]['last_seen_at']
            and keep_contacts[contact['email']]['created_at'] > contact['created_at']
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


def mark_not_dupe_update_intercom(mark_duplicate: list):
    for contact in mark_duplicate:
        if contact['custom_attributes'].get('is_duplicate') is not False:
            url = f'/contacts/{contact["id"]}'
            data = {'role': contact['role'], 'email': contact['email'], 'custom_attributes': {'is_duplicate': False}}
            intercom_request(url, method='PUT', data=data)
