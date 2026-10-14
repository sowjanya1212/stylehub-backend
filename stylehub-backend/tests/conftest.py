import os

# Must be set BEFORE the app is imported.
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only"
os.environ["DATABASE_URL"] = "sqlite:///./test_stylehub.db"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_PUBLISHABLE_KEY"] = "pk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
os.environ["SEED_PRODUCTS"] = "true"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:  # runs lifespan: create tables + seed
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def auth_headers(client):
    def _make(email="user@example.com", password="Passw0rdX"):
        client.post(
            "/auth/register",
            json={"email": email, "full_name": "Test User", "password": password},
        )
        r = client.post("/auth/login", json={"email": email, "password": password})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _make
