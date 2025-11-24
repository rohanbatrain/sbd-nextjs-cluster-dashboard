"""
# Migration Instance Models

This module defines the data structures for **direct server-to-server migrations**, allowing
seamless data transfer between registered SBD instances without intermediate file exports.
It handles instance registration, authentication, and real-time transfer progress tracking.

## Domain Model Overview

The instance migration system allows for:

- **Instance Registry**: A directory of known SBD instances (e.g., "Production", "Staging").
- **Direct Transfer**: Streaming data directly from one instance to another via API.
- **Conflict Resolution**: Strategies for handling duplicate data (Skip, Overwrite, Merge).

## Key Features

### 1. Instance Management
- **Registration**: Securely register remote instances with API keys.
- **Health Checks**: Monitor connectivity and sync status of registered instances.

### 2. Direct Transfer Protocol
- **Streaming**: Data is streamed in chunks to minimize memory usage.
- **Progress**: Real-time feedback on documents transferred and ETA.
- **Security**: All transfers occur over HTTPS with encrypted authentication.

## Usage Examples

### Registering a Remote Instance

```python
instance = InstanceRegistrationRequest(
    instance_name="Staging Server",
    instance_url="https://staging.api.sbd.com",
    api_key="sk_live_..."
)
```

### Initiating a Direct Transfer

```python
transfer = DirectTransferRequest(
    from_instance_id="inst_prod",
    to_instance_id="inst_staging",
    collections=["users", "settings"],
    conflict_resolution=ConflictResolution.OVERWRITE
)
```

## Module Attributes

Attributes:
    TransferStatus (Enum): Lifecycle states of a transfer (Pending, In Progress, etc.).
    ConflictResolution (Enum): Strategies for handling data collisions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


class TransferStatus(str, Enum):
    """Enumeration of direct transfer operation statuses.

    Attributes:
        PENDING: Transfer queued but not started.
        IN_PROGRESS: Transfer is actively moving data.
        COMPLETED: Transfer finished successfully.
        FAILED: Transfer stopped due to an error.
        CANCELLED: Transfer was manually stopped by user.
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConflictResolution(str, Enum):
    """Enumeration of conflict resolution strategies.

    Determines what happens when a document with the same ID already exists in the target.

    Attributes:
        SKIP: Ignore the incoming document and keep the existing one.
        OVERWRITE: Replace the existing document with the incoming one.
        MERGE: Attempt to merge fields (implementation specific).
    """
    SKIP = "skip"
    OVERWRITE = "overwrite"
    MERGE = "merge"


class SBDInstanceModel(BaseModel):
    """Model representing a registered SBD instance in the registry.

    Attributes:
        instance_id (str): Unique identifier for this instance.
        owner_id (str): User ID who owns/registered this instance.
        instance_name (str): Human-readable display name.
        instance_url (str): Base URL of the instance API.
        api_key_encrypted (str): Encrypted API key used for authenticating with this instance.
        size_gb (float): Total database size in GB (cached).
        collection_count (int): Number of collections (cached).
        last_synced (Optional[datetime]): Timestamp of the last health check/sync.
        created_at (datetime): Registration timestamp.
        metadata (Dict[str, Any]): Arbitrary metadata.
    """
    instance_id: str = Field(..., description="Unique identifier for this instance")
    owner_id: str = Field(..., description="User ID who owns this instance")
    instance_name: str = Field(..., description="Human-readable name", max_length=100)
    instance_url: str = Field(..., description="Base URL of the instance")
    api_key_encrypted: str = Field(..., description="Encrypted API key for authentication")
    size_gb: float = Field(default=0.0, description="Total database size in GB")
    collection_count: int = Field(default=0, description="Number of collections")
    last_synced: Optional[datetime] = Field(default=None, description="Last sync timestamp")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Registration timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("instance_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL is HTTPS for security (or localhost for dev)."""
        if not v.startswith("https://") and not v.startswith("http://localhost"):
            raise ValueError("Instance URL must use HTTPS (or localhost for development)")
        return v.rstrip("/")


class InstanceRegistrationRequest(BaseModel):
    """Request model for registering a new remote SBD instance.

    Attributes:
        instance_name (str): Display name for the instance.
        instance_url (str): Base URL of the instance API.
        api_key (str): API key for authentication (will be encrypted).
    """
    instance_name: str = Field(..., description="Human-readable name", max_length=100)
    instance_url: str = Field(..., description="Base URL of the instance")
    api_key: str = Field(..., description="API key for authentication", min_length=32)

    @field_validator("instance_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure URL is HTTPS for security (or localhost for dev)."""
        if not v.startswith("https://") and not v.startswith("http://localhost"):
            raise ValueError("Instance URL must use HTTPS (or localhost for development)")
        return v.rstrip("/")


class InstanceInfoResponse(BaseModel):
    """Response model containing public information about an instance.

    Attributes:
        instance_id (str): Unique identifier.
        instance_name (str): Display name.
        instance_url (str): Base URL.
        size_gb (float): Database size.
        collection_count (int): Collection count.
        collections (List[str]): List of available collections.
        status (str): Operational status ("online" or "offline").
        last_synced (Optional[datetime]): Last sync time.
        created_at (datetime): Registration time.
    """
    instance_id: str = Field(..., description="Instance ID")
    instance_name: str = Field(..., description="Instance name")
    instance_url: str = Field(..., description="Instance URL")
    size_gb: float = Field(..., description="Size in GB")
    collection_count: int = Field(..., description="Collection count")
    collections: List[str] = Field(..., description="Available collections")
    status: str = Field(..., description="Status (online/offline)")
    last_synced: Optional[datetime] = Field(None, description="Last sync time")
    created_at: datetime = Field(..., description="Creation time")


class DirectTransferRequest(BaseModel):
    """Request model to initiate a direct transfer between two instances.

    Attributes:
        from_instance_id (str): ID of the source instance.
        to_instance_id (str): ID of the target instance.
        collections (Optional[List[str]]): Specific collections to transfer. If None, transfers all.
        include_indexes (bool): Whether to transfer index definitions.
        conflict_resolution (ConflictResolution): Strategy for handling duplicates.
    """
    from_instance_id: str = Field(..., description="Source instance ID")
    to_instance_id: str = Field(..., description="Target instance ID")
    collections: Optional[List[str]] = Field(default=None, description="Specific collections to transfer")
    include_indexes: bool = Field(default=True, description="Include indexes")
    conflict_resolution: ConflictResolution = Field(default=ConflictResolution.SKIP, description="Conflict resolution strategy")

    @field_validator("from_instance_id", "to_instance_id")
    @classmethod
    def validate_not_same(cls, v: str, info) -> str:
        """Ensure source and target instances are different."""
        if info.field_name == "to_instance_id":
            from_id = info.data.get("from_instance_id")
            if from_id == v:
                raise ValueError("Source and target instances must be different")
        return v


class TransferProgress(BaseModel):
    """Real-time progress information for a direct transfer.

    Attributes:
        current_collection (Optional[str]): Collection currently being transferred.
        documents_transferred (int): Total documents transferred so far.
        total_documents (int): Total expected documents.
        percentage (float): Completion percentage (0-100).
        eta_seconds (Optional[int]): Estimated seconds remaining.
        error_message (Optional[str]): Error details if failed.
    """
    current_collection: Optional[str] = Field(None, description="Current collection")
    documents_transferred: int = Field(0, description="Documents transferred")
    total_documents: int = Field(0, description="Total documents")
    percentage: float = Field(0.0, description="Progress percentage")
    eta_seconds: Optional[int] = Field(None, description="ETA in seconds")
    error_message: Optional[str] = Field(None, description="Error message")


class DirectTransferResponse(BaseModel):
    """Response model for a direct transfer operation.

    Attributes:
        transfer_id (str): Unique transfer ID.
        status (TransferStatus): Current status.
        from_instance_name (str): Source instance name.
        to_instance_name (str): Target instance name.
        progress (TransferProgress): Current progress.
        created_at (datetime): Start time.
        updated_at (datetime): Last update time.
    """
    transfer_id: str = Field(..., description="Transfer ID")
    status: TransferStatus = Field(..., description="Status")
    from_instance_name: str = Field(..., description="Source name")
    to_instance_name: str = Field(..., description="Target name")
    progress: TransferProgress = Field(..., description="Progress info")
    created_at: datetime = Field(..., description="Start time")
    updated_at: datetime = Field(..., description="Last update time")


class TransferHistoryItem(BaseModel):
    """Historical record of a completed or failed transfer operation.

    Attributes:
        transfer_id (str): Transfer ID.
        from_instance_id (str): Source ID.
        to_instance_id (str): Target ID.
        from_instance_name (str): Source name.
        to_instance_name (str): Target name.
        status (TransferStatus): Final status.
        collections_transferred (List[str]): List of collections involved.
        documents_transferred (int): Total documents moved.
        duration_seconds (Optional[int]): Total duration.
        error_message (Optional[str]): Error details if failed.
        created_at (datetime): Start time.
        completed_at (Optional[datetime]): End time.
    """
    transfer_id: str = Field(..., description="Transfer ID")
    from_instance_id: str = Field(..., description="Source ID")
    to_instance_id: str = Field(..., description="Target ID")
    from_instance_name: str = Field(..., description="Source name")
    to_instance_name: str = Field(..., description="Target name")
    status: TransferStatus = Field(..., description="Status")
    collections_transferred: List[str] = Field(..., description="Collections transferred")
    documents_transferred: int = Field(..., description="Documents count")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds")
    error_message: Optional[str] = Field(None, description="Error message")
    created_at: datetime = Field(..., description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
