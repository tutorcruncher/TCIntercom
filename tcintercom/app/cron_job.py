import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from tcintercom.app._mark_duplicate import get_relevant_accounts, list_all_contacts, update_duplicate_custom_attribute


def update_duplicate_contacts():
    """
    Updates intercom with the relevant duplicate/not duplicate contacts
    """
    contacts = list_all_contacts()
    mark_duplicate, mark_not_duplicate = get_relevant_accounts(contacts)
    update_duplicate_custom_attribute(contacts_to_update=mark_duplicate, mark_duplicate=True)
    update_duplicate_custom_attribute(contacts_to_update=mark_not_duplicate, mark_duplicate=False)


if __name__ == '__main__':
    update_duplicate_contacts()
