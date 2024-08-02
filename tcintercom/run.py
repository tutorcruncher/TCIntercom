import logging
import os
import sys
from pathlib import Path
from typing import Any

import logfire
import uvicorn
from arq.typing import WorkerSettingsType
from arq.worker import Worker, get_kwargs

project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from tcintercom.app.logs import logfire_setup, setup_logging
from tcintercom.app.main import create_app
from tcintercom.app.routers.worker import WorkerSettings
from tcintercom.app.settings import Settings

logger = logging.getLogger('tc-intercom.run')


class TCIntercomWorker(Worker):
    async def run_job(self, job_id: str, score: int) -> None:
        """
        Overrides the run_job method from arq Worker class to use logfire to log the jobs.
        """
        func = job_id.split(':')[1]
        with logfire.span(func):
            await super().run_job(job_id, score)


def create_worker(settings_cls: WorkerSettingsType, **kwargs: Any) -> TCIntercomWorker:
    """
    Looks at arq create_worker function and does the same, except it uses the TCIntercomWorker class which allows us
    to use logfire to log the jobs.
    """
    worker = TCIntercomWorker(**{**get_kwargs(settings_cls), **kwargs})
    worker.run()
    return worker


def web():
    setup_logging()
    port = int(os.getenv('PORT', 8000))
    logger.info('starting uvicorn on port %d', port)
    uvicorn.run(create_app(), host='0.0.0.0', port=port)


def worker():
    """
    Run the worker
    """
    setup_logging()
    logger.info('waiting for redis to come up...')
    settings = Settings()
    logfire_setup('worker')
    create_worker(WorkerSettings, redis_settings=settings.redis_settings, ctx={'settings': settings})


def main():
    command = sys.argv[1]
    if command == 'web':
        web()
    elif command == 'worker':
        worker()
    else:
        logger.error(f'Invalid command {command}')


if __name__ == '__main__':
    main()  # pragma: no cover
