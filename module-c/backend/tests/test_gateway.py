"""Basic smoke tests for the gateway module."""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_check():
    """Verify /health returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "module-c-gateway"


def test_proxy_no_target_returns_404():
    """Unmatched paths should return 404."""
    response = client.get("/api/v1/unknown/path")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == 404


def test_cors_headers_present():
    """CORS middleware should add headers."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    # GET should succeed with CORS headers
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_old_predict_route_returns_404():
    """Removed /api/v1/predict routes should now return 404."""
    response = client.get("/api/v1/predict/health")
    assert response.status_code == 404


def test_old_workflow_route_returns_404():
    """Removed /api/v1/workflow routes should now return 404."""
    response = client.get("/api/v1/workflow/status")
    assert response.status_code == 404


def test_old_diagnose_route_returns_404():
    """Removed /api/v1/diagnose routes should now return 404."""
    response = client.get("/api/v1/diagnose/report")
    assert response.status_code == 404


def test_monitor_routing():
    """Verify /api/v1/monitor/health gets routed to monitor_url (not 404).

    The backend won't be running during tests, so we expect a connection
    error (5xx) rather than a 404 — this proves the path WAS recognized
    and a forwarding attempt was made.
    """
    with TestClient(app) as client:
        response = client.get("/api/v1/monitor/health")
    # Should NOT be 404 — the path matches _get_target, forwarding is attempted
    assert response.status_code != 404
