"""
# IPAM Database Indexes

This module defines and manages the **comprehensive indexing strategy** for the IP Address Management (IPAM) system.
It ensures high-performance lookups, strict uniqueness constraints, and efficient audit trails across
multiple collections including regions, hosts, quotas, and audit logs.

## Index Strategy

The IPAM system relies on a complex set of indexes to support:
1.  **Hierarchical Lookups**: Efficiently finding hosts within regions, countries, and continents.
2.  **Uniqueness Constraints**: Enforcing strict rules (e.g., no duplicate IPs per user, no overlapping CIDRs).
3.  **Audit Performance**: Rapid retrieval of history for specific resources or IP addresses.
4.  **Quota Management**: Fast validation of user resource limits.

## Index Catalog

### 1. Reference Data (`continent_country_mapping`)
| Index | Type | Purpose |
|-------|------|---------|
| `continent_idx` | Single | Filtering countries by continent. |
| `country_idx` | Unique | Ensuring country codes are unique. |
| `x_start_idx` | Single | Range queries for IP allocation logic. |

### 2. Regions (`ipam_regions`)
| Index | Type | Purpose |
|-------|------|---------|
| `user_country_region_unique_idx` | Unique | Prevents duplicate region names per country for a user. |
| `user_xy_unique_idx` | Unique | Ensures no two regions share the same X.Y coordinates. |
| `user_tags_idx` | Compound | Fast filtering of regions by user tags. |

### 3. Hosts (`ipam_hosts`)
| Index | Type | Purpose |
|-------|------|---------|
| `user_ip_unique_idx` | Unique | **Critical**: Prevents duplicate IP addresses for a user. |
| `user_region_hostname_unique_idx` | Unique | Ensures unique hostnames within a region. |
| `user_host_tags_idx` | Compound | Searching hosts by tags. |

### 4. Audit History (`ipam_audit_history`)
| Index | Type | Purpose |
|-------|------|---------|
| `user_ip_audit_idx` | Compound | "Who changed this IP address?" |
| `user_resource_timestamp_idx` | Compound | Timeline of changes for a specific resource. |

## Management Operations

- `create_ipam_indexes()`: Idempotent creation of all 30+ required indexes.
- `verify_ipam_indexes()`: detailed verification report of index health.
- `drop_ipam_indexes()`: Safe removal of indexes (for schema updates).

## Usage Example

```python
from second_brain_database.database.ipam_indexes import (
    create_ipam_indexes,
    verify_ipam_indexes
)

# Initialize indexes on startup
await create_ipam_indexes()

# Check for missing indexes
report = await verify_ipam_indexes()
print(f"Verified: {report['verified_indexes']}/{report['total_indexes']}")
```

## Module Attributes

Attributes:
    IPAM_INDEXES (List[Dict]): Configuration list defining 30+ indexes across 5 collections.
    logger (Logger): Specialized logger for IPAM index operations (`[IPAMIndexes]`).
"""

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAMIndexes]")

# IPAM index specifications following the family_audit_indexes pattern
IPAM_INDEXES = [
    # Continent-country mapping indexes (read-only reference data)
    {
        "collection": "continent_country_mapping",
        "index": [("continent", 1)],
        "options": {"name": "continent_idx"},
    },
    {
        "collection": "continent_country_mapping",
        "index": [("country", 1)],
        "options": {"name": "country_idx", "unique": True},
    },
    {
        "collection": "continent_country_mapping",
        "index": [("x_start", 1)],
        "options": {"name": "x_start_idx"},
    },
    {
        "collection": "continent_country_mapping",
        "index": [("is_reserved", 1)],
        "options": {"name": "is_reserved_idx"},
    },
    # IPAM regions collection indexes
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("country", 1), ("region_name", 1)],
        "options": {"name": "user_country_region_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("x_octet", 1), ("y_octet", 1)],
        "options": {"name": "user_xy_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("country", 1), ("status", 1)],
        "options": {"name": "user_country_status_idx"},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("tags", 1)],
        "options": {"name": "user_tags_idx"},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("created_at", -1)],
        "options": {"name": "user_created_idx"},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("continent", 1)],
        "options": {"name": "user_continent_idx"},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("x_octet", 1)],
        "options": {"name": "user_x_octet_idx"},
    },
    {
        "collection": "ipam_regions",
        "index": [("cidr", 1)],
        "options": {"name": "cidr_idx"},
    },
    # IPAM hosts collection indexes
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("region_id", 1), ("hostname", 1)],
        "options": {"name": "user_region_hostname_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("x_octet", 1), ("y_octet", 1), ("z_octet", 1)],
        "options": {"name": "user_xyz_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("ip_address", 1)],
        "options": {"name": "user_ip_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("status", 1)],
        "options": {"name": "user_status_idx"},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("region_id", 1)],
        "options": {"name": "user_region_idx"},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("tags", 1)],
        "options": {"name": "user_host_tags_idx"},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("created_at", -1)],
        "options": {"name": "user_host_created_idx"},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("device_type", 1)],
        "options": {"name": "user_device_type_idx"},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("hostname", 1)],
        "options": {"name": "user_hostname_idx"},
    },
    # IPAM audit history collection indexes
    {
        "collection": "ipam_audit_history",
        "index": [("user_id", 1), ("timestamp", -1)],
        "options": {"name": "user_timestamp_idx"},
    },
    {
        "collection": "ipam_audit_history",
        "index": [("user_id", 1), ("resource_type", 1), ("action_type", 1)],
        "options": {"name": "user_resource_action_idx"},
    },
    {
        "collection": "ipam_audit_history",
        "index": [("user_id", 1), ("ip_address", 1)],
        "options": {"name": "user_ip_audit_idx"},
    },
    {
        "collection": "ipam_audit_history",
        "index": [("user_id", 1), ("cidr", 1)],
        "options": {"name": "user_cidr_audit_idx"},
    },
    {
        "collection": "ipam_audit_history",
        "index": [("user_id", 1), ("resource_id", 1), ("timestamp", -1)],
        "options": {"name": "user_resource_timestamp_idx"},
    },
    {
        "collection": "ipam_audit_history",
        "index": [("timestamp", -1)],
        "options": {"name": "timestamp_desc_audit_idx"},
    },
    # IPAM user quotas collection indexes
    {
        "collection": "ipam_user_quotas",
        "index": [("user_id", 1)],
        "options": {"name": "user_quota_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_user_quotas",
        "index": [("last_updated", -1)],
        "options": {"name": "quota_last_updated_idx"},
    },
    # IPAM export jobs collection indexes
    {
        "collection": "ipam_export_jobs",
        "index": [("user_id", 1), ("created_at", -1)],
        "options": {"name": "user_export_created_idx"},
    },
    {
        "collection": "ipam_export_jobs",
        "index": [("user_id", 1), ("status", 1)],
        "options": {"name": "user_export_status_idx"},
    },
    {
        "collection": "ipam_export_jobs",
        "index": [("expires_at", 1)],
        "options": {"name": "export_expires_idx"},
    },
]


async def create_ipam_indexes() -> bool:
    """
    Create all required indexes for IPAM collections.

    This function iterates through the `IPAM_INDEXES` configuration list (containing over 30 indexes)
    and ensures that each index exists on the specified collection. It is designed to be
    **idempotent** - calling it multiple times is safe and will not duplicate indexes.

    **Scope:**
    - `continent_country_mapping`: Reference data indexes
    - `ipam_regions`: Region management indexes
    - `ipam_hosts`: Host allocation indexes
    - `ipam_audit_history`: Audit trail indexes
    - `ipam_user_quotas`: Quota enforcement indexes
    - `ipam_export_jobs`: Job management indexes

    **Process:**
    1.  Iterates through the defined index specifications.
    2.  Retrieves the target collection using `db_manager`.
    3.  Calls `create_index` with the specified keys and options.
    4.  Tracks success/failure counts.

    **Error Handling:**
    - Individual index creation failures are logged as warnings but do **not** stop the
      process. This ensures maximum possible coverage even if one index fails.
    - Critical failures (e.g., database connectivity issues) are caught, logged, and
      returned as `False`.

    Returns:
        `bool`: `True` if the process completed (even with individual index failures),
        `False` if a critical error occurred preventing execution.

    Example:
        ```python
        # In application startup
        if await create_ipam_indexes():
            logger.info("IPAM indexes initialized successfully")
        else:
            logger.critical("Failed to initialize IPAM indexes")
        ```
    """
    try:
        logger.info("Creating IPAM indexes...")

        created_count = 0
        failed_count = 0

        for index_spec in IPAM_INDEXES:
            collection_name = index_spec["collection"]
            index_keys = index_spec["index"]
            options = index_spec.get("options", {})
            index_name = options.get("name", "unnamed")

            try:
                collection = db_manager.get_collection(collection_name)
                await collection.create_index(index_keys, **options)
                created_count += 1
                logger.debug("Created index %s on collection %s", index_name, collection_name)
            except Exception as e:
                # Index might already exist, log warning but continue
                failed_count += 1
                logger.warning(
                    "Failed to create index %s on collection %s: %s",
                    index_name,
                    collection_name,
                    e,
                )

        logger.info(
            "IPAM index creation completed: %d/%d indexes created, %d failed/already exist",
            created_count,
            len(IPAM_INDEXES),
            failed_count,
        )

        return True

    except Exception as e:
        logger.error("Failed to create IPAM indexes: %s", e, exc_info=True)
        return False


async def drop_ipam_indexes() -> bool:
    """
    Drop all IPAM indexes.

    This function removes all indexes defined in `IPAM_INDEXES` from the database.
    It is primarily intended for **maintenance**, **testing**, or **schema migrations**
    where a clean slate is required.

    **Warning:**
    This operation is **destructive**. Dropping indexes on large IPAM collections
    can have severe performance impacts and may temporarily violate uniqueness constraints
    until indexes are recreated.

    **Process:**
    1.  Iterates through the defined index specifications.
    2.  Identifies the index name from the options.
    3.  Calls `drop_index` on the target collection.
    4.  Logs the result.

    Returns:
        `bool`: `True` if the process completed, `False` if a critical error occurred.

    Example:
        ```python
        # In a test teardown or migration script
        await drop_ipam_indexes()
        ```
    """
    try:
        logger.info("Dropping IPAM indexes...")

        dropped_count = 0
        failed_count = 0

        for index_spec in IPAM_INDEXES:
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
                    failed_count += 1
                    logger.warning(
                        "Failed to drop index %s from collection %s: %s",
                        index_name,
                        collection_name,
                        e,
                    )

        logger.info(
            "IPAM index removal completed: %d indexes dropped, %d failed",
            dropped_count,
            failed_count,
        )

        return True

    except Exception as e:
        logger.error("Failed to drop IPAM indexes: %s", e, exc_info=True)
        return False


async def verify_ipam_indexes() -> Dict[str, Any]:
    """
    Verify the existence and state of all required IPAM indexes.

    This function performs a comprehensive health check on the IPAM database schema
    by comparing the actual indexes present in the database against the expected
    configuration in `IPAM_INDEXES`.

    **Verification Steps:**
    1.  For each required index, it lists the existing indexes on the collection.
    2.  Checks if an index with the expected name exists.
    3.  Compiles a detailed report of verified vs. missing indexes.

    Returns:
        `Dict[str, Any]`: A detailed verification report containing:
            - `total_indexes` (`int`): Total number of indexes defined (30+).
            - `verified_indexes` (`int`): Number of indexes successfully found.
            - `missing_indexes` (`List[Dict]`): Details of any missing indexes.
            - `collections_checked` (`List[str]`): List of collections scanned.
            - `error` (`str`, optional): Error message if the process failed.

    Example:
        ```python
        # Health check endpoint
        report = await verify_ipam_indexes()
        if report["missing_indexes"]:
            logger.warning("IPAM index mismatch: %s", report["missing_indexes"])
        ```
    """
    try:
        logger.info("Verifying IPAM indexes...")

        verification_results = {
            "total_indexes": len(IPAM_INDEXES),
            "verified_indexes": 0,
            "missing_indexes": [],
            "collections_checked": set(),
        }

        for index_spec in IPAM_INDEXES:
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
                        {
                            "collection": collection_name,
                            "index_name": index_name,
                            "index_spec": index_spec["index"],
                        }
                    )
                    logger.warning("Missing index %s on collection %s", index_name, collection_name)

            except Exception as e:
                logger.warning(
                    "Failed to verify index %s on collection %s: %s",
                    index_name,
                    collection_name,
                    e,
                )
                verification_results["missing_indexes"].append(
                    {
                        "collection": collection_name,
                        "index_name": index_name,
                        "error": str(e),
                    }
                )

        verification_results["collections_checked"] = list(verification_results["collections_checked"])

        logger.info(
            "IPAM index verification completed: %d/%d indexes verified",
            verification_results["verified_indexes"],
            verification_results["total_indexes"],
        )

        return verification_results

    except Exception as e:
        logger.error("Failed to verify IPAM indexes: %s", e, exc_info=True)
        return {
            "total_indexes": len(IPAM_INDEXES),
            "verified_indexes": 0,
            "missing_indexes": [],
            "collections_checked": [],
            "error": str(e),
        }
