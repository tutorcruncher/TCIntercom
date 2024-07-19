from arq import cron

from .._mark_duplicate import get_relevant_accounts, list_all_contacts, update_duplicate_custom_attribute


async def update_duplicate_contacts(ctx):
    """
    Runs every hour, and updates intercom with the relevant duplicate/not duplicate contacts
    """
    contacts = list_all_contacts()
    mark_duplicate, mark_not_duplicate = get_relevant_accounts(contacts)
    update_duplicate_custom_attribute(contacts_to_update=mark_duplicate, mark_duplicate=True)
    update_duplicate_custom_attribute(contacts_to_update=mark_not_duplicate, mark_duplicate=False)


class WorkerSettings:
    cron_jobs = [cron(update_duplicate_contacts, hour=1, timeout=600)]
