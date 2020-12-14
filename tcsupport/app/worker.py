import logging

from tcsupport.help_feedback.github import process_feedback
from tcsupport.tc_intercom.kare import check_kare_data

logger = logging.getLogger('tc-support.worker')


class WorkerSettings:
    functions = [check_kare_data, process_feedback]
