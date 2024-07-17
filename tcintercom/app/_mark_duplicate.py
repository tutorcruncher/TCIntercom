import logging
import time

import requests

from .settings import Settings
from .views import intercom_request

session = requests.Session()
logger = logging.getLogger('tc-intercom.views')

conf = Settings()


def list_all_contacts() -> list:
    """
    Makes a request to intercom and returns a list of all contacts that were active in the last 91 days
    """
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


def get_relevant_accounts(recently_active: list) -> tuple[list, list]:
    """
    Filters through and assigns contacts as either duplicate or not
    """
    keep_contacts = {}
    mark_dupe_contacts = []

    for contact in recently_active:
        email = contact['email']
        if email not in keep_contacts.keys():
            # If contact email has not been seen before, add it to the dictionary of unique contacts
            keep_contacts[email] = contact
        elif (
            email in keep_contacts.keys()
            and keep_contacts[email]['custom_attributes'].get('is_duplicate')
            and contact['custom_attributes'].get('is_duplicate') is False
        ):
            # If more recent is not duplicate and original is
            mark_dupe_contacts.append(keep_contacts[email])
            keep_contacts[email] = contact
        elif (
            email in keep_contacts.keys()
            and contact.get('session_count')
            and keep_contacts[email].get('session_count') < contact['session_count']
        ):
            # If this new contact has a larger session count replace the existing contact and add it to duplicates
            mark_dupe_contacts.append(keep_contacts[email])
            keep_contacts[email] = contact
        elif (
            email in keep_contacts.keys()
            and keep_contacts[email]['last_seen_at']
            and keep_contacts[email]['last_seen_at'] < contact['last_seen_at']
        ):
            # Take the most recently active contact to be the unique contact
            mark_dupe_contacts.append(keep_contacts[email])
            keep_contacts[email] = contact
        elif (
            email in keep_contacts.keys()
            and not keep_contacts[email]['last_seen_at']
            and keep_contacts[email]['created_at'] > contact['created_at']
        ):
            mark_dupe_contacts.append(keep_contacts[email])
            keep_contacts[email] = contact
        else:
            mark_dupe_contacts.append(contact)

    # Only need to unmark the ones that are not already marked as duplicates
    mark_not_dupe_contacts = [v for k, v in keep_contacts.items() if v['custom_attributes'].get('is_duplicate')]
    # Only need to mark the ones that are not already marked as duplicates
    mark_dupe_contacts = [
        contact for contact in mark_dupe_contacts if not contact['custom_attributes'].get('is_duplicate')
    ]
    return mark_dupe_contacts, mark_not_dupe_contacts


def update_duplicate_custom_attribute(contacts_to_update: list, mark_duplicate: bool):
    """
    Takes a list of contacts and depending on what mark duplicate is, marks them as a duplicate or not a duplicate.
    """
    print(contacts_to_update)
    for contact in contacts_to_update:
        if contact['custom_attributes'].get('is_duplicate') != mark_duplicate:
            url = f'/contacts/{contact["id"]}'
            data = {
                'role': contact['role'],
                'email': contact['email'],
                'custom_attributes': {'is_duplicate': mark_duplicate},
            }
            intercom_request(url, method='PUT', data=data)
