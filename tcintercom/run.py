#!/usr/bin/env python3.11
import logging
import os
from typing import Any

import click
import logfire
import uvicorn
from arq.typing import WorkerSettingsType
from arq.worker import Worker, get_kwargs

from .app.logs import logfire_setup, setup_logging
from .app.main import create_app
from .app.routers.worker import WorkerSettings
from .app.settings import Settings

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


@click.group()
@click.option('-v', '--verbose', is_flag=True)
def cli(verbose):
    setup_logging(verbose)


def web():
    port = int(os.getenv('PORT', 8000))
    logger.info('starting uvicorn on port %d', port)
    uvicorn.run(create_app(), host='0.0.0.0', port=port)


def worker():
    """
    Run the worker
    """
    logger.info('waiting for redis to come up...')
    settings = Settings()
    logfire_setup('worker')
    create_worker(WorkerSettings, redis_settings=settings.redis_settings, ctx={'settings': settings})


@cli.command()
def auto():
    port_env = os.getenv('PORT')
    dyno_env = os.getenv('DYNO')
    if dyno_env:
        logger.info('using environment variable DYNO=%r to infer command', dyno_env)
        if dyno_env.lower().startswith('web'):
            web()
        else:
            worker()
    elif port_env and port_env.isdigit():
        logger.info('using environment variable PORT=%s to infer command as web', port_env)
        web()
    else:
        logger.info('no environment variable found to infer command, assuming worker')
        worker()


if __name__ == '__main__':
    cli()
