"""
# Migration Route Dependencies

This module provides the **security and dependency injection** for the Migration System.
It ensures that critical data operations are restricted to authorized personnel only.

## Security Model

Migrations involve sensitive data export/import, requiring strict access control:
- **Tenant Owner Only**: Most operations require the `OWNER` role.
- **IP Whitelisting**: (Implemented in routes) Restricts access to trusted networks.
- **Audit Logging**: All access attempts (success/failure) are logged.

## Dependencies

### 1. `require_tenant_owner`
- **Purpose**: Validates that the current user is the owner of the active tenant.
- **Usage**: Used as a dependency in `export`, `import`, and `rollback` endpoints.
- **Behavior**: Raises 403 Forbidden if the user is not an owner.

### 2. `get_migration_service`
- **Purpose**: Provides a singleton instance of the `MigrationService`.
- **Usage**: Injects the business logic layer into route handlers.

## Usage Example

```python
@router.post("/export")
async def export_db(
    user: dict = Depends(require_tenant_owner),
    service: MigrationService = Depends(get_migration_service)
):
    # Only owners reach here
    return await service.export(...)
```
"""

from typing import Any, Dict

from fastapi import Depends, HTTPException, status

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.tenant_models import TENANT_ROLES
from second_brain_database.routes.auth.dependencies import get_current_user_dep
from second_brain_database.services.migration_service import migration_service

logger = get_logger(prefix="[MigrationDeps]")


async def require_tenant_owner(
    current_user: Dict[str, Any] = Depends(get_current_user_dep),
) -> Dict[str, Any]:
    """
    Require user to have owner role in their tenant.

    Migration operations are restricted to tenant owners only for security.

    Args:
        current_user: Current authenticated user

    Returns:
        User dict if authorized

    Raises:
        HTTPException: If user is not a tenant owner
    """
    user_id = current_user.get("_id") or current_user.get("user_id")

    # Check if user has any tenant memberships
    memberships_collection = db_manager.get_collection("tenant_memberships")
    membership = await memberships_collection.find_one(
        {"user_id": user_id, "role": "owner", "status": "active"}
    )

    if not membership:
        logger.warning(
            f"User {user_id} attempted migration operation without owner role"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Migration operations require tenant owner role",
        )

    logger.info(f"User {user_id} authorized for migration (owner role)")
    return current_user


async def get_migration_service():
    """
    Dependency to get migration service instance.

    Returns:
        MigrationService instance
    """
    return migration_service


async def validate_migration_permissions(
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
) -> Dict[str, Any]:
    """
    Validate user has permissions for migration operations.

    This is a comprehensive permission check that can be extended
    with additional validation logic.

    Args:
        current_user: Current authenticated user (must be owner)

    Returns:
        User dict with validated permissions
    """
    # Additional permission checks can be added here
    # For now, owner role is sufficient

    return current_user
