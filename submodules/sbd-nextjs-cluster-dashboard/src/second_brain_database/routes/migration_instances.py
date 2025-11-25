"""
# Migration Instance Routes

This module provides the **REST API endpoints** for Direct Server-to-Server Migrations.
It enables seamless data transfer between different SBD instances without manual file handling.

## Domain Overview

Direct Migration allows users to move their "Second Brain" from one server to another:
- **Source Instance**: The server sending the data.
- **Target Instance**: The server receiving the data.
- **Direct Transfer**: Data streams directly between servers via encrypted channels.

## Key Features

### 1. Instance Registry
- **Registration**: Users register their other SBD instances using API keys.
- **Discovery**: Automatically fetches instance metadata (size, version, health).
- **Management**: List, update, and remove registered instances.

### 2. Direct Transfer Control
- **Initiation**: Start a transfer from a registered source to the current target.
- **Monitoring**: Real-time progress tracking (bytes, documents, collections).
- **Flow Control**: Pause, resume, and cancel active transfers.

### 3. Bandwidth Management
- **Throttling**: Limit transfer speed to prevent network saturation.
- **Resumability**: Automatically resumes interrupted transfers from the last checkpoint.

## API Endpoints

### Instance Management
- `POST /migration/instances` - Register remote instance
- `GET /migration/instances` - List registered instances
- `DELETE /migration/instances/{id}` - Unregister instance

### Transfer Operations
- `POST /migration/transfer/direct` - Start transfer
- `GET /migration/transfer/{id}/status` - Check progress
- `POST /migration/transfer/{id}/control` - Pause/Resume/Cancel

## Usage Examples

### Registering an Instance

```python
await client.post("/migration/instances", json={
    "name": "Home Server",
    "url": "https://home.example.com",
    "api_key": "sk_..."
})
```

### Starting a Transfer

```python
await client.post("/migration/transfer/direct", json={
    "source_instance_id": "inst_123",
    "collections": ["all"],
    "bandwidth_limit_mbps": 10
})
```

## Module Attributes

Attributes:
    router (APIRouter): FastAPI router with `/migration/instances` prefix
    transfer_router (APIRouter): FastAPI router with `/migration/transfer` prefix
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.migration_instance_models import (
    DirectTransferRequest,
    DirectTransferResponse,
    InstanceInfoResponse,
    InstanceRegistrationRequest,
    TransferHistoryItem,
)
from second_brain_database.models.migration_advanced_models import (
    TransferControlRequest,
    BandwidthLimit,
)
from second_brain_database.routes.migration_instance_dependencies import (
    get_migration_instance_service,
    require_authenticated_user,
)
from second_brain_database.services.migration_instance_service import MigrationInstanceService
from second_brain_database.services.migration_resume_service import migration_resume_service

logger = get_logger(prefix="[MigrationInstanceRoutes]")

router = APIRouter(prefix="/migration/instances", tags=["migration-instances"])


@router.post("", response_model=InstanceInfoResponse, status_code=status.HTTP_201_CREATED)
async def register_instance(
    request: InstanceRegistrationRequest,
    current_user: Dict[str, Any] = Depends(require_authenticated_user),
    service: MigrationInstanceService = Depends(get_migration_instance_service),
):
    """
    Register a new SBD instance for direct transfers.
    
    This endpoint:
    1. Validates connectivity to the instance
    2. Fetches instance metadata (size, collections)
    3. Stores encrypted API credentials
    4. Returns instance information
    
    **Security**: API keys are encrypted before storage.
    """
    try:
        user_id = current_user.get("user_id") or current_user.get("_id")
        return await service.register_instance(request, str(user_id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to register instance: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register instance"
        )


@router.get("", response_model=List[InstanceInfoResponse])
async def list_instances(
    current_user: Dict[str, Any] = Depends(require_authenticated_user),
    service: MigrationInstanceService = Depends(get_migration_instance_service),
):
    """
    List all registered SBD instances owned by the current user.
    
    Returns instance details including:
    - Name, URL
    - Size (GB), collection count
    - Online/offline status
    - Last sync timestamp
    """
    user_id = current_user.get("user_id") or current_user.get("_id")
    return await service.list_instances(str(user_id))


@router.delete("/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instance(
    instance_id: str,
    current_user: Dict[str, Any] = Depends(require_authenticated_user),
    service: MigrationInstanceService = Depends(get_migration_instance_service),
):
    """
    Unregister an SBD instance.
    
    This removes the instance from the registry and deletes stored credentials.
    """
    user_id = current_user.get("user_id") or current_user.get("_id")
    deleted = await service.delete_instance(instance_id, str(user_id))
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instance not found"
        )


@router.get("/{instance_id}", response_model=InstanceInfoResponse)
async def get_instance_info(
    instance_id: str,
    current_user: Dict[str, Any] = Depends(require_authenticated_user),
    service: MigrationInstanceService = Depends(get_migration_instance_service),
):
    """
    Get detailed information about a specific instance.
    
    Fetches live data from the instance including current size and collections.
    """
    user_id = current_user.get("user_id") or current_user.get("_id")
    instance = await service.get_instance(instance_id, str(user_id))
    
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instance not found"
        )
    
    # Return basic info (live fetch handled by list_instances)
    return InstanceInfoResponse(
        instance_id=instance.instance_id,
        instance_name=instance.instance_name,
        instance_url=instance.instance_url,
        size_gb=instance.size_gb,
        collection_count=instance.collection_count,
        collections=[],
        status="unknown",
        last_synced=instance.last_synced,
        created_at=instance.created_at,
    )


# Transfer endpoints
transfer_router = APIRouter(prefix="/migration/transfer", tags=["migration-transfer"])


@transfer_router.post("/direct", response_model=DirectTransferResponse, status_code=status.HTTP_202_ACCEPTED)
async def initiate_direct_transfer(
    request: DirectTransferRequest,
    current_user: Dict[str, Any] = Depends(require_authenticated_user),
    service: MigrationInstanceService = Depends(get_migration_instance_service),
):
    """
    Initiate a direct server-to-server transfer.
    
    This endpoint:
    1. Validates both instances are owned by the user
    2. Checks size compatibility (warns if source > target)
    3. Creates a transfer job
    4. Starts background transfer process
    
    **Process**:
    - Data streams directly from source to target
    - Progress can be monitored via GET /migration/transfer/{id}/status
    - Collections transferred one by one
    
    **Returns**: Transfer ID and initial status
    """
    try:
        user_id = current_user.get("user_id") or current_user.get("_id")
        return await service.initiate_direct_transfer(request, str(user_id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to initiate transfer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate transfer"
        )


@transfer_router.get("/{transfer_id}/status", response_model=DirectTransferResponse)
async def get_transfer_status(
    transfer_id: str,
    current_user: Dict[str, Any] = Depends(require_authenticated_user),
    service: MigrationInstanceService = Depends(get_migration_instance_service),
):
    """
    Get the current status of a transfer operation.
    
    Returns:
    - Transfer status (pending, in_progress, completed, failed)
    - Progress information (current collection, docs transferred, percentage)
    - Timestamps (created, updated)
    """
    user_id = current_user.get("user_id") or current_user.get("_id")
    transfer = await service.get_transfer_status(transfer_id, str(user_id))
    
    if not transfer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer not found"
        )
    
    return transfer


@transfer_router.get("", response_model=List[TransferHistoryItem])
async def list_transfer_history(
    current_user: Dict[str, Any] = Depends(require_authenticated_user),
    service: MigrationInstanceService = Depends(get_migration_instance_service),
    limit: int = 50,
):
    """
    List transfer history for the current user.
    
    Returns up to `limit` most recent transfers with:
    - Source/target instances
    - Status and progress
    - Duration (if completed)
    - Error messages (if failed)
    """
    user_id = current_user.get("user_id") or current_user.get("_id")
    return await service.list_transfer_history(str(user_id), limit)


@transfer_router.post("/{transfer_id}/control")
async def control_transfer(
    transfer_id: str,
    request: TransferControlRequest,
    current_user: Dict[str, Any] = Depends(require_authenticated_user),
):
    """
    Control a transfer (pause/resume/cancel).
    
    **Actions**:
    - `pause`: Temporarily halt the transfer
    - `resume`: Continue from last checkpoint
    - `cancel`: Permanently stop and mark as cancelled
    """
    user_id = current_user.get("user_id") or current_user.get("_id")
    
    if request.action == "pause":
        success = await migration_resume_service.pause_transfer(transfer_id)
        return {"status": "paused" if success else "error", "message": "Transfer paused"}
    
    elif request.action == "resume":
        success = await migration_resume_service.resume_transfer(transfer_id)
        return {"status": "resumed" if success else "error", "message": "Transfer resumed"}
    
    elif request.action == "cancel":
        # Mark transfer as cancelled in database
        from second_brain_database.database import db_manager
        collection = await db_manager.get_collection("migration_transfers")
        result = await collection.update_one(
            {"transfer_id": transfer_id, "owner_id": str(user_id)},
            {"$set": {"status": "cancelled"}}
        )
        return {"status": "cancelled" if result.modified_count > 0 else "error"}
    
    raise HTTPException(status_code=400, detail="Invalid action")
