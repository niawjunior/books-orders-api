import pytest
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import engine
from app.models.base import Base
from app.core.config import settings

# Test database URL
BASE_URL = settings.DATABASE_URL
TEST_DATABASE_URL = BASE_URL.rsplit("/", 1)[0] + "/test_books_orders_db"

# Create test engine
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True, echo=False)
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Setup test database and clean up after tests."""
    with engine.connect() as conn:
        _ = conn.execute(text("COMMIT"))
        try:
            _ = conn.execute(text("CREATE DATABASE test_books_orders_db"))
        except Exception:
            pass

    # Create extensions and tables in test database
    with test_engine.connect() as conn:
        _ = conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        Base.metadata.create_all(bind=conn)

    yield

    # Clean up: drop all tables
    Base.metadata.drop_all(bind=test_engine)

    # Clean up test database - handle transaction properly by using autocommit
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        try:
            _ = conn.execute(text("DROP DATABASE IF EXISTS test_books_orders_db"))
        except Exception:
            pass  # Database might not exist or have connections


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        # Ensure all connections are properly closed and transactions cleaned up
        try:
            session.rollback()  # Rollback any pending transactions
        except:
            pass  # Ignore rollback errors
        session.close()  # Close the session
        # Additional cleanup to prevent hanging
        session.expunge_all()  # Remove all objects from session


@pytest.fixture
def test_client():
    """Create a test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def test_tenant():
    """Test tenant name."""
    import uuid
    return f"test_tenant_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def bootstrap_tenant(test_tenant):
    """Bootstrap a tenant schema for testing."""
    # For test database, we need to bootstrap using test engine
    from sqlalchemy import text

    # Also create schema in main engine for tenant middleware to find it
    with engine.connect() as conn:
        # Ensure proper cleanup before setup
        _ = conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_tenant}" CASCADE'))
        conn.commit()

        # Create schema in main database for middleware
        _ = conn.execute(text(f'CREATE SCHEMA "{test_tenant}"'))
        conn.commit()

        # Create tables in tenant schema in main database
        conn.execute(text(f'SET search_path TO "{test_tenant}", public'))

        # Create tables with explicit schema target
        for table in Base.metadata.tables.values():
            table.schema = test_tenant
        Base.metadata.create_all(bind=conn)
        # Reset schema to None to avoid affecting other operations
        for table in Base.metadata.tables.values():
            table.schema = None

        conn.commit()

    # Now create schema in test database for actual test operations
    with test_engine.connect() as conn:
        # Ensure proper cleanup before setup
        _ = conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_tenant}" CASCADE'))
        conn.commit()

        # Create schema
        _ = conn.execute(text(f'CREATE SCHEMA "{test_tenant}"'))
        conn.commit()

        # Create tables in tenant schema
        conn.execute(text(f'SET search_path TO "{test_tenant}", public'))
        Base.metadata.create_all(bind=conn)
        conn.commit()

    yield test_tenant

    # Cleanup - drop schema from both databases
    try:
        # Force close all connections and dispose engine to prevent hanging
        test_engine.dispose()

        # Use autocommit and timeout to avoid hanging
        with test_engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("SET statement_timeout = '5s'"))
            _ = conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_tenant}" CASCADE'))
    except Exception:
        pass  # Schema might already be dropped or connection issues

    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("SET statement_timeout = '5s'"))
            _ = conn.execute(text(f'DROP SCHEMA IF EXISTS "{test_tenant}" CASCADE'))
    except Exception:
        pass  # Schema might already be dropped


@pytest.fixture
def sample_author(test_client, bootstrap_tenant, headers_with_tenant):
    """Create a sample author for testing using the API (avoiding session conflicts)."""
    import uuid
    unique_suffix = str(uuid.uuid4())[:8]

    author_data = {
        "name": f"Test Author {unique_suffix}",
        "email": f"test-{unique_suffix}@author.com"
    }

    response = test_client.post(
        "/api/v1/authors",
        json=author_data,
        headers=headers_with_tenant
    )

    assert response.status_code == 200, f"Failed to create sample author: {response.text}"
    return response.json()


@pytest.fixture
def sample_book(test_client, bootstrap_tenant, sample_author, headers_with_tenant):
    """Create a sample book for testing using the API (avoiding session conflicts)."""
    import uuid
    unique_suffix = str(uuid.uuid4())[:8]

    book_data = {
        "title": f"Test Book {unique_suffix}",
        "author_id": sample_author["id"],
        "price": 29.99,
        "stock": 10,
        "published_at": "2023-01-01"
    }

    response = test_client.post(
        "/api/v1/books",
        json=book_data,
        headers=headers_with_tenant
    )

    assert response.status_code == 200, f"Failed to create sample book: {response.text}"
    return response.json()


@pytest.fixture
def sample_order(test_client, bootstrap_tenant, sample_book, headers_with_tenant):
    """Create a sample order for testing using the API (avoids DB session conflicts)."""
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

    assert response.status_code == 200, f"Failed to create sample order: {response.text}"
    return response.json()


# Fixtures for repository tests that need SQLAlchemy model objects
@pytest.fixture
def sample_author_model(db_session, bootstrap_tenant):
    """Create a sample author model for repository tests."""
    from app.models.author import Author

    # Set search path for this session (tables should already exist from bootstrap_tenant)
    _ = db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

    import uuid
    unique_suffix = str(uuid.uuid4())[:8]

    author = Author(
        name=f"Test Author {unique_suffix}",
        email=f"test-{unique_suffix}@author.com"
    )
    db_session.add(author)
    db_session.commit()
    db_session.refresh(author)
    return author


@pytest.fixture
def sample_book_model(db_session, bootstrap_tenant, sample_author_model):
    """Create a sample book model for repository tests."""
    from app.models.book import Book
    from datetime import date

    # Set search path to test tenant schema (tables should already exist from bootstrap_tenant)
    _ = db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

    import uuid
    unique_suffix = str(uuid.uuid4())[:8]

    book = Book(
        title=f"Test Book {unique_suffix}",
        author_id=sample_author_model.id,
        price=29.99,
        stock=10,
        version=1,
        published_at=date(2023, 1, 1)
    )
    db_session.add(book)
    db_session.commit()
    db_session.refresh(book)
    return book


@pytest.fixture
def sample_order_model(db_session, bootstrap_tenant, sample_book_model):
    """Create a sample order model for repository tests."""
    from app.models.order import Order, OrderItem

    # Set search path to test tenant schema (tables should already exist from bootstrap_tenant)
    _ = db_session.execute(text(f'SET search_path TO "{bootstrap_tenant}", public'))

    order = Order(status="DRAFT")
    db_session.add(order)
    db_session.flush()

    order_item = OrderItem(
        order_id=order.id,
        product_id=sample_book_model.id,
        qty=2
    )
    db_session.add(order_item)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def headers_with_tenant(test_tenant):
    """HTTP headers with tenant information."""
    return {"X-Tenant": test_tenant}


@pytest.fixture
def headers_with_correlation():
    """HTTP headers with correlation ID."""
    return {"X-Request-ID": str(uuid.uuid4())}


@pytest.fixture
def headers_full(test_tenant):
    """HTTP headers with tenant and correlation ID."""
    return {
        "X-Tenant": test_tenant,
        "X-Request-ID": str(uuid.uuid4())
    }
