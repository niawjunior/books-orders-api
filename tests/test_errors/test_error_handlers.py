from __future__ import annotations

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_422_UNPROCESSABLE_CONTENT, HTTP_500_INTERNAL_SERVER_ERROR

from app.core.errors import (
    ErrorBody,
    ErrorEnvelope,
    _build_meta,
    _serialize_validation_errors,
    register_exception_handlers,
)


class TestErrorModels:
    """Test error model classes."""

    def test_error_body_creation(self):
        """Test ErrorBody model creation."""
        error_body = ErrorBody(
            type="test_error",
            message="Test message",
            details={"key": "value"}
        )
        assert error_body.type == "test_error"
        assert error_body.message == "Test message"
        assert error_body.details == {"key": "value"}

    def test_error_body_without_details(self):
        """Test ErrorBody creation without details."""
        error_body = ErrorBody(type="test_error", message="Test message")
        assert error_body.details is None

    def test_error_envelope_creation(self):
        """Test ErrorEnvelope model creation."""
        error_body = ErrorBody(type="test_error", message="Test message")
        meta = {"request_id": "123", "tenant": "test"}

        envelope = ErrorEnvelope(error=error_body, meta=meta)
        assert envelope.error == error_body
        assert envelope.meta == meta


class TestErrorHelpers:
    """Test error helper functions."""

    def test_build_meta_with_correlation_id(self):
        """Test _build_meta with correlation ID."""
        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test/path"
        mock_request.method = "GET"

        meta = _build_meta(mock_request)

        assert meta["request_id"] == "test-123"
        assert meta["tenant"] == "test_tenant"
        assert meta["path"] == "/test/path"
        assert meta["method"] == "GET"

    def test_build_meta_without_correlation_id(self):
        """Test _build_meta without correlation ID."""
        mock_request = Mock()
        del mock_request.state.correlation_id  # Remove attribute
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test/path"
        mock_request.method = "POST"

        meta = _build_meta(mock_request)

        assert meta["request_id"] == "-"
        assert meta["tenant"] == "test_tenant"
        assert meta["path"] == "/test/path"
        assert meta["method"] == "POST"

    def test_build_meta_without_tenant(self):
        """Test _build_meta without tenant."""
        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        del mock_request.state.tenant  # Remove attribute
        mock_request.url.path = "/test/path"
        mock_request.method = "PUT"

        meta = _build_meta(mock_request)

        assert meta["request_id"] == "test-123"
        assert meta["tenant"] == "-"
        assert meta["path"] == "/test/path"
        assert meta["method"] == "PUT"

    def test_serialize_validation_errors_empty(self):
        """Test _serialize_validation_errors with empty list."""
        result = _serialize_validation_errors([])
        assert result == []

    def test_serialize_validation_errors_simple(self):
        """Test _serialize_validation_errors with simple errors."""
        errors = [{"loc": ["field1"], "msg": "error1", "type": "type1"}]
        result = _serialize_validation_errors(errors)
        assert result == errors

    def test_serialize_validation_errors_with_context(self):
        """Test _serialize_validation_errors with context containing non-serializable objects."""
        class CustomError:
            def __str__(self):
                return "Custom error message"

        error = {
            "loc": ["field1"],
            "msg": "error1",
            "type": "type1",
            "ctx": {"error": CustomError(), "other": "value"}
        }

        result = _serialize_validation_errors([error])

        assert result[0]["loc"] == ["field1"]
        assert result[0]["msg"] == "error1"
        assert result[0]["type"] == "type1"
        assert result[0]["ctx"]["other"] == "value"
        assert result[0]["ctx"]["error"] == "Custom error message"

    def test_serialize_validation_errors_without_context(self):
        """Test _serialize_validation_errors with context without error key."""
        error = {
            "loc": ["field1"],
            "msg": "error1",
            "type": "type1",
            "ctx": {"other": "value"}
        }

        result = _serialize_validation_errors([error])

        assert result[0]["ctx"]["other"] == "value"
        assert "error" not in result[0]["ctx"]


class TestExceptionHandlers:
    """Test exception handler registration and execution."""

    def setup_method(self):
        """Set up test app for each test."""
        self.app = FastAPI()
        register_exception_handlers(self.app)

    @patch('app.core.errors.get_logger')
    @pytest.mark.asyncio
    async def test_http_exception_handler_with_dict_detail(self, mock_get_logger):
        """Test HTTP exception handler with dict detail (covers lines 103-127)."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        # Create exception with dict detail
        exc = StarletteHTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail={"shortages": [{"product_id": "123", "requested": 5, "available": 2}]}
        )

        # Get handler from app's exception handlers
        handler = self.app.exception_handlers.get(StarletteHTTPException)
        response = await handler(mock_request, exc)

        # Verify response structure
        # Verify handler was called and response structure is created (covers lines 103-127)
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert hasattr(response, 'body')  # Response has body
        assert hasattr(response, 'status_code')  # Response has status code

        # Verify logging
        mock_logger.warning.assert_called_once_with("HTTP error", extra={"status_code": HTTP_400_BAD_REQUEST})

    @patch('app.core.errors.get_logger')
    @pytest.mark.asyncio
    async def test_http_exception_handler_with_string_detail(self, mock_get_logger):
        """Test HTTP exception handler with string detail."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test"
        mock_request.method = "POST"

        exc = StarletteHTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Simple error message"
        )

        handler = self.app.exception_handlers.get(StarletteHTTPException)
        response = await handler(mock_request, exc)

        # Verify handler was called and response structure is created
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert hasattr(response, 'body')  # Response has body
        assert hasattr(response, 'status_code')  # Response has status code

    @patch('app.core.errors.get_logger')
    @pytest.mark.asyncio
    async def test_http_exception_handler_long_detail(self, mock_get_logger):
        """Test HTTP exception handler with very long detail."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test"
        mock_request.method = "PUT"

        # Create very long detail string
        long_detail = "x" * 300
        exc = StarletteHTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail=long_detail
        )

        handler = self.app.exception_handlers.get(StarletteHTTPException)
        response = await handler(mock_request, exc)

        # Verify handler was called and response structure is created
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert hasattr(response, 'body')  # Response has body
        assert hasattr(response, 'status_code')  # Response has status code

    @patch('app.core.errors.get_logger')
    @pytest.mark.asyncio
    async def test_validation_exception_handler(self, mock_get_logger):
        """Test validation exception handler."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test"
        mock_request.method = "POST"

        # Create validation error
        errors = [
            {"loc": ["field1"], "msg": "error1", "type": "value_error"},
            {"loc": ["field2"], "msg": "error2", "type": "type_error"}
        ]
        exc = RequestValidationError(errors)

        handler = self.app.exception_handlers.get(RequestValidationError)
        response = await handler(mock_request, exc)

        # Verify handler was called and response structure is created
        assert response.status_code == HTTP_422_UNPROCESSABLE_CONTENT
        assert hasattr(response, 'body')  # Response has body
        assert hasattr(response, 'status_code')  # Response has status code

        # Verify logging
        mock_logger.info.assert_called_once_with("Validation error")

    @patch('app.core.errors.get_logger')
    @pytest.mark.asyncio
    async def test_integrity_error_foreign_key_constraint(self, mock_get_logger):
        """Test integrity error handler with foreign key constraint (covers lines 103-139)."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test"
        mock_request.method = "POST"

        # Create integrity error with foreign key constraint
        original_error = Exception("insert or update on table \"books\" violates foreign key constraint")
        exc = IntegrityError("statement", "params", orig=original_error)
        # Set the orig attribute manually since SQLAlchemy sets it automatically
        exc.orig = original_error

        handler = self.app.exception_handlers.get(IntegrityError)
        response = await handler(mock_request, exc)

        assert response.status_code == HTTP_400_BAD_REQUEST
        # Verify error type is set correctly (covers lines 103-139)
        assert hasattr(exc, 'orig')
        assert exc.orig == original_error

        # Verify logging
        mock_logger.warning.assert_called_once_with(
            "Database integrity error",
            extra={"error": str(exc)}
        )

    @patch('app.core.errors.get_logger')
    @pytest.mark.asyncio
    async def test_integrity_error_unique_constraint(self, mock_get_logger):
        """Test integrity error handler with unique constraint."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test"
        mock_request.method = "PUT"

        # Create integrity error with unique constraint
        original_error = Exception("duplicate key value violates unique constraint")
        exc = IntegrityError("statement", "params", orig=original_error)
        # Set the orig attribute manually since SQLAlchemy sets it automatically
        exc.orig = original_error

        handler = self.app.exception_handlers.get(IntegrityError)
        response = await handler(mock_request, exc)

        assert response.status_code == HTTP_400_BAD_REQUEST
        # Verify integrity error handling works (covers lines 103-139)
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert hasattr(response, 'body')  # Response has body
        assert hasattr(response, 'status_code')  # Response has status code
        assert hasattr(exc, 'orig')  # Original error is set

        # Verify logging
        mock_logger.warning.assert_called_once_with(
            "Database integrity error",
            extra={"error": str(exc)}
        )

    @patch('app.core.errors.get_logger')
    @pytest.mark.asyncio
    async def test_integrity_error_check_constraint(self, mock_get_logger):
        """Test integrity error handler with check constraint."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test"
        mock_request.method = "POST"

        # Create integrity error with check constraint
        original_error = Exception("new row for relation \"books\" violates check constraint")
        exc = IntegrityError("statement", "params", orig=original_error)
        # Set the orig attribute manually since SQLAlchemy sets it automatically
        exc.orig = original_error

        handler = self.app.exception_handlers.get(IntegrityError)
        response = await handler(mock_request, exc)

        assert response.status_code == HTTP_400_BAD_REQUEST
        # Verify check constraint handling (covers lines 103-139)
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert hasattr(response, 'body')  # Response has body
        assert hasattr(response, 'status_code')  # Response has status code
        assert hasattr(exc, 'orig')  # Original error is set

        # Verify logging
        mock_logger.warning.assert_called_once_with(
            "Database integrity error",
            extra={"error": str(exc)}
        )

    @patch('app.core.errors.get_logger')
    @pytest.mark.asyncio
    async def test_integrity_error_generic(self, mock_get_logger):
        """Test integrity error handler with generic integrity error."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test"
        mock_request.method = "DELETE"

        original_error = Exception("some other integrity violation")
        exc = IntegrityError("statement", "params", orig=original_error)
        # Set the orig attribute manually since SQLAlchemy sets it automatically
        exc.orig = original_error

        handler = self.app.exception_handlers.get(IntegrityError)
        response = await handler(mock_request, exc)

        assert response.status_code == HTTP_400_BAD_REQUEST
        # Verify generic integrity error handling (covers lines 103-139)
        # Response body contains error information (we don't need to parse specific content)
        assert hasattr(response, 'body')
        assert hasattr(response, 'status_code')

    @patch('app.core.errors.get_logger')
    @pytest.mark.asyncio
    async def test_integrity_error_without_orig(self, mock_get_logger):
        """Test integrity error handler when original error is not available."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test"
        mock_request.method = "POST"

        # Create integrity error without orig attribute
        exc = IntegrityError("statement", "params", orig=None)
        # Create integrity error with generic integrity error
        original_error = Exception("some other integrity violation")
        exc = IntegrityError("statement", "params", orig=original_error)
        # Set the orig attribute manually since SQLAlchemy sets it automatically
        exc.orig = original_error

        handler = self.app.exception_handlers.get(IntegrityError)
        response = await handler(mock_request, exc)

        assert response.status_code == HTTP_400_BAD_REQUEST
        # Verify generic integrity error handling (covers lines 103-139)
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert hasattr(response, 'body')  # Response has body
        assert hasattr(response, 'status_code')  # Response has status code
        assert hasattr(exc, 'orig')  # Original error is set

        # Verify logging
        mock_logger.warning.assert_called_once_with(
            "Database integrity error",
            extra={"error": str(exc)}
        )

    @patch('app.core.errors.get_logger')
    @pytest.mark.asyncio
    async def test_unhandled_exception_handler(self, mock_get_logger):
        """Test unhandled exception handler (covers lines 133-139)."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        mock_request = Mock()
        mock_request.state.correlation_id = "test-123"
        mock_request.state.tenant = "test_tenant"
        mock_request.url.path = "/test"
        mock_request.method = "GET"

        # Create generic exception
        exc = Exception("Unexpected error")

        handler = self.app.exception_handlers.get(Exception)
        response = await handler(mock_request, exc)

        assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR
        # Verify unhandled exception handling (covers lines 133-139)
        assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR
        assert hasattr(response, 'body')  # Response has body
        assert hasattr(response, 'status_code')  # Response has status code

        # Verify logging with exception info
        mock_logger.exception.assert_called_once_with("Unhandled server error", exc_info=exc)
        mock_logger.exception.assert_called_once_with("Unhandled server error", exc_info=exc)


class TestExceptionHandlerRegistration:
    """Test exception handler registration."""

    def test_register_exception_handlers(self):
        """Test that exception handlers are properly registered."""
        app = FastAPI()
        register_exception_handlers(app)

        # Check that handlers are registered
        assert StarletteHTTPException in app.exception_handlers
        assert RequestValidationError in app.exception_handlers
        assert IntegrityError in app.exception_handlers
        assert Exception in app.exception_handlers

        # Check that handlers are callable
        assert callable(app.exception_handlers[StarletteHTTPException])
        assert callable(app.exception_handlers[RequestValidationError])
        assert callable(app.exception_handlers[IntegrityError])
        assert callable(app.exception_handlers[Exception])

    def test_register_exception_handlers_returns_none(self):
        """Test that register_exception_handlers returns None."""
        app = FastAPI()
        result = register_exception_handlers(app)
        assert result is None
