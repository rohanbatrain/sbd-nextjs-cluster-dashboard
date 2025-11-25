"""
# Cluster Dependencies

This module provides **security dependencies** for inter-node communication.
It ensures that only authorized cluster nodes can access internal management endpoints.

## Security Model

Cluster communication is secured via a **Shared Secret Token** mechanism:
- **Token Verification**: Validates the `X-Cluster-Token` header against the configured secret.
- **Environment Isolation**: Supports an "insecure" mode for development when no token is set.

## Dependencies

### `verify_cluster_token`
- **Purpose**: Authenticates internal requests between nodes.
- **Usage**: Applied to sensitive endpoints like `register`, `promote`, and `replication`.
- **Behavior**:
    - Checks for `CLUSTER_AUTH_TOKEN` in settings.
    - Validates `X-Cluster-Token` header.
    - Raises 401/403 if invalid.

## Usage Example

```python
@router.post("/internal/sync")
async def sync_data(token: str = Depends(verify_cluster_token)):
    # Only trusted nodes reach here
    ...
```
"""

from fastapi import Header, HTTPException, status

from second_brain_database.config import settings


async def verify_cluster_token(
    x_cluster_token: str = Header(None, alias="X-Cluster-Token"),
) -> str:
    """
    Verify the cluster authentication token.
    """
    if not settings.CLUSTER_AUTH_TOKEN:
        # If no token configured, allow access (dev mode or insecure)
        return "insecure"

    if not x_cluster_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing cluster token",
        )

    if x_cluster_token != settings.CLUSTER_AUTH_TOKEN.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid cluster token",
        )

    return x_cluster_token
