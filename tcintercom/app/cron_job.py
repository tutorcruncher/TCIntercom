import logging
import sys
from pathlib import Path

import logfire

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))
from tcintercom.app._mark_duplicate import get_relevant_accounts, list_all_contacts, update_duplicate_custom_attribute
from tcintercom.app.logs import logfire_setup

logger = logging.getLogger('tc-intercom.cron_job')


def update_duplicate_contacts():
    """
    Updates intercom with the relevant duplicate/not duplicate contacts
    """
    logfire_setup(service_name='cron-job', console=True)
    with logfire.span('Updating duplicate/not duplicate contacts.'):
        contacts = list_all_contacts()
        logfire.info('Found {contacts} contacts.', contacts=len(contacts))
        mark_duplicate, mark_not_duplicate = get_relevant_accounts(contacts)
        logfire.info(
            'Updating {duplicates} duplicate contacts and {not_duplicates} not duplicate contacts.',
            duplicates=len(mark_duplicate),
            not_duplicates=len(mark_not_duplicate),
        )
        update_duplicate_custom_attribute(contacts_to_update=mark_duplicate, mark_duplicate=True)
        update_duplicate_custom_attribute(contacts_to_update=mark_not_duplicate, mark_duplicate=False)


if __name__ == '__main__':
    update_duplicate_contacts()  # pragma: no cover
