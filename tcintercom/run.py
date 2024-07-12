#!/usr/bin/env python3.9
import logging
import os

import uvicorn
from app.main import create_app
from app.routers.worker import WorkerSettings
from app.settings import Settings
from arq import run_worker

logger = logging.getLogger('tc-intercom.run')


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
