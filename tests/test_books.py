from fastapi import status
import uuid


class TestBookEndpoints:
    """Test book management endpoints."""

    def test_create_book_success(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test successful book creation."""
        book_data = {
            "title": "Test Book Title",
            "author_id": str(sample_author["id"]),
            "price": 29.99,
            "stock": 10,
            "published_at": "2023-01-01"
        }

        response = test_client.post(
            "/api/v1/books",
            json=book_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == book_data["title"]
        assert data["author_id"] == book_data["author_id"]
        assert float(data["price"]) == book_data["price"]
        assert data["stock"] == book_data["stock"]
        assert data["published_at"] == book_data["published_at"]
        assert "id" in data

    def test_create_book_without_optional_fields(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test creating book without optional fields."""
        book_data = {
            "title": "Simple Book",
            "author_id": str(sample_author["id"]),
            "price": 15.99,
            "stock": 5
        }

        response = test_client.post(
            "/api/v1/books",
            json=book_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == book_data["title"]
        assert data["published_at"] is None

    def test_create_book_negative_price(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test creating book with negative price."""
        book_data = {
            "title": "Negative Price Book",
            "author_id": str(sample_author["id"]),
            "price": -10.99,
            "stock": 5
        }

        response = test_client.post(
            "/api/v1/books",
            json=book_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "price must be >= 0" in response.text

    def test_create_book_negative_stock(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test creating book with negative stock."""
        book_data = {
            "title": "Negative Stock Book",
            "author_id": str(sample_author["id"]),
            "price": 29.99,
            "stock": -5
        }

        response = test_client.post(
            "/api/v1/books",
            json=book_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        # This should be caught by Pydantic validation

    def test_create_book_empty_title(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test creating book with empty title."""
        book_data = {
            "title": "   ",
            "author_id": str(sample_author["id"]),
            "price": 29.99,
            "stock": 5
        }

        response = test_client.post(
            "/api/v1/books",
            json=book_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert "title cannot be empty" in response.text

    def test_create_book_trim_title(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test that book title is trimmed."""
        book_data = {
            "title": "  Trimmed Book Title  ",
            "author_id": str(sample_author["id"]),
            "price": 29.99,
            "stock": 5
        }

        response = test_client.post(
            "/api/v1/books",
            json=book_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title"] == "Trimmed Book Title"

    def test_create_book_nonexistent_author(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test creating book with non-existent author."""
        book_data = {
            "title": "Orphan Book",
            "author_id": str(uuid.uuid4()),
            "price": 29.99,
            "stock": 5
        }

        response = test_client.post(
            "/api/v1/books",
            json=book_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        # Should fail at foreign key constraint level

    def test_create_duplicate_book_same_author_year(self, test_client, bootstrap_tenant, sample_author, sample_book, headers_with_tenant):
        """Test creating duplicate book (same title + author + year)."""
        book_data = {
            "title": sample_book["title"],
            "author_id": str(sample_author["id"]),
            "price": 19.99,
            "stock": 3,
            "published_at": "2023-01-01"  # Same year as sample_book
        }

        response = test_client.post(
            "/api/v1/books",
            json=book_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Duplicate book" in response.text

    def test_create_duplicate_book_different_year(self, test_client, bootstrap_tenant, sample_author, sample_book, headers_with_tenant):
        """Test creating book with same title and author but different year."""
        book_data = {
            "title": sample_book["title"],
            "author_id": str(sample_author["id"]),
            "price": 19.99,
            "stock": 3,
            "published_at": "2024-01-01"  # Different year
        }

        response = test_client.post(
            "/api/v1/books",
            json=book_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        # Should succeed as year is different

    def test_list_books_empty(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test listing books when none exist."""
        response = test_client.get("/api/v1/books", headers=headers_with_tenant)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_books_with_data(self, test_client, bootstrap_tenant, sample_book, headers_with_tenant):
        """Test listing books with existing data."""
        response = test_client.get("/api/v1/books", headers=headers_with_tenant)

        assert response.status_code == status.HTTP_200_OK
        books = response.json()
        assert len(books) == 1
        assert books[0]["id"] == str(sample_book["id"])
        assert books[0]["title"] == sample_book["title"]

    def test_list_books_by_author(self, test_client, bootstrap_tenant, sample_author, sample_book, headers_with_tenant):
        """Test filtering books by author."""
        # Create another author and book
        other_author_data = {"name": "Other Author"}
        response = test_client.post(
            "/api/v1/authors",
            json=other_author_data,
            headers=headers_with_tenant
        )
        other_author_id = response.json()["id"]

        other_book_data = {
            "title": "Other Book",
            "author_id": other_author_id,
            "price": 25.99,
            "stock": 8
        }
        test_client.post(
            "/api/v1/books",
            json=other_book_data,
            headers=headers_with_tenant
        )

        # Filter by original author
        response = test_client.get(
            f"/api/v1/books?author_id={sample_author['id']}",
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        books = response.json()
        assert len(books) == 1
        assert books[0]["author_id"] == str(sample_author["id"])

    def test_list_books_search(self, test_client, bootstrap_tenant, sample_author, sample_book, headers_with_tenant):
        """Test searching books by title."""
        # Create another book
        search_book_data = {
            "title": "Searchable Book",
            "author_id": str(sample_author["id"]),
            "price": 35.99,
            "stock": 6
        }
        test_client.post(
            "/api/v1/books",
            json=search_book_data,
            headers=headers_with_tenant
        )

        # Search for "Searchable"
        response = test_client.get(
            "/api/v1/books?q=Searchable",
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        books = response.json()
        assert len(books) == 1
        assert "Searchable" in books[0]["title"]

    def test_list_books_sort_by_title(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test sorting books by title."""
        # Create multiple books with different titles
        books_data = [
            {"title": "Zebra Book", "author_id": str(sample_author["id"]), "price": 10.99, "stock": 2},
            {"title": "Apple Book", "author_id": str(sample_author["id"]), "price": 15.99, "stock": 3},
            {"title": "Banana Book", "author_id": str(sample_author["id"]), "price": 12.99, "stock": 4}
        ]

        for book_data in books_data:
            test_client.post("/api/v1/books", json=book_data, headers=headers_with_tenant)

        # Sort by title
        response = test_client.get("/api/v1/books?sort=title", headers=headers_with_tenant)

        assert response.status_code == status.HTTP_200_OK
        books = response.json()
        titles = [book["title"] for book in books]
        assert titles == sorted(titles)

    def test_list_books_pagination(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test book pagination."""
        # Create multiple books
        for i in range(25):
            book_data = {
                "title": f"Book {i:02d}",
                "author_id": str(sample_author["id"]),
                "price": 10.99 + i,
                "stock": i + 1
            }
            test_client.post("/api/v1/books", json=book_data, headers=headers_with_tenant)

        # Test limit and offset
        response = test_client.get("/api/v1/books?limit=10&offset=5", headers=headers_with_tenant)

        assert response.status_code == status.HTTP_200_OK
        books = response.json()
        assert len(books) == 10
        # Should return books 5-14 (0-indexed)
        assert books[0]["title"] == "Book 05"
        assert books[-1]["title"] == "Book 14"

    def test_list_books_invalid_sort_field(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test sorting with invalid field."""
        response = test_client.get("/api/v1/books?sort=invalid_field", headers=headers_with_tenant)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_list_books_pagination_limits(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test pagination limits."""
        response = test_client.get("/api/v1/books?limit=101", headers=headers_with_tenant)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        response = test_client.get("/api/v1/books?limit=0", headers=headers_with_tenant)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        response = test_client.get("/api/v1/books?limit=-1", headers=headers_with_tenant)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_book_tenant_isolation(self, test_client, bootstrap_tenant, sample_book):
        """Test that books are properly isolated by tenant."""
        # Create another tenant
        other_tenant = "other_tenant"
        test_client.post(f"/api/v1/tenants/{other_tenant}/bootstrap", headers={"X-Tenant": other_tenant})

        # Original tenant should see the book
        headers1 = {"X-Tenant": bootstrap_tenant}
        response1 = test_client.get("/api/v1/books", headers=headers1)
        assert response1.status_code == status.HTTP_200_OK
        assert len(response1.json()) == 1

        # Other tenant should not see the book
        headers2 = {"X-Tenant": other_tenant}
        response2 = test_client.get("/api/v1/books", headers=headers2)
        assert response2.status_code == status.HTTP_200_OK
        assert len(response2.json()) == 0

    def test_book_version_field(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test that book version field is properly set."""
        book_data = {
            "title": "Version Test Book",
            "author_id": str(sample_author["id"]),
            "price": 29.99,
            "stock": 10
        }

        response = test_client.post(
            "/api/v1/books",
            json=book_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["version"] == 1

    def test_book_missing_tenant_header(self, test_client, bootstrap_tenant, sample_author):
        """Test book endpoints without tenant header."""
        book_data = {
            "title": "No Tenant Book",
            "author_id": str(sample_author["id"]),
            "price": 29.99,
            "stock": 5
        }

        response = test_client.post("/api/v1/books", json=book_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = test_client.get("/api/v1/books")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
