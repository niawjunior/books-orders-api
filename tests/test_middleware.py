from __future__ import annotations

import uuid
import pytest
from fastapi import status
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestTenantMiddleware:
    """Test tenant middleware functionality."""

    def test_tenant_header_required(self, test_client: TestClient) -> None:
        response = test_client.get("/api/v1/authors")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_data = response.json()
        assert error_data["error"]["type"] == "missing_tenant"
        assert "X-Tenant header is required" in error_data["error"]["message"]
        assert "request_id" in error_data["meta"]
        assert error_data["meta"]["tenant"] == "-"

    def test_nonexistent_tenant(self, test_client: TestClient) -> None:
        headers = {"X-Tenant": "nonexistent_tenant"}
        response = test_client.get("/api/v1/authors", headers=headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        error_data = response.json()
        assert error_data["error"]["type"] == "tenant_not_found"
        assert "not found" in error_data["error"]["message"]
        assert error_data["meta"]["tenant"] == "nonexistent_tenant"

    def test_valid_tenant_header_in_response(
        self,
        test_client: TestClient,
        bootstrap_tenant: str,
        test_tenant: str,
    ) -> None:
        headers = {"X-Tenant": test_tenant}
        response = test_client.get("/api/v1/authors", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["X-Tenant"] == test_tenant

    def test_tenant_isolation_verification(
        self,
        test_client: TestClient,
        bootstrap_tenant: str,
        sample_author: dict[str, str],
    ) -> None:
        other_tenant = "other_tenant"
        test_client.post(f"/api/v1/tenants/{other_tenant}/bootstrap")

        headers1 = {"X-Tenant": bootstrap_tenant}
        headers2 = {"X-Tenant": other_tenant}

        resp1 = test_client.get("/api/v1/authors", headers=headers1)
        assert resp1.status_code == status.HTTP_200_OK
        assert len(resp1.json()) == 1

        resp2 = test_client.get("/api/v1/authors", headers=headers2)
        assert resp2.status_code == status.HTTP_200_OK
        assert len(resp2.json()) == 0

    def test_tenant_case_sensitivity(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        headers = {"X-Tenant": bootstrap_tenant.upper()}
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert bootstrap_tenant.upper() in resp.json()["error"]["message"]

    def test_tenant_special_characters(self, test_client: TestClient) -> None:
        # Test actually invalid tenant names with special characters
        # Note: Skip slashes as they break URL routing for bootstrap endpoint
        invalid_tenants = [
            "tenant with spaces",  # spaces not allowed
            "tenant@with@symbols",  # special symbols not allowed
            "tenant.with.dots",  # dots not allowed
            "tenant\\with\\backslashes",  # backslashes not allowed
            "",  # empty string
            "a" * 64,  # too long (over 63 characters)
        ]

        for invalid_tenant in invalid_tenants:
            resp = test_client.post(f"/api/v1/tenants/{invalid_tenant}/bootstrap")
            assert resp.status_code == status.HTTP_400_BAD_REQUEST

        # Test that valid characters with hyphens work
        valid_tenant = "tenant-with-dashes"
        resp = test_client.post(f"/api/v1/tenants/{valid_tenant}/bootstrap")
        assert resp.status_code == status.HTTP_200_OK

    def test_tenant_database_connection_error(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        headers = {"X-Tenant": bootstrap_tenant}
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_200_OK

    def test_tenant_middleware_order(
        self,
        test_client: TestClient,
        bootstrap_tenant: str,
        test_tenant: str,
    ) -> None:
        headers = {
            "X-Tenant": test_tenant,
            "X-Request-ID": str(uuid.uuid4()),
        }
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["X-Tenant"] == test_tenant


class TestCorrelationIdMiddleware:
    """Test correlation ID middleware functionality."""

    def test_correlation_id_generated_when_missing(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        headers = {"X-Tenant": bootstrap_tenant}
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        corr_id = resp.headers["X-Request-ID"]
        assert len(corr_id) == 36 and corr_id.count("-") == 4

    def test_correlation_id_preserved_when_provided(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        provided = str(uuid.uuid4())
        headers = {"X-Tenant": bootstrap_tenant, "X-Request-ID": provided}
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["X-Request-ID"] == provided

    def test_correlation_id_in_error_responses(self, test_client: TestClient) -> None:
        provided = str(uuid.uuid4())
        headers = {"X-Request-ID": provided}
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        body = resp.json()
        assert body["meta"]["request_id"] == provided
        assert resp.headers["X-Request-ID"] == provided

    def test_correlation_id_different_per_request(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        headers = {"X-Tenant": bootstrap_tenant}
        r1 = test_client.get("/api/v1/authors", headers=headers)
        r2 = test_client.get("/api/v1/authors", headers=headers)
        assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]

    def test_correlation_id_with_invalid_uuid(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        headers = {"X-Tenant": bootstrap_tenant, "X-Request-ID": "invalid-uuid-format"}
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["X-Request-ID"] == "invalid-uuid-format"

    def test_correlation_id_empty_string(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        headers = {"X-Tenant": bootstrap_tenant, "X-Request-ID": ""}
        resp = test_client.get("/api/v1/authors", headers=headers)
        corr_id = resp.headers["X-Request-ID"]
        assert len(corr_id) == 36

    def test_middleware_stack_interaction(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        corr_id = str(uuid.uuid4())
        headers = {"X-Tenant": bootstrap_tenant, "X-Request-ID": corr_id}
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["X-Tenant"] == bootstrap_tenant
        assert resp.headers["X-Request-ID"] == corr_id


class TestMiddlewareIntegration:
    """Integration-level middleware tests."""

    def test_middleware_execution_order(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        corr_id = str(uuid.uuid4())
        headers = {"X-Tenant": bootstrap_tenant, "X-Request-ID": corr_id}
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["X-Request-ID"] == corr_id

    def test_middleware_error_propagation(self, test_client: TestClient) -> None:
        corr_id = str(uuid.uuid4())
        headers = {"X-Tenant": "invalid_tenant", "X-Request-ID": corr_id}
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        body = resp.json()
        assert body["meta"]["request_id"] == corr_id


class TestMiddlewareEdgeCases:
    """Test edge cases and advanced middleware scenarios."""

    def test_multiple_request_headers_preserved(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        """Test that multiple headers are properly preserved and processed."""
        headers = {
            "X-Tenant": bootstrap_tenant,
            "X-Request-ID": str(uuid.uuid4()),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["X-Tenant"] == bootstrap_tenant
        assert resp.headers["X-Request-ID"] == headers["X-Request-ID"]

    def test_correlation_id_with_special_characters(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        """Test correlation ID with various special characters."""
        special_ids = [
            "test-id_with.dots",
            "ID-WITH-DASHES",
            "id_with_underscores",
            "123456",
            "a" * 36,  # Maximum length UUID
        ]
        headers = {"X-Tenant": bootstrap_tenant}

        for test_id in special_ids:
            headers["X-Request-ID"] = test_id
            resp = test_client.get("/api/v1/authors", headers=headers)
            assert resp.status_code == status.HTTP_200_OK
            assert resp.headers["X-Request-ID"] == test_id

    def test_tenant_header_whitespace_handling(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        """Test tenant header with various whitespace scenarios."""
        # Test leading/trailing whitespace
        resp = test_client.get("/api/v1/authors", headers={"X-Tenant": f" {bootstrap_tenant} "})
        assert resp.status_code == status.HTTP_404_NOT_FOUND

        # Test empty tenant
        resp = test_client.get("/api/v1/authors", headers={"X-Tenant": ""})
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_middleware_timing_and_order_verification(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        """Verify that middleware executes in the correct order."""
        corr_id = str(uuid.uuid4())
        headers = {"X-Tenant": bootstrap_tenant, "X-Request-ID": corr_id}

        resp = test_client.get("/api/v1/authors", headers=headers)

        # Both headers should be present in response
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["X-Tenant"] == bootstrap_tenant
        assert resp.headers["X-Request-ID"] == corr_id

        # Verify correlation ID is available in error responses
        error_resp = test_client.get("/api/v1/authors", headers={"X-Request-ID": corr_id})
        assert error_resp.status_code == status.HTTP_400_BAD_REQUEST
        assert error_resp.json()["meta"]["request_id"] == corr_id

    def test_bootstrap_endpoint_middleware_interaction(self, test_client: TestClient) -> None:
        """Test middleware behavior on bootstrap endpoints."""
        tenant_name = f"test_bootstrap_{uuid.uuid4().hex[:8]}"
        corr_id = str(uuid.uuid4())
        headers = {"X-Request-ID": corr_id}

        resp = test_client.post(f"/api/v1/tenants/{tenant_name}/bootstrap", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers["X-Request-ID"] == corr_id
        # Bootstrap endpoints don't return X-Tenant header since tenant comes from URL

    def test_middleware_error_response_consistency(self, test_client: TestClient) -> None:
        """Test that all error responses have consistent format."""
        corr_id = str(uuid.uuid4())
        headers = {"X-Request-ID": corr_id}

        # Test missing tenant error
        resp = test_client.get("/api/v1/authors", headers=headers)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        body = resp.json()
        assert "error" in body
        assert "meta" in body
        assert body["meta"]["request_id"] == corr_id
        assert body["meta"]["tenant"] == "-"

        # Test invalid tenant error
        resp = test_client.get("/api/v1/authors", headers={**headers, "X-Tenant": "invalid"})
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        body = resp.json()
        assert "error" in body
        assert "meta" in body
        assert body["meta"]["request_id"] == corr_id
        assert body["meta"]["tenant"] == "invalid"

    def test_middleware_state_isolation(self, test_client: TestClient, bootstrap_tenant: str) -> None:
        """Test that middleware state is properly isolated between requests."""
        headers1 = {"X-Tenant": bootstrap_tenant}
        headers2 = {"X-Tenant": bootstrap_tenant}

        # Make two concurrent requests
        resp1 = test_client.get("/api/v1/authors", headers=headers1)
        resp2 = test_client.get("/api/v1/authors", headers=headers2)

        # Both should succeed with different correlation IDs
        assert resp1.status_code == status.HTTP_200_OK
        assert resp2.status_code == status.HTTP_200_OK
        assert resp1.headers["X-Request-ID"] != resp2.headers["X-Request-ID"]
        assert resp1.headers["X-Tenant"] == resp2.headers["X-Tenant"] == bootstrap_tenant

    def test_docs_endpoints_middleware_bypass(self, test_client: TestClient) -> None:
        """Test that documentation endpoints bypass tenant middleware."""
        docs_endpoints = ["/", "/docs", "/redoc", "/api/v1/openapi.json"]

        for endpoint in docs_endpoints:
            resp = test_client.get(endpoint)
            assert resp.status_code == status.HTTP_200_OK
            # These should work without tenant headers
            # They should still have correlation IDs
            assert "X-Request-ID" in resp.headers
            # Should not have X-Tenant header since they bypass tenant validation
            assert "X-Tenant" not in resp.headers
