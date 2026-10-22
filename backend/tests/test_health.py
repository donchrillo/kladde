"""Tests für den Health-Endpoint."""

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
