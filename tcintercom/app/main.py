import os

import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from starlette.applications import Starlette
from starlette.routing import Route

from .kare import callback as kare_callback
from .views import index, callback, raise_error


def create_app():
    starlette_app = Starlette(
        debug=bool(os.getenv('DEBUG')),
        routes=[
            Route('/', index),
            Route('/callback/', callback, methods=['POST']),
            Route('/deploy-hook/', kare_callback),
            Route('/error/', raise_error),
        ],
    )

    if dsn := os.getenv('RAVEN_DSN'):
        sentry_sdk.init(dsn=dsn)
        starlette_app.add_middleware(SentryAsgiMiddleware)
    return starlette_app
