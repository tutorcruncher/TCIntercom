import pytest
from starlette.testclient import TestClient

from tcintercom.main import app


@pytest.fixture
def client():
    return TestClient(app)
