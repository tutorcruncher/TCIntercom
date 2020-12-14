import asyncio

import pytest
from starlette.testclient import TestClient

from tcsupport.app.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def loop():
    return asyncio.get_event_loop()
