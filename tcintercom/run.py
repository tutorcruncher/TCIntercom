#!/usr/bin/env python3.8
import logging
import os

import click
import uvicorn
from app.logs import setup_logging
from app.main import create_app
from app.settings import Settings
from app.worker import WorkerSettings
from arq import run_worker

logger = logging.getLogger('tc-intercom.run')


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
    run_worker(WorkerSettings, redis_settings=settings.redis_settings, ctx={'settings': settings})


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
