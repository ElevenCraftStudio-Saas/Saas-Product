"""Logic tests for Firestore role management.

These tests mock the Firestore client to ensure the logic in firestore_service.py
is actually executed and covered, rather than mocking the service functions.
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services import firestore_service

@pytest.fixture
def mock_firestore():
    """Provides a mock Firestore client and the patcher to inject it."""
    # Create the mock client and chain
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_document = MagicMock()

    mock_client.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_document

    # Patch _get_client to return our mock
    with patch("app.services.firestore_service._get_client", return_value=mock_client):
        yield {
            "client": mock_client,
            "collection": mock_collection,
            "doc": mock_document
        }

def test_get_user_role_success(mock_firestore):
    """Test reading a role when the user exists."""
    # Setup: document exists and has role 'admin'
    mock_snapshot = MagicMock()
    mock_snapshot.exists = True
    mock_snapshot.get.return_value = "admin"
    mock_firestore["doc"].get.return_value = mock_snapshot

    role = firestore_service.get_user_role("test-uid")
    assert role == "admin"
    mock_firestore["client"].collection.assert_called_once_with("users")
    mock_firestore["collection"].document.assert_called_once_with("test-uid")
    mock_firestore["doc"].get.assert_called_once()

def test_get_user_role_not_found(mock_firestore):
    """Test reading a role when the document does not exist."""
    mock_snapshot = MagicMock()
    mock_snapshot.exists = False
    mock_firestore["doc"].get.return_value = mock_snapshot

    role = firestore_service.get_user_role("unknown-uid")
    assert role is None

def test_get_user_role_firestore_unavailable():
    """Test reading a role when the Firestore client is unavailable."""
    with patch("app.services.firestore_service._get_client", return_value=None):
        role = firestore_service.get_user_role("any-uid")
        assert role is None

def test_get_user_role_exception(mock_firestore):
    """Test that exceptions during read are caught and return None."""
    mock_firestore["doc"].get.side_effect = Exception("Firebase Error")

    role = firestore_service.get_user_role("test-uid")
    assert role is None

def test_set_user_role_success(mock_firestore):
    """Test setting a role successfully."""
    success = firestore_service.set_user_role("test-uid", "admin", "test@ai.com", "Test User")
    assert success is True
    mock_firestore["doc"].set.assert_called_once()
    # Verify merge=True is used
    args, kwargs = mock_firestore["doc"].set.call_args
    assert kwargs["merge"] is True

def test_set_user_role_invalid(mock_firestore):
    """Test that invalid roles raise a ValueError."""
    with pytest.raises(ValueError, match="Invalid role"):
        firestore_service.set_user_role("test-uid", "super-admin")

def test_set_user_role_unavailable():
    """Test setting a role when client is unavailable."""
    with patch("app.services.firestore_service._get_client", return_value=None):
        success = firestore_service.set_user_role("test-uid", "admin")
        assert success is False

def test_ensure_user_doc_existing(mock_firestore):
    """Test ensure_user_doc when user already exists."""
    mock_snapshot = MagicMock()
    mock_snapshot.exists = True
    mock_snapshot.get.return_value = "admin"
    mock_firestore["doc"].get.return_value = mock_snapshot

    role = firestore_service.ensure_user_doc("test-uid", "test@ai.com", "Test User")
    assert role == "admin"
    # Should not call set() if user already exists
    mock_firestore["doc"].set.assert_not_called()

def test_ensure_user_doc_create_new(mock_firestore):
    """Test ensure_user_doc creating a new user."""
    mock_snapshot = MagicMock()
    mock_snapshot.exists = False
    mock_firestore["doc"].get.return_value = mock_snapshot

    role = firestore_service.ensure_user_doc("new-uid", "new@ai.com", "New User")
    assert role == "user"
    mock_firestore["doc"].set.assert_called_once()

def test_ensure_user_doc_unavailable():
    """Test ensure_user_doc when Firestore is unavailable."""
    with patch("app.services.firestore_service._get_client", return_value=None):
        role = firestore_service.ensure_user_doc("any-uid", "any@ai.com", "Any User")
        assert role == "user"

def test_ensure_user_doc_exception(mock_firestore):
    """Test ensure_user_doc handles set() exceptions."""
    mock_snapshot = MagicMock()
    mock_snapshot.exists = False
    mock_firestore["doc"].get.return_value = mock_snapshot
    mock_firestore["doc"].set.side_effect = Exception("Write failed")

    role = firestore_service.ensure_user_doc("test-uid", "test@ai.com", "Test User")
    assert role == "user" # Should still return 'user' as fallback
