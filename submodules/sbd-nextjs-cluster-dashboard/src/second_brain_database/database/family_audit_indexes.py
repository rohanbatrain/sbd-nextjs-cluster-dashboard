"""
# Family Audit Trail Indexes

This module defines and manages the **database indexes** required for the Family Audit Trail system.
It ensures optimal query performance for audit logs, compliance reporting, and security analysis
by maintaining a specific set of compound and unique indexes on the `family_audit_trails` collection.

## Index Strategy

The indexing strategy is designed to support three primary access patterns:

1.  **Timeline Queries**: Retrieving audit logs for a specific family sorted by time.
2.  **Member Attribution**: Finding all actions performed by a specific user.
3.  **Compliance & Integrity**: Enforcing uniqueness and supporting retention policies.

## Index Catalog

| Index Name | Fields | Type | Purpose |
|------------|--------|------|---------|
| `family_timestamp_idx` | `family_id` (1), `timestamp` (-1) | Compound | **Primary Access**: Most common query for showing family history. |
| `family_event_timestamp_idx` | `family_id` (1), `event_type` (1), `timestamp` (-1) | Compound | Filtering logs by event type (e.g., "SHOW_LOGIN_ATTEMPTS"). |
| `transaction_id_idx` | `transaction_details.transaction_id` (1) | Unique | **Integrity**: Prevents duplicate processing of the same transaction. |
| `member_timestamp_idx` | `member_id` (1), `timestamp` (-1) | Compound | **User History**: "What did this user do recently?" |
| `retention_idx` | `compliance_metadata.retention_until` (1) | Single | **TTL Support**: Efficiently finding expired logs for cleanup. |
| `integrity_hash_idx` | `integrity.hash` (1) | Single | **Security**: Verifying chain of custody and detecting tampering. |

## Management Operations

This module provides three core async functions for index lifecycle management:

- `create_family_audit_indexes()`: Idempotent creation of all missing indexes.
- `verify_family_audit_indexes()`: Checks existence and reports missing/misconfigured indexes.
- `drop_family_audit_indexes()`: Removes all indexes (useful for schema migrations or testing).

## Usage Example

```python
from second_brain_database.database.family_audit_indexes import (
    create_family_audit_indexes,
    verify_family_audit_indexes
)

# Startup: Ensure indexes exist
await create_family_audit_indexes()

# Health Check: Verify index state
status = await verify_family_audit_indexes()
if status["missing_indexes"]:
    logger.warning("Database indexes are out of sync!")
```

## Performance Considerations

- **Write Overhead**: Each new audit log requires updating 6+ indexes. This is acceptable for
  audit trails where read performance and integrity are prioritized over write latency.
- **Storage**: Indexes can consume significant disk space. The `retention_idx` supports
  efficient data lifecycle management to keep storage costs in check.

## Module Attributes

Attributes:
    FAMILY_AUDIT_INDEXES (List[Dict]): Configuration list defining all required indexes.
    logger (Logger): Specialized logger for index operations (`[FamilyAuditIndexes]`).
"""

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[FamilyAuditIndexes]")

FAMILY_AUDIT_INDEXES = [
    # Primary query indexes
    {
        "collection": "family_audit_trails",
        "index": [("family_id", 1), ("timestamp", -1)],
        "options": {"name": "family_timestamp_idx"},
    },
    {
        "collection": "family_audit_trails",
        "index": [("family_id", 1), ("event_type", 1), ("timestamp", -1)],
        "options": {"name": "family_event_timestamp_idx"},
    },
    {
        "collection": "family_audit_trails",
        "index": [("transaction_details.transaction_id", 1)],
        "options": {"name": "transaction_id_idx", "unique": True},
    },
    # Family member attribution indexes
    {
        "collection": "family_audit_trails",
        "index": [("family_member_attribution.member_id", 1), ("timestamp", -1)],
        "options": {"name": "member_timestamp_idx"},
    },
    {
        "collection": "family_audit_trails",
        "index": [("family_id", 1), ("family_member_attribution.member_id", 1)],
        "options": {"name": "family_member_idx"},
    },
    # Compliance and audit indexes
    {
        "collection": "family_audit_trails",
        "index": [("compliance_metadata.retention_until", 1)],
        "options": {"name": "retention_idx"},
    },
    {
        "collection": "family_audit_trails",
        "index": [("audit_id", 1)],
        "options": {"name": "audit_id_idx", "unique": True},
    },
    {"collection": "family_audit_trails", "index": [("integrity.hash", 1)], "options": {"name": "integrity_hash_idx"}},
    # Performance indexes for large datasets
    {
        "collection": "family_audit_trails",
        "index": [("family_id", 1), ("event_subtype", 1), ("timestamp", -1)],
        "options": {"name": "family_subtype_timestamp_idx"},
    },
    {"collection": "family_audit_trails", "index": [("timestamp", -1)], "options": {"name": "timestamp_desc_idx"}},
    # Update family collection indexes for audit summary
    {
        "collection": "families",
        "index": [("audit_summary.last_audit_at", -1)],
        "options": {"name": "family_last_audit_idx"},
    },
]


async def create_family_audit_indexes():
    """
    Create all required indexes for family audit trail collections.

    This function iterates through the `FAMILY_AUDIT_INDEXES` configuration list and
    ensures that each index exists on the specified collection. It is designed to be
    **idempotent** - calling it multiple times is safe and will not duplicate indexes.

    **Process:**
    1.  Iterates through the defined index specifications.
    2.  Retrieves the target collection using `db_manager`.
    3.  Calls `create_index` with the specified keys and options (e.g., unique constraints).
    4.  Logs the outcome (success or failure) for each index.

    **Error Handling:**
    - Individual index creation failures are logged as warnings but do **not** stop the
      process. This ensures that a single problematic index doesn't prevent others from
      being created.
    - Critical failures (e.g., database connectivity issues) will propagate as exceptions.

    Raises:
        `Exception`: If a critical error occurs that prevents the operation from starting
            or completing (e.g., database connection failure).

    Example:
        ```python
        # In application startup
        try:
            await create_family_audit_indexes()
            logger.info("Indexes initialized")
        except Exception as e:
            logger.critical("Failed to initialize indexes: %s", e)
        ```
    """
    try:
        logger.info("Creating family audit trail indexes...")

        created_count = 0
        for index_spec in FAMILY_AUDIT_INDEXES:
            collection_name = index_spec["collection"]
            index_keys = index_spec["index"]
            options = index_spec.get("options", {})

            try:
                collection = db_manager.get_collection(collection_name)
                await collection.create_index(index_keys, **options)
                created_count += 1
                logger.debug("Created index %s on collection %s", options.get("name", "unnamed"), collection_name)
            except Exception as e:
                # Index might already exist, log warning but continue
                logger.warning(
                    "Failed to create index %s on collection %s: %s", options.get("name", "unnamed"), collection_name, e
                )

        logger.info(
            "Family audit trail index creation completed: %d/%d indexes created",
            created_count,
            len(FAMILY_AUDIT_INDEXES),
        )

    except Exception as e:
        logger.error("Failed to create family audit trail indexes: %s", e, exc_info=True)
        raise


async def drop_family_audit_indexes():
    """
    Drop all family audit trail indexes.

    This function removes all indexes defined in `FAMILY_AUDIT_INDEXES` from the database.
    It is primarily intended for **maintenance**, **testing**, or **schema migrations**
    where a clean slate is required.

    **Warning:**
    This operation is **destructive**. Dropping indexes on a large production collection
    can have severe performance impacts:
    - Queries may revert to full collection scans.
    - Unique constraints will no longer be enforced.

    **Process:**
    1.  Iterates through the defined index specifications.
    2.  Identifies the index name from the options.
    3.  Calls `drop_index` on the target collection.
    4.  Logs the result.

    Raises:
        `Exception`: If a critical error occurs during the drop process.

    Example:
        ```python
        # In a test teardown or migration script
        await drop_family_audit_indexes()
        ```
    """
    try:
        logger.info("Dropping family audit trail indexes...")

        dropped_count = 0
        for index_spec in FAMILY_AUDIT_INDEXES:
            collection_name = index_spec["collection"]
            options = index_spec.get("options", {})
            index_name = options.get("name")

            if index_name:
                try:
                    collection = db_manager.get_collection(collection_name)
                    await collection.drop_index(index_name)
                    dropped_count += 1
                    logger.debug("Dropped index %s from collection %s", index_name, collection_name)
                except Exception as e:
                    logger.warning("Failed to drop index %s from collection %s: %s", index_name, collection_name, e)

        logger.info("Family audit trail index removal completed: %d indexes dropped", dropped_count)

    except Exception as e:
        logger.error("Failed to drop family audit trail indexes: %s", e, exc_info=True)
        raise


async def verify_family_audit_indexes() -> Dict[str, Any]:
    """
    Verify the existence and state of all required family audit trail indexes.

    This function performs a health check on the database schema by comparing the
    actual indexes present in the database against the expected configuration in
    `FAMILY_AUDIT_INDEXES`.

    **Verification Steps:**
    1.  For each required index, it lists the existing indexes on the collection.
    2.  Checks if an index with the expected name exists.
    3.  Compiles a report of verified vs. missing indexes.

    Returns:
        `Dict[str, Any]`: A detailed verification report containing:
            - `total_indexes` (`int`): Number of indexes defined in configuration.
            - `verified_indexes` (`int`): Number of indexes successfully found in DB.
            - `missing_indexes` (`List[Dict]`): Details of any missing indexes.
            - `collections_checked` (`List[str]`): List of collections scanned.
            - `error` (`str`, optional): Error message if the process failed.

    Example:
        ```python
        # Health check endpoint
        status = await verify_family_audit_indexes()
        if status["missing_indexes"]:
            for missing in status["missing_indexes"]:
                print(f"Missing index: {missing['index_name']}")
        ```
    """
    try:
        logger.info("Verifying family audit trail indexes...")

        verification_results = {
            "total_indexes": len(FAMILY_AUDIT_INDEXES),
            "verified_indexes": 0,
            "missing_indexes": [],
            "collections_checked": set(),
        }

        for index_spec in FAMILY_AUDIT_INDEXES:
            collection_name = index_spec["collection"]
            options = index_spec.get("options", {})
            index_name = options.get("name", "unnamed")

            verification_results["collections_checked"].add(collection_name)

            try:
                collection = db_manager.get_collection(collection_name)
                indexes = await collection.list_indexes().to_list(length=None)
                index_names = [idx.get("name") for idx in indexes]

                if index_name in index_names:
                    verification_results["verified_indexes"] += 1
                    logger.debug("Verified index %s on collection %s", index_name, collection_name)
                else:
                    verification_results["missing_indexes"].append(
                        {"collection": collection_name, "index_name": index_name, "index_spec": index_spec["index"]}
                    )
                    logger.warning("Missing index %s on collection %s", index_name, collection_name)

            except Exception as e:
                logger.warning("Failed to verify index %s on collection %s: %s", index_name, collection_name, e)
                verification_results["missing_indexes"].append(
                    {"collection": collection_name, "index_name": index_name, "error": str(e)}
                )

        verification_results["collections_checked"] = list(verification_results["collections_checked"])

        logger.info(
            "Family audit trail index verification completed: %d/%d indexes verified",
            verification_results["verified_indexes"],
            verification_results["total_indexes"],
        )

        return verification_results

    except Exception as e:
        logger.error("Failed to verify family audit trail indexes: %s", e, exc_info=True)
        return {
            "total_indexes": len(FAMILY_AUDIT_INDEXES),
            "verified_indexes": 0,
            "missing_indexes": [],
            "collections_checked": [],
            "error": str(e),
        }
