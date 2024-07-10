from fastapi_utilities import repeat_at

from tcintercom.app2.mark_duplicate import (
    get_relevant_accounts,
    list_all_contacts,
    mark_duplicates_in_intercom,
    mark_not_dupicates_update_intercom,
)


@repeat_at(cron='0 * * * *')
async def run(ctx):
    """
    Runs every hour, and updates intercom with the relevant duplicate/not duplicate contacts
    """
    contacts = list_all_contacts()
    mark_duplicate, mark_not_dupe = get_relevant_accounts(contacts)
    mark_duplicates_in_intercom(mark_duplicate)
    mark_not_dupicates_update_intercom(mark_not_dupe)
