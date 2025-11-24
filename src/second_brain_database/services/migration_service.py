"""
# Migration Service

This module is the **Core Engine** for database export, import, and validation.
It orchestrates the entire lifecycle of moving data in and out of the system.

## Domain Overview

Migrations are complex operations involving multiple steps and safety checks.
- **Export**: Reading data, sanitizing, compressing, encrypting, and packaging.
- **Import**: Decrypting, validating, creating rollbacks, and writing data.
- **Rollback**: Reverting to a previous state if an import fails.

## Key Features

### 1. Export Orchestration
- **Selective Export**: Full DB or specific collections.
- **Metadata Generation**: Checksums, version info, and manifest creation.

### 2. Import Orchestration
- **Safety First**: Validates package integrity before touching the DB.
- **Rollback Points**: Snapshots current data before overwriting.
- **Conflict Resolution**: Strategies for handling existing data (`skip`, `overwrite`, `fail`).

## Usage Example

```python
# Start an export
result = await migration_service.export_full_database(
    user_id="user_123",
    collections=["users", "notes"],
    compression=CompressionType.GZIP
)

# Import a package
await migration_service.import_migration_package(
    migration_package_id=result["migration_id"],
    user_id="user_123",
    conflict_resolution="overwrite"
)
```
"""

import asyncio
import gzip
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.migration_models import (
    CollectionExportData,
    CollectionMetadata,
    CompressionType,
    MigrationDocument,
    MigrationMetadata,
    MigrationProgress,
    MigrationStatus,
    MigrationType,
    MigrationValidationResult,
)
from second_brain_database.services.migration_security import (
    migration_encryption,
    migration_validator,
    migration_rate_limiter,
    migration_lock,
)
from second_brain_database.services.migration_audit import audit_logger
from second_brain_database.services.migration_sanitizer import data_sanitizer
from second_brain_database.services.migration_metrics import migration_metrics

logger = get_logger(prefix="[MigrationService]")


class MigrationService:
    """
    Service for handling database migration operations.

    This service orchestrates the entire migration lifecycle, including exporting data,
    importing packages, validating integrity, and managing rollbacks.

    **Key Features:**
    - **Full/Partial Export**: Support for selective collection migration.
    - **Secure Import**: Validation, encryption, and conflict resolution.
    - **Rollback Capability**: Automatic creation of restore points.
    - **Audit Logging**: Comprehensive tracking of all migration actions.
    - **Rate Limiting**: Protection against abuse.
    """

    # Collections that should always be migrated
    CORE_COLLECTIONS = [
        "users",
        "permanent_tokens",
        "families",
        "family_relationships",
        "family_invitations",
        "family_notifications",
        "family_token_requests",
        "family_admin_actions",
        "tenants",
        "tenant_memberships",
        "workspaces",
        "user_skills",
        "chat_sessions",
        "chat_messages",
        "token_usage",
        "message_votes",
    ]

    # IPAM collections
    IPAM_COLLECTIONS = [
        "ipam_regions",
        "ipam_hosts",
        "ipam_reservations",
        "ipam_shares",
        "ipam_user_preferences",
        "ipam_notifications",
        "ipam_notification_rules",
        "ipam_webhooks",
        "ipam_webhook_deliveries",
        "ipam_bulk_jobs",
        "ipam_audit_history",
        "ipam_user_quotas",
        "ipam_export_jobs",
    ]

    # Collections to exclude from migration
    EXCLUDED_COLLECTIONS = [
        "migrations",  # Migration history itself
        "backups",  # Backup metadata
    ]

    def __init__(self, migration_dir: str = "migrations"):
        """
        Initialize the migration service.

        Sets up the storage directory and initializes dependent security and audit components.

        Args:
            migration_dir: Directory path for storing migration packages (default: "migrations").
        """
        self.migration_dir = Path(migration_dir)
        self.migration_dir.mkdir(parents=True, exist_ok=True)
        
        # Security components
        self.encryption = migration_encryption
        self.validator = migration_validator
        self.rate_limiter = migration_rate_limiter
        self.lock = migration_lock
        
        # Audit and sanitization
        self.audit = audit_logger
        self.sanitizer = data_sanitizer
        self.metrics = migration_metrics
        
        logger.info(f"Migration service initialized with directory: {self.migration_dir}")

    async def export_full_database(
        self,
        user_id: str,
        tenant_id: Optional[str] = None,
        collections: Optional[List[str]] = None,
        include_indexes: bool = True,
        compression: CompressionType = CompressionType.GZIP,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Export full database or specific collections to a migration package.

        Orchestrates the export process:
        1.  Checks rate limits and acquires tenant lock.
        2.  Determines target collections.
        3.  Exports data and indexes for each collection.
        4.  Compiles metadata and calculates checksums.
        5.  Saves and encrypts the package.
        6.  Logs audit events and metrics.

        Args:
            user_id: The ID of the user performing the export.
            tenant_id: The tenant ID (optional, for multi-tenant isolation).
            collections: List of specific collections to export (None for all).
            include_indexes: Whether to include index definitions in the export.
            compression: Compression algorithm to use (default: GZIP).
            description: Optional user-provided description of the export.

        Returns:
            A dictionary containing the `migration_id`, `status`, and package details.

        Raises:
            ValueError: If rate limit exceeded, lock acquisition fails, or export errors occur.
        """
        migration_id = str(uuid.uuid4())
        logger.info(f"Starting database export {migration_id} by user {user_id}")
        start_time = datetime.now(timezone.utc)
        self.metrics.record_operation_start("export")

        try:
            # Check rate limit
            allowed, error_msg = self.rate_limiter.check_rate_limit(user_id, "export", limit_hours=1)
            if not allowed:
                logger.warning(f"Rate limit exceeded for user {user_id}: {error_msg}")
                self.audit.log_rate_limit_exceeded(user_id, "export")
                self.metrics.record_rate_limit_violation("export")
                raise ValueError(error_msg)
            
            # Acquire migration lock for tenant
            if tenant_id:
                lock_acquired, lock_error = await self.lock.acquire_lock(tenant_id)
                if not lock_acquired:
                    logger.warning(f"Failed to acquire lock for tenant {tenant_id}: {lock_error}")
                    raise ValueError(lock_error)
            
            # Determine collections to export
            collections_to_export = await self._get_collections_to_export(collections)
            logger.info(f"Exporting {len(collections_to_export)} collections")
            
            # Log export started
            self.audit.log_export_started(
                user_id=user_id,
                tenant_id=tenant_id,
                migration_id=migration_id,
                collections=collections_to_export,
            )

            # Create migration document
            migration_doc = await self._create_migration_document(
                migration_id=migration_id,
                migration_type=MigrationType.EXPORT,
                user_id=user_id,
                tenant_id=tenant_id,
                total_collections=len(collections_to_export),
            )

            # Export collections
            export_data = []
            total_documents = 0

            for idx, collection_name in enumerate(collections_to_export):
                logger.info(f"Exporting collection {collection_name} ({idx + 1}/{len(collections_to_export)})")

                # Update progress
                await self._update_migration_progress(
                    migration_id=migration_id,
                    current_collection=collection_name,
                    collections_completed=idx,
                    total_collections=len(collections_to_export),
                )

                # Export collection
                collection_data = await self._export_collection(
                    collection_name=collection_name,
                    include_indexes=include_indexes,
                )

                export_data.append(collection_data)
                total_documents += len(collection_data.documents)

            # Create migration package
            metadata = MigrationMetadata(
                sbd_version=settings.VERSION if hasattr(settings, "VERSION") else "unknown",
                export_timestamp=datetime.now(timezone.utc),
                exported_by=user_id,
                tenant_id=tenant_id,
                collections=[data.metadata for data in export_data],
                total_documents=total_documents,
                checksum="",  # Will be calculated
                compression=compression,
                description=description,
            )

            # Save migration package
            package_path = await self._save_migration_package(
                migration_id=migration_id,
                export_data=export_data,
                metadata=metadata,
                compression=compression,
            )

            # Calculate package checksum
            package_checksum = self._calculate_file_checksum(package_path)
            metadata.checksum = package_checksum
            
            # Encrypt package
            encrypted_path = package_path.parent / f"{migration_id}_encrypted.json.gz"
            encryption_key = self.encryption.generate_encryption_key()
            encryption_metadata = self.encryption.encrypt_file(
                package_path, encrypted_path, encryption_key
            )
            
            # Replace original with encrypted
            package_path.unlink()
            encrypted_path.rename(package_path)
            
            # Recalculate checksum for encrypted file
            encrypted_checksum = self._calculate_file_checksum(package_path)

            # Update migration document
            await self._complete_migration(
                migration_id=migration_id,
                status=MigrationStatus.COMPLETED,
                metadata=metadata.model_dump(),
                package_path=str(package_path),
                package_checksum=encrypted_checksum,
                package_size=package_path.stat().st_size,
            )
            
            # Record operation for rate limiting
            self.rate_limiter.record_operation(user_id, "export")
            
            # Release lock
            if tenant_id:
                await self.lock.release_lock(tenant_id)
            
            # Log export completed
            self.audit.log_export_completed(
                user_id=user_id,
                tenant_id=tenant_id,
                migration_id=migration_id,
                collections=collections_to_export,
                document_count=total_documents,
                package_size=package_path.stat().st_size,
            )
            
            # Record metrics
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.metrics.record_operation_complete(
                operation_type="export",
                status="success",
                user_id=user_id,
                duration=duration,
                package_size=package_path.stat().st_size
            )

            logger.info(f"Export {migration_id} completed successfully")

            return {
                "migration_id": migration_id,
                "status": MigrationStatus.COMPLETED,
                "collections_count": len(collections_to_export),
                "total_documents": total_documents,
                "package_size_bytes": package_path.stat().st_size,
                "package_path": str(package_path),
                "checksum": package_checksum,
            }

        except Exception as e:
            logger.error(f"Export {migration_id} failed: {e}", exc_info=True)
            
            # Record error metrics
            self.metrics.record_error("export", type(e).__name__)
            self.metrics.record_operation_complete(
                operation_type="export",
                status="failure",
                user_id=user_id,
                duration=(datetime.now(timezone.utc) - start_time).total_seconds()
            )
            
            # Release lock on failure
            if tenant_id:
                await self.lock.release_lock(tenant_id)
            
            await self._fail_migration(migration_id, str(e))
            # Don't expose internal errors to users
            raise ValueError("Export operation failed. Please contact support.")

    async def import_migration_package(
        self,
        migration_package_id: str,
        user_id: str,
        tenant_id: Optional[str] = None,
        collections: Optional[List[str]] = None,
        conflict_resolution: str = "fail",
        create_rollback: bool = True,
    ) -> Dict[str, Any]:
        """
        Import a migration package into the database.

        Orchestrates the import process:
        1.  Checks rate limits and acquires tenant lock.
        2.  Validates the package file and checksums.
        3.  Creates a rollback point (snapshot of current data).
        4.  Imports data collection by collection, handling conflicts.
        5.  Recreates indexes.
        6.  Logs audit events and metrics.

        Args:
            migration_package_id: The ID of the package to import.
            user_id: The ID of the user performing the import.
            tenant_id: The tenant ID (optional).
            collections: Specific collections to import (None for all in package).
            conflict_resolution: Strategy for existing data (`skip`, `overwrite`, `fail`).
            create_rollback: Whether to create a restore point before importing.

        Returns:
            A dictionary containing the `migration_id`, `status`, and import statistics.

        Raises:
            ValueError: If validation fails, rate limit exceeded, or import errors occur.
        """
        migration_id = str(uuid.uuid4())
        logger.info(f"Starting import {migration_id} from package {migration_package_id}")
        start_time = datetime.now(timezone.utc)
        self.metrics.record_operation_start("import")

        try:
            # Check rate limit
            allowed, error_msg = self.rate_limiter.check_rate_limit(user_id, "import", limit_hours=24)
            if not allowed:
                logger.warning(f"Rate limit exceeded for user {user_id}: {error_msg}")
                self.audit.log_rate_limit_exceeded(user_id, "import")
                self.metrics.record_rate_limit_violation("import")
                raise ValueError(error_msg)
            
            # Acquire migration lock for tenant
            if tenant_id:
                lock_acquired, lock_error = await self.lock.acquire_lock(tenant_id)
                if not lock_acquired:
                    logger.warning(f"Failed to acquire lock for tenant {tenant_id}: {lock_error}")
                    raise ValueError(lock_error)
            
            # Validate package file
            package_path = self.migration_dir / f"{migration_package_id}.json.gz"
            is_valid, validation_error = self.validator.validate_upload_file(package_path)
            if not is_valid:
                logger.error(f"Package validation failed: {validation_error}")
                self.audit.log_validation_failed(user_id, migration_id, validation_error)
                self.metrics.record_validation_failure(validation_error)
                raise ValueError(f"Invalid migration package: {validation_error}")
            
            # Load migration package
            package_data, metadata = await self._load_migration_package(migration_package_id)

            # Validate package
            validation_result = await self.validate_migration_package(migration_package_id)
            if not validation_result.valid:
                raise ValueError(f"Invalid migration package: {validation_result.errors}")

            # Determine collections to import
            collections_to_import = collections or [c.name for c in metadata.collections]
            logger.info(f"Importing {len(collections_to_import)} collections")

            # Create rollback point if requested
            rollback_path = None
            if create_rollback:
                rollback_path = await self._create_rollback_point(
                    migration_id=migration_id,
                    collections=collections_to_import,
                )

            # Create migration document
            await self._create_migration_document(
                migration_id=migration_id,
                migration_type=MigrationType.IMPORT,
                user_id=user_id,
                tenant_id=tenant_id,
                total_collections=len(collections_to_import),
                rollback_path=rollback_path,
            )

            # Import collections
            imported_count = 0
            total_documents = 0

            for idx, collection_name in enumerate(collections_to_import):
                logger.info(f"Importing collection {collection_name} ({idx + 1}/{len(collections_to_import)})")

                # Update progress
                await self._update_migration_progress(
                    migration_id=migration_id,
                    current_collection=collection_name,
                    collections_completed=idx,
                    total_collections=len(collections_to_import),
                )

                # Find collection data in package
                collection_data = next(
                    (c for c in package_data if c["collection_name"] == collection_name),
                    None,
                )

                if collection_data:
                    # Import collection
                    docs_imported = await self._import_collection(
                        collection_name=collection_name,
                        documents=collection_data["documents"],
                        indexes=collection_data.get("indexes", []),
                        conflict_resolution=conflict_resolution,
                    )
                    imported_count += 1
                    total_documents += docs_imported

            # Complete migration
            await self._complete_migration(
                migration_id=migration_id,
                status=MigrationStatus.COMPLETED,
                metadata=metadata.model_dump(),
            )
            
            # Record operation for rate limiting
            self.rate_limiter.record_operation(user_id, "import")
            
            # Release lock
            if tenant_id:
                await self.lock.release_lock(tenant_id)
                
            # Record metrics
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.metrics.record_operation_complete(
                operation_type="import",
                status="success",
                user_id=user_id,
                duration=duration
            )

            logger.info(f"Import {migration_id} completed successfully")

            return {
                "migration_id": migration_id,
                "status": MigrationStatus.COMPLETED,
                "collections_imported": imported_count,
                "total_documents": total_documents,
                "rollback_available": rollback_path is not None,
            }

        except Exception as e:
            logger.error(f"Import {migration_id} failed: {e}", exc_info=True)
            
            # Record error metrics
            self.metrics.record_error("import", type(e).__name__)
            self.metrics.record_operation_complete(
                operation_type="import",
                status="failure",
                user_id=user_id,
                duration=(datetime.now(timezone.utc) - start_time).total_seconds()
            )
            
            # Release lock on failure
            if tenant_id:
                await self.lock.release_lock(tenant_id)
            
            await self._fail_migration(migration_id, str(e))
            # Don't expose internal errors to users
            raise ValueError("Import operation failed. Please contact support.")

    async def validate_migration_package(
        self, migration_package_id: str
    ) -> MigrationValidationResult:
        """
        Perform comprehensive validation on a migration package.

        Checks:
        - **File Integrity**: Verifies the package file checksum.
        - **Data Integrity**: Verifies checksums for each collection.
        - **Schema Compatibility**: Checks version compatibility.
        - **Dependency Check**: Warns if target collections don't exist.

        Args:
            migration_package_id: The ID of the package to validate.

        Returns:
            A `MigrationValidationResult` object containing valid status, errors, and warnings.
        """
        logger.info(f"Validating migration package {migration_package_id}")

        errors = []
        warnings = []

        try:
            # Load package
            package_data, metadata = await self._load_migration_package(migration_package_id)

            # Validate checksum
            package_path = self.migration_dir / f"{migration_package_id}.json.gz"
            calculated_checksum = self._calculate_file_checksum(package_path)

            if calculated_checksum != metadata.checksum:
                errors.append(f"Checksum mismatch: expected {metadata.checksum}, got {calculated_checksum}")

            # Validate collection checksums
            for collection_data in package_data:
                collection_name = collection_data["collection_name"]
                collection_metadata = next(
                    (c for c in metadata.collections if c.name == collection_name),
                    None,
                )

                if collection_metadata:
                    # Calculate collection checksum
                    collection_checksum = self._calculate_data_checksum(
                        json.dumps(collection_data["documents"], sort_keys=True)
                    )

                    if collection_checksum != collection_metadata.checksum:
                        errors.append(
                            f"Collection {collection_name} checksum mismatch"
                        )

            # Check schema compatibility
            schema_compatible = True
            if hasattr(settings, "VERSION"):
                if metadata.sbd_version != settings.VERSION:
                    warnings.append(
                        f"Version mismatch: package from {metadata.sbd_version}, "
                        f"current version {settings.VERSION}"
                    )
                    schema_compatible = False

            # Validate collections exist
            available_collections = await self._get_all_collections()
            for collection_meta in metadata.collections:
                if collection_meta.name not in available_collections:
                    warnings.append(
                        f"Collection {collection_meta.name} does not exist in target database"
                    )

            valid = len(errors) == 0
            checksum_valid = not any("checksum" in e.lower() for e in errors)

            return MigrationValidationResult(
                valid=valid,
                errors=errors,
                warnings=warnings,
                metadata=metadata if valid else None,
                schema_compatible=schema_compatible,
                checksum_valid=checksum_valid,
            )

        except Exception as e:
            logger.error(f"Validation failed: {e}", exc_info=True)
            return MigrationValidationResult(
                valid=False,
                errors=[f"Validation error: {str(e)}"],
                warnings=warnings,
                metadata=None,
                schema_compatible=False,
                checksum_valid=False,
            )

    async def rollback_migration(self, migration_id: str) -> Dict[str, Any]:
        """
        Rollback a completed migration to its pre-import state.

        Uses the rollback data saved during the import process to restore
        collections to their previous state.

        **Process:**
        1.  Locates the rollback file for the given migration.
        2.  Clears the affected collections.
        3.  Restores the original documents from the rollback file.
        4.  Updates the migration status to `ROLLED_BACK`.

        Args:
            migration_id: The ID of the migration to rollback.

        Returns:
            A dictionary containing the rollback status and count of restored collections.

        Raises:
            ValueError: If migration not found or rollback data unavailable.
        """
        logger.info(f"Rolling back migration {migration_id}")

        try:
            # Get migration document
            migrations_collection = db_manager.get_collection("migrations")
            migration_doc = await migrations_collection.find_one(
                {"migration_id": migration_id}
            )

            if not migration_doc:
                raise ValueError(f"Migration {migration_id} not found")

            if not migration_doc.get("rollback_available"):
                raise ValueError(f"No rollback data available for migration {migration_id}")

            # Load rollback data
            rollback_path = Path(migration_doc["rollback_data_path"])
            rollback_data = await self._load_rollback_data(rollback_path)

            # Restore collections
            collections_restored = 0
            for collection_name, documents in rollback_data.items():
                logger.info(f"Restoring collection {collection_name}")

                collection = db_manager.get_collection(collection_name)

                # Clear collection
                await collection.delete_many({})

                # Restore documents
                if documents:
                    await collection.insert_many(documents)

                collections_restored += 1

            # Update migration status
            await migrations_collection.update_one(
                {"migration_id": migration_id},
                {
                    "$set": {
                        "status": MigrationStatus.ROLLED_BACK,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

            logger.info(f"Rollback {migration_id} completed successfully")

            return {
                "migration_id": migration_id,
                "status": MigrationStatus.ROLLED_BACK,
                "collections_restored": collections_restored,
            }

        except Exception as e:
            logger.error(f"Rollback {migration_id} failed: {e}", exc_info=True)
            raise

    # Private helper methods

    async def _get_collections_to_export(
        self, collections: Optional[List[str]] = None
    ) -> List[str]:
        """
        Determine the list of collections to export.

        Filters out system collections and excluded collections (like backups).
        If specific collections are requested, validates they exist.

        Args:
            collections: Optional list of specific collections to export.

        Returns:
            A list of collection names to be exported.
        """

    async def _get_all_collections(self) -> List[str]:
        """
        Retrieve all collection names from the database.

        Returns:
            A list of all collection names.

        Raises:
            RuntimeError: If the database connection is not active.
        """

    async def _export_collection(
        self, collection_name: str, include_indexes: bool = True
    ) -> CollectionExportData:
        """
        Export a single collection's data and metadata.

        Args:
            collection_name: Name of the collection to export.
            include_indexes: Whether to include index definitions.

        Returns:
            A `CollectionExportData` object containing documents, indexes, and metadata.
        """
        collection = db_manager.get_collection(collection_name)

        # Get all documents
        documents = await collection.find({}).to_list(length=None)

        # Get indexes if requested
        indexes = []
        if include_indexes:
            index_info = await collection.list_indexes().to_list(length=None)
            indexes = [idx for idx in index_info if idx["name"] != "_id_"]

        # Calculate metadata
        documents_json = json.dumps(documents, default=str, sort_keys=True)
        checksum = self._calculate_data_checksum(documents_json)

        metadata = CollectionMetadata(
            name=collection_name,
            document_count=len(documents),
            size_bytes=len(documents_json.encode("utf-8")),
            checksum=checksum,
            indexes=indexes,
        )

        return CollectionExportData(
            collection_name=collection_name,
            documents=documents,
            indexes=indexes,
            metadata=metadata,
        )

    async def _import_collection(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        indexes: List[Dict[str, Any]],
        conflict_resolution: str = "fail",
    ) -> int:
        """
        Import data into a single collection.

        Handles conflict resolution strategies:
        - `overwrite`: Deletes existing data before import.
        - `fail`: Raises error if collection is not empty.
        - `skip`: (Implicit) Appends data, potentially causing duplicate key errors if not careful.

        Args:
            collection_name: Target collection name.
            documents: List of document dictionaries to insert.
            indexes: List of index definitions to recreate.
            conflict_resolution: Strategy for handling existing data.

        Returns:
            The number of documents imported.

        Raises:
            ValueError: If conflict resolution fails (e.g., collection not empty).
        """
        collection = db_manager.get_collection(collection_name)

        # Handle conflicts
        if conflict_resolution == "overwrite":
            # Clear existing data
            await collection.delete_many({})
        elif conflict_resolution == "fail":
            # Check if collection has data
            existing_count = await collection.count_documents({})
            if existing_count > 0:
                raise ValueError(
                    f"Collection {collection_name} already has data. "
                    f"Use conflict_resolution='overwrite' or 'skip'"
                )

        # Insert documents
        if documents:
            await collection.insert_many(documents)

        # Create indexes
        for index in indexes:
            try:
                keys = index.get("key", {})
                options = {k: v for k, v in index.items() if k not in ["key", "v", "ns"]}
                await collection.create_index(list(keys.items()), **options)
            except Exception as e:
                logger.warning(f"Failed to create index on {collection_name}: {e}")

        return len(documents)

    async def _save_migration_package(
        self,
        migration_id: str,
        export_data: List[CollectionExportData],
        metadata: MigrationMetadata,
        compression: CompressionType,
    ) -> Path:
        """
        Save the migration package to disk.

        Serializes the export data and metadata into a JSON structure,
        optionally compressing it with GZIP.

        Args:
            migration_id: Unique identifier for the migration.
            export_data: List of exported collection data.
            metadata: Global migration metadata.
            compression: Compression type to apply.

        Returns:
            The file path of the saved package.
        """
        package_path = self.migration_dir / f"{migration_id}.json.gz"

        # Prepare package data
        package = {
            "metadata": metadata.model_dump(mode="json"),
            "collections": [
                {
                    "collection_name": data.collection_name,
                    "documents": data.documents,
                    "indexes": data.indexes,
                    "metadata": data.metadata.model_dump(mode="json"),
                }
                for data in export_data
            ],
        }

        # Save with compression
        if compression == CompressionType.GZIP:
            with gzip.open(package_path, "wt", encoding="utf-8") as f:
                json.dump(package, f, default=str, indent=2)
        else:
            with open(package_path, "w", encoding="utf-8") as f:
                json.dump(package, f, default=str, indent=2)

        logger.info(f"Saved migration package to {package_path}")
        return package_path

    async def _load_migration_package(
        self, migration_package_id: str
    ) -> tuple[List[Dict[str, Any]], MigrationMetadata]:
        """
        Load a migration package from disk.

        Handles both compressed (GZIP) and uncompressed files.

        Args:
            migration_package_id: ID of the package to load.

        Returns:
            A tuple containing the list of collection data and the migration metadata.

        Raises:
            FileNotFoundError: If the package file does not exist.
        """
        package_path = self.migration_dir / f"{migration_package_id}.json.gz"

        if not package_path.exists():
            raise FileNotFoundError(f"Migration package {migration_package_id} not found")

        # Load package
        try:
            with gzip.open(package_path, "rt", encoding="utf-8") as f:
                package = json.load(f)
        except gzip.BadGzipFile:
            # Try without compression
            with open(package_path, "r", encoding="utf-8") as f:
                package = json.load(f)

        metadata = MigrationMetadata(**package["metadata"])
        collections_data = package["collections"]

        return collections_data, metadata

    async def _create_rollback_point(
        self, migration_id: str, collections: List[str]
    ) -> str:
        """
        Create a snapshot of collections before modification.

        Saves the current state of the target collections to a separate rollback file.
        This allows for restoring the database if the import fails or needs to be reverted.

        Args:
            migration_id: ID of the migration operation.
            collections: List of collections to snapshot.

        Returns:
            The file path of the rollback data.
        """
        rollback_path = self.migration_dir / f"{migration_id}_rollback.json.gz"

        rollback_data = {}
        for collection_name in collections:
            collection = db_manager.get_collection(collection_name)
            documents = await collection.find({}).to_list(length=None)
            rollback_data[collection_name] = documents

        # Save rollback data
        with gzip.open(rollback_path, "wt", encoding="utf-8") as f:
            json.dump(rollback_data, f, default=str, indent=2)

        logger.info(f"Created rollback point at {rollback_path}")
        return str(rollback_path)

    async def _load_rollback_data(self, rollback_path: Path) -> Dict[str, List[Dict[str, Any]]]:
        """Load rollback data from file."""
        with gzip.open(rollback_path, "rt", encoding="utf-8") as f:
            return json.load(f)

    async def _create_migration_document(
        self,
        migration_id: str,
        migration_type: MigrationType,
        user_id: str,
        tenant_id: Optional[str],
        total_collections: int,
        rollback_path: Optional[str] = None,
    ) -> MigrationDocument:
        """Create migration tracking document."""
        migrations_collection = db_manager.get_collection("migrations")

        migration_doc = MigrationDocument(
            migration_id=migration_id,
            migration_type=migration_type,
            status=MigrationStatus.IN_PROGRESS,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by=user_id,
            tenant_id=tenant_id,
            progress={
                "collections_completed": 0,
                "total_collections": total_collections,
                "documents_processed": 0,
            },
            rollback_available=rollback_path is not None,
            rollback_data_path=rollback_path,
        )

        await migrations_collection.insert_one(migration_doc.model_dump())
        return migration_doc

    async def _update_migration_progress(
        self,
        migration_id: str,
        current_collection: str,
        collections_completed: int,
        total_collections: int,
    ):
        """Update migration progress."""
        migrations_collection = db_manager.get_collection("migrations")

        progress_percentage = (collections_completed / total_collections * 100) if total_collections > 0 else 0

        await migrations_collection.update_one(
            {"migration_id": migration_id},
            {
                "$set": {
                    "progress": {
                        "current_collection": current_collection,
                        "collections_completed": collections_completed,
                        "total_collections": total_collections,
                        "progress_percentage": progress_percentage,
                    },
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    async def _complete_migration(
        self,
        migration_id: str,
        status: MigrationStatus,
        metadata: Dict[str, Any],
        package_path: Optional[str] = None,
        package_checksum: Optional[str] = None,
        package_size: Optional[int] = None,
    ):
        """Mark migration as completed."""
        migrations_collection = db_manager.get_collection("migrations")

        update_data = {
            "status": status,
            "completed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "metadata": metadata,
        }

        if package_path:
            update_data["package_file_path"] = package_path
        if package_checksum:
            update_data["package_checksum"] = package_checksum
        if package_size:
            update_data["package_size_bytes"] = package_size

        await migrations_collection.update_one(
            {"migration_id": migration_id},
            {"$set": update_data},
        )

    async def _fail_migration(self, migration_id: str, error_message: str):
        """Mark migration as failed."""
        migrations_collection = db_manager.get_collection("migrations")

        await migrations_collection.update_one(
            {"migration_id": migration_id},
            {
                "$set": {
                    "status": MigrationStatus.FAILED,
                    "error_message": error_message,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return f"sha256:{sha256_hash.hexdigest()}"

    def _calculate_data_checksum(self, data: str) -> str:
        """Calculate SHA-256 checksum of data."""
        sha256_hash = hashlib.sha256()
        sha256_hash.update(data.encode("utf-8"))
        return f"sha256:{sha256_hash.hexdigest()}"


# Global migration service instance
migration_service = MigrationService()
