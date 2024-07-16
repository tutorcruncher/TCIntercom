import pytest_asyncio
from starlette.testclient import TestClient

from tcintercom.app.main import create_app


@pytest_asyncio.fixture
def client():
    with TestClient(create_app()) as client:
        yield client
