import asyncio

import pytest
from starlette.testclient import TestClient

from tcintercom.app.main import create_app


@pytest.fixture
def client():
    loop = asyncio.get_event_loop()
    app = loop.run_until_complete(create_app())
    yield TestClient(app)
