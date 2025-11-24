"""
# Blog Access Control Dependencies

This module implements the **Role-Based Access Control (RBAC)** system for the Blog Platform.
It provides FastAPI dependencies to enforce permissions at the website level.

## Domain Overview

The blog platform uses a hierarchical role system. Permissions cascade downwards:
- **OWNER**: Full control, can delete website.
- **ADMIN**: Manage settings, users, and all content.
- **EDITOR**: Manage and publish all content.
- **AUTHOR**: Manage and publish *own* content.
- **VIEWER**: Read-only access to published content.

## Key Features

### 1. Dual Authentication Strategy
The system supports two types of authentication tokens:
- **Global User Token**: Standard login token. Checks DB for website membership.
- **Website-Scoped Token**: Special token for API clients, containing role claims directly.

### 2. Context Injection
The dependencies automatically inject context into the `current_user` object:
- `website_id`: The context of the current request.
- `website_role`: The user's effective role on this website.

### 3. Permission Dependencies
Reusable dependencies for route protection:
- `require_access_viewer`: Minimum access (Read).
- `require_access_author`: Write access (Own content).
- `require_access_editor`: Editorial access (All content).
- `require_access_admin`: Administrative access (Settings).
- `require_access_owner`: Ownership access (Destructive actions).

## Usage Examples

### Protecting a Route

```python
@router.delete("/posts/{post_id}")
async def delete_post(
    current_user: dict = Depends(require_access_editor)
):
    # Only Editors, Admins, and Owners can reach here
    pass
```

### Custom Role Logic

```python
async def custom_logic(user: dict = Depends(require_website_access)):
    if user["website_role"] == WebsiteRole.AUTHOR:
        # Custom logic for authors
        pass
```

## Module Attributes

Attributes:
    oauth2_scheme (OAuth2PasswordBearer): Token extraction scheme
"""
from typing import Dict, Any, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from second_brain_database.managers.blog_auth_manager import blog_auth_manager
from second_brain_database.managers.blog_manager import BlogWebsiteManager
from second_brain_database.routes.auth.services.auth.login import get_current_user
from second_brain_database.models.blog_models import WebsiteRole

# Use the same scheme as the main app for simplicity, or both
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def require_website_access(
    website_id: str,
    token: str = Depends(oauth2_scheme)
) -> Dict[str, Any]:
    """
    Dependency to validate access to a specific website.
    Accepts either a website-scoped token (matching website_id) OR a global user token (checked against DB).
    """
    user = None
    role = None

    # 1. Try to validate as a website-scoped token
    try:
        # We manually call validate because we want to handle the failure gracefully
        token_payload = await blog_auth_manager.validate_website_token(token)
        
        # If it's a website token, it MUST match the requested website_id
        if token_payload.get("website_id") != website_id:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token is for a different website"
            )
        
        # Token is valid and matches. Get the user details.
        # We trust the role in the token.
        user = await get_current_user(token) # This gets the basic user info
        user["website_id"] = token_payload["website_id"]
        user["website_role"] = token_payload["role"]
        return user

    except HTTPException:
        # Not a valid website token (or expired, or wrong type). 
        # Fallback to checking as a global user token.
        pass
    except Exception:
        pass

    # 2. Validate as global user token
    try:
        user = await get_current_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Check database for membership
    website_manager = BlogWebsiteManager()
    membership = await website_manager.check_website_access(
        user["_id"], website_id, WebsiteRole.VIEWER
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this website"
        )

    # Attach context to user object
    user["website_id"] = website_id
    user["website_role"] = membership.role
    
    return user

async def require_access_viewer(user: Dict[str, Any] = Depends(require_website_access)) -> Dict[str, Any]:
    return user

async def require_access_author(user: Dict[str, Any] = Depends(require_website_access)) -> Dict[str, Any]:
    if not blog_auth_manager.has_role_level(user["website_role"], WebsiteRole.AUTHOR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires Author role")
    return user

async def require_access_editor(user: Dict[str, Any] = Depends(require_website_access)) -> Dict[str, Any]:
    if not blog_auth_manager.has_role_level(user["website_role"], WebsiteRole.EDITOR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires Editor role")
    return user

async def require_access_admin(user: Dict[str, Any] = Depends(require_website_access)) -> Dict[str, Any]:
    if not blog_auth_manager.has_role_level(user["website_role"], WebsiteRole.ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires Admin role")
    return user

async def require_access_owner(user: Dict[str, Any] = Depends(require_website_access)) -> Dict[str, Any]:
    if not blog_auth_manager.has_role_level(user["website_role"], WebsiteRole.OWNER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Requires Owner role")
    return user
