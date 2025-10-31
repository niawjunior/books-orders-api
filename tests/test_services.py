import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.services.author_service import AuthorService
from app.services.book_service import BookService
from app.services.order_service import OrderService
from app.schemas.author import AuthorCreate
from app.schemas.book import BookCreate
from app.schemas.order import OrderCreate, OrderItemCreate
from app.models.author import Author
from app.models.book import Book
from app.models.order import Order
from fastapi import HTTPException
import uuid
from datetime import date


class TestAuthorService:
    """Test author service layer."""

    def test_create_author_success(self, db_session, bootstrap_tenant):
        """Test successful author creation through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        author_data = AuthorCreate(name="Service Test Author", email="service@test.com")
        author = AuthorService.create_author(db_session, author_data)

        assert author.name == "Service Test Author"
        assert author.email == "service@test.com"
        assert author.id is not None

    def test_list_authors_empty(self, db_session, bootstrap_tenant):
        """Test listing authors when none exist through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        authors = AuthorService.list_authors(db_session)
        assert authors == []

    def test_list_authors_with_data(self, db_session, bootstrap_tenant, sample_author_model):
        """Test listing authors with existing data through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        authors = AuthorService.list_authors(db_session)
        assert len(authors) == 1
        assert authors[0].id == sample_author_model.id
        assert authors[0].name == sample_author_model.name

    def test_author_service_error_handling(self, db_session, bootstrap_tenant):
        """Test service error handling for author operations."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Test with invalid data that would cause database errors
        author_data = AuthorCreate(name="Test Author", email="test@author.com")

        # Create first author
        author1 = AuthorService.create_author(db_session, author_data)
        assert author1.id is not None

        # Try to create author with duplicate email - should fail at DB constraint
        author_data2 = AuthorCreate(name="Different Name", email="test@author.com")

        with pytest.raises(Exception):  # Should raise database integrity error
            AuthorService.create_author(db_session, author_data2)


class TestBookService:
    """Test book service layer."""

    def test_create_book_success(self, db_session, bootstrap_tenant, sample_author_model):
        """Test successful book creation through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        book_data = BookCreate(
            title="Service Test Book",
            author_id=sample_author_model.id,
            price=29.99,
            stock=10,
            published_at=date(2023, 1, 1)
        )
        book = BookService.create_book(db_session, book_data)

        assert book.title == "Service Test Book"
        assert book.author_id == sample_author_model.id
        assert float(book.price) == 29.99
        assert book.stock == 10
        assert book.version == 1

    def test_create_duplicate_book_business_rule(self, db_session, bootstrap_tenant, sample_author_model):
        """Test business rule: prevent duplicate books (title + author + year)."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create first book
        book_data1 = BookCreate(
            title="Same Title",
            author_id=sample_author_model.id,
            price=19.99,
            stock=5,
            published_at=date(2023, 5, 15)
        )
        book1 = BookService.create_book(db_session, book_data1)
        assert book1.id is not None

        # Try to create duplicate (same title + author + year)
        book_data2 = BookCreate(
            title="Same Title",
            author_id=sample_author_model.id,
            price=25.99,
            stock=3,
            published_at=date(2023, 5, 15)  # Same year
        )

        with pytest.raises(ValueError, match="Duplicate book"):
            BookService.create_book(db_session, book_data2)

    def test_create_similar_book_different_year(self, db_session, bootstrap_tenant, sample_author_model):
        """Test that similar book with different year is allowed."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create first book
        book_data1 = BookCreate(
            title="Same Title",
            author_id=sample_author_model.id,
            price=19.99,
            stock=5,
            published_at=date(2023, 5, 15)
        )
        book1 = BookService.create_book(db_session, book_data1)
        assert book1.id is not None

        # Create similar book with different year (should be allowed)
        book_data2 = BookCreate(
            title="Same Title",
            author_id=sample_author_model.id,
            price=25.99,
            stock=3,
            published_at=date(2024, 5, 15)  # Different year
        )
        book2 = BookService.create_book(db_session, book_data2)
        assert book2.id is not None
        assert book2.id != book1.id

    def test_create_duplicate_book_no_published_date(self, db_session, bootstrap_tenant, sample_author_model):
        """Test duplicate book logic when published_at is None."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create first book without published date
        book_data1 = BookCreate(
            title="No Date Book",
            author_id=sample_author_model.id,
            price=19.99,
            stock=5,
            published_at=None
        )
        book1 = BookService.create_book(db_session, book_data1)
        assert book1.id is not None

        # Try to create duplicate (same title + author + no date)
        book_data2 = BookCreate(
            title="No Date Book",
            author_id=sample_author_model.id,
            price=25.99,
            stock=3,
            published_at=None
        )

        with pytest.raises(ValueError, match="Duplicate book"):
            BookService.create_book(db_session, book_data2)

    def test_list_books_empty(self, db_session, bootstrap_tenant):
        """Test listing books when none exist through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        books = BookService.list_books(db_session)
        assert books == []

    def test_list_books_with_filters(self, db_session, bootstrap_tenant, sample_author_model):
        """Test listing books with various filters through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create multiple books
        books_data = [
            BookCreate(title="Alpha Book", author_id=sample_author_model.id, price=10.99, stock=5),
            BookCreate(title="Beta Book", author_id=sample_author_model.id, price=20.99, stock=3),
            BookCreate(title="Alpha Second", author_id=sample_author_model.id, price=15.99, stock=8),
        ]

        for book_data in books_data:
            BookService.create_book(db_session, book_data)

        # Test search filter
        books = BookService.list_books(db_session, q="Alpha")
        assert len(books) == 2
        assert all("Alpha" in book.title for book in books)

        # Test author filter
        books = BookService.list_books(db_session, author_id=sample_author_model.id)
        assert len(books) == 3

        # Test sort by title
        books = BookService.list_books(db_session, sort="title")
        titles = [book.title for book in books]
        assert titles == sorted(titles)

        # Test pagination
        books = BookService.list_books(db_session, limit=2, offset=1)
        assert len(books) == 2

    def test_list_books_nonexistent_author(self, db_session, bootstrap_tenant):
        """Test listing books with non-existent author ID."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        books = BookService.list_books(db_session, author_id=uuid.uuid4())
        assert books == []


class TestOrderService:
    """Test order service layer."""

    def test_create_order_success(self, db_session, bootstrap_tenant, sample_book_model):
        """Test successful order creation through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        order_data = OrderCreate(
            items=[OrderItemCreate(product_id=sample_book_model.id, qty=2)]
        )
        order = OrderService.create_order(db_session, order_data)

        assert order.status == "DRAFT"
        assert order.id is not None
        assert len(order.items) == 1
        assert order.items[0].product_id == sample_book_model.id
        assert order.items[0].qty == 2

    def test_create_order_multiple_items(self, db_session, bootstrap_tenant, sample_author_model):
        """Test creating order with multiple items through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create multiple books
        book1_data = BookCreate(title="Book One", author_id=sample_author_model.id, price=10.99, stock=5)
        book2_data = BookCreate(title="Book Two", author_id=sample_author_model.id, price=15.99, stock=8)

        book1 = BookService.create_book(db_session, book1_data)
        book2 = BookService.create_book(db_session, book2_data)

        order_data = OrderCreate(
            items=[
                OrderItemCreate(product_id=book1.id, qty=1),
                OrderItemCreate(product_id=book2.id, qty=2)
            ]
        )
        order = OrderService.create_order(db_session, order_data)

        assert order.status == "DRAFT"
        assert len(order.items) == 2

    def test_create_order_empty_items(self, db_session, bootstrap_tenant):
        """Test creating order with empty items through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        order_data = OrderCreate(items=[])
        order = OrderService.create_order(db_session, order_data)

        assert order.status == "DRAFT"
        assert len(order.items) == 0

    def test_confirm_order_success(self, db_session, bootstrap_tenant, sample_order_model, sample_book_model):
        """Test successful order confirmation through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        initial_stock = sample_book_model.stock

        result = OrderService.confirm_order(db_session, sample_order_model.id, None)

        assert result["status"] == "CONFIRMED"
        assert result["id"] == str(sample_order_model.id)

        # Verify stock was reduced
        updated_book = BookService.list_books(db_session)[0]  # Get the updated book
        assert updated_book.stock == initial_stock - 2  # 2 was the quantity in sample_order_model

    def test_confirm_order_with_idempotency(self, db_session, bootstrap_tenant, sample_order_model):
        """Test order confirmation with idempotency through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        idempotency_key = "test-idempotency-key"

        # First confirmation
        result1 = OrderService.confirm_order(db_session, sample_order_model.id, idempotency_key)
        assert result1["status"] == "CONFIRMED"

        # Second confirmation with same key should return same result
        result2 = OrderService.confirm_order(db_session, sample_order_model.id, idempotency_key)
        assert result2 == result1  # Should be identical

    def test_confirm_order_insufficient_stock(self, db_session, bootstrap_tenant, sample_book_model):
        """Test confirming order with insufficient stock through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create order with quantity greater than stock
        order_data = OrderCreate(
            items=[OrderItemCreate(product_id=sample_book_model.id, qty=sample_book_model.stock + 5)]
        )
        order = OrderService.create_order(db_session, order_data)

        with pytest.raises(HTTPException) as exc_info:
            OrderService.confirm_order(db_session, order.id, None)

        assert exc_info.value.status_code == 409
        assert "shortages" in str(exc_info.value.detail)

    def test_confirm_nonexistent_order(self, db_session, bootstrap_tenant):
        """Test confirming non-existent order through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        with pytest.raises(HTTPException) as exc_info:
            OrderService.confirm_order(db_session, uuid.uuid4(), None)

        assert exc_info.value.status_code == 404
        assert "order not found" in str(exc_info.value.detail)

    def test_confirm_already_confirmed_order(self, db_session, bootstrap_tenant, sample_order_model):
        """Test confirming an already confirmed order through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Confirm order first
        OrderService.confirm_order(db_session, sample_order_model.id, None)

        # Try to confirm again - should be idempotent
        result = OrderService.confirm_order(db_session, sample_order_model.id, None)

        assert result["status"] == "CONFIRMED"
        assert result["id"] == str(sample_order_model.id)

    def test_confirm_order_stock_shortages_detail(self, db_session, bootstrap_tenant, sample_book_model):
        """Test detailed stock shortage information through service."""
        db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

        # Create order that will have stock shortage
        order_data = OrderCreate(
            items=[OrderItemCreate(product_id=sample_book_model.id, qty=sample_book_model.stock + 10)]
        )
        order = OrderService.create_order(db_session, order_data)

        with pytest.raises(HTTPException) as exc_info:
            OrderService.confirm_order(db_session, order.id, None)

        assert exc_info.value.status_code == 409
        detail = exc_info.value.detail
        assert "shortages" in detail
        assert len(detail["shortages"]) == 1
        shortage = detail["shortages"][0]
        assert shortage["product_id"] == str(sample_book_model.id)
        assert shortage["requested"] == sample_book_model.stock + 10
        assert shortage["available"] == sample_book_model.stock

    def test_confirm_order_multiple_items_partial_shortage(self, db_session, bootstrap_tenant, sample_author_model):
        """Test order confirmation with multiple items and partial shortages."""
        db_session.execute(text(f"SET search_path TO {bootstrap_tenant}, public"))

        # Create books with different stock levels
        book1_data = BookCreate(title="Book 1", author_id=sample_author_model.id, price=10.99, stock=10)
        book2_data = BookCreate(title="Book 2", author_id=sample_author_model.id, price=15.99, stock=2)

        book1 = BookService.create_book(db_session, book1_data)
        book2 = BookService.create_book(db_session, book2_data)

        # Create order that will exceed stock for book2
        order_data = OrderCreate(
            items=[
                OrderItemCreate(product_id=book1.id, qty=5),  # OK
                OrderItemCreate(product_id=book2.id, qty=5),  # Will fail
            ]
        )
        order = OrderService.create_order(db_session, order_data)

        with pytest.raises(HTTPException) as exc_info:
            OrderService.confirm_order(db_session, order.id, None)

        assert exc_info.value.status_code == 409
        detail = exc_info.value.detail
        assert len(detail["shortages"]) == 1
        shortage = detail["shortages"][0]
        assert shortage["product_id"] == str(book2.id)
        assert shortage["requested"] == 5
        assert shortage["available"] == 2

    def test_order_service_transaction_rollback(self, db_session, bootstrap_tenant, sample_book_model):
        """Test that order service properly handles transaction rollback."""
        db_session.execute(text(f"SET search_path TO {bootstrap_tenant}, public"))

        initial_stock = sample_book_model.stock

        # Create order that will fail confirmation
        order_data = OrderCreate(
            items=[OrderItemCreate(product_id=sample_book_model.id, qty=sample_book_model.stock + 1)]
        )
        order = OrderService.create_order(db_session, order_data)

        # Try to confirm - should fail and rollback
        with pytest.raises(HTTPException):
            OrderService.confirm_order(db_session, order.id, None)

        # Verify stock was not changed
        books = BookService.list_books(db_session)
        updated_book = next(b for b in books if b.id == sample_book_model.id)
        assert updated_book.stock == initial_stock

    def test_order_service_error_propagation(self, db_session, bootstrap_tenant):
        """Test that service properly propagates errors from lower layers."""
        db_session.execute(text(f"SET search_path TO {bootstrap_tenant}, public"))

        # Try to create order with non-existent book
        order_data = OrderCreate(
            items=[OrderItemCreate(product_id=uuid.uuid4(), qty=1)]
        )

        # Should raise exception (from repository layer)
        with pytest.raises(Exception):
            OrderService.create_order(db_session, order_data)


class TestServiceLayerIntegration:
    """Test service layer integration scenarios."""

    def test_complex_order_workflow(self, db_session, bootstrap_tenant, sample_author_model):
        """Test complex order workflow through service layer."""
        db_session.execute(text(f"SET search_path TO {bootstrap_tenant}, public"))

        # Create multiple books
        books = []
        for i in range(3):
            book_data = BookCreate(
                title=f"Book {i+1}",
                author_id=sample_author_model.id,
                price=10.99 * (i + 1),
                stock=10 - i
            )
            book = BookService.create_book(db_session, book_data)
            books.append(book)

        # Create order with multiple items
        order_data = OrderCreate(
            items=[
                OrderItemCreate(product_id=books[0].id, qty=2),
                OrderItemCreate(product_id=books[1].id, qty=3),
                OrderItemCreate(product_id=books[2].id, qty=1),
            ]
        )
        order = OrderService.create_order(db_session, order_data)

        # Verify order created successfully
        assert order.status == "DRAFT"
        assert len(order.items) == 3

        # Confirm order
        result = OrderService.confirm_order(db_session, order.id, None)
        assert result["status"] == "CONFIRMED"

        # Verify stock reductions
        updated_books = BookService.list_books(db_session)
        book_stocks = {book.id: book.stock for book in updated_books}

        assert book_stocks[books[0].id] == 8  # 10 - 2
        assert book_stocks[books[1].id] == 6  # 9 - 3
        assert book_stocks[books[2].id] == 7  # 8 - 1

    def test_service_layer_validation_comprehensive(self, db_session, bootstrap_tenant, sample_author_model):
        """Test comprehensive validation at service layer."""
        db_session.execute(text(f"SET search_path TO {bootstrap_tenant}, public"))

        # Test book business rules
        book1_data = BookCreate(
            title="First Book",
            author_id=sample_author_model.id,
            price=20.99,
            stock=8,
            published_at=date(2023, 2, 20)
        )
        book1 = BookService.create_book(db_session, book1_data)

        # Duplicate check - same title, author, year
        duplicate_data = BookCreate(
            title="First Book",
            author_id=sample_author_model.id,
            price=19.99,
            stock=3,
            published_at=date(2023, 2, 20)
        )

        with pytest.raises(ValueError, match="Duplicate book"):
            BookService.create_book(db_session, duplicate_data)

        # Different year - should work
        different_year_data = BookCreate(
            title="First Book",
            author_id=sample_author_model.id,
            price=39.99,
            stock=2,
            published_at=date(2024, 1, 1)
        )
        book2 = BookService.create_book(db_session, different_year_data)
        assert book2.id != book1.id

        # Test order business rules
        order_data = OrderCreate(
            items=[OrderItemCreate(product_id=book1.id, qty=book1.stock + 1)]
        )
        order = OrderService.create_order(db_session, order_data)

        # Should fail on confirmation due to insufficient stock
        with pytest.raises(HTTPException) as exc_info:
            OrderService.confirm_order(db_session, order.id, None)

        assert exc_info.value.status_code == 409
        assert "shortages" in str(exc_info.value.detail)
