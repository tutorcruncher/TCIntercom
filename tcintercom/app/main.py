import os

import sentry_sdk
from arq import create_pool
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from starlette.applications import Starlette
from starlette.routing import Route

from .settings import Settings
from .views import callback, deploy_hook, index, raise_error


async def create_app():
    app = Starlette(
        debug=bool(os.getenv('DEBUG')),
        routes=[
            Route('/', index),
            Route('/callback/', callback, methods=['POST']),
            Route('/deploy-hook/', deploy_hook),
            Route('/error/', raise_error),
        ],
    )

    if dsn := os.getenv('RAVEN_DSN'):
        sentry_sdk.init(dsn=dsn)
        app.add_middleware(SentryAsgiMiddleware)
    app.settings = Settings()
    app.redis = await create_pool(app.settings.redis_settings)
    return app
