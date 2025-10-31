from __future__ import annotations

import pytest
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch
from fastapi import Request
from sqlalchemy import text

from app.db.session import get_db_with_tenant, engine, SessionLocal


class TestDatabaseSession:
    """Test database session functionality."""

    def test_session_local_configuration(self):
        """Test that SessionLocal is properly configured."""
        # Verify SessionLocal is a sessionmaker
        assert hasattr(SessionLocal, '__call__')
        assert SessionLocal.kw.get('autocommit') is False
        assert SessionLocal.kw.get('autoflush') is False

    def test_engine_configuration(self):
        """Test that engine is properly configured."""
        assert engine is not None
        assert engine.url is not None

    @patch('app.db.session.SessionLocal')
    def test_get_db_with_tenant_none(self, mock_session_local):
        """Test session creation when tenant is None (missing lines 17-22)."""
        # Mock request without tenant
        mock_request = Mock()
        mock_request.state = Mock()
        del mock_request.state.tenant  # Ensure tenant attribute doesn't exist

        # Mock session instance
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db

        # Get the generator and advance it
        generator = get_db_with_tenant(mock_request)
        session = next(generator)

        # Verify session was created
        mock_session_local.assert_called_once()
        assert session == mock_db

        # Verify no search path was set (text execution not called)
        mock_db.execute.assert_not_called()

        # Clean up generator to test finally block
        try:
            next(generator)
        except StopIteration:
            pass

        # Verify session was closed
        mock_db.close.assert_called_once()

    @patch('app.db.session.SessionLocal')
    def test_get_db_with_tenant_none_attribute_error(self, mock_session_local):
        """Test session creation when tenant attribute doesn't exist."""
        # Mock request without tenant attribute at all
        mock_request = Mock()
        mock_request.state = Mock(spec=[])  # Empty spec, no tenant attribute

        # Mock session instance
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db

        # Get the generator and advance it
        generator = get_db_with_tenant(mock_request)
        session = next(generator)

        # Verify session was created
        mock_session_local.assert_called_once()
        assert session == mock_db

        # Verify no search path was set
        mock_db.execute.assert_not_called()

        # Clean up generator to test finally block
        try:
            next(generator)
        except StopIteration:
            pass

        # Verify session was closed
        mock_db.close.assert_called_once()

    @patch('app.db.session.SessionLocal')
    def test_get_db_with_tenant_provided(self, mock_session_local):
        """Test session creation when tenant is provided."""
        # Mock request with tenant
        mock_request = Mock()
        mock_request.state.tenant = "test_tenant"

        # Mock session instance
        mock_db = Mock(spec=Session)
        mock_db.execute.return_value = None
        mock_session_local.return_value = mock_db

        # Get the generator and advance it
        generator = get_db_with_tenant(mock_request)
        session = next(generator)

        # Verify session was created
        mock_session_local.assert_called_once()
        assert session == mock_db

        # Verify search path was set
        mock_db.execute.assert_called_once()
        expected_call = text('SET search_path TO "test_tenant", public')
        actual_call = mock_db.execute.call_args[0][0]
        assert str(actual_call) == str(expected_call)

        # Clean up generator to test finally block
        try:
            next(generator)
        except StopIteration:
            pass

        # Verify session was closed
        mock_db.close.assert_called_once()

    @patch('app.db.session.SessionLocal')
    def test_get_db_with_tenant_empty_string(self, mock_session_local):
        """Test session creation when tenant is empty string."""
        # Mock request with empty tenant
        mock_request = Mock()
        mock_request.state.tenant = ""

        # Mock session instance
        mock_db = Mock(spec=Session)
        mock_db.execute.return_value = None
        mock_session_local.return_value = mock_db

        # Get the generator and advance it
        generator = get_db_with_tenant(mock_request)
        session = next(generator)

        # Verify session was created
        mock_session_local.assert_called_once()
        assert session == mock_db

        # Verify search path was set to empty string (line 21)
        mock_db.execute.assert_called_once()
        expected_call = text('SET search_path TO "", public')
        actual_call = mock_db.execute.call_args[0][0]
        assert str(actual_call) == str(expected_call)

        # Clean up generator
        try:
            next(generator)
        except StopIteration:
            pass

        # Verify session was closed
        mock_db.close.assert_called_once()

    @patch('app.db.session.SessionLocal')
    def test_get_db_exception_handling_no_tenant(self, mock_session_local):
        """Test exception handling when no tenant provided."""
        # Mock request without tenant
        mock_request = Mock()
        mock_request.state = Mock()
        del mock_request.state.tenant

        # Mock session that raises exception
        mock_db = Mock(spec=Session)
        mock_db.close.side_effect = Exception("Database error")
        mock_session_local.return_value = mock_db

        # Get the generator
        generator = get_db_with_tenant(mock_request)

        # Should work normally
        session = next(generator)
        assert session == mock_db

        # Exception should be raised on cleanup
        with pytest.raises(Exception, match="Database error"):
            try:
                next(generator)
            except StopIteration:
                pass

        # close should still be called despite exception
        mock_db.close.assert_called_once()

    @patch('app.db.session.SessionLocal')
    def test_get_db_exception_handling_with_tenant(self, mock_session_local):
        """Test exception handling when tenant provided."""
        # Mock request with tenant
        mock_request = Mock()
        mock_request.state.tenant = "test_tenant"

        # Mock session that raises exception on execute
        mock_db = Mock(spec=Session)
        mock_db.execute.side_effect = Exception("Search path error")
        mock_session_local.return_value = mock_db

        # Get the generator - should raise exception during setup
        generator = get_db_with_tenant(mock_request)

        with pytest.raises(Exception, match="Search path error"):
            next(generator)

        # Verify search path was attempted
        mock_db.execute.assert_called_once()
        expected_call = text('SET search_path TO "test_tenant", public')
        actual_call = mock_db.execute.call_args[0][0]
        assert str(actual_call) == str(expected_call)

    @patch('app.db.session.SessionLocal')
    def test_get_db_generator_behavior_no_tenant(self, mock_session_local):
        """Test proper generator behavior without tenant."""
        # Mock request without tenant
        mock_request = Mock()
        mock_request.state = Mock()
        del mock_request.state.tenant

        # Mock session
        mock_db = Mock(spec=Session)
        mock_session_local.return_value = mock_db

        # Use as generator
        generator = get_db_with_tenant(mock_request)
        session = next(generator)

        assert session == mock_db
        mock_db.execute.assert_not_called()

        # Clean up generator
        try:
            next(generator)
        except StopIteration:
            pass

        # Verify cleanup was called
        mock_db.close.assert_called_once()

    @patch('app.db.session.SessionLocal')
    def test_get_db_generator_behavior_with_tenant(self, mock_session_local):
        """Test proper generator behavior with tenant."""
        # Mock request with tenant
        mock_request = Mock()
        mock_request.state.tenant = "test_tenant"

        # Mock session
        mock_db = Mock(spec=Session)
        mock_db.execute.return_value = None
        mock_session_local.return_value = mock_db

        # Use as generator
        generator = get_db_with_tenant(mock_request)
        session = next(generator)

        assert session == mock_db
        mock_db.execute.assert_called_once()

        # Clean up generator
        try:
            next(generator)
        except StopIteration:
            pass

        # Verify cleanup was called
        mock_db.close.assert_called_once()

    def test_session_multiple_calls_independence(self):
        """Test that multiple session calls are independent."""
        # Mock request with tenant
        mock_request1 = Mock()
        mock_request1.state.tenant = "tenant1"

        mock_request2 = Mock()
        mock_request2.state.tenant = "tenant2"

        with patch('app.db.session.SessionLocal') as mock_session_local:
            mock_db1 = Mock(spec=Session)
            mock_db2 = Mock(spec=Session)
            mock_db1.execute.return_value = None
            mock_db2.execute.return_value = None

            # Return different sessions for different calls
            mock_session_local.side_effect = [mock_db1, mock_db2]

            # First session
            generator1 = get_db_with_tenant(mock_request1)
            session1 = next(generator1)
            assert session1 == mock_db1
            assert mock_db1.execute.call_count == 1
            actual_call = mock_db1.execute.call_args[0][0]
            assert str(actual_call) == str(text('SET search_path TO "tenant1", public'))
            try:
                next(generator1)
            except StopIteration:
                pass

            # Second session
            generator2 = get_db_with_tenant(mock_request2)
            session2 = next(generator2)
            assert session2 == mock_db2
            assert mock_db2.execute.call_count == 1
            actual_call = mock_db2.execute.call_args[0][0]
            assert str(actual_call) == str(text('SET search_path TO "tenant2", public'))
            try:
                next(generator2)
            except StopIteration:
                pass

        # Verify both sessions were closed
        mock_db1.close.assert_called_once()
        mock_db2.close.assert_called_once()
