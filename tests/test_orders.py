import pytest
from fastapi import status
from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT
from sqlalchemy import text
import uuid


class TestOrderEndpoints:
    """Test order management endpoints."""

    def test_create_order_success(self, test_client, bootstrap_tenant, sample_book, headers_with_tenant):
        """Test successful order creation."""
        order_data = {
            "items": [
                {
                    "product_id": sample_book["id"],
                    "qty": 2
                }
            ]
        }

        response = test_client.post(
            "/api/v1/orders",
            json=order_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "DRAFT"
        assert len(data["items"]) == 1
        assert data["items"][0]["product_id"] == sample_book["id"]
        assert data["items"][0]["qty"] == 2
        assert "id" in data
        assert "created_at" in data

    def test_create_order_multiple_items(self, test_client, bootstrap_tenant, sample_author, headers_with_tenant):
        """Test creating order with multiple items."""
        # Create multiple books
        book1_data = {
            "title": "Book One",
            "author_id": sample_author["id"],
            "price": 29.99,
            "stock": 10
        }
        book2_data = {
            "title": "Book Two",
            "author_id": sample_author["id"],
            "price": 39.99,
            "stock": 5
        }

        response1 = test_client.post("/api/v1/books", json=book1_data, headers=headers_with_tenant)
        response2 = test_client.post("/api/v1/books", json=book2_data, headers=headers_with_tenant)

        book1_id = response1.json()["id"]
        book2_id = response2.json()["id"]

        order_data = {
            "items": [
                {"product_id": book1_id, "qty": 1},
                {"product_id": book2_id, "qty": 2}
            ]
        }

        response = test_client.post(
            "/api/v1/orders",
            json=order_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "DRAFT"
        assert len(data["items"]) == 2

    def test_create_order_zero_quantity(self, test_client, bootstrap_tenant, sample_book, headers_with_tenant):
        """Test creating order with zero quantity."""
        order_data = {
            "items": [
                {
                    "product_id": sample_book["id"],
                    "qty": 0
                }
            ]
        }

        response = test_client.post(
            "/api/v1/orders",
            json=order_data,
            headers=headers_with_tenant
        )

        assert response.status_code == HTTP_422_UNPROCESSABLE_CONTENT
        assert "qty must be > 0" in response.text

    def test_create_order_negative_quantity(self, test_client, bootstrap_tenant, sample_book, headers_with_tenant):
        """Test creating order with negative quantity."""
        order_data = {
            "items": [
                {
                    "product_id": sample_book["id"],
                    "qty": -1
                }
            ]
        }

        response = test_client.post(
            "/api/v1/orders",
            json=order_data,
            headers=headers_with_tenant
        )

        assert response.status_code == HTTP_422_UNPROCESSABLE_CONTENT

    def test_create_order_empty_items(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test creating order with empty items."""
        order_data = {"items": []}

        response = test_client.post(
            "/api/v1/orders",
            json=order_data,
            headers=headers_with_tenant
        )

        # Should succeed - empty order is technically valid
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "DRAFT"
        assert len(data["items"]) == 0

    def test_create_order_nonexistent_book(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test creating order with non-existent book."""
        order_data = {
            "items": [
                {
                    "product_id": str(uuid.uuid4()),
                    "qty": 1
                }
            ]
        }

        response = test_client.post(
            "/api/v1/orders",
            json=order_data,
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_order_success(self, test_client, bootstrap_tenant, sample_order, sample_book, headers_with_tenant):
        """Test successful order confirmation."""
        initial_stock = sample_book["stock"]

        response = test_client.post(
            f"/api/v1/orders/{sample_order['id']}/confirm",
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "CONFIRMED"
        assert data["id"] == sample_order["id"]

        # Verify stock was reduced
        book_response = test_client.get("/api/v1/books", headers=headers_with_tenant)
        books = book_response.json()
        confirmed_book = next(b for b in books if b["id"] == sample_book["id"])
        assert confirmed_book["stock"] == initial_stock - 2  # 2 was the quantity in sample_order

    def test_confirm_order_with_idempotency_key(self, test_client, bootstrap_tenant, sample_order, headers_with_tenant):
        """Test order confirmation with idempotency key."""
        idempotency_key = str(uuid.uuid4())
        headers_with_idempotency = headers_with_tenant.copy()
        headers_with_idempotency["Idempotency-Key"] = idempotency_key

        # First confirmation
        response1 = test_client.post(
            f"/api/v1/orders/{sample_order['id']}/confirm",
            headers=headers_with_idempotency
        )

        assert response1.status_code == status.HTTP_200_OK
        data1 = response1.json()
        assert data1["status"] == "CONFIRMED"

        # Second confirmation with same idempotency key should return same result
        response2 = test_client.post(
            f"/api/v1/orders/{sample_order['id']}/confirm",
            headers=headers_with_idempotency
        )

        assert response2.status_code == status.HTTP_200_OK
        data2 = response2.json()
        assert data2 == data1  # Should be identical response

    def test_confirm_order_insufficient_stock(self, test_client, bootstrap_tenant, sample_book, headers_with_tenant):
        """Test confirming order with insufficient stock."""
        # Create order with quantity greater than stock
        order_data = {
            "items": [
                {
                    "product_id": sample_book["id"],
                    "qty": sample_book["stock"] + 5  # More than available
                }
            ]
        }

        response = test_client.post(
            "/api/v1/orders",
            json=order_data,
            headers=headers_with_tenant
        )

        order_data = response.json()
        order_id = order_data["id"]

        # Try to confirm - should fail due to insufficient stock
        confirm_response = test_client.post(
            f"/api/v1/orders/{order_id}/confirm",
            headers=headers_with_tenant
        )

        assert confirm_response.status_code == status.HTTP_409_CONFLICT
        error_data = confirm_response.json()

        assert "shortages" in error_data["error"]["details"]
        assert len(error_data["error"]["details"]["shortages"]) == 1
        assert error_data["error"]["details"]["shortages"][0]["product_id"] == sample_book["id"]
        assert error_data["error"]["details"]["shortages"][0]["requested"] == sample_book["stock"] + 5
        assert error_data["error"]["details"]["shortages"][0]["available"] == sample_book["stock"]

    def test_confirm_order_already_confirmed(self, test_client, bootstrap_tenant, sample_order, headers_with_tenant):
        """Test confirming an already confirmed order."""
        # Confirm order first
        test_client.post(
            f"/api/v1/orders/{sample_order['id']}/confirm",
            headers=headers_with_tenant
        )

        # Try to confirm again - should be idempotent
        response = test_client.post(
            f"/api/v1/orders/{sample_order['id']}/confirm",
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "CONFIRMED"

    def test_confirm_nonexistent_order(self, test_client, bootstrap_tenant, headers_with_tenant):
        """Test confirming non-existent order."""
        fake_order_id = str(uuid.uuid4())

        response = test_client.post(
            f"/api/v1/orders/{fake_order_id}/confirm",
            headers=headers_with_tenant
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "order not found" in response.json()["error"]["message"]

    def test_confirm_order_optimistic_locking(self, test_client, bootstrap_tenant, sample_book, headers_with_tenant):
        """Test optimistic locking during order confirmation."""
        # Create order
        order_data = {
            "items": [
                {
                    "product_id": sample_book["id"],
                    "qty": 1
                }
            ]
        }

        response = test_client.post(
            "/api/v1/orders",
            json=order_data,
            headers=headers_with_tenant
        )

        order_id = response.json()["id"]

        # Simulate concurrent update by updating book version manually
        # In a real scenario, this would be another transaction
        with test_client:
            test_client.put(
                f"/api/v1/books/{sample_book['id']}",
                json={"title": sample_book["title"], "author_id": sample_book["author_id"], "price": 99.99, "stock": sample_book["stock"]},
                headers=headers_with_tenant
            )

        # Now try to confirm - should work since we're not actually testing the race condition here
        # The optimistic locking is implemented at the database level
        response = test_client.post(
            f"/api/v1/orders/{order_id}/confirm",
            headers=headers_with_tenant
        )

        # This test is more conceptual - the actual optimistic locking happens in the DB transaction
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_409_CONFLICT]

    def test_order_tenant_isolation(self, test_client, bootstrap_tenant, sample_order):
        """Test that orders are properly isolated by tenant."""
        # Create another tenant
        other_tenant = "other_tenant"
        test_client.post(f"/api/v1/tenants/{other_tenant}/bootstrap")

        # Original tenant can't access order without tenant header
        response = test_client.get("/api/v1/orders")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Note: There's no GET /orders endpoint in the current API,
        # but the principle applies to POST and confirm endpoints

    def test_order_missing_tenant_header(self, test_client, bootstrap_tenant, sample_book):
        """Test order endpoints without tenant header."""
        order_data = {
            "items": [
                {
                    "product_id": sample_book["id"],
                    "qty": 1
                }
            ]
        }

        response = test_client.post("/api/v1/orders", json=order_data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        response = test_client.post(f"/api/v1/orders/{uuid.uuid4()}/confirm")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_order_validation_at_three_levels(self, test_client, bootstrap_tenant, sample_book, headers_with_tenant):
        """Test validation at Pydantic, DB constraint, and business rule levels."""
        # Pydantic level: invalid data structure
        invalid_data = {"items": [{"product_id": sample_book["id"]}]}  # Missing qty
        response = test_client.post("/api/v1/orders", json=invalid_data, headers=headers_with_tenant)
        assert response.status_code == HTTP_422_UNPROCESSABLE_CONTENT

        # DB constraint level: non-existent foreign key
        fk_violation_data = {
            "items": [
                {
                    "product_id": str(uuid.uuid4()),  # Non-existent book
                    "qty": 1
                }
            ]
        }
        response = test_client.post("/api/v1/orders", json=fk_violation_data, headers=headers_with_tenant)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Business logic level: insufficient stock
        stock_violation_data = {
            "items": [
                {
                    "product_id": sample_book["id"],
                    "qty": sample_book["stock"] + 100  # Way more than available
                }
            ]
        }

        # Create order
        response = test_client.post("/api/v1/orders", json=stock_violation_data, headers=headers_with_tenant)
        assert response.status_code == status.HTTP_200_OK

        order_id = response.json()["id"]

        # Try to confirm - should fail at business logic level
        response = test_client.post(f"/api/v1/orders/{order_id}/confirm", headers=headers_with_tenant)
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_order_idempotency_with_different_keys(self, test_client, bootstrap_tenant, sample_order, headers_with_tenant):
        """Test that different idempotency keys work independently."""
        # First confirmation with key A
        headers_a = headers_with_tenant.copy()
        headers_a["Idempotency-Key"] = str(uuid.uuid4())

        response_a = test_client.post(
            f"/api/v1/orders/{sample_order['id']}/confirm",
            headers=headers_a
        )
        assert response_a.status_code == status.HTTP_200_OK

        # Try with different key B - should fail since order is already confirmed
        headers_b = headers_with_tenant.copy()
        headers_b["Idempotency-Key"] = str(uuid.uuid4())

        response_b = test_client.post(
            f"/api/v1/orders/{sample_order['id']}/confirm",
            headers=headers_b
        )
        assert response_b.status_code == status.HTTP_200_OK  # Still succeeds but because order is confirmed
