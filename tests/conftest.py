import pytest
from starlette.testclient import TestClient

from tcintercom.app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())
