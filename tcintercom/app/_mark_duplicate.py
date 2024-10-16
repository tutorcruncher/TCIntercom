import logging
import time
from typing import Optional

import logfire

from tcintercom.app.views import intercom_request

logger = logging.getLogger('tc-intercom.mark_duplicate')


class DuplicateContactChecks:
    def __init__(self, keep_contact: Optional[dict], contact: dict):
        self.keep_contact = keep_contact
        self.contact = contact
        self.email = contact.get('email')
        self.last_seen_at = contact.get('last_seen_at')
        self.is_duplicate = contact.get('custom_attributes', {}).get('is_duplicate')

    def check_new_contact(self) -> bool:
        """
        Checks if this is the first time seeing the contact, add it to the dictionary of unique contacts
        """
        return not bool(self.keep_contact)

    def check_more_recent_not_duplicate(self) -> bool:
        """
        Checks if the contact in keep_contacts is a duplicate but the most recent contact we're processing is not
        """
        return (
            self.keep_contact and self.keep_contact['custom_attributes'].get('is_duplicate') and not self.is_duplicate
        )

    def check_more_recently_active(self) -> bool:
        """
        Checks if the new contact is more recently active than the contact in keep_contacts
        """
        return (
            self.keep_contact
            and self.keep_contact.get('last_seen_at')
            and self.last_seen_at
            and self.keep_contact['last_seen_at'] < self.last_seen_at
        )

    def check_created_at(self) -> bool:
        """
        Checks if the new contact was created more recently than the contact in keep_contacts
        """
        return (
            self.keep_contact
            and not self.keep_contact.get('last_seen_at')
            and self.keep_contact['created_at'] > self.contact['created_at']
        )


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
        keep_contact = keep_contacts.get(email)
        contact_checks = DuplicateContactChecks(contact=contact, keep_contact=keep_contact)
        if contact_checks.check_new_contact():
            keep_contacts[email] = contact
        elif contact_checks.check_more_recent_not_duplicate():
            mark_dupe_contacts.append(keep_contacts[email])
            keep_contacts[email] = contact
        elif contact_checks.check_more_recently_active():
            mark_dupe_contacts.append(keep_contacts[email])
            keep_contacts[email] = contact
        elif contact_checks.check_created_at():
            mark_dupe_contacts.append(keep_contacts[email])
            keep_contacts[email] = contact
        else:
            mark_dupe_contacts.append(contact)

    keep_con_list = [v for k, v in keep_contacts.items()]
    return mark_dupe_contacts, keep_con_list


def update_duplicate_custom_attribute(contacts_to_update: list, mark_duplicate: bool):
    """
    Takes a list of contacts and depending on what mark duplicate is, marks them as a duplicate or not a duplicate.
    """
    updated = 0
    for contact in contacts_to_update:
        if contact['custom_attributes'].get('is_duplicate') != mark_duplicate:
            url = f'/contacts/{contact["id"]}'
            data = {
                'role': contact['role'],
                'email': contact['email'],
                'custom_attributes': {'is_duplicate': mark_duplicate},
            }
            intercom_request(url, method='PUT', data=data)
            updated += 1
    logfire.info(
        'Updated {updated} contacts to {duplicate}',
        updated=updated,
        duplicate='duplicate' if mark_duplicate else 'not duplicate',
    )
