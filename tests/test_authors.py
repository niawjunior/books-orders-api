from fastapi import status


class TestAuthorEndpoints:
    """Test author management endpoints."""

    def test_create_author_success(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test successful author creation."""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        author_data = {
            "name": f"John Doe {unique_id}",
            "email": f"john{unique_id}@example.com"
        }

        response = test_client.post(
            "/api/v1/authors",
            json=author_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == author_data["name"]
        assert data["email"] == author_data["email"]
        assert "id" in data

    def test_create_author_without_email(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test creating author without email (optional field)."""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        author_data = {
            "name": f"Jane Smith {unique_id}"
        }

        response = test_client.post(
            "/api/v1/authors",
            json=author_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == author_data["name"]
        assert data["email"] is None
        assert "id" in data

    def test_create_author_duplicate_email(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test creating author with duplicate email."""
        author_data = {
            "name": "Different Name",
            "email": sample_author["email"]
        }

        response = test_client.post(
            "/api/v1/authors",
            json=author_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # This should fail at database constraint level

    def test_create_author_empty_name(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test creating author with empty name."""
        author_data = {
            "name": "   ",
            "email": "test@example.com"
        }

        response = test_client.post(
            "/api/v1/authors",
            json=author_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "name cannot be empty" in response.text.lower()

    def test_create_author_trim_name(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test that author name is trimmed."""
        author_data = {
            "name": "  Trimmed Name  ",
            "email": "trimmed@example.com"
        }

        response = test_client.post(
            "/api/v1/authors",
            json=author_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "Trimmed Name"

    def test_create_author_invalid_email(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test creating author with invalid email."""
        author_data = {
            "name": "Test Author",
            "email": "invalid-email"
        }

        response = test_client.post(
            "/api/v1/authors",
            json=author_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        # Pydantic validation should catch invalid email format

    def test_list_authors_empty(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test listing authors when none exist."""
        response = test_client.get("/api/v1/authors", headers=headers_with_tenant)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_authors_with_data(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test listing authors with existing data."""


        response = test_client.get("/api/v1/authors", headers=headers_with_tenant)

        assert response.status_code == status.HTTP_200_OK
        authors = response.json()

        assert len(authors) == 1
        assert authors[0]["id"] == sample_author["id"]
        assert authors[0]["name"] == sample_author["name"]
        assert authors[0]["email"] == sample_author["email"]

    def test_list_authors_multiple(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test listing multiple authors."""
        # Create multiple authors
        authors_data = [
            {"name": "Author One", "email": "one@example.com"},
            {"name": "Author Two", "email": "two@example.com"},
            {"name": "Author Three"}  # No email
        ]

        created_authors = []
        for author_data in authors_data:
            response = test_client.post(
                "/api/v1/authors",
                json=author_data,
                headers=headers_with_tenant
            )
            assert response.status_code == status.HTTP_200_OK
            created_authors.append(response.json())

        # List all authors
        response = test_client.get("/api/v1/authors", headers=headers_with_tenant)
        assert response.status_code == status.HTTP_200_OK

        authors = response.json()
        assert len(authors) == 3

    def test_author_tenant_isolation(self, test_client, bootstrap_tenant, sample_author):
        """Test that authors are properly isolated by tenant."""
        # Create another tenant
        other_tenant = "other_tenant"
        test_client.post(f"/api/v1/tenants/{other_tenant}/bootstrap", headers={"X-Tenant": other_tenant})

        # Original tenant should see the author
        headers1 = {"X-Tenant": bootstrap_tenant}
        response1 = test_client.get("/api/v1/authors", headers=headers1)
        assert response1.status_code == status.HTTP_200_OK
        assert len(response1.json()) == 1

        # Other tenant should not see the author
        headers2 = {"X-Tenant": other_tenant}
        response2 = test_client.get("/api/v1/authors", headers=headers2)
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()) == 0

    def test_author_fields_validation(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test various field validations for author creation."""
        test_cases = [
            # Missing required fields
            ({}, 422),
            # Empty object
            ({}, 422),
            # Name with special characters (should be allowed)
            ({"name": "José María", "email": "jose@example.com"}, 200),
            # Long name (should be allowed)
            ({"name": "A" * 100, "email": "long@example.com"}, 200),
        ]

        for author_data, expected_status in test_cases:
            response = test_client.post(
                "/api/v1/authors",
                json=author_data,
                headers=headers_with_tenant
            )
            assert response.status_code == expected_status

    def test_author_citext_email_case_insensitive(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test that email uniqueness is case insensitive due to citext."""
        author_data = {
            "name": "Different Name",
            "email": sample_author["email"].upper()  # Different case but same email
        }

        response = test_client.post(
            "/api/v1/authors",
            json=author_data,
            headers=headers_with_tenant
        )

        # Should fail due to case-insensitive email constraint
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_author_missing_tenant_header(self, test_client):
        """Test author endpoints without tenant header."""
        author_data = {"name": "Test Author"}

        response = test_client.post("/api/v1/authors", json=author_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = test_client.get("/api/v1/authors")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
