"""
# Migration Instance Dependencies

This module provides **dependency injection** for the Direct Migration feature.
It manages service instantiation and user authentication for instance-to-instance transfers.

## Key Dependencies

### 1. `get_migration_instance_service`
- **Purpose**: Provides a fresh instance of `MigrationInstanceService`.
- **Scope**: Per-request instantiation (stateless service).

### 2. `require_authenticated_user`
- **Purpose**: Ensures the request comes from a valid, logged-in user.
- **Usage**: Protects instance registration and transfer endpoints.
- **Note**: Unlike full migration, this doesn't strictly require `OWNER` role for all ops,
  but typically users manage their own instances.

## Usage Example

```python
@router.get("/instances")
async def list_instances(
    service: MigrationInstanceService = Depends(get_migration_instance_service)
):
    return await service.list_instances(...)
```
"""

from typing import Dict, Any
from fastapi import Depends
    return MigrationInstanceService()


async def require_authenticated_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Require authenticated user for instance operations."""
    return current_user
