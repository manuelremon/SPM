from __future__ import annotations


def test_healthz_endpoint(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
