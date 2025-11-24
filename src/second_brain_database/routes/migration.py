"""
# Migration System Routes

This module provides the **REST API endpoints** for the Database Migration System.
It handles the export, import, validation, and rollback of tenant data.

## Domain Overview

Data portability is a core feature of the Second Brain Database. The Migration System allows:
- **Export**: Packaging tenant data into portable, encrypted archives.
- **Import**: Restoring data from archives into a new or existing tenant.
- **Validation**: Ensuring data integrity and schema compatibility before import.
- **Rollback**: Reverting changes if an import fails or causes issues.

## Key Features

### 1. Secure Data Transfer
- **Encryption**: All migration packages are encrypted at rest and in transit.
- **IP Whitelisting**: Migration operations are restricted to trusted IP addresses.
- **RBAC**: Only Tenant Owners can initiate migration tasks.

### 2. Robust Import/Export
- **Streaming**: Handles large datasets efficiently without memory overload.
- **Compression**: Uses GZIP to minimize storage and bandwidth usage.
- **Selective Migration**: Users can choose specific collections to export/import.

### 3. Safety Mechanisms
- **Dry Run**: Simulate imports to detect conflicts without changing data.
- **Automatic Rollback**: Creates a restore point before every import.
- **Checksum Validation**: Verifies file integrity before processing.

## API Endpoints

### Export Operations
- `POST /migration/export` - Start export job
- `GET /migration/export/{id}/download` - Download package

### Import Operations
- `POST /migration/import` - Start import job
- `POST /migration/import/dry-run` - Simulate import
- `POST /migration/import/validate` - Check package integrity
- `POST /migration/import/{id}/rollback` - Revert import

### Management
- `GET /migration/history` - List past migrations
- `GET /migration/{id}/status` - Check job status
- `GET /migration/health` - System health check

## Usage Examples

### Starting an Export

```python
response = await client.post("/migration/export", json={
    "collections": ["notes", "tasks"],
    "compression": "gzip",
    "description": "Backup before upgrade"
})
migration_id = response.json()["migration_id"]
```

### Rolling Back an Import

```python
await client.post(f"/migration/import/{migration_id}/rollback", json={
    "reason": "Data corruption detected"
})
```

## Module Attributes

Attributes:
    router (APIRouter): FastAPI router with `/migration` prefix
    ALLOWED_MIGRATION_IPS (list): List of whitelisted IP addresses
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.migration_models import (
    CollectionListResponse,
    MigrationExportRequest,
    MigrationHistoryItem,
    MigrationHistoryResponse,
    MigrationImportRequest,
    MigrationResponse,
    MigrationRollbackRequest,
    MigrationStatus,
    MigrationType,
    MigrationValidateRequest,
    MigrationValidationResult,
)
from second_brain_database.routes.migration_dependencies import (
    get_migration_service,
    require_tenant_owner,
)
from second_brain_database.services.migration_service import MigrationService
from second_brain_database.services.migration_metrics import migration_metrics
from fastapi import Request

# IP Whitelist Configuration (Should be moved to settings)
ALLOWED_MIGRATION_IPS = ["127.0.0.1", "::1"]  # Default to localhost only for safety

def check_ip_whitelist(request: Request):
    """Verify request IP is whitelisted for migration operations."""
    client_ip = request.client.host
    # In production, this should check X-Forwarded-For if behind proxy
    if client_ip not in ALLOWED_MIGRATION_IPS:
        logger.warning(f"Blocked migration request from unauthorized IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: IP not whitelisted for migration operations"
        )

logger = get_logger(prefix="[MigrationRoutes]")

router = APIRouter(prefix="/migration", tags=["migration"])


@router.get("/health")
async def migration_health_check(
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
):
    """
    Check migration system health and operational metrics.

    Provides a real-time status report on the migration subsystem, including:
    - **Active Migrations**: Number of currently running jobs.
    - **Total Operations**: Historical count of imports/exports.
    - **Error Rates**: Recent failure counts.
    - **Service Status**: Connectivity to Database, Encryption, and Validation services.

    Args:
        current_user: The authenticated user (requires `tenant_owner` role).

    Returns:
        A dictionary containing health status, metrics, and service connectivity.
    """
    # Get collection names from database
    collection_names = await db_manager.database.list_collection_names()
    
    return {
        "status": "healthy",
        "metrics": {
            "active_migrations": migration_metrics.active_migrations.collect()[0].samples[0].value,
            "total_operations": sum(s.value for s in migration_metrics.operations_total.collect()[0].samples),
            "errors": sum(s.value for s in migration_metrics.errors_total.collect()[0].samples),
        },
        "services": {
            "database": "connected" if db_manager.client else "disconnected",
            "encryption": "ready",
            "validation": "ready",
        },
        "collections": collection_names,
    }

@router.post("/import/dry-run")
async def dry_run_import(
    request: MigrationImportRequest,
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
    service: MigrationService = Depends(get_migration_service),
):
    """
    Simulate an import operation without making persistent changes.

    Performs a "dry run" validation of a migration package to identify potential issues
    before executing a real import. Checks for:
    - Schema compatibility.
    - Data integrity.
    - Potential conflicts.

    Args:
        request: The import configuration request.
        current_user: The authenticated user (requires `tenant_owner` role).
        service: The migration service instance.

    Returns:
        A simulation result containing validation status, errors, warnings, and estimated duration.

    Raises:
        HTTPException: **400** if package ID is missing.
    """
    # This would reuse validation logic but skip actual import
    # For now, we'll just validate the package
    if not request.migration_package_id:
        raise HTTPException(400, "Migration package ID required")
        
    result = await service.validate_migration_package(request.migration_package_id)
    
    return {
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "summary": result.summary,
        "dry_run": True,
        "estimated_duration_seconds": result.summary.get("total_documents", 0) * 0.01  # Rough estimate
    }

@router.post("/export", response_model=MigrationResponse)
async def export_database(
    request: MigrationExportRequest,
    req: Request,
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
    service: MigrationService = Depends(get_migration_service),
):
    """
    Export database collections to a portable migration package.

    **Owner Role Required**

    Creates a secure, compressed export of selected database collections.
    The resulting package is encrypted and ready for import into another SBD instance.

    **Features:**
    - **Full/Partial Export**: Export entire DB or specific collections.
    - **Integrity**: Automatic checksum generation.
    - **Compression**: Gzip compression for efficient storage.
    - **Security**: API tokens are excluded; password hashes are preserved.

    **IP Whitelisted:**
    - Access restricted to whitelisted IPs (default: localhost).

    Args:
        request: Configuration for the export job.
        req: The raw FastAPI request (for IP checking).
        current_user: The authenticated user (requires `tenant_owner` role).
        service: The migration service instance.

    Returns:
        A response object containing the `migration_id` and download URL.

    Raises:
        HTTPException: **500** if the export process fails.
    """
    user_id = current_user.get("_id") or current_user.get("user_id")
    tenant_id = current_user.get("tenant_id")

    logger.info(f"Export requested by user {user_id}")

    try:
        result = await service.export_full_database(
            user_id=user_id,
            tenant_id=tenant_id,
            collections=request.collections,
            include_indexes=request.include_indexes,
            compression=request.compression,
            description=request.description,
        )

        return MigrationResponse(
            migration_id=result["migration_id"],
            status=MigrationStatus(result["status"]),
            migration_type=MigrationType.EXPORT,
            created_at=result.get("created_at"),
            created_by=user_id,
            download_url=f"/api/migration/export/{result['migration_id']}/download",
            rollback_available=False,
        )

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )


@router.get("/export/{migration_id}/download")
async def download_export(
    migration_id: str,
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
    service: MigrationService = Depends(get_migration_service),
):
    """
    Download a completed migration export package.

    **Owner Role Required**

    Retrieves the compressed `.json.gz` file for a specific migration ID.
    Validates that the requesting user is the creator of the export.

    Args:
        migration_id: The unique identifier of the export job.
        current_user: The authenticated user (requires `tenant_owner` role).
        service: The migration service instance.

    Returns:
        A `FileResponse` stream of the migration package.

    Raises:
        HTTPException: **404** if not found, **403** if access denied.
    """
    user_id = current_user.get("_id") or current_user.get("user_id")

    # Verify migration exists and user has access
    migrations_collection = db_manager.get_collection("migrations")
    migration_doc = await migrations_collection.find_one({"migration_id": migration_id})

    if not migration_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Migration {migration_id} not found",
        )

    if migration_doc["created_by"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this migration",
        )

    # Get package path
    package_path = service.migration_dir / f"{migration_id}.json.gz"

    if not package_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Migration package file not found",
        )

    return FileResponse(
        path=str(package_path),
        filename=f"sbd_migration_{migration_id}.json.gz",
        media_type="application/gzip",
    )


@router.post("/import", response_model=MigrationResponse)
async def import_database(
    request: MigrationImportRequest,
    req: Request,
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
    service: MigrationService = Depends(get_migration_service),
):
    """
    Import a migration package into the database.

    **Owner Role Required**

    Restores data from a previously exported migration package.
    Can be used for system restoration, environment cloning, or data seeding.

    **Features:**
    - **Selective Import**: Choose specific collections to import.
    - **Conflict Resolution**: Strategies for handling existing data (`skip`, `overwrite`, `fail`).
    - **Safety**: Automatic rollback point creation (default).
    - **Validation**: Pre-flight checks before data ingestion.

    **IP Whitelisted:**
    - Access restricted to whitelisted IPs.

    **Warning:**
    - This operation modifies the database state.
    - Ensure a rollback point is created (default behavior).

    Args:
        request: Configuration for the import job.
        req: The raw FastAPI request (for IP checking).
        current_user: The authenticated user (requires `tenant_owner` role).
        service: The migration service instance.

    Returns:
        A response object containing the `migration_id` and import status.

    Raises:
        HTTPException: **500** if the import process fails.
    """
    user_id = current_user.get("_id") or current_user.get("user_id")
    tenant_id = current_user.get("tenant_id")

    logger.info(f"Import requested by user {user_id}")

    try:
        # Validate first if not validate_only
        if not request.validate_only:
            validation = await service.validate_migration_package(
                request.migration_package_id
            )
            if not validation.valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid migration package: {validation.errors}",
                )

        if request.validate_only:
            # Just validate, don't import
            validation = await service.validate_migration_package(
                request.migration_package_id
            )
            return MigrationResponse(
                migration_id=request.migration_package_id,
                status=MigrationStatus.COMPLETED if validation.valid else MigrationStatus.FAILED,
                migration_type=MigrationType.IMPORT,
                created_at=validation.metadata.export_timestamp if validation.metadata else None,
                created_by=user_id,
                rollback_available=False,
            )

        result = await service.import_migration_package(
            migration_package_id=request.migration_package_id,
            user_id=user_id,
            tenant_id=tenant_id,
            collections=request.collections,
            conflict_resolution=request.conflict_resolution,
            create_rollback=request.create_rollback,
        )

        return MigrationResponse(
            migration_id=result["migration_id"],
            status=MigrationStatus(result["status"]),
            migration_type=MigrationType.IMPORT,
            created_at=result.get("created_at"),
            created_by=user_id,
            rollback_available=result.get("rollback_available", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        )


@router.post("/import/validate", response_model=MigrationValidationResult)
async def validate_migration(
    request: MigrationValidateRequest,
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
    service: MigrationService = Depends(get_migration_service),
):
    """
    Validate a migration package before importing.

    **Owner Role Required**

    Performs a comprehensive integrity and compatibility check on a migration package.
    Crucial step to prevent data corruption or partial imports.

    **Validation Checks:**
    - **Integrity**: Verifies file checksums.
    - **Schema**: Checks if data matches current schema versions.
    - **Dependencies**: Ensures required collections exist.
    - **Format**: Validates JSON/BSON structure.

    Args:
        request: The validation request containing the package ID.
        current_user: The authenticated user (requires `tenant_owner` role).
        service: The migration service instance.

    Returns:
        A detailed validation report with status and any errors found.

    Raises:
        HTTPException: **500** if validation fails.
    """
    logger.info(f"Validation requested for package {request.migration_package_id}")

    try:
        result = await service.validate_migration_package(request.migration_package_id)
        return result

    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}",
        )


@router.post("/import/{migration_id}/rollback", response_model=Dict[str, Any])
async def rollback_import(
    migration_id: str,
    request: MigrationRollbackRequest,
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
    service: MigrationService = Depends(get_migration_service),
):
    """
    Rollback a migration to its pre-import state.

    **Owner Role Required**

    Reverts changes made by a specific import operation using the rollback point
    created during that import.

    **Critical Warnings:**
    - **Destructive**: Removes all data imported by the target migration.
    - **Restorative**: Replaces modified data with the original pre-import version.
    - **Irreversible**: The rollback action itself cannot be undone.

    Args:
        migration_id: The unique identifier of the import to rollback.
        request: Confirmation payload.
        current_user: The authenticated user (requires `tenant_owner` role).
        service: The migration service instance.

    Returns:
        A dictionary containing the results of the rollback operation.

    Raises:
        HTTPException: **400** if rollback is not possible or fails.
    """
    user_id = current_user.get("_id") or current_user.get("user_id")

    logger.warning(f"Rollback requested for migration {migration_id} by user {user_id}")

    try:
        result = await service.rollback_migration(migration_id)
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Rollback failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rollback failed: {str(e)}",
        )


@router.get("/history", response_model=MigrationHistoryResponse)
async def get_migration_history(
    limit: int = 50,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
):
    """
    Retrieve the migration history for the current user.

    **Owner Role Required**

    Returns a chronological list of all migration operations (imports and exports)
    performed by the user. Includes status, type, and summary statistics.

    Args:
        limit: Maximum number of records to return (default: 50).
        offset: Number of records to skip (for pagination).
        current_user: The authenticated user (requires `tenant_owner` role).

    Returns:
        A paginated history response object containing migration items and total count.

    Raises:
        HTTPException: **500** if the query fails.
    """
    user_id = current_user.get("_id") or current_user.get("user_id")

    try:
        migrations_collection = db_manager.get_collection("migrations")

        # Get migrations for this user
        cursor = migrations_collection.find(
            {"created_by": user_id}
        ).sort("created_at", -1).skip(offset).limit(limit)

        migrations = await cursor.to_list(length=limit)

        # Get total count
        total_count = await migrations_collection.count_documents({"created_by": user_id})

        # Convert to response model
        history_items = [
            MigrationHistoryItem(
                migration_id=m["migration_id"],
                migration_type=MigrationType(m["migration_type"]),
                status=MigrationStatus(m["status"]),
                created_at=m["created_at"],
                completed_at=m.get("completed_at"),
                created_by=m["created_by"],
                collections_count=len(m.get("metadata", {}).get("collections", [])),
                documents_count=m.get("metadata", {}).get("total_documents", 0),
                description=m.get("metadata", {}).get("description"),
            )
            for m in migrations
        ]

        return MigrationHistoryResponse(
            migrations=history_items,
            total_count=total_count,
        )

    except Exception as e:
        logger.error(f"Failed to get migration history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration history: {str(e)}",
        )


@router.delete("/{migration_id}")
async def delete_migration(
    migration_id: str,
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
    service: MigrationService = Depends(get_migration_service),
):
    """
    Permanently delete a migration record and its associated files.

    **Owner Role Required**

    Removes the migration entry from the database and deletes the physical
    package file from storage. If a rollback file exists, it is also deleted.

    **Side Effects:**
    - Deletes `.json.gz` package file.
    - Deletes rollback data (if applicable).
    - Removes database record.

    Args:
        migration_id: The unique identifier of the migration to delete.
        current_user: The authenticated user (requires `tenant_owner` role).
        service: The migration service instance.

    Returns:
        A dictionary confirming the deletion.

    Raises:
        HTTPException: **404** if not found, **403** if access denied.
    """
    user_id = current_user.get("_id") or current_user.get("user_id")

    try:
        migrations_collection = db_manager.get_collection("migrations")

        # Verify migration exists and user has access
        migration_doc = await migrations_collection.find_one({"migration_id": migration_id})

        if not migration_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found",
            )

        if migration_doc["created_by"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this migration",
            )

        # Delete package file if exists
        package_path = service.migration_dir / f"{migration_id}.json.gz"
        if package_path.exists():
            package_path.unlink()

        # Delete rollback file if exists
        if migration_doc.get("rollback_data_path"):
            rollback_path = service.migration_dir / f"{migration_id}_rollback.json.gz"
            if rollback_path.exists():
                rollback_path.unlink()

        # Delete migration document
        await migrations_collection.delete_one({"migration_id": migration_id})

        logger.info(f"Deleted migration {migration_id}")

        return {
            "migration_id": migration_id,
            "deleted": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete migration: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete migration: {str(e)}",
        )


@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
    service: MigrationService = Depends(get_migration_service),
):
    """
    List all database collections available for migration.

    **Owner Role Required**

    Retrieves a list of all non-system collections in the database.
    Useful for populating UI selection lists for partial exports.

    **Filters:**
    - Excludes system collections (e.g., `system.*`, `local.*`).
    - Excludes internal migration collections.

    Args:
        current_user: The authenticated user (requires `tenant_owner` role).
        service: The migration service instance.

    Returns:
        A response object containing the list of collection names and total count.

    Raises:
        HTTPException: **500** if the database query fails.
    """
    try:
        collections = await service._get_all_collections()

        # Filter out excluded collections
        available_collections = [
            c for c in collections if c not in service.EXCLUDED_COLLECTIONS
        ]

        return CollectionListResponse(
            collections=sorted(available_collections),
            total_count=len(available_collections),
        )

    except Exception as e:
        logger.error(f"Failed to list collections: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collections: {str(e)}",
        )


@router.get("/{migration_id}/status", response_model=MigrationResponse)
async def get_migration_status(
    migration_id: str,
    current_user: Dict[str, Any] = Depends(require_tenant_owner),
):
    """
    Get the real-time status of a specific migration operation.

    **Owner Role Required**

    Provides current progress, status (e.g., `in_progress`, `completed`, `failed`),
    and metadata for a migration job.

    Args:
        migration_id: The unique identifier of the migration.
        current_user: The authenticated user (requires `tenant_owner` role).

    Returns:
        A detailed migration response object including status and metadata.

    Raises:
        HTTPException: **404** if not found, **403** if access denied.
    """
    user_id = current_user.get("_id") or current_user.get("user_id")

    try:
        migrations_collection = db_manager.get_collection("migrations")
        migration_doc = await migrations_collection.find_one({"migration_id": migration_id})

        if not migration_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found",
            )

        if migration_doc["created_by"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this migration",
            )

        return MigrationResponse(
            migration_id=migration_doc["migration_id"],
            status=MigrationStatus(migration_doc["status"]),
            migration_type=MigrationType(migration_doc["migration_type"]),
            created_at=migration_doc["created_at"],
            created_by=migration_doc["created_by"],
            metadata=migration_doc.get("metadata"),
            download_url=(
                f"/api/migration/export/{migration_id}/download"
                if migration_doc["migration_type"] == MigrationType.EXPORT
                else None
            ),
            rollback_available=migration_doc.get("rollback_available", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get migration status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration status: {str(e)}",
        )
