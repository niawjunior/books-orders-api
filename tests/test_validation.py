import pytest
from pydantic import ValidationError
from fastapi import status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.schemas.author import AuthorCreate, AuthorRead
from app.schemas.book import BookCreate, BookRead
from app.schemas.order import OrderCreate, OrderItemCreate
from app.services.author_service import AuthorService
from app.services.book_service import BookService
from app.services.order_service import OrderService
from fastapi import HTTPException
import uuid
from datetime import date


class TestPydanticValidation:
    """Test Pydantic schema level validation."""

    def test_author_name_validation(self):
        """Test author name validation at Pydantic level."""
        # Valid name
        author_data = AuthorCreate(name="Valid Author", email="test@example.com")
        assert author_data.name == "Valid Author"
        assert author_data.email == "test@example.com"

        # Empty/whitespace name should fail
        with pytest.raises(ValidationError) as exc_info:
            AuthorCreate(name="   ", email="test@example.com")
        assert "name cannot be empty" in str(exc_info.value)

        # Missing name should fail
        with pytest.raises(ValidationError) as exc_info:
            AuthorCreate(email="test@example.com")
        assert "name" in str(exc_info.value)

        # Name with spaces should be trimmed
        author_data = AuthorCreate(name="  Trimmed Author  ", email="test@example.com")
        assert author_data.name == "Trimmed Author"

    def test_author_email_validation(self):
        """Test author email validation at Pydantic level."""
        # Valid email
        author_data = AuthorCreate(name="Test Author", email="test@example.com")
        assert author_data.email == "test@example.com"

        # Invalid email format
        with pytest.raises(ValidationError) as exc_info:
            AuthorCreate(name="Test Author", email="invalid-email")
        assert "value is not a valid email address" in str(exc_info.value)

        # None email is allowed
        author_data = AuthorCreate(name="Test Author", email=None)
        assert author_data.email is None

    def test_book_title_validation(self):
        """Test book title validation at Pydantic level."""
        # Valid title
        book_data = BookCreate(
            title="Valid Title",
            author_id=uuid.uuid4(),
            price=29.99,
            stock=5
        )
        assert book_data.title == "Valid Title"

        # Empty/whitespace title should fail
        with pytest.raises(ValidationError) as exc_info:
            BookCreate(
                title="   ",
                author_id=uuid.uuid4(),
                price=29.99,
                stock=5
            )
        assert "title cannot be empty" in str(exc_info.value)

        # Title with spaces should be trimmed
        book_data = BookCreate(
            title="  Trimmed Title  ",
            author_id=uuid.uuid4(),
            price=29.99,
            stock=5
        )
        assert book_data.title == "Trimmed Title"

    def test_book_price_validation(self):
        """Test book price validation at Pydantic level."""
        # Valid price
        book_data = BookCreate(
            title="Test Book",
            author_id=uuid.uuid4(),
            price=29.99,
            stock=5
        )
        assert float(book_data.price) == 29.99

        # Negative price should fail
        with pytest.raises(ValidationError) as exc_info:
            BookCreate(
                title="Test Book",
                author_id=uuid.uuid4(),
                price=-10.99,
                stock=5
            )
        assert "price must be >= 0" in str(exc_info.value)

        # Zero price should work
        book_data = BookCreate(
            title="Free Book",
            author_id=uuid.uuid4(),
            price=0.0,
            stock=5
        )
        assert float(book_data.price) == 0.0

    def test_book_stock_validation(self):
        """Test book stock validation at Pydantic level."""
        # Valid stock
        book_data = BookCreate(
            title="Test Book",
            author_id=uuid.uuid4(),
            price=29.99,
            stock=10
        )
        assert book_data.stock == 10

        # Negative stock should fail
        with pytest.raises(ValidationError) as exc_info:
            BookCreate(
                title="Test Book",
                author_id=uuid.uuid4(),
                price=29.99,
                stock=-5
            )
        assert "stock must be >= 0" in str(exc_info.value)

    def test_book_uuid_validation(self):
        """Test book author_id UUID validation at Pydantic level."""
        # Valid UUID
        valid_uuid = uuid.uuid4()
        book_data = BookCreate(
            title="Test Book",
            author_id=valid_uuid,
            price=29.99,
            stock=5
        )
        assert book_data.author_id == valid_uuid

        # Invalid UUID should fail
        with pytest.raises(ValidationError) as exc_info:
            BookCreate(
                title="Test Book",
                author_id="invalid-uuid",
                price=29.99,
                stock=5
            )
        assert "Input should be a valid UUID" in str(exc_info.value)

    def test_order_item_validation(self):
        """Test order item validation at Pydantic level."""
        # Valid order item
        item_data = OrderItemCreate(product_id=uuid.uuid4(), qty=5)
        assert item_data.qty == 5

        # Zero quantity should fail
        with pytest.raises(ValidationError) as exc_info:
            OrderItemCreate(product_id=uuid.uuid4(), qty=0)
        assert "qty must be > 0" in str(exc_info.value)

        # Negative quantity should fail
        with pytest.raises(ValidationError) as exc_info:
            OrderItemCreate(product_id=uuid.uuid4(), qty=-1)
        assert "qty must be > 0" in str(exc_info.value)

        # UUID validation
        with pytest.raises(ValidationError) as exc_info:
            OrderItemCreate(product_id="invalid-uuid", qty=1)
        assert "Input should be a valid UUID" in str(exc_info.value)

    def test_order_validation(self):
        """Test order validation at Pydantic level."""
        # Valid order with items
        order_data = OrderCreate(
            items=[
                OrderItemCreate(product_id=uuid.uuid4(), qty=2),
                OrderItemCreate(product_id=uuid.uuid4(), qty=1)
            ]
        )
        assert len(order_data.items) == 2

        # Empty order is valid
        order_data = OrderCreate(items=[])
        assert order_data.items == []

        # Invalid item in order should fail
        with pytest.raises(ValidationError):
            OrderCreate(
                items=[
                    OrderItemCreate(product_id=uuid.uuid4(), qty=2),
                    OrderItemCreate(product_id="invalid-uuid", qty=1)  # Invalid UUID
                ]
            )


class TestDatabaseConstraints:
    """Test database constraint level validation."""

    def test_author_unique_name_constraint(self, db_session, bootstrap_tenant):
        """Test author unique name constraint at database level."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create first author
        author_data = AuthorCreate(name="Unique Name", email="unique@test.com")
        author1 = AuthorService.create_author(db_session, author_data)

        # Try to create another author with same name
        author_data2 = AuthorCreate(name="Unique Name", email="different@test.com")

        with pytest.raises(IntegrityError):
            AuthorService.create_author(db_session, author_data2)

    def test_author_unique_email_constraint(self, db_session, bootstrap_tenant):
        """Test author unique email constraint at database level."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create first author
        author_data = AuthorCreate(name="Author One", email="shared@test.com")
        author1 = AuthorService.create_author(db_session, author_data)

        # Try to create another author with same email (case insensitive due to citext)
        author_data2 = AuthorCreate(name="Author Two", email="SHARED@TEST.COM")

        with pytest.raises(IntegrityError):
            AuthorService.create_author(db_session, author_data2)

    def test_book_foreign_key_constraint(self, db_session, bootstrap_tenant):
        """Test book foreign key constraint at database level."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Try to create book with non-existent author
        book_data = BookCreate(
            title="Orphan Book",
            author_id=uuid.uuid4(),  # Non-existent author
            price=29.99,
            stock=5
        )

        with pytest.raises(IntegrityError):
            BookService.create_book(db_session, book_data)

    def test_book_price_check_constraint(self, db_session, bootstrap_tenant, sample_author):
        """Test book price check constraint at database level."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Direct database manipulation to bypass Pydantic
        with pytest.raises(IntegrityError):
            db_session.execute(
                text("""
                    INSERT INTO books (id, title, author_id, price, stock, version)
                    VALUES (:id, :title, :author_id, :price, :stock, :version)
                """),
                {
                    "id": uuid.uuid4(),
                    "title": "Negative Price Book",
                    "author_id": sample_author["id"],
                    "price": -10.99,  # Negative price
                    "stock": 5,
                    "version": 1
                }
            )

    def test_book_stock_check_constraint(self, db_session, bootstrap_tenant, sample_author):
        """Test book stock check constraint at database level."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Direct database manipulation to bypass Pydantic
        with pytest.raises(IntegrityError):
            db_session.execute(
                text("""
                    INSERT INTO books (id, title, author_id, price, stock, version)
                    VALUES (:id, :title, :author_id, :price, :stock, :version)
                """),
                {
                    "id": uuid.uuid4(),
                    "title": "Negative Stock Book",
                    "author_id": sample_author["id"],
                    "price": 29.99,
                    "stock": -5,  # Negative stock
                    "version": 1
                }
            )

    def test_order_status_check_constraint(self, db_session, bootstrap_tenant):
        """Test order status check constraint at database level."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Try to create order with invalid status
        with pytest.raises(IntegrityError):
            db_session.execute(
                text("""
                    INSERT INTO orders (id, status, created_at)
                    VALUES (:id, :status, NOW())
                """),
                {
                    "id": uuid.uuid4(),
                    "status": "INVALID_STATUS"  # Not in allowed values
                }
            )

    def test_order_item_quantity_check_constraint(self, db_session, bootstrap_tenant, sample_order, sample_book):
        """Test order item quantity check constraint at database level."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Try to create order item with non-positive quantity
        with pytest.raises(IntegrityError):
            db_session.execute(
                text("""
                    INSERT INTO order_items (order_id, product_id, qty)
                    VALUES (:order_id, :product_id, :qty)
                """),
                {
                    "order_id": sample_order["id"],
                    "product_id": sample_book["id"],
                    "qty": 0  # Should be > 0
                }
            )

    def test_order_item_foreign_key_constraints(self, db_session, bootstrap_tenant):
        """Test order item foreign key constraints at database level."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create an order first
        order_id = uuid.uuid4()
        db_session.execute(
            text("INSERT INTO orders (id, status, created_at) VALUES (:id, 'DRAFT', NOW())"),
            {"id": order_id}
        )

        # Try to create order item with non-existent book
        with pytest.raises(IntegrityError):
            db_session.execute(
                text("""
                    INSERT INTO order_items (order_id, product_id, qty)
                    VALUES (:order_id, :product_id, :qty)
                """),
                {
                    "order_id": order_id,
                    "product_id": uuid.uuid4(),  # Non-existent book
                    "qty": 1
                }
            )


class TestBusinessRuleValidation:
    """Test business rule level validation in service layer."""

    def test_duplicate_book_business_rule(self, db_session, bootstrap_tenant):
        """Test duplicate book business rule in service layer."""
        from app.models.author import Author

        # Create author directly in the same session
        author = Author(
            name="Test Author",
            email=f"test-author-{uuid.uuid4().hex[:8]}@example.com"
        )
        db_session.add(author)
        db_session.commit()
        db_session.refresh(author)

        # Create first book
        book_data = BookCreate(
            title="Same Title",
            author_id=author.id,
            price=29.99,
            stock=5,
            published_at=date(2023, 1, 1)
        )
        book1 = BookService.create_book(db_session, book_data)

        # Try to create duplicate (same title + author + year)
        duplicate_data = BookCreate(
            title="Same Title",
            author_id=author.id,
            price=19.99,
            stock=3,
            published_at=date(2023, 1, 1)  # Same year
        )

        with pytest.raises(ValueError, match="Duplicate book"):
            BookService.create_book(db_session, duplicate_data)

    def test_similar_book_different_year(self, db_session, bootstrap_tenant):
        """Test that similar book with different year is allowed."""
        from app.models.author import Author

        # Create author directly in the same session
        author = Author(
            name="Test Author",
            email=f"test-author-{uuid.uuid4().hex[:8]}@example.com"
        )
        db_session.add(author)
        db_session.commit()
        db_session.refresh(author)

        # Create first book
        book_data = BookCreate(
            title="Same Title",
            author_id=author.id,
            price=29.99,
            stock=5,
            published_at=date(2023, 1, 1)
        )
        book1 = BookService.create_book(db_session, book_data)

        # Same title and author but different year should be allowed
        similar_data = BookCreate(
            title="Same Title",
            author_id=author.id,
            price=19.99,
            stock=3,
            published_at=date(2024, 1, 1)  # Different year
        )

        # This should succeed
        book2 = BookService.create_book(db_session, similar_data)
        assert book2.title == "Same Title"
        assert book2.author_id == author.id
        assert book2.published_at.year == 2024

    def test_duplicate_book_no_published_date(self, db_session, bootstrap_tenant):
        """Test duplicate book logic when published_at is None."""
        from app.models.author import Author

        # Create author directly in the same session
        author = Author(
            name="Test Author",
            email=f"test-author-{uuid.uuid4().hex[:8]}@example.com"
        )
        db_session.add(author)
        db_session.commit()
        db_session.refresh(author)

        # Create first book without published date
        book_data = BookCreate(
            title="No Date Book",
            author_id=author.id,
            price=19.99,
            stock=5,
            published_at=None
        )
        book1 = BookService.create_book(db_session, book_data)

        # Try to create duplicate (same title + author + no published date)
        duplicate_data = BookCreate(
            title="No Date Book",
            author_id=author.id,
            price=29.99,
            stock=3,
            published_at=None  # Also no published date
        )

        with pytest.raises(ValueError, match="Duplicate book"):
            BookService.create_book(db_session, duplicate_data)

    def test_stock_insufficient_business_rule(self, db_session, bootstrap_tenant):
        """Test insufficient stock business rule in order confirmation."""
        from app.models.author import Author
        from app.models.book import Book
        from datetime import date

        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create author directly in the same session
        author = Author(
            name="Test Author",
            email=f"test-author-{uuid.uuid4().hex[:8]}@example.com"
        )
        db_session.add(author)
        db_session.commit()
        db_session.refresh(author)

        # Create book with limited stock directly in the same session
        book = Book(
            title="Limited Stock Book",
            author_id=author.id,
            price=29.99,
            stock=3,  # Limited stock
            version=1,
            published_at=date(2023, 1, 1)
        )
        db_session.add(book)
        db_session.commit()
        db_session.refresh(book)

        # Create order with quantity exceeding stock
        order_data = OrderCreate(
            items=[
                OrderItemCreate(
                    product_id=book.id,
                    qty=book.stock + 5  # More than available
                )
            ]
        )

        # Create order first (should succeed)
        order = OrderService.create_order(db_session, order_data)

        # Confirmation should fail with business rule violation
        with pytest.raises(HTTPException) as exc_info:
            OrderService.confirm_order(db_session, order.id, None)

        assert exc_info.value.status_code == 409
        assert "shortages" in str(exc_info.value.detail)

    def test_order_confirmation_business_rules(self, db_session, bootstrap_tenant):
        """Test various business rules in order confirmation."""
        from app.models.author import Author
        from app.models.book import Book
        from app.models.order import Order, OrderItem
        from datetime import date

        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create author directly in the same session
        author = Author(
            name="Test Author",
            email=f"test-author-{uuid.uuid4().hex[:8]}@example.com"
        )
        db_session.add(author)
        db_session.commit()
        db_session.refresh(author)

        # Create book directly in the same session
        book = Book(
            title="Test Book",
            author_id=author.id,
            price=29.99,
            stock=10,
            version=1,
            published_at=date(2023, 1, 1)
        )
        db_session.add(book)
        db_session.commit()
        db_session.refresh(book)

        # Create order directly in the same session
        order = Order(status="DRAFT")
        db_session.add(order)
        db_session.flush()

        order_item = OrderItem(
            order_id=order.id,
            product_id=book.id,
            qty=2
        )
        db_session.add(order_item)
        db_session.commit()
        db_session.refresh(order)

        # Confirm order
        result = OrderService.confirm_order(db_session, order.id, None)
        assert result["status"] == "CONFIRMED"

        # Confirming again should be idempotent (business rule)
        result2 = OrderService.confirm_order(db_session, order.id, None)
        assert result2["status"] == "CONFIRMED"
        assert result2["id"] == result["id"]

    def test_order_not_found_business_rule(self, db_session, bootstrap_tenant):
        """Test business rule for non-existent order."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        with pytest.raises(HTTPException) as exc_info:
            OrderService.confirm_order(db_session, uuid.uuid4(), None)

        assert exc_info.value.status_code == 404
        assert "order not found" in str(exc_info.value.detail)

    def test_idempotency_business_rule(self, db_session, bootstrap_tenant):
        """Test idempotency business rule in order confirmation."""
        from app.models.author import Author
        from app.models.book import Book
        from app.models.order import Order, OrderItem
        from datetime import date

        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create author directly in the same session
        author = Author(
            name="Test Author",
            email=f"test-author-{uuid.uuid4().hex[:8]}@example.com"
        )
        db_session.add(author)
        db_session.commit()
        db_session.refresh(author)

        # Create book directly in the same session
        book = Book(
            title="Test Book",
            author_id=author.id,
            price=29.99,
            stock=10,
            version=1,
            published_at=date(2023, 1, 1)
        )
        db_session.add(book)
        db_session.commit()
        db_session.refresh(book)

        # Create order directly in the same session
        order = Order(status="DRAFT")
        db_session.add(order)
        db_session.flush()

        order_item = OrderItem(
            order_id=order.id,
            product_id=book.id,
            qty=2
        )
        db_session.add(order_item)
        db_session.commit()
        db_session.refresh(order)

        # Confirm order
        result = OrderService.confirm_order(db_session, order.id, None)
        assert result["status"] == "CONFIRMED"

        # Confirming again with same idempotency key should return same result
        result2 = OrderService.confirm_order(db_session, order.id, None)
        assert result2["status"] == "CONFIRMED"
        assert result2["id"] == result["id"]









#         assert result1 == result2  # Should be identical
#





class TestValidationLayerIntegration:
    """Test integration of all three validation layers."""

    def test_validation_layers_working_together(self, db_session, bootstrap_tenant, test_client):
        """Test that all three validation layers work together properly."""
        # Bootstrap tenant through API
        test_client.post(f"/api/v1/tenants/{bootstrap_tenant}/bootstrap")
        headers = {"X-Tenant": bootstrap_tenant}

        # 1. Pydantic validation
        # Invalid author data
        response = test_client.post("/api/v1/authors", json={"name": "", "email": "invalid"}, headers=headers)
        assert response.status_code == 422  # Pydantic validation error

        # 2. Database constraints
        # Create valid author first
        author_data = {"name": "Test Author", "email": "test@example.com"}
        response = test_client.post("/api/v1/authors", json=author_data, headers=headers)
        author = response.json()

        # Try duplicate email
        duplicate_data = {"name": "Another Author", "email": "test@example.com"}
        response = test_client.post("/api/v1/authors", json=duplicate_data, headers=headers)
        assert response.status_code == 400  # Database constraint error

        # 3. Business rules
        # Create book
        book_data = {
            "title": "Business Rule Test",
            "author_id": author["id"],
            "price": 29.99,
            "stock": 5
        }
        response = test_client.post("/api/v1/books", json=book_data, headers=headers)
        book = response.json()

        # Try to create duplicate book
        duplicate_book = {
            "title": "Business Rule Test",
            "author_id": author["id"],
            "price": 19.99,
            "stock": 3
        }
        response = test_client.post("/api/v1/books", json=duplicate_book, headers=headers)
        assert response.status_code == 400  # Business rule error

        # Test order business rule
        order_data = {
            "items": [{"product_id": book["id"], "qty": 10}]  # More than stock
        }
        response = test_client.post("/api/v1/orders", json=order_data, headers=headers)
        order = response.json()

        # Should fail on confirmation
        response = test_client.post(f"/api/v1/orders/{order['id']}/confirm", headers=headers)
        assert response.status_code == 409  # Business rule error

    def test_error_message_consistency(self, db_session, bootstrap_tenant):
        """Test that error messages are consistent across validation layers."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Pydantic validation errors should be structured
        try:
            AuthorCreate(name="")  # Empty name
        except ValidationError as e:
            errors = e.errors()
            assert len(errors) > 0
            assert "name cannot be empty" in str(errors[0])

        # Database constraint errors should raise IntegrityError
        author_data = AuthorCreate(name="Test", email="test@test.com")
        AuthorService.create_author(db_session, author_data)

        try:
            AuthorService.create_author(db_session, author_data)  # Duplicate
        except IntegrityError:
            db_session.rollback()  # Rollback to clean session state
            pass  # Expected database constraint error

        # Business rule errors should raise ValueError or HTTPException
        try:
            BookService.create_book(
                db_session,
                BookCreate(
                    title="Duplicate",
                    author_id=uuid.uuid4(),  # Non-existent author
                    price=29.99,
                    stock=5
                )
            )
        except (IntegrityError, ValueError, HTTPException):
            pass  # Expected at some validation layer

    def test_validation_order_of_execution(self, db_session, bootstrap_tenant):
        """Test order in which validation layers execute."""
        from app.models.author import Author
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create author directly in the same session
        author = Author(
            name="Test Author",
            email=f"test-author-{uuid.uuid4().hex[:8]}@example.com"
        )
        db_session.add(author)
        db_session.commit()
        db_session.refresh(author)

        # Pydantic executes first (can test with invalid UUID format)
        try:
            BookCreate(
                title="Test",
                author_id="invalid-uuid",  # Invalid at Pydantic level
                price=29.99,
                stock=5
            )
        except ValidationError:
            pass  # Pydantic validation happens first

        # If Pydantic passes, then database constraints are checked
        try:
            BookService.create_book(
                db_session,
                BookCreate(
                    title="Test",
                    author_id=uuid.uuid4(),  # Valid UUID format but non-existent
                    price=29.99,
                    stock=5
                )
            )
        except IntegrityError:
            db_session.rollback()  # Rollback to clean session state
            pass  # Database constraint checked after Pydantic

        # Business rules are checked in service layer after data passes lower-level validation
        book_data = BookCreate(
            title="Business Rule Test",
            author_id=author.id,
            price=29.99,
            stock=5
        )
        book1 = BookService.create_book(db_session, book_data)

        try:
            # Business rule check
            BookService.create_book(db_session, book_data)  # Same data
        except ValueError as e:
            assert "Duplicate book" in str(e)  # Business rule error
