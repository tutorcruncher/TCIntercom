import os

import sentry_sdk
from arq import create_pool
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from starlette.applications import Starlette
from starlette.routing import Route

from tcsupport.app.settings import Settings
from tcsupport.app.views import index, raise_error
from tcsupport.help_feedback.views import submit_feedback
from tcsupport.tc_intercom.views import callback, deploy_hook


async def lifespan(app):
    app.settings = Settings()
    app.redis = await create_pool(app.settings.redis_settings)
    yield


def create_app():
    app = Starlette(
        debug=bool(os.getenv('DEBUG')),
        routes=[
            Route('/', index),
            Route('/error/', raise_error),
            Route('/callback/', callback, methods=['POST']),
            Route('/deploy-hook/', deploy_hook),
            Route('/submit-feedback/', submit_feedback, methods=['POST']),
        ],
        lifespan=lifespan,
    )

    if dsn := os.getenv('RAVEN_DSN'):
        sentry_sdk.init(dsn=dsn)
        app.add_middleware(SentryAsgiMiddleware)
    return app
