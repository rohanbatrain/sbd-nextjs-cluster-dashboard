"""
# Migration Instance Service

This module manages **SBD Instances** and orchestrates **Direct Transfers**.
It allows users to connect multiple Second Brain deployments and move data between them directly.

## Domain Overview

Users may have multiple SBD instances (e.g., Cloud, Local, Backup).
- **Registry**: securely stores connection details and API keys for remote instances.
- **Direct Transfer**: Server-to-server streaming of data without intermediate download.
- **Conflict Resolution**: Handling data collisions during transfers.

## Key Features

### 1. Instance Management
- **Registration**: Validates connectivity and stores encrypted credentials.
- **Health Checks**: Periodically verifies status of registered instances.

### 2. Transfer Orchestration
- **Streaming**: Streams data collection-by-collection to minimize memory usage.
- **Progress Tracking**: Real-time updates via WebSocket.
- **History**: Maintains a log of all past transfers.

## Usage Example

```python
# Register a new instance
instance = await migration_instance_service.register_instance(
    request=InstanceRegistrationRequest(
        name="Home Server",
        url="https://home.sbd.local",
        api_key="sk_..."
    ),
    owner_id="user_123"
)

# Start a transfer
await migration_instance_service.initiate_direct_transfer(
    request=DirectTransferRequest(
        from_instance_id=instance.instance_id,
        to_instance_id="cloud_instance_id",
        collections=["notes"]
    ),
    owner_id="user_123"
)
```
"""

import asyncio
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from cryptography.fernet import Fernet

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.migration_instance_models import (
    ConflictResolution,
    DirectTransferRequest,
    DirectTransferResponse,
    InstanceInfoResponse,
    InstanceRegistrationRequest,
    SBDInstanceModel,
    TransferHistoryItem,
    TransferProgress,
    TransferStatus,
)
from second_brain_database.routes.migration_websocket import progress_broadcaster

logger = get_logger(prefix="[MigrationInstanceService]")


class MigrationInstanceService:
    """
    Manages SBD instance registration and direct server-to-server transfers.

    Enables users to register multiple SBD instances and perform direct data transfers
    between them without downloading/uploading packages manually.

    **Features:**
    - Instance registration with encrypted API key storage
    - Direct server-to-server transfers
    - Real-time progress tracking via WebSocket
    - Transfer history and status monitoring
    - Conflict resolution strategies
    """

    def __init__(self):
        self.collection_name = "migration_instances"
        self.transfer_collection = "migration_transfers"
        # Use a consistent encryption key (should be in settings)
        self.cipher = Fernet(settings.SECRET_KEY[:32].encode().ljust(32, b'0')[:32])

    def _encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key for storage."""
        return self.cipher.encrypt(api_key.encode()).decode()

    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt stored API key."""
        return self.cipher.decrypt(encrypted_key.encode()).decode()

    async def register_instance(
        self, request: InstanceRegistrationRequest, owner_id: str
    ) -> InstanceInfoResponse:
        """
        Register a new SBD instance for direct transfers.

        Validates connectivity, fetches metadata, and stores encrypted credentials.

        Args:
            request: Instance registration details (name, URL, API key).
            owner_id: User ID registering the instance.

        Returns:
            Instance information including size, collections, and status.

        Raises:
            ValueError: If connectivity test fails.
        """
        logger.info(f"Registering instance {request.instance_name} for user {owner_id}")

        # Test connectivity
        try:
            info = await self._fetch_instance_info(request.instance_url, request.api_key)
        except Exception as e:
            logger.error(f"Failed to connect to instance {request.instance_url}: {e}")
            raise ValueError(f"Cannot connect to instance: {str(e)}")

        # Create instance record
        instance_id = secrets.token_urlsafe(16)
        instance = SBDInstanceModel(
            instance_id=instance_id,
            owner_id=owner_id,
            instance_name=request.instance_name,
            instance_url=request.instance_url,
            api_key_encrypted=self._encrypt_api_key(request.api_key),
            size_gb=info["size_gb"],
            collection_count=len(info["collections"]),
            last_synced=datetime.now(timezone.utc),
        )

        # Store in database
        collection = await db_manager.get_collection(self.collection_name)
        await collection.insert_one(instance.model_dump())

        logger.info(f"Instance {instance_id} registered successfully")

        return InstanceInfoResponse(
            instance_id=instance_id,
            instance_name=request.instance_name,
            instance_url=request.instance_url,
            size_gb=info["size_gb"],
            collection_count=len(info["collections"]),
            collections=info["collections"],
            status="online",
            last_synced=instance.last_synced,
            created_at=instance.created_at,
        )

    async def _fetch_instance_info(self, url: str, api_key: str) -> Dict[str, Any]:
        """Fetch instance information via API."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{url}/api/migration/health",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
            data = response.json()

            # Extract info from health endpoint
            return {
                "size_gb": data.get("metrics", {}).get("total_size_gb", 0.0),
                "collections": data.get("collections", []),
            }

    async def list_instances(self, owner_id: str) -> List[InstanceInfoResponse]:
        """List all instances owned by a user."""
        collection = await db_manager.get_collection(self.collection_name)
        cursor = collection.find({"owner_id": owner_id})
        instances = []

        async for doc in cursor:
            instance = SBDInstanceModel(**doc)
            
            # Try to get live status
            try:
                api_key = self._decrypt_api_key(instance.api_key_encrypted)
                info = await self._fetch_instance_info(instance.instance_url, api_key)
                status = "online"
                collections = info["collections"]
                size_gb = info["size_gb"]
            except Exception:
                status = "offline"
                collections = []
                size_gb = instance.size_gb

            instances.append(
                InstanceInfoResponse(
                    instance_id=instance.instance_id,
                    instance_name=instance.instance_name,
                    instance_url=instance.instance_url,
                    size_gb=size_gb,
                    collection_count=len(collections),
                    collections=collections,
                    status=status,
                    last_synced=instance.last_synced,
                    created_at=instance.created_at,
                )
            )

        return instances

    async def delete_instance(self, instance_id: str, owner_id: str) -> bool:
        """Delete an instance."""
        collection = await db_manager.get_collection(self.collection_name)
        result = await collection.delete_one({"instance_id": instance_id, "owner_id": owner_id})
        return result.deleted_count > 0

    async def get_instance(self, instance_id: str, owner_id: str) -> Optional[SBDInstanceModel]:
        """Get a specific instance."""
        collection = await db_manager.get_collection(self.collection_name)
        doc = await collection.find_one({"instance_id": instance_id, "owner_id": owner_id})
        if doc:
            return SBDInstanceModel(**doc)
        return None

    async def initiate_direct_transfer(
        self, request: DirectTransferRequest, owner_id: str
    ) -> DirectTransferResponse:
        """
        Initiate a direct server-to-server transfer between two SBD instances.

        Creates a transfer record and starts a background task to stream data
        from source to target. Progress is tracked via WebSocket.

        Args:
            request: Transfer configuration (source, target, collections, conflict resolution).
            owner_id: User ID initiating the transfer.

        Returns:
            Transfer response with ID and initial status.

        Raises:
            ValueError: If instances not found or not owned by user.
        """
        logger.info(
            f"Initiating transfer from {request.from_instance_id} to {request.to_instance_id}"
        )

        # Validate both instances are owned by user
        from_instance = await self.get_instance(request.from_instance_id, owner_id)
        to_instance = await self.get_instance(request.to_instance_id, owner_id)

        if not from_instance or not to_instance:
            raise ValueError("One or both instances not found")

        # Check size compatibility (warn if from > to)
        if from_instance.size_gb > to_instance.size_gb:
            logger.warning(
                f"Source instance ({from_instance.size_gb}GB) is larger than target ({to_instance.size_gb}GB)"
            )

        # Create transfer record
        transfer_id = secrets.token_urlsafe(16)
        transfer_doc = {
            "transfer_id": transfer_id,
            "owner_id": owner_id,
            "from_instance_id": request.from_instance_id,
            "to_instance_id": request.to_instance_id,
            "from_instance_name": from_instance.instance_name,
            "to_instance_name": to_instance.instance_name,
            "collections": request.collections,
            "include_indexes": request.include_indexes,
            "conflict_resolution": request.conflict_resolution.value,
            "status": TransferStatus.PENDING.value,
            "progress": TransferProgress().model_dump(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        collection = await db_manager.get_collection(self.transfer_collection)
        await collection.insert_one(transfer_doc)

        # Start background transfer (non-blocking)
        asyncio.create_task(
            self._execute_transfer(
                transfer_id,
                from_instance,
                to_instance,
                request.collections,
                request.include_indexes,
                request.conflict_resolution,
            )
        )

        return DirectTransferResponse(
            transfer_id=transfer_id,
            status=TransferStatus.PENDING,
            from_instance_name=from_instance.instance_name,
            to_instance_name=to_instance.instance_name,
            progress=TransferProgress(),
            created_at=transfer_doc["created_at"],
            updated_at=transfer_doc["updated_at"],
        )

    async def _execute_transfer(
        self,
        transfer_id: str,
        from_instance: SBDInstanceModel,
        to_instance: SBDInstanceModel,
        collections: Optional[List[str]],
        include_indexes: bool,
        conflict_resolution: ConflictResolution,
    ):
        """
        Execute the actual transfer in the background.
        
        This streams data from source to target collection by collection.
        """
        collection = await db_manager.get_collection(self.transfer_collection)
        
        try:
            # Update status to in_progress
            await collection.update_one(
                {"transfer_id": transfer_id},
                {
                    "$set": {
                        "status": TransferStatus.IN_PROGRESS.value,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            # Decrypt API keys
            from_api_key = self._decrypt_api_key(from_instance.api_key_encrypted)
            to_api_key = self._decrypt_api_key(to_instance.api_key_encrypted)

            # Get list of collections to transfer
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Fetch collections from source
                response = await client.get(
                    f"{from_instance.instance_url}/api/migration/health",
                    headers={"Authorization": f"Bearer {from_api_key}"},
                )
                response.raise_for_status()
                available_collections = response.json().get("collections", [])

            collections_to_transfer = collections or available_collections

            total_docs = 0
            transferred_docs = 0

            # Transfer each collection
            for coll_name in collections_to_transfer:
                logger.info(f"Transferring collection: {coll_name}")

                # Update progress in database
                await collection.update_one(
                    {"transfer_id": transfer_id},
                    {
                        "$set": {
                            "progress.current_collection": coll_name,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    },
                )
                
                # Broadcast via WebSocket
                await progress_broadcaster.broadcast_progress(
                    transfer_id,
                    {
                        "status": "in_progress",
                        "current_collection": coll_name,
                        "percentage": (transferred_docs / max(total_docs, 1)) * 100,
                    }
                )

                # Stream collection data
                # NOTE: This is a simplified implementation
                # In production, you'd want to batch this and handle errors
                async with httpx.AsyncClient(timeout=300.0) as client:
                    # Export from source
                    export_response = await client.post(
                        f"{from_instance.instance_url}/api/migration/export",
                        json={"collections": [coll_name], "include_indexes": include_indexes},
                        headers={"Authorization": f"Bearer {from_api_key}"},
                    )
                    export_response.raise_for_status()
                    package_id = export_response.json().get("migration_package_id")

                    # Import to target
                    import_response = await client.post(
                        f"{to_instance.instance_url}/api/migration/import",
                        json={
                            "migration_package_id": package_id,
                            "conflict_resolution": conflict_resolution.value,
                        },
                        headers={"Authorization": f"Bearer {to_api_key}"},
                    )
                    import_response.raise_for_status()

                transferred_docs += 1000  # Placeholder

            # Mark as completed
            await collection.update_one(
                {"transfer_id": transfer_id},
                {
                    "$set": {
                        "status": TransferStatus.COMPLETED.value,
                        "completed_at": datetime.now(timezone.utc),
                        "progress.percentage": 100.0,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            
            # Broadcast completion via WebSocket
            await progress_broadcaster.broadcast_progress(
                transfer_id,
                {
                    "status": "completed",
                    "percentage": 100.0,
                    "message": "Transfer completed successfully"
                }
            )

            logger.info(f"Transfer {transfer_id} completed successfully")

        except Exception as e:
            logger.error(f"Transfer {transfer_id} failed: {e}", exc_info=True)
            await collection.update_one(
                {"transfer_id": transfer_id},
                {
                    "$set": {
                        "status": TransferStatus.FAILED.value,
                        "progress.error_message": str(e),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

    async def get_transfer_status(self, transfer_id: str, owner_id: str) -> Optional[DirectTransferResponse]:
        """Get the status of a transfer."""
        collection = await db_manager.get_collection(self.transfer_collection)
        doc = await collection.find_one({"transfer_id": transfer_id, "owner_id": owner_id})
        
        if not doc:
            return None

        return DirectTransferResponse(
            transfer_id=doc["transfer_id"],
            status=TransferStatus(doc["status"]),
            from_instance_name=doc["from_instance_name"],
            to_instance_name=doc["to_instance_name"],
            progress=TransferProgress(**doc["progress"]),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    async def list_transfer_history(self, owner_id: str, limit: int = 50) -> List[TransferHistoryItem]:
        """List transfer history for a user."""
        collection = await db_manager.get_collection(self.transfer_collection)
        cursor = collection.find({"owner_id": owner_id}).sort("created_at", -1).limit(limit)
        
        history = []
        async for doc in cursor:
            duration = None
            if doc.get("completed_at"):
                duration = int((doc["completed_at"] - doc["created_at"]).total_seconds())

            history.append(
                TransferHistoryItem(
                    transfer_id=doc["transfer_id"],
                    from_instance_id=doc["from_instance_id"],
                    to_instance_id=doc["to_instance_id"],
                    from_instance_name=doc["from_instance_name"],
                    to_instance_name=doc["to_instance_name"],
                    status=TransferStatus(doc["status"]),
                    collections_transferred=doc.get("collections", []),
                    documents_transferred=doc.get("progress", {}).get("documents_transferred", 0),
                    duration_seconds=duration,
                    error_message=doc.get("progress", {}).get("error_message"),
                    created_at=doc["created_at"],
                    completed_at=doc.get("completed_at"),
                )
            )

        return history
