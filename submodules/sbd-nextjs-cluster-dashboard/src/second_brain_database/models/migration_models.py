"""
# Data Migration Models

This module defines the **data portability primitives** for the Second Brain Database.
It handles the export and import of database collections, ensuring data integrity,
schema compatibility, and safe transfer between environments.

## Domain Model Overview

The migration system is built around the concept of a **Migration Package**:

- **Metadata**: Versioning, source instance, timestamp, and checksums.
- **Data**: Serialized documents from selected collections.
- **Indexes**: Definitions for recreating database indexes.
- **Manifest**: A detailed inventory of the package contents.

## Key Features

### 1. Data Portability
- **Export**: Create compressed archives (GZIP/BZIP2) of specific collections or the entire DB.
- **Import**: Restore data with configurable conflict resolution (skip, overwrite, fail).
- **Validation**: Checksum verification to detect corruption during transfer.

### 2. Safety Mechanisms
- **Rollback**: Automatic creation of restore points before import operations.
- **Dry Run**: Validate packages and simulate imports without modifying data.
- **Progress Tracking**: Real-time status updates for long-running operations.

## Usage Examples

### Initiating an Export

```python
request = MigrationExportRequest(
    collections=["users", "families"],
    compression=CompressionType.GZIP,
    description="Weekly backup"
)
```

### Importing with Rollback

```python
request = MigrationImportRequest(
    migration_package_id="pkg_123",
    conflict_resolution="overwrite",
    create_rollback=True,
    validate_only=False
)
```

## Module Attributes

Attributes:
    MigrationStatus (Enum): Lifecycle states (Pending, In Progress, Completed, Failed).
    MigrationType (Enum): Direction of operation (Export, Import).
    CompressionType (Enum): Supported compression algorithms.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Enums
class MigrationStatus(str, Enum):
    """Enumeration of migration operation statuses.

    Tracks the lifecycle of an export or import job.

    Attributes:
        PENDING: Job created but not yet started.
        IN_PROGRESS: Job is currently running.
        COMPLETED: Job finished successfully.
        FAILED: Job encountered an error and stopped.
        ROLLED_BACK: Job was reverted to its pre-operation state.
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class MigrationType(str, Enum):
    """Enumeration of migration types.

    Defines the direction of data flow.

    Attributes:
        EXPORT: Data is being extracted from the database to a package.
        IMPORT: Data is being loaded from a package into the database.
    """
    EXPORT = "export"
    IMPORT = "import"


class CompressionType(str, Enum):
    """Enumeration of supported compression algorithms.

    Used to reduce the size of migration packages.

    Attributes:
        NONE: No compression (raw JSON/BSON).
        GZIP: Standard GZIP compression (good balance of speed/ratio).
        BZIP2: BZIP2 compression (higher ratio, slower speed).
    """
    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"


# Request Models
class MigrationExportRequest(BaseModel):
    """Request model for initiating a database export.

    Attributes:
        collections (Optional[List[str]]): List of collection names to export. If None, exports all.
        include_indexes (bool): Whether to include index definitions in the export. Defaults to True.
        compression (CompressionType): Compression algorithm to use. Defaults to GZIP.
        description (Optional[str]): Human-readable description of the export.
    """
    collections: Optional[List[str]] = Field(
        None, description="Specific collections to export (None for all)"
    )
    include_indexes: bool = Field(True, description="Include index definitions")
    compression: CompressionType = Field(
        CompressionType.GZIP, description="Compression type for export package"
    )
    description: Optional[str] = Field(
        None, max_length=500, description="Optional description of this export"
    )

    @field_validator("collections")
    @classmethod
    def validate_collections(cls, v):
        """Validate that the collections list is not empty if provided."""
        if v is not None and len(v) == 0:
            raise ValueError("Collections list cannot be empty if provided")
        return v


class MigrationImportRequest(BaseModel):
    """Request model for initiating a database import.

    Attributes:
        migration_package_id (Optional[str]): ID of a previously uploaded package to import.
        collections (Optional[List[str]]): Specific collections to import from the package.
        conflict_resolution (Literal["skip", "overwrite", "fail"]): Strategy for handling existing documents.
        create_rollback (bool): Whether to create a backup before importing. Defaults to True.
        validate_only (bool): If True, checks package validity without importing data.
    """
    migration_package_id: Optional[str] = Field(
        None, description="ID of previously uploaded migration package"
    )
    collections: Optional[List[str]] = Field(
        None, description="Specific collections to import (None for all)"
    )
    conflict_resolution: Literal["skip", "overwrite", "fail"] = Field(
        "fail", description="How to handle existing documents"
    )
    create_rollback: bool = Field(
        True, description="Create rollback point before import"
    )
    validate_only: bool = Field(
        False, description="Only validate package without importing"
    )

    @field_validator("collections")
    @classmethod
    def validate_collections(cls, v):
        """Validate that the collections list is not empty if provided."""
        if v is not None and len(v) == 0:
            raise ValueError("Collections list cannot be empty if provided")
        return v


class MigrationValidateRequest(BaseModel):
    """Request model for validating a migration package integrity.

    Attributes:
        migration_package_id (str): ID of the package to validate.
    """
    migration_package_id: str = Field(..., description="ID of migration package to validate")


class MigrationRollbackRequest(BaseModel):
    """Request model for rolling back a completed or failed migration.

    Attributes:
        migration_id (str): ID of the migration operation to revert.
        confirm (bool): Safety flag that must be set to True to execute rollback.
    """
    migration_id: str = Field(..., description="ID of migration to rollback")
    confirm: bool = Field(
        False, description="Confirmation flag to prevent accidental rollback"
    )

    @field_validator("confirm")
    @classmethod
    def validate_confirm(cls, v):
        """Ensure confirmation is explicitly provided."""
        if not v:
            raise ValueError("Rollback must be confirmed by setting confirm=true")
        return v


# Response Models
class CollectionMetadata(BaseModel):
    """Metadata describing a single collection within a migration package.

    Attributes:
        name (str): Name of the collection.
        document_count (int): Number of documents included.
        size_bytes (int): Uncompressed size of the collection data.
        checksum (str): SHA-256 checksum for data integrity verification.
        indexes (List[Dict[str, Any]]): List of index definitions.
    """
    name: str = Field(..., description="Collection name")
    document_count: int = Field(..., description="Number of documents")
    size_bytes: int = Field(..., description="Total size in bytes")
    checksum: str = Field(..., description="SHA-256 checksum of collection data")
    indexes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Index definitions"
    )


class MigrationMetadata(BaseModel):
    """Comprehensive metadata for a migration package.

    Attributes:
        version (str): Schema version of the migration package format.
        sbd_version (str): Version of the SBD application that created the export.
        export_timestamp (datetime): When the export was generated.
        source_instance (Optional[str]): Identifier of the source database instance.
        exported_by (str): ID of the user who initiated the export.
        tenant_id (Optional[str]): ID of the tenant (for multi-tenant exports).
        collections (List[CollectionMetadata]): Metadata for each included collection.
        total_documents (int): Total count of documents across all collections.
        total_size_bytes (int): Total uncompressed size of all data.
        checksum (str): Global checksum for the entire package.
        compression (CompressionType): Compression algorithm used.
        description (Optional[str]): User-provided description.
    """
    version: str = Field("1.0.0", description="Migration package format version")
    sbd_version: str = Field(..., description="SBD application version")
    export_timestamp: datetime = Field(..., description="When export was created")
    source_instance: Optional[str] = Field(
        None, description="Source instance identifier"
    )
    exported_by: str = Field(..., description="User ID who created export")
    tenant_id: Optional[str] = Field(None, description="Tenant ID if applicable")
    collections: List[CollectionMetadata] = Field(
        default_factory=list, description="Collection metadata"
    )
    total_documents: int = Field(0, description="Total document count")
    total_size_bytes: int = Field(0, description="Total size in bytes")
    checksum: str = Field(..., description="Overall package checksum")
    compression: CompressionType = Field(
        CompressionType.GZIP, description="Compression type used"
    )
    description: Optional[str] = Field(None, description="Export description")


class MigrationValidationResult(BaseModel):
    """Result of a migration package validation check.

    Attributes:
        valid (bool): True if the package is structurally valid and checksums match.
        errors (List[str]): List of critical validation errors.
        warnings (List[str]): List of non-critical warnings.
        metadata (Optional[MigrationMetadata]): Parsed metadata if validation succeeded.
        schema_compatible (bool): True if the data schema matches the current system.
        checksum_valid (bool): True if calculated checksums match metadata.
    """
    valid: bool = Field(..., description="Whether package is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    metadata: Optional[MigrationMetadata] = Field(
        None, description="Package metadata if valid"
    )
    schema_compatible: bool = Field(
        True, description="Whether schema is compatible"
    )
    checksum_valid: bool = Field(True, description="Whether checksums are valid")


class MigrationProgress(BaseModel):
    """Real-time progress tracking for a migration operation.

    Attributes:
        migration_id (str): ID of the migration being tracked.
        status (MigrationStatus): Current operational status.
        migration_type (MigrationType): Type of operation (Import/Export).
        progress_percentage (float): Overall completion percentage (0-100).
        current_collection (Optional[str]): Name of the collection currently being processed.
        collections_completed (int): Count of fully processed collections.
        total_collections (int): Total number of collections to process.
        documents_processed (int): Count of documents processed in the current step.
        total_documents (int): Total expected documents to process.
        started_at (datetime): Timestamp when the operation started.
        estimated_completion (Optional[datetime]): Estimated finish time based on current rate.
        error_message (Optional[str]): Error details if the operation failed.
    """
    migration_id: str = Field(..., description="Migration ID")
    status: MigrationStatus = Field(..., description="Current status")
    migration_type: MigrationType = Field(..., description="Type of migration")
    progress_percentage: float = Field(
        0.0, ge=0.0, le=100.0, description="Progress percentage"
    )
    current_collection: Optional[str] = Field(
        None, description="Currently processing collection"
    )
    collections_completed: int = Field(0, description="Number of collections completed")
    total_collections: int = Field(0, description="Total collections to process")
    documents_processed: int = Field(0, description="Documents processed so far")
    total_documents: int = Field(0, description="Total documents to process")
    started_at: datetime = Field(..., description="When migration started")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")


class MigrationResponse(BaseModel):
    """Standard response for migration API operations.

    Attributes:
        migration_id (str): ID of the migration.
        status (MigrationStatus): Current status.
        migration_type (MigrationType): Type of operation.
        created_at (datetime): Creation timestamp.
        created_by (str): User ID who initiated the operation.
        metadata (Optional[MigrationMetadata]): Package metadata.
        progress (Optional[MigrationProgress]): Current progress state.
        download_url (Optional[str]): Signed URL for downloading the export package.
        rollback_available (bool): True if this migration can be rolled back.
    """
    migration_id: str = Field(..., description="Unique migration ID")
    status: MigrationStatus = Field(..., description="Migration status")
    migration_type: MigrationType = Field(..., description="Type of migration")
    created_at: datetime = Field(..., description="When migration was created")
    created_by: str = Field(..., description="User ID who created migration")
    metadata: Optional[MigrationMetadata] = Field(
        None, description="Migration metadata"
    )
    progress: Optional[MigrationProgress] = Field(
        None, description="Progress information"
    )
    download_url: Optional[str] = Field(
        None, description="URL to download export package"
    )
    rollback_available: bool = Field(
        False, description="Whether rollback is available"
    )


class MigrationHistoryItem(BaseModel):
    """Summary item for migration history lists.

    Attributes:
        migration_id (str): Migration ID.
        migration_type (MigrationType): Type of operation.
        status (MigrationStatus): Final status.
        created_at (datetime): Start time.
        completed_at (Optional[datetime]): End time.
        created_by (str): Initiating user.
        collections_count (int): Number of collections involved.
        documents_count (int): Total documents processed.
        description (Optional[str]): User description.
    """
    migration_id: str = Field(..., description="Migration ID")
    migration_type: MigrationType = Field(..., description="Type of migration")
    status: MigrationStatus = Field(..., description="Final status")
    created_at: datetime = Field(..., description="When created")
    completed_at: Optional[datetime] = Field(None, description="When completed")
    created_by: str = Field(..., description="User ID")
    collections_count: int = Field(0, description="Number of collections")
    documents_count: int = Field(0, description="Number of documents")
    description: Optional[str] = Field(None, description="Description")


class MigrationHistoryResponse(BaseModel):
    """Response model for listing migration history.

    Attributes:
        migrations (List[MigrationHistoryItem]): List of historical migration records.
        total_count (int): Total number of records found.
    """
    migrations: List[MigrationHistoryItem] = Field(
        default_factory=list, description="List of migrations"
    )
    total_count: int = Field(0, description="Total number of migrations")


class CollectionListResponse(BaseModel):
    """Response model for listing available database collections.

    Attributes:
        collections (List[str]): List of collection names.
        total_count (int): Total number of collections.
    """
    collections: List[str] = Field(
        default_factory=list, description="List of collection names"
    )
    total_count: int = Field(0, description="Total number of collections")


# Database Document Models
class MigrationDocument(BaseModel):
    """Database document model for storing migration state in the 'migrations' collection.

    Attributes:
        migration_id (str): Unique migration ID.
        migration_type (MigrationType): Type of operation.
        status (MigrationStatus): Current status.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
        completed_at (Optional[datetime]): Completion timestamp.
        created_by (str): User ID who created migration.
        tenant_id (Optional[str]): Tenant ID if applicable.
        metadata (Optional[Dict[str, Any]]): Migration metadata.
        progress (Optional[Dict[str, Any]]): Progress data.
        package_file_path (Optional[str]): Storage path to the package file.
        package_size_bytes (Optional[int]): Size of the package file.
        package_checksum (Optional[str]): Checksum of the package file.
        rollback_available (bool): Whether rollback is available.
        rollback_data_path (Optional[str]): Storage path to rollback data.
        error_message (Optional[str]): Error message if failed.
        error_details (Optional[Dict[str, Any]]): Detailed error info.
    """
    migration_id: str = Field(..., description="Unique migration ID")
    migration_type: MigrationType = Field(..., description="Type of migration")
    status: MigrationStatus = Field(..., description="Current status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    created_by: str = Field(..., description="User ID who created migration")
    tenant_id: Optional[str] = Field(None, description="Tenant ID if applicable")

    # Migration details
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Migration metadata"
    )
    progress: Optional[Dict[str, Any]] = Field(None, description="Progress data")

    # File information
    package_file_path: Optional[str] = Field(
        None, description="Path to migration package file"
    )
    package_size_bytes: Optional[int] = Field(None, description="Package size")
    package_checksum: Optional[str] = Field(None, description="Package checksum")

    # Rollback information
    rollback_available: bool = Field(False, description="Rollback available")
    rollback_data_path: Optional[str] = Field(
        None, description="Path to rollback data"
    )

    # Error tracking
    error_message: Optional[str] = Field(None, description="Error message if failed")
    error_details: Optional[Dict[str, Any]] = Field(
        None, description="Detailed error information"
    )


class CollectionExportData(BaseModel):
    """Internal data structure for representing a single collection's export data.

    Attributes:
        collection_name (str): Name of the collection.
        documents (List[Dict[str, Any]]): List of document dictionaries.
        indexes (List[Dict[str, Any]]): List of index definitions.
        metadata (CollectionMetadata): Metadata about this collection export.
    """
    collection_name: str = Field(..., description="Collection name")
    documents: List[Dict[str, Any]] = Field(
        default_factory=list, description="Collection documents"
    )
    indexes: List[Dict[str, Any]] = Field(
        default_factory=list, description="Index definitions"
    )
    metadata: CollectionMetadata = Field(..., description="Collection metadata")
