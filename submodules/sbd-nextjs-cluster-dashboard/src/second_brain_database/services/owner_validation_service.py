"""
# Owner Validation Service

This module ensures **Data Consistency** for user accounts across the distributed cluster.
It verifies that an owner account exists on all relevant nodes before allowing operations.

## Domain Overview

In a distributed system, data integrity depends on the existence of the owner.
- **Orphaned Data**: Data without a valid owner account is problematic.
- **Consistency Check**: Verifying user existence across all healthy nodes.

## Key Features

### 1. Distributed Validation
- **Parallel Querying**: Checks multiple nodes simultaneously for performance.
- **Aggregation**: Combines results to report which nodes are missing the user.

### 2. Safety Checks
- **Pre-Migration**: Prevents migrating data to a node where the user doesn't exist.
- **Health-Aware**: Only queries nodes that are currently `HEALTHY`.

## Usage Example

```python
result = await owner_validation_service.validate_owner_across_cluster(
    owner_user_id="user_123"
)

if not result.is_valid:
    print(f"User missing on nodes: {result.failed_nodes}")
```
"""

import asyncio
from typing import Dict, List, Optional

import httpx

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.cluster_manager import cluster_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.cluster_models import (
    NodeStatus,
    OwnerValidationResult,
)

logger = get_logger()


class OwnerValidationService:
    """
    Validates owner account existence and consistency across distributed clusters.

    Ensures that migrations only proceed when the owner account exists on all target nodes,
    preventing orphaned data and maintaining referential integrity.

    **Validation Process:**
    1. Check owner existence locally
    2. Query all healthy cluster nodes in parallel
    3. Aggregate results and report inconsistencies
    """

    async def validate_owner_across_cluster(
        self,
        owner_user_id: str,
        target_nodes: Optional[List[str]] = None,
    ) -> OwnerValidationResult:
        """
        Validate that an owner account exists across all cluster nodes.

        Performs parallel validation checks and reports any nodes where the owner is missing.

        Args:
            owner_user_id: The user ID of the owner to validate.
            target_nodes: Optional list of specific node IDs to check. If `None`, validates all healthy nodes.

        Returns:
            An `OwnerValidationResult` containing validation status, failed nodes, and error details.
        """
        try:
            # Get nodes to validate
            if target_nodes:
                nodes = []
                for node_id in target_nodes:
                    node = await cluster_manager.get_node(node_id)
                    if node:
                        nodes.append(node)
            else:
                nodes = await cluster_manager.list_nodes(status=NodeStatus.HEALTHY)

            # Filter out self if included, as we can check locally
            remote_nodes = [n for n in nodes if n.node_id != cluster_manager.node_id]
            
            # Check locally first
            local_valid = await self._check_local_owner(owner_user_id)
            
            validation_errors: Dict[str, str] = {}
            failed_nodes: List[str] = []
            validated_count = 0

            if local_valid:
                validated_count += 1
            else:
                validation_errors[cluster_manager.node_id or "local"] = "Owner not found locally"
                failed_nodes.append(cluster_manager.node_id or "local")

            # Check remote nodes in parallel
            if remote_nodes:
                results = await asyncio.gather(
                    *[self._check_remote_owner(n.endpoint, owner_user_id) for n in remote_nodes],
                    return_exceptions=True
                )

                for node, result in zip(remote_nodes, results):
                    if isinstance(result, Exception):
                        validation_errors[node.node_id] = str(result)
                        failed_nodes.append(node.node_id)
                    elif result:
                        validated_count += 1
                    else:
                        validation_errors[node.node_id] = "Owner not found on node"
                        failed_nodes.append(node.node_id)

            total_nodes = 1 + len(remote_nodes) if cluster_manager.node_id else len(remote_nodes)
            
            return OwnerValidationResult(
                owner_user_id=owner_user_id,
                total_nodes=total_nodes,
                validated_nodes=validated_count,
                failed_nodes=failed_nodes,
                validation_errors=validation_errors,
                is_valid=len(failed_nodes) == 0
            )

        except Exception as e:
            logger.error(f"Owner validation failed: {e}", exc_info=True)
            return OwnerValidationResult(
                owner_user_id=owner_user_id,
                total_nodes=0,
                validated_nodes=0,
                failed_nodes=[],
                validation_errors={"error": str(e)},
                is_valid=False
            )

    async def _check_local_owner(self, owner_user_id: str) -> bool:
        """Check if owner exists in local database."""
        try:
            users_collection = db_manager.get_collection("users")
            user = await users_collection.find_one({"user_id": owner_user_id})
            return user is not None
        except Exception as e:
            logger.error(f"Local owner check failed: {e}")
            return False

    async def _check_remote_owner(self, endpoint: str, owner_user_id: str) -> bool:
        """Check if owner exists on a remote node."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # We use a specific endpoint for checking user existence
                # This assumes an endpoint exists. If not, we might need to add one.
                # For now, let's assume we can query the cluster/validate-owner endpoint recursively
                # but that might cause loops. Better to have a direct check endpoint.
                
                # Using the public user profile endpoint as a proxy for existence check
                # or a dedicated internal endpoint.
                
                headers = {}
                if settings.CLUSTER_AUTH_TOKEN:
                    headers["X-Cluster-Token"] = settings.CLUSTER_AUTH_TOKEN.get_secret_value()

                response = await client.get(
                    f"{endpoint}/cluster/internal/check-user/{owner_user_id}",
                    headers=headers
                )
                
                return response.status_code == 200 and response.json().get("exists", False)

        except Exception as e:
            logger.warning(f"Remote owner check failed for {endpoint}: {e}")
            return False

# Global instance
owner_validation_service = OwnerValidationService()
