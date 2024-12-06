from contextlib import asynccontextmanager

import logfire
import sentry_sdk
from arq import create_pool
from fastapi import FastAPI
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from starlette.middleware.cors import CORSMiddleware

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

    allowed_origins = ['https://tutorcruncher.com', 'http://localhost:8000', 'https://tutorcruncher.vercel.app']
    if app_settings.dev_mode:
        allowed_origins = ['*']
    app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=['*'], allow_headers=['*'])

    if app_settings.logfire_token:
        logfire_setup('web')
        logfire.instrument_fastapi(app)

    if dsn := app_settings.raven_dsn:
        sentry_sdk.init(dsn=dsn)
        app.add_middleware(SentryAsgiMiddleware)
    return app
