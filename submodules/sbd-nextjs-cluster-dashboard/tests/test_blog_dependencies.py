"""
Tests for blog multitenancy dependencies.
"""
import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch

from second_brain_database.routes.blog_dependencies import (
    require_website_access,
    require_access_viewer,
    require_access_author,
    require_access_editor,
    require_access_admin,
    require_access_owner,
)
from second_brain_database.models.blog_models import WebsiteRole


@pytest.fixture
def mock_user():
    return {
        "_id": "user-123",
        "username": "testuser",
        "email": "test@example.com",
    }


@pytest.fixture
def mock_membership():
    class MockMembership:
        def __init__(self, role):
            self.role = role
    return MockMembership


@pytest.mark.asyncio
async def test_require_website_access_with_global_token(mock_user, mock_membership):
    """Test require_website_access with a global user token."""
    website_id = "website-123"
    
    with patch('second_brain_database.routes.blog_dependencies.get_current_user') as mock_get_user, \
         patch('second_brain_database.routes.blog_dependencies.BlogWebsiteManager') as mock_manager_class:
        
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_manager = AsyncMock()
        mock_manager.check_website_access.return_value = mock_membership(WebsiteRole.VIEWER)
        mock_manager_class.return_value = mock_manager
        
        # Call dependency
        result = await require_website_access(website_id, "fake-token")
        
        # Assertions
        assert result["_id"] == "user-123"
        assert result["website_id"] == website_id
        assert result["website_role"] == WebsiteRole.VIEWER
        mock_manager.check_website_access.assert_called_once_with(
            "user-123", website_id, WebsiteRole.VIEWER
        )


@pytest.mark.asyncio
async def test_require_website_access_with_website_token(mock_user):
    """Test require_website_access with a website-scoped token."""
    website_id = "website-123"
    
    with patch('second_brain_database.routes.blog_dependencies.blog_auth_manager') as mock_auth, \
         patch('second_brain_database.routes.blog_dependencies.get_current_user') as mock_get_user:
        
        # Setup mocks for website token
        mock_auth.validate_website_token.return_value = {
            "website_id": website_id,
            "role": WebsiteRole.AUTHOR,
        }
        mock_get_user.return_value = mock_user
        
        # Call dependency
        result = await require_website_access(website_id, "fake-website-token")
        
        # Assertions
        assert result["_id"] == "user-123"
        assert result["website_id"] == website_id
        assert result["website_role"] == WebsiteRole.AUTHOR


@pytest.mark.asyncio
async def test_require_website_access_wrong_website_token():
    """Test require_website_access with website token for different website."""
    website_id = "website-123"
    
    with patch('second_brain_database.routes.blog_dependencies.blog_auth_manager') as mock_auth:
        
        # Setup mocks for website token with different website_id
        mock_auth.validate_website_token.return_value = {
            "website_id": "different-website-456",
            "role": WebsiteRole.AUTHOR,
        }
        
        # Should raise 403
        with pytest.raises(HTTPException) as exc_info:
            await require_website_access(website_id, "fake-website-token")
        
        assert exc_info.value.status_code == 403
        assert "different website" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_website_access_no_membership(mock_user, mock_membership):
    """Test require_website_access when user has no access to website."""
    website_id = "website-123"
    
    with patch('second_brain_database.routes.blog_dependencies.get_current_user') as mock_get_user, \
         patch('second_brain_database.routes.blog_dependencies.BlogWebsiteManager') as mock_manager_class, \
         patch('second_brain_database.routes.blog_dependencies.blog_auth_manager') as mock_auth:
        
        # Setup mocks - website token validation fails, fallback to global token
        mock_auth.validate_website_token.side_effect = HTTPException(status_code=401)
        mock_get_user.return_value = mock_user
        mock_manager = AsyncMock()
        mock_manager.check_website_access.return_value = None  # No membership
        mock_manager_class.return_value = mock_manager
        
        # Should raise 403
        with pytest.raises(HTTPException) as exc_info:
            await require_website_access(website_id, "fake-token")
        
        assert exc_info.value.status_code == 403
        assert "do not have access" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_access_viewer_allows_all_roles(mock_user):
    """Test that require_access_viewer allows all roles."""
    user_with_context = {
        **mock_user,
        "website_id": "website-123",
        "website_role": WebsiteRole.VIEWER,
    }
    
    # Should not raise for VIEWER
    result = await require_access_viewer(user_with_context)
    assert result == user_with_context
    
    # Should not raise for higher roles
    for role in [WebsiteRole.AUTHOR, WebsiteRole.EDITOR, WebsiteRole.ADMIN, WebsiteRole.OWNER]:
        user_with_context["website_role"] = role
        result = await require_access_viewer(user_with_context)
        assert result == user_with_context


@pytest.mark.asyncio
async def test_require_access_author_blocks_viewer(mock_user):
    """Test that require_access_author blocks VIEWER role."""
    user_with_context = {
        **mock_user,
        "website_id": "website-123",
        "website_role": WebsiteRole.VIEWER,
    }
    
    with pytest.raises(HTTPException) as exc_info:
        await require_access_author(user_with_context)
    
    assert exc_info.value.status_code == 403
    assert "Author" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_access_editor_allows_higher_roles(mock_user):
    """Test that require_access_editor allows EDITOR and higher."""
    user_with_context = {
        **mock_user,
        "website_id": "website-123",
        "website_role": WebsiteRole.EDITOR,
    }
    
    # Should allow EDITOR
    result = await require_access_editor(user_with_context)
    assert result == user_with_context
    
    # Should allow ADMIN and OWNER
    for role in [WebsiteRole.ADMIN, WebsiteRole.OWNER]:
        user_with_context["website_role"] = role
        result = await require_access_editor(user_with_context)
        assert result == user_with_context
    
    # Should block AUTHOR and VIEWER
    for role in [WebsiteRole.AUTHOR, WebsiteRole.VIEWER]:
        user_with_context["website_role"] = role
        with pytest.raises(HTTPException) as exc_info:
            await require_access_editor(user_with_context)
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_access_admin_blocks_lower_roles(mock_user):
    """Test that require_access_admin blocks roles below ADMIN."""
    user_with_context = {
        **mock_user,
        "website_id": "website-123",
        "website_role": WebsiteRole.ADMIN,
    }
    
    # Should allow ADMIN
    result = await require_access_admin(user_with_context)
    assert result == user_with_context
    
    # Should allow OWNER
    user_with_context["website_role"] = WebsiteRole.OWNER
    result = await require_access_admin(user_with_context)
    assert result == user_with_context
    
    # Should block lower roles
    for role in [WebsiteRole.EDITOR, WebsiteRole.AUTHOR, WebsiteRole.VIEWER]:
        user_with_context["website_role"] = role
        with pytest.raises(HTTPException) as exc_info:
            await require_access_admin(user_with_context)
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_require_access_owner_only_allows_owner(mock_user):
    """Test that require_access_owner only allows OWNER role."""
    user_with_context = {
        **mock_user,
        "website_id": "website-123",
        "website_role": WebsiteRole.OWNER,
    }
    
    # Should allow OWNER
    result = await require_access_owner(user_with_context)
    assert result == user_with_context
    
    # Should block all other roles
    for role in [WebsiteRole.ADMIN, WebsiteRole.EDITOR, WebsiteRole.AUTHOR, WebsiteRole.VIEWER]:
        user_with_context["website_role"] = role
        with pytest.raises(HTTPException) as exc_info:
            await require_access_owner(user_with_context)
        assert exc_info.value.status_code == 403
