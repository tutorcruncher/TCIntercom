from arq import cron

from .._mark_duplicate import (
    get_relevant_accounts,
    list_all_contacts,
    mark_duplicates_in_intercom,
    mark_not_dupicates_update_intercom,
)


async def update_duplicate_contacts(ctx):
    """
    Runs every hour, and updates intercom with the relevant duplicate/not duplicate contacts
    """
    contacts = list_all_contacts()
    mark_duplicate, mark_not_dupe = get_relevant_accounts(contacts)
    mark_duplicates_in_intercom(mark_duplicate)
    mark_not_dupicates_update_intercom(mark_not_dupe)


class WorkerSettings:
    cron_jobs = [cron(update_duplicate_contacts, hour=1, timeout=600)]
