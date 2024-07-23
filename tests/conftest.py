import pytest

from tcintercom.app.main import app_settings


@pytest.fixture(scope='module', autouse=True)
def initialize_tests(request):
    app_settings.testing = True
    return app_settings
