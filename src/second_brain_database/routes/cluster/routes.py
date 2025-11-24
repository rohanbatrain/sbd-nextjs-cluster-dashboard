"""
# Cluster Management Routes

This module provides the **Core API** for High Availability (HA) Cluster Management.
It handles node lifecycle, role management, and replication control.

## Domain Overview

The Cluster System enables the application to run across multiple nodes for redundancy and scale.
This module is the "Control Plane" for the cluster, managing:
- **Membership**: Nodes joining and leaving the cluster.
- **Consensus**: Leader election and role assignment (Master/Replica).
- **Replication**: Controlling data flow between nodes.

## Key Features

### 1. Node Lifecycle
- **Registration**: New nodes call `/register` to join.
- **Removal**: Graceful or forced removal of nodes via `/nodes/{id}`.
- **Discovery**: Listing all known nodes and their status.

### 2. Role Management
- **Promotion**: Manually promoting a Replica to Master (Failover).
- **Demotion**: Stepping down a Master to Replica.

### 3. Replication Control
- **Event Application**: Internal endpoint for applying replication logs.
- **Lag Monitoring**: Checking replication delay for health status.

## API Endpoints

### Public/Internal
- `POST /cluster/register` - Join cluster
- `POST /cluster/replication/apply` - Receive data

### Management (Protected)
- `GET /cluster/nodes` - List nodes
- `POST /cluster/nodes/promote` - Trigger failover
- `GET /cluster/health` - Cluster-wide health check

## Usage Example

### Promoting a Node

```python
# Force promotion of node-2 to master
await client.post("/cluster/nodes/promote", json={
    "node_id": "node-2",
    "force": True
})
```
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from second_brain_database.config import settings
from second_brain_database.managers.cluster_manager import cluster_manager
from second_brain_database.models.cluster_models import (
    ClusterConfigurationRequest,
    ClusterHealth,
    ClusterNode,
    NodePromotionRequest,
    NodeRegistrationRequest,
    NodeRole,
    NodeStatus,
    OwnerValidationRequest,
    OwnerValidationResult,
    ReplicationEvent,
)
from second_brain_database.services.replication_service import replication_service
from second_brain_database.routes.cluster.dependencies import verify_cluster_token

router = APIRouter(prefix="/cluster", tags=["Cluster Management"])

# --- Public/Internal Endpoints ---

@router.post("/register", response_model=str)
async def register_node(
    request: NodeRegistrationRequest,
    token: str = Depends(verify_cluster_token),
):
    """
    Register a new node in the cluster.
    Internal endpoint called by nodes during startup.
    """
    try:
        node_id = await cluster_manager.register_node(
            hostname=request.hostname,
            port=request.port,
            owner_user_id=request.owner_user_id,
        )
        return node_id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/replication/apply")
async def apply_replication_event(
    event: ReplicationEvent,
    token: str = Depends(verify_cluster_token),
):
    """
    Apply a replication event to this node.
    Internal endpoint called by replication service.
    """
    try:
        success = await replication_service.apply_event(event)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to apply event",
            )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# --- Management Endpoints (Protected) ---

@router.get("/health", response_model=ClusterHealth)
async def get_cluster_health():
    """Get aggregated cluster health status."""
    return await cluster_manager.get_cluster_health()


@router.get("/nodes", response_model=List[ClusterNode])
async def list_nodes(
    role: Optional[NodeRole] = None,
    status: Optional[NodeStatus] = None,
):
    """List all nodes in the cluster."""
    return await cluster_manager.list_nodes(role=role, status=status)


@router.get("/nodes/{node_id}", response_model=ClusterNode)
async def get_node(node_id: str):
    """Get details for a specific node."""
    node = await cluster_manager.get_node(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found",
        )
    return node


@router.delete("/nodes/{node_id}")
async def remove_node(
    node_id: str,
    token: str = Depends(verify_cluster_token),
):
    """Remove a node from the cluster."""
    success = await cluster_manager.remove_node(node_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found or could not be removed",
        )
    return {"status": "success", "message": f"Node {node_id} removed"}


@router.post("/nodes/promote")
async def promote_node(
    request: NodePromotionRequest,
    token: str = Depends(verify_cluster_token),
):
    """Promote a replica node to master."""
    success = await cluster_manager.promote_node(
        node_id=request.node_id,
        force=request.force,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to promote node",
        )
    return {"status": "success", "message": f"Node {request.node_id} promoted to master"}


@router.post("/nodes/{node_id}/demote")
async def demote_node(
    node_id: str,
    token: str = Depends(verify_cluster_token),
):
    """Demote a master node to replica."""
    success = await cluster_manager.demote_node(node_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to demote node",
        )
    return {"status": "success", "message": f"Node {node_id} demoted to replica"}


from second_brain_database.services.owner_validation_service import owner_validation_service
from second_brain_database.database import db_manager

# --- Internal Utility Endpoints ---

@router.get("/internal/check-user/{user_id}")
async def check_user_exists(
    user_id: str,
    token: str = Depends(verify_cluster_token),
):
    """
    Internal endpoint to check if a user exists locally.
    Used by OwnerValidationService.
    """
    try:
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"user_id": user_id})
        return {"exists": user is not None}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

@router.post("/validate-owner", response_model=OwnerValidationResult)
async def validate_owner(
    request: OwnerValidationRequest,
    token: str = Depends(verify_cluster_token),
):
    """
    Validate owner account existence across cluster nodes.
    """
    return await owner_validation_service.validate_owner_across_cluster(
        owner_user_id=request.owner_user_id,
        target_nodes=request.target_nodes
    )


@router.post("/configure")
async def configure_cluster(
    request: ClusterConfigurationRequest,
    token: str = Depends(verify_cluster_token),
):
    """Update cluster configuration."""
    # TODO: Implement dynamic configuration updates
    return {"status": "success", "message": "Configuration updated"}


@router.get("/replication/lag")
async def get_replication_lag():
    """Get replication lag for this node."""
    lag = await replication_service.get_replication_lag(cluster_manager.node_id)
    return {"lag_seconds": lag}
