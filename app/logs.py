import logging.config
import os


def setup_logging():
    """
    setup logging config by updating the arq logging config
    """
    log_level = 'DEBUG' if os.getenv('DEBUG') else 'INFO'
    raven_dsn = os.getenv('RAVEN_DSN')
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {'default': {'format': '%(levelname)s %(name)s %(message)s'}},
        'handlers': {
            'tcfat': {'level': log_level, 'class': 'logging.StreamHandler', 'formatter': 'default'},
            'sentry': {
                'level': 'WARNING',
                'class': 'raven.handlers.logging.SentryHandler',
                'dsn': raven_dsn,
                'release': os.getenv('COMMIT', None),
            },
        },
        'loggers': {
            'tcfat': {'handlers': ['default', 'sentry'], 'level': log_level},
            'gunicorn.error': {'handlers': ['sentry'], 'level': 'ERROR'},
            'arq': {'handlers': ['default', 'sentry'], 'level': log_level},
        },
    }
    logging.config.dictConfig(config)
