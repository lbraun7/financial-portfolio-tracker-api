"""Health endpoint tests."""

from app.main import create_app
from fastapi.testclient import TestClient


def test_healthcheck_returns_ok() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_request_id_is_preserved() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "trace-123"})

    assert response.headers["X-Request-ID"] == "trace-123"
