import pytest
from fastapi import status
from sqlalchemy import text


class TestTenantBootstrap:
    """Test tenant bootstrap functionality."""

    def test_bootstrap_tenant_success(self, test_client):
        """Test successful tenant bootstrap."""
        tenant_name = "bootstrap_test_tenant"
        headers = {"X-Tenant": tenant_name}
        response = test_client.post(f"/api/v1/tenants/{tenant_name}/bootstrap", headers=headers)



        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok", "tenant": tenant_name}

    def test_bootstrap_tenant_invalid_name(self, test_client):
        """Test bootstrap with invalid tenant name."""
        # Test actually invalid tenant names with special characters
        invalid_tenants = [
            "invalid name with spaces",  # spaces not allowed
            "invalid@name@with@symbols",  # special symbols not allowed
            "invalid.name.with.dots",  # dots not allowed
            "invalid\\name\\with\\backslashes",  # backslashes not allowed
            "a" * 64,  # too long (over 63 characters)
        ]

        for invalid_tenant in invalid_tenants:
            response = test_client.post(f"/api/v1/tenants/{invalid_tenant}/bootstrap", headers={"X-Tenant": invalid_tenant})
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            error_response = response.json()
            # Check for appropriate error message based on validation type
            if len(invalid_tenant) > 63:  # length validation
                assert "Tenant name must be 1-63 characters" in error_response["error"]["message"]
            else:  # regex validation
                assert "Invalid tenant name" in error_response["error"]["message"]

        # Test that valid hyphenated names work
        valid_tenant = "valid-name-with-dashes"
        response = test_client.post(f"/api/v1/tenants/{valid_tenant}/bootstrap", headers={"X-Tenant": valid_tenant})
        assert response.status_code == status.HTTP_200_OK



    def test_bootstrap_tenant_twice(self, test_client):
        """Test that bootstrap can be called multiple times safely."""
        tenant_name = "twice_test_tenant"
        headers = {"X-Tenant": tenant_name}
        # First bootstrap
        response1 = test_client.post(f"/api/v1/tenants/{tenant_name}/bootstrap", headers=headers)
        assert response1.status_code == status.HTTP_200_OK

        # Second bootstrap should also succeed
        response2 = test_client.post(f"/api/v1/tenants/{tenant_name}/bootstrap", headers=headers)
        assert response2.status_code == status.HTTP_200_OK
        assert response2.json() == response1.json()

    def test_bootstrap_creates_proper_schema(self, test_client):
        """Test that bootstrap creates the correct schema and tables."""
        tenant_name = "schema_test_tenant"
        headers = {"X-Tenant": tenant_name}
        # Bootstrap tenant
        response = test_client.post(f"/api/v1/tenants/{tenant_name}/bootstrap", headers=headers)
        assert response.status_code == status.HTTP_200_OK

        # Verify schema exists and has expected tables using direct database access
        from app.db.session import engine
        with engine.connect() as conn:
            # Verify schema exists
            result = conn.execute(
                text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"),
                {"s": tenant_name}
            ).first()
            assert result is not None

            # Verify tables exist in the schema using direct SQL
            conn.execute(text(f"SET search_path TO {tenant_name}, public"))
            result = conn.execute(
                text("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = :s
                    AND table_type = 'BASE TABLE'
                """),
                {"s": tenant_name}
            ).fetchall()

            table_names = [row[0] for row in result]
            expected_tables = ["authors", "books", "orders", "order_items", "idempotency_keys"]
            for table in expected_tables:
                assert table in table_names, f"Expected table '{table}' not found in schema '{tenant_name}'. Found: {table_names}"


class TestTenantMiddleware:
    """Test tenant middleware functionality."""

    def test_missing_tenant_header(self, test_client):
        """Test request without X-Tenant header."""
        response = test_client.get("/api/v1/authors")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["error"]["type"] == "missing_tenant"
        assert "X-Tenant header is required" in response.json()["error"]["message"]

    def test_nonexistent_tenant(self, test_client):
        """Test request with non-existent tenant."""
        headers = {"X-Tenant": "nonexistent_tenant"}
        response = test_client.get("/api/v1/authors", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["error"]["type"] == "tenant_not_found"
        assert "not found" in response.json()["error"]["message"]

    def test_valid_tenant_header_added_to_response(self, test_client, test_tenant):
        """Test that X-Tenant header is added to response."""
        # Bootstrap tenant first
        headers = {"X-Tenant": test_tenant}
        bootstrap_response = test_client.post(f"/api/v1/tenants/{test_tenant}/bootstrap", headers=headers)
        assert bootstrap_response.status_code == status.HTTP_200_OK

        # Now test the header addition
        response = test_client.get("/api/v1/authors", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["X-Tenant"] == test_tenant

    def test_tenant_search_path_isolation(self, test_client):
        """Test that tenant search_path properly isolates data."""
        # Use unique tenant names to avoid conflicts with other tests
        import time
        import uuid
        timestamp = int(time.time() * 1000)

        tenant1 = f"isolation_test_{timestamp}_1"
        tenant2 = f"isolation_test_{timestamp}_2"

        headers1 = {"X-Tenant": tenant1}
        headers2 = {"X-Tenant": tenant2}

        # Create both tenants
        resp1 = test_client.post(f"/api/v1/tenants/{tenant1}/bootstrap", headers=headers1)
        resp2 = test_client.post(f"/api/v1/tenants/{tenant2}/bootstrap", headers=headers2)

        assert resp1.status_code == status.HTTP_200_OK
        assert resp2.status_code == status.HTTP_200_OK

        # Add author to first tenant only
        unique_name = f"Test Author {timestamp} {uuid.uuid4().hex[:8]}"
        author_resp = test_client.post("/api/v1/authors",
                                   json={"name": unique_name, "email": f"{timestamp}-{uuid.uuid4().hex[:8]}@example.com"},
                                   headers=headers1)

        assert author_resp.status_code == status.HTTP_200_OK

        # Check tenant1 has the author
        authors1_resp = test_client.get("/api/v1/authors", headers=headers1)
        assert authors1_resp.status_code == status.HTTP_200_OK
        authors1 = authors1_resp.json()

        # Check tenant2 does not have the author
        authors2_resp = test_client.get("/api/v1/authors", headers=headers2)
        assert authors2_resp.status_code == status.HTTP_200_OK
        authors2 = authors2_resp.json()

        # Verify isolation
        found_in_tenant1 = any(a["name"] == unique_name for a in authors1)
        found_in_tenant2 = any(a["name"] == unique_name for a in authors2)

        assert found_in_tenant1, f"Author {unique_name} not found in tenant {tenant1}"
        assert not found_in_tenant2, f"Author {unique_name} leaked to tenant {tenant2}"

    def test_tenant_case_sensitivity(self, test_client):
        """Test that tenant names are case sensitive."""
        # Try accessing with different case
        headers = {"X-Tenant": "nonexistent_upper"}
        response = test_client.get("/api/v1/authors", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND
