"""
Phase 1 — Health Check API Tests

Verifies the health check endpoint returns the expected response
structure and data, confirming the application is correctly assembled
and running.
"""

from app.schemas.common import StandardResponse


class TestHealthCheck:
    """Tests for GET /api/v1/health."""

    def test_health_check_returns_200(self, client):
        """The health endpoint should return HTTP 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_check_response_structure(self, client):
        """The response should match the StandardResponse schema."""
        response = client.get("/api/v1/health")
        body = response.json()

        assert body["success"] is True
        assert "message" in body
        assert "data" in body

    def test_health_check_data_content(self, client):
        """The data payload should contain status and version."""
        response = client.get("/api/v1/health")
        data = response.json()["data"]

        assert data["status"] == "healthy"
        assert "version" in data
        # Version should be a non-empty string
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_health_check_message(self, client):
        """The message should indicate the API is running."""
        response = client.get("/api/v1/health")
        body = response.json()

        assert "running" in body["message"].lower()

    def test_health_check_has_request_id_header(self, client):
        """
        The response should include an X-Request-ID header
        set by the RequestLoggingMiddleware.
        """
        response = client.get("/api/v1/health")
        assert "X-Request-ID" in response.headers
        # Should be a valid UUID format (36 chars with hyphens)
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36
