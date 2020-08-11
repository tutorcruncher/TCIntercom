import os

import sentry_sdk
import uvicorn as uvicorn
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
from starlette.applications import Starlette
from starlette.routing import Route

from .app.views import index, raise_error, callback
from .app.kare import callback as kare_callback

app = Starlette(
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
    app.add_middleware(SentryAsgiMiddleware)

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', 8000)))
