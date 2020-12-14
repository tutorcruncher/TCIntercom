import logging
import logging.config


def setup_logging(verbose: bool = False):
    """
    setup logging config by updating the arq logging config
    """
    log_level = 'DEBUG' if verbose else 'INFO'
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {'tc-support': {'format': '%(levelname)s %(name)s %(message)s'}},
        'handlers': {
            'tc-support': {'level': log_level, 'class': 'logging.StreamHandler', 'formatter': 'tc-support'},
            'sentry': {'level': 'WARNING', 'class': 'sentry_sdk.integrations.logging.SentryHandler'},
        },
        'loggers': {
            'tc-support': {'handlers': ['tc-intercom', 'sentry'], 'level': log_level},
            'uvicorn.error': {'handlers': ['sentry'], 'level': 'ERROR'},
            'arq': {'handlers': ['tc-intercom', 'sentry'], 'level': log_level},
        },
    }
    logging.config.dictConfig(config)
