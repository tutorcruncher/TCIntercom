import contextlib
import os

import sentry_sdk
from arq import create_pool
from fastapi import FastAPI
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from .routers.views import views_router
from .settings import Settings


@contextlib.asynccontextmanager
async def lifespan(app):
    app.settings = Settings()
    app.redis = await create_pool(app.settings.redis_settings)
    yield


def create_app():
    app = FastAPI(debug=bool(os.getenv('DEBUG')), lifespan=lifespan)
    app.include_router(views_router)

    if dsn := os.getenv('RAVEN_DSN'):
        sentry_sdk.init(dsn=dsn)
        app.add_middleware(SentryAsgiMiddleware)

    return app
