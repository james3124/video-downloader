import pytest
from app import create_app


@pytest.fixture
def app():
    application = create_app(testing=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()
