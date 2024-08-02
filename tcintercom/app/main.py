from contextlib import asynccontextmanager

import logfire
import sentry_sdk
from arq import create_pool
from fastapi import FastAPI
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from .logs import logfire_setup
from .routers.views import views_router
from .settings import app_settings


@asynccontextmanager
async def lifespan(app):
    app.settings = app_settings
    app.redis = await create_pool(app.settings.redis_settings)
    yield


def create_app():
    app = FastAPI(lifespan=lifespan)
    app.include_router(views_router)

    if app_settings.logfire_token:
        logfire_setup('web')
        logfire.instrument_fastapi(app)

    if dsn := app_settings.raven_dsn:
        sentry_sdk.init(dsn=dsn)
        app.add_middleware(SentryAsgiMiddleware)
    return app
