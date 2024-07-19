import logging
import logging.config

import logfire
from logfire import PydanticPlugin


def logfire_setup(service_name: str):
    from .main import app_settings

    if not app_settings.testing and bool(app_settings.logfire_token):
        logfire.configure(
            service_name=service_name,
            send_to_logfire=True,
            token=app_settings.logfire_token,
            pydantic_plugin=PydanticPlugin(record='all'),
            console=False,
        )


def setup_logging(verbose: bool = False):
    """
    setup logging config by updating the arq logging config
    """
    log_level = 'DEBUG' if verbose else 'INFO'
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {'tc-intercom': {'format': '%(levelname)s %(name)s %(message)s'}},
        'handlers': {
            'tc-intercom': {'level': log_level, 'class': 'logging.StreamHandler', 'formatter': 'tc-intercom'},
            'sentry': {'level': 'WARNING', 'class': 'sentry_sdk.integrations.logging.SentryHandler'},
        },
        'loggers': {
            'tc-intercom': {'handlers': ['tc-intercom', 'sentry'], 'level': log_level},
            'uvicorn.error': {'handlers': ['sentry'], 'level': 'ERROR'},
            'arq': {'handlers': ['tc-intercom', 'sentry'], 'level': log_level},
        },
    }
    logging.config.dictConfig(config)
