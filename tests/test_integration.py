import pytest
from fastapi import status
import uuid


class TestCompleteBookOrderFlow:
    """Test complete end-to-end book order workflows."""

    def test_full_bookstore_workflow(self, test_client, test_tenant):
        """Test complete workflow: tenant setup -> author -> books -> order -> confirm."""
        # 1. Bootstrap tenant
        response = test_client.post(f"/api/v1/tenants/{test_tenant}/bootstrap")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["tenant"] == test_tenant

        headers = {"X-Tenant": test_tenant}

        # 2. Create author
        author_data = {"name": "J.K. Rowling", "email": "jk@rowling.com"}
        response = test_client.post("/api/v1/authors", json=author_data, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        author = response.json()

        # 3. Create multiple books
        books_data = [
            {
                "title": "Harry Potter and the Sorcerer's Stone",
                "author_id": author["id"],
                "price": 19.99,
                "stock": 10,
                "published_at": "1997-06-26"
            },
            {
                "title": "Harry Potter and the Chamber of Secrets",
                "author_id": author["id"],
                "price": 21.99,
                "stock": 8,
                "published_at": "1998-07-02"
            },
            {
                "title": "Harry Potter and the Prisoner of Azkaban",
                "author_id": author["id"],
                "price": 23.99,
                "stock": 5,
                "published_at": "1999-07-08"
            }
        ]

        created_books = []
        for book_data in books_data:
            response = test_client.post("/api/v1/books", json=book_data, headers=headers)
            assert response.status_code == status.HTTP_200_OK
            created_books.append(response.json())

        # 4. Verify books are listed correctly
        response = test_client.get("/api/v1/books", headers=headers)
        assert response.status_code == status.HTTP_200_OK
        books_list = response.json()
        assert len(books_list) == 3

        # 5. Create order with multiple items
        order_data = {
            "items": [
                {"product_id": created_books[0]["id"], "qty": 2},
                {"product_id": created_books[1]["id"], "qty": 1},
                {"product_id": created_books[2]["id"], "qty": 3}
            ]
        }

        response = test_client.post("/api/v1/orders", json=order_data, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        order = response.json()
        assert order["status"] == "DRAFT"
        assert len(order["items"]) == 3

        # 6. Confirm order with idempotency key
        idempotency_key = str(uuid.uuid4())
        confirm_headers = headers.copy()
        confirm_headers["Idempotency-Key"] = idempotency_key

        response = test_client.post(
            f"/api/v1/orders/{order['id']}/confirm",
            headers=confirm_headers
        )
        assert response.status_code == status.HTTP_200_OK
        confirm_result = response.json()
        assert confirm_result["status"] == "CONFIRMED"

        # 7. Verify idempotency - confirm again with same key
        response = test_client.post(
            f"/api/v1/orders/{order['id']}/confirm",
            headers=confirm_headers
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == confirm_result

        # 8. Verify stock was properly reduced
        response = test_client.get("/api/v1/books", headers=headers)
        updated_books = response.json()

        updated_book1 = next(b for b in updated_books if b["id"] == created_books[0]["id"])
        updated_book2 = next(b for b in updated_books if b["id"] == created_books[1]["id"])
        updated_book3 = next(b for b in updated_books if b["id"] == created_books[2]["id"])

        assert updated_book1["stock"] == 8  # 10 - 2
        assert updated_book2["stock"] == 7  # 8 - 1
        assert updated_book3["stock"] == 2  # 5 - 3

    def test_multiple_tenants_complete_isolation(self, test_client):
        """Test that multiple tenants have complete data isolation."""
        import time
        timestamp = str(int(time.time()))
        tenant1 = f"tenant1_{timestamp}"
        tenant2 = f"tenant2_{timestamp}"

        # Bootstrap both tenants
        test_client.post(f"/api/v1/tenants/{tenant1}/bootstrap")
        test_client.post(f"/api/v1/tenants/{tenant2}/bootstrap")

        headers1 = {"X-Tenant": tenant1}
        headers2 = {"X-Tenant": tenant2}

        # Create author and book in tenant1
        author_data = {"name": f"Tenant1 Author {timestamp}", "email": f"author{timestamp}@tenant1.com"}
        response = test_client.post("/api/v1/authors", json=author_data, headers=headers1)
        author1 = response.json()

        book_data = {
            "title": "Tenant1 Book",
            "author_id": author1["id"],
            "price": 29.99,
            "stock": 10
        }
        response = test_client.post("/api/v1/books", json=book_data, headers=headers1)
        book1 = response.json()

        # Create different author and book in tenant2
        author_data = {"name": f"Tenant2 Author {timestamp}", "email": f"author2{timestamp}@tenant2.com"}
        response = test_client.post("/api/v1/authors", json=author_data, headers=headers2)
        author2 = response.json()

        book_data = {
            "title": "Tenant2 Book",
            "author_id": author2["id"],
            "price": 39.99,
            "stock": 5
        }
        response = test_client.post("/api/v1/books", json=book_data, headers=headers2)
        book2 = response.json()

        # Verify isolation
        # Tenant1 should only see their data
        response = test_client.get("/api/v1/authors", headers=headers1)
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == f"Tenant1 Author {timestamp}"

        response = test_client.get("/api/v1/books", headers=headers1)
        assert len(response.json()) == 1
        assert response.json()[0]["title"] == "Tenant1 Book"

        # Tenant2 should only see their data
        response = test_client.get("/api/v1/authors", headers=headers2)
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == f"Tenant2 Author {timestamp}"

        response = test_client.get("/api/v1/books", headers=headers2)
        assert len(response.json()) == 1
        assert response.json()[0]["title"] == "Tenant2 Book"

        # Create orders in each tenant
        order1_data = {
            "items": [{"product_id": book1["id"], "qty": 2}]
        }
        response = test_client.post("/api/v1/orders", json=order1_data, headers=headers1)
        order1 = response.json()

        order2_data = {
            "items": [{"product_id": book2["id"], "qty": 1}]
        }
        response = test_client.post("/api/v1/orders", json=order2_data, headers=headers2)
        order2 = response.json()

        # Confirm orders
        test_client.post(f"/api/v1/orders/{order1['id']}/confirm", headers=headers1)
        test_client.post(f"/api/v1/orders/{order2['id']}/confirm", headers=headers2)

        # Verify stock only affected in respective tenants
        response = test_client.get("/api/v1/books", headers=headers1)
        tenant1_books = response.json()
        assert tenant1_books[0]["stock"] == 8  # 10 - 2

        response = test_client.get("/api/v1/books", headers=headers2)
        tenant2_books = response.json()
        assert tenant2_books[0]["stock"] == 4  # 5 - 1

    def test_concurrent_order_handling(self, test_client, test_tenant):
        """Test concurrent order handling and stock management."""
        # Bootstrap tenant
        test_client.post(f"/api/v1/tenants/{test_tenant}/bootstrap")
        headers = {"X-Tenant": test_tenant}

        # Create author and book with limited stock
        author_data = {"name": "Concurrent Test Author"}
        response = test_client.post("/api/v1/authors", json=author_data, headers=headers)
        author = response.json()

        book_data = {
            "title": "Limited Stock Book",
            "author_id": author["id"],
            "price": 99.99,
            "stock": 5
        }
        response = test_client.post("/api/v1/books", json=book_data, headers=headers)
        book = response.json()

        # Create order with quantity greater than stock - should fail on confirmation
        order_data = {
            "items": [{"product_id": book["id"], "qty": 10}]  # Wants 10, only 5 available
        }
        response = test_client.post("/api/v1/orders", json=order_data, headers=headers)
        order = response.json()

        # Try to confirm order - should fail due to insufficient stock
        response = test_client.post(f"/api/v1/orders/{order['id']}/confirm", headers=headers)
        assert response.status_code == status.HTTP_409_CONFLICT
        error_data = response.json()
        assert "shortages" in error_data["error"]["details"]
        assert error_data["error"]["details"]["shortages"][0]["available"] == 5
        assert error_data["error"]["details"]["shortages"][0]["requested"] == 10

        # Stock should remain unchanged after failed confirmation
        response = test_client.get("/api/v1/books", headers=headers)
        final_book = response.json()[0]
        assert final_book["stock"] == 5

    def test_complex_search_and_filtering(self, test_client, test_tenant):
        """Test advanced book search and filtering functionality."""
        # Bootstrap tenant
        test_client.post(f"/api/v1/tenants/{test_tenant}/bootstrap")
        headers = {"X-Tenant": test_tenant}

        # Create multiple authors
        authors = []
        for i, name in enumerate(["J.R.R. Tolkien", "George R.R. Martin", "Isaac Asimov"]):
            author_data = {"name": name, "email": f"author{i}@example.com"}
            response = test_client.post("/api/v1/authors", json=author_data, headers=headers)
            authors.append(response.json())

        # Create books with various characteristics
        books_data = [
            {"title": "The Hobbit", "author_id": authors[0]["id"], "price": 15.99, "stock": 10, "published_at": "1937-09-21"},
            {"title": "The Lord of the Rings", "author_id": authors[0]["id"], "price": 45.99, "stock": 5, "published_at": "1954-07-29"},
            {"title": "A Game of Thrones", "author_id": authors[1]["id"], "price": 25.99, "stock": 8, "published_at": "1996-08-01"},
            {"title": "A Clash of Kings", "author_id": authors[1]["id"], "price": 27.99, "stock": 6, "published_at": "1998-11-16"},
            {"title": "Foundation", "author_id": authors[2]["id"], "price": 18.99, "stock": 12, "published_at": "1951-05-01"},
            {"title": "I, Robot", "author_id": authors[2]["id"], "price": 14.99, "stock": 15, "published_at": "1950-12-02"},
        ]

        for book_data in books_data:
            test_client.post("/api/v1/books", json=book_data, headers=headers)

        # Test filtering by author
        response = test_client.get(f"/api/v1/books?author_id={authors[0]['id']}", headers=headers)
        tolkien_books = response.json()
        assert len(tolkien_books) == 2
        assert all(book["author_id"] == authors[0]["id"] for book in tolkien_books)

        # Test text search
        response = test_client.get("/api/v1/books?q=Thrones", headers=headers)
        thrones_books = response.json()
        assert len(thrones_books) == 1
        assert "Thrones" in thrones_books[0]["title"]

        # Test sorting by title
        response = test_client.get("/api/v1/books?sort=title", headers=headers)
        sorted_books = response.json()
        titles = [book["title"] for book in sorted_books]
        assert titles == sorted(titles)

        # Test sorting by published_at
        response = test_client.get("/api/v1/books?sort=published_at", headers=headers)
        sorted_by_date = response.json()
        dates = [book["published_at"] for book in sorted_by_date if book["published_at"]]
        assert dates == sorted(dates)

        # Test pagination
        response = test_client.get("/api/v1/books?limit=2&offset=0", headers=headers)
        first_page = response.json()
        assert len(first_page) == 2

        response = test_client.get("/api/v1/books?limit=2&offset=2", headers=headers)
        second_page = response.json()
        assert len(second_page) == 2
        assert first_page[0]["title"] != second_page[0]["title"]

    def test_validation_comprehensive(self, test_client, test_tenant):
        """Test all three levels of validation comprehensively."""
        # Bootstrap tenant
        test_client.post(f"/api/v1/tenants/{test_tenant}/bootstrap")
        headers = {"X-Tenant": test_tenant}

        # Create author
        author_data = {"name": "Validation Test Author", "email": "validation@author.com"}
        response = test_client.post("/api/v1/authors", json=author_data, headers=headers)
        author = response.json()

        # 1. Pydantic level validation tests
        invalid_books = [
            # Empty title
            {"title": "   ", "author_id": author["id"], "price": 29.99, "stock": 5},
            # Negative price
            {"title": "Valid Title", "author_id": author["id"], "price": -10.00, "stock": 5},
            # Negative stock
            {"title": "Valid Title", "author_id": author["id"], "price": 29.99, "stock": -1},
            # Invalid UUID
            {"title": "Valid Title", "author_id": "invalid-uuid", "price": 29.99, "stock": 5},
        ]

        for invalid_book in invalid_books:
            response = test_client.post("/api/v1/books", json=invalid_book, headers=headers)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # Create valid book
        book_data = {
            "title": "Validation Test Book",
            "author_id": author["id"],
            "price": 29.99,
            "stock": 10,
            "published_at": "2023-01-01"
        }
        response = test_client.post("/api/v1/books", json=book_data, headers=headers)
        book = response.json()

        # 2. Database constraint level tests
        # Duplicate email (citext - case insensitive)
        duplicate_author = {"name": "Different Name", "email": author["email"].upper()}
        response = test_client.post("/api/v1/authors", json=duplicate_author, headers=headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # 3. Business logic level tests
        # Duplicate book (same title + author + year)
        duplicate_book = {
            "title": book["title"],
            "author_id": author["id"],
            "price": 19.99,
            "stock": 5,
            "published_at": "2023-01-01"  # Same year
        }
        response = test_client.post("/api/v1/books", json=duplicate_book, headers=headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Duplicate book" in response.text

        # Order with insufficient stock
        order_data = {
            "items": [{"product_id": book["id"], "qty": book["stock"] + 1}]
        }
        response = test_client.post("/api/v1/orders", json=order_data, headers=headers)
        assert response.status_code == status.HTTP_200_OK
        order = response.json()

        # Business logic: should fail on confirm
        response = test_client.post(f"/api/v1/orders/{order['id']}/confirm", headers=headers)
        assert response.status_code == status.HTTP_409_CONFLICT
        error_response = response.json()
        assert "shortages" in error_response["error"]["details"]

    def test_error_handling_and_correlation(self, test_client, test_tenant):
        """Test error handling and correlation ID propagation."""
        correlation_id = str(uuid.uuid4())

        # Bootstrap tenant
        test_client.post(f"/api/v1/tenants/{test_tenant}/bootstrap")
        headers = {
            "X-Tenant": test_tenant,
            "X-Request-ID": correlation_id
        }

        # Test various error scenarios
        # 1. Missing tenant header
        response = test_client.get("/api/v1/authors")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_data = response.json()
        assert "meta" in error_data
        assert "request_id" in error_data["meta"]

        # 2. Non-existent tenant
        response = test_client.get("/api/v1/authors", headers={"X-Tenant": "nonexistent"})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        error_data = response.json()
        assert error_data["error"]["type"] == "tenant_not_found"

        # 3. Validation errors with correlation
        response = test_client.post("/api/v1/authors", json={"name": ""}, headers=headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

        # 4. Business logic errors with correlation
        response = test_client.post("/api/v1/orders", json={"items": []}, headers=headers)
        assert response.status_code == status.HTTP_200_OK  # Empty order is valid

        # Test with correlation ID preserved
        assert response.headers["X-Request-ID"] == correlation_id

        # 5. Try to confirm non-existent order
        fake_order_id = str(uuid.uuid4())
        response = test_client.post(f"/api/v1/orders/{fake_order_id}/confirm", headers=headers)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.headers["X-Request-ID"] == correlation_id

    def test_idempotency_comprehensive(self, test_client, test_tenant):
        """Test idempotency functionality comprehensively."""
        # Bootstrap tenant
        test_client.post(f"/api/v1/tenants/{test_tenant}/bootstrap")
        headers = {"X-Tenant": test_tenant}

        # Create author and book
        author_data = {"name": "Idempotency Test Author"}
        response = test_client.post("/api/v1/authors", json=author_data, headers=headers)
        author = response.json()

        book_data = {
            "title": "Idempotency Test Book",
            "author_id": author["id"],
            "price": 29.99,
            "stock": 10
        }
        response = test_client.post("/api/v1/books", json=book_data, headers=headers)
        book = response.json()

        # Create order
        order_data = {
            "items": [{"product_id": book["id"], "qty": 3}]
        }
        response = test_client.post("/api/v1/orders", json=order_data, headers=headers)
        order = response.json()

        # Test idempotency with same key
        idempotency_key = str(uuid.uuid4())
        confirm_headers = headers.copy()
        confirm_headers["Idempotency-Key"] = idempotency_key

        # First confirmation
        response1 = test_client.post(
            f"/api/v1/orders/{order['id']}/confirm",
            headers=confirm_headers
        )
        assert response1.status_code == status.HTTP_200_OK
        result1 = response1.json()

        # Second confirmation with same key
        response2 = test_client.post(
            f"/api/v1/orders/{order['id']}/confirm",
            headers=confirm_headers
        )
        assert response2.status_code == status.HTTP_200_OK
        result2 = response2.json()

        # Results should be identical
        assert result1 == result2

        # Stock should only be reduced once
        response = test_client.get("/api/v1/books", headers=headers)
        updated_book = response.json()[0]
        assert updated_book["stock"] == 7  # 10 - 3, not 4

        # Test with different idempotency key
        different_key = str(uuid.uuid4())
        confirm_headers["Idempotency-Key"] = different_key

        response = test_client.post(
            f"/api/v1/orders/{order['id']}/confirm",
            headers=confirm_headers
        )
        assert response.status_code == status.HTTP_200_OK
        # Should still succeed because order is already confirmed

        # Stock should still be 7
        response = test_client.get("/api/v1/books", headers=headers)
        final_book = response.json()[0]
        assert final_book["stock"] == 7
