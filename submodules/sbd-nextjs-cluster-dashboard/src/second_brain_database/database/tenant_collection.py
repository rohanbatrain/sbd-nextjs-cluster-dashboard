"""
# Multi-Tenant Collection Wrapper

This module provides the **core mechanism for multi-tenancy** in the Second Brain Database.
It implements the `TenantAwareCollection` wrapper, which acts as a secure proxy around standard
MongoDB collections, enforcing strict data isolation by automatically injecting tenant context
into every database operation.

## Architecture Overview

The wrapper intercepts all calls to the underlying Motor collection, modifying queries and documents
in-flight to ensure they are scoped to the correct tenant:

```
┌─────────────────────────────────────────────────────────────┐
│                 Multi-Tenant Data Isolation                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────┐      ┌───────────────────────────────┐    │
│   │  Service     │─────▶│     TenantAwareCollection     │    │
│   │  Layer       │      │     (tenant_id="t_123")       │    │
│   └──────────────┘      └──────────────┬────────────────┘    │
│                                        │                     │
│                         ┌──────────────▼──────────────┐      │
│                         │    Query/Doc Modification   │      │
│                         │  + {"tenant_id": "t_123"}   │      │
│                         └──────────────┬──────────────┘      │
│                                        │                     │
│                         ┌──────────────▼──────────────┐      │
│                         │    AsyncIOMotorCollection   │      │
│                         │    (Underlying Driver)      │      │
│                         └──────────────┬──────────────┘      │
│                                        │                     │
│          ┌─────────────────────────────▼─────────────────────┐
│          │                 MongoDB Database                  │
│          │  { "_id": 1, "user": "alice", "tenant_id": "A" }  │
│          │  { "_id": 2, "user": "bob",   "tenant_id": "B" }  │
│          └───────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Automatic Read Filtering
- **Find Operations**: Automatically appends `{"tenant_id": "..."}` to all query filters
- **Aggregations**: Prepends a `$match` stage with the tenant ID to the pipeline
- **Counting**: Scopes document counts to the specific tenant

### 2. Automatic Write Scoping
- **Insertions**: Automatically injects `"tenant_id": "..."` field into new documents
- **Bulk Writes**: Processes lists of documents to ensure all have the correct tenant ID
- **Updates**: Ensures update filters are scoped, preventing cross-tenant modifications

### 3. Transparent Interface
- **Drop-in Replacement**: Mimics the `AsyncIOMotorCollection` API (find, insert_one, etc.)
- **Type Compatibility**: designed to work seamlessly with existing service logic
- **Logging**: Provides debug logging for all intercepted operations with tenant context

### 4. Security & Isolation
- **Defense in Depth**: Prevents accidental data leaks even if service layer forgets filtering
- **Hard Isolation**: Makes it impossible to query another tenant's data via this wrapper
- **Auditability**: All operations are logged with the specific tenant ID they were executed for

## Usage Examples

### Basic Usage

```python
from second_brain_database.database import db_manager

# Get a tenant-scoped collection
users = db_manager.get_tenant_collection("users", tenant_id="tenant_123")

# READ: Automatically filters by tenant_id="tenant_123"
user = await users.find_one({"username": "alice"})
# Actual query: {"username": "alice", "tenant_id": "tenant_123"}

# WRITE: Automatically adds tenant_id="tenant_123"
await users.insert_one({"username": "bob", "role": "admin"})
# Actual doc: {"username": "bob", "role": "admin", "tenant_id": "tenant_123"}
```

### Aggregation Pipelines

```python
pipeline = [
    {"$group": {"_id": "$role", "count": {"$sum": 1}}}
]

# The wrapper automatically prepends a $match stage
results = await users.aggregate(pipeline).to_list(None)

# Actual pipeline executed:
# [
#   {"$match": {"tenant_id": "tenant_123"}},
#   {"$group": {"_id": "$role", "count": {"$sum": 1}}}
# ]
```

### Bulk Operations

```python
docs = [
    {"name": "Doc A"},
    {"name": "Doc B"}
]

# Both documents get tenant_id injected
await users.insert_many(docs)
```

## Security Considerations

- **Tenant ID Validation**: The wrapper assumes the `tenant_id` passed to it is valid.
  Validation should happen at the API/Middleware layer (e.g., `middleware/tenant.py`).
- **Index Requirements**: For performance, all collections should have compound indexes
  that include `tenant_id` (e.g., `("tenant_id", 1), ("username", 1)`).
- **Root Access**: System-level services (like migrations) should use the raw `db_manager.get_collection()`
  to access data across all tenants, bypassing this wrapper.

## Module Attributes

Attributes:
    logger (Logger): Specialized logger for tenant collection operations (`[Tenant Collection]`).

## Todo

Todo:
    * Add support for `bulk_write` operations with automatic scoping
    * Implement `watch` (Change Streams) with tenant filtering
    * Add strict validation to prevent `tenant_id` overwrites in updates
    * Implement read-only mode for specific tenants
"""

from typing import Any, Dict, List, Optional, Union

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorCursor
from pymongo import ReturnDocument

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Tenant Collection]")


class TenantAwareCollection:
    """
    A wrapper around `AsyncIOMotorCollection` that enforces tenant isolation.

    This class intercepts all standard MongoDB operations (`find`, `insert`, `update`, `delete`, etc.)
    and modifies them to ensure they are scoped to a specific `tenant_id`. This provides a
    robust layer of security for multi-tenant applications, preventing accidental data leakage.

    **Mechanism:**
    - **Reads**: Appends `{"tenant_id": self.tenant_id}` to the query filter.
    - **Writes**: Adds `"tenant_id": self.tenant_id` to the document(s) being inserted.
    - **Updates**: Ensures the update filter includes the tenant ID.
    - **Deletes**: Restricts deletion to documents matching the tenant ID.

    Attributes:
        _collection (`AsyncIOMotorCollection`): The underlying Motor collection instance.
        _tenant_id (`str`): The unique identifier of the tenant this wrapper is scoped to.

    Example:
        ```python
        # Create wrapper (usually done by DatabaseManager)
        tenant_users = TenantAwareCollection(db.users, "tenant_abc")

        # Safe operation
        await tenant_users.delete_many({})
        # Only deletes users where tenant_id == "tenant_abc"
        ```
    """

    def __init__(self, collection: AsyncIOMotorCollection, tenant_id: str):
        """
        Initialize the tenant-aware collection wrapper.

        Args:
            collection (`AsyncIOMotorCollection`): The underlying MongoDB collection to wrap.
            tenant_id (`str`): The tenant ID to enforce for all operations. Must be a non-empty string.
        """
        self._collection = collection
        self._tenant_id = tenant_id
        logger.debug("Created tenant-aware collection for tenant: %s", tenant_id)

    def _add_tenant_filter(self, filter_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Inject the tenant ID into a query filter dictionary.

        This helper method ensures that the `tenant_id` field is present in the filter.
        If the filter is `None`, a new dictionary `{"tenant_id": ...}` is created.
        If the filter exists, `tenant_id` is added to it (overwriting if present, though
        callers should not be manually setting it).

        Args:
            filter_dict (`Optional[Dict[str, Any]]`): The original query filter. Defaults to `None`.

        Returns:
            `Dict[str, Any]`: The modified filter dictionary containing the `tenant_id` constraint.
        """
        filter_dict = filter_dict or {}
        filter_dict["tenant_id"] = self._tenant_id
        return filter_dict

    def _add_tenant_to_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject the tenant ID into a document before insertion.

        This helper method modifies the document in-place (and returns it) to include
        the `tenant_id` field. This is critical for ensuring that all new data is
        correctly attributed to the current tenant.

        Args:
            document (`Dict[str, Any]`): The document to be inserted.

        Returns:
            `Dict[str, Any]`: The modified document with `tenant_id` set.
        """
        document["tenant_id"] = self._tenant_id
        return document

    async def find_one(
        self, filter: Optional[Dict[str, Any]] = None, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Finds a single document, automatically applying the tenant_id filter.

        Behaves like AsyncIOMotorCollection.find_one, but ensures tenant isolation.

        Args:
            filter: The query filter to apply, in addition to the tenant_id.
            *args: Positional arguments passed directly to the underlying find_one.
            **kwargs: Keyword arguments passed directly to the underlying find_one.

        Returns:
            The found document as a dictionary, or None if no document matches.
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.find_one(filter, *args, **kwargs)
        logger.debug("find_one for tenant %s: %s", self._tenant_id, "found" if result else "not found")
        return result

    def find(self, filter: Optional[Dict[str, Any]] = None, *args, **kwargs) -> AsyncIOMotorCursor:
        """
        Finds multiple documents, automatically applying the tenant_id filter.

        Behaves like AsyncIOMotorCollection.find, but ensures tenant isolation.

        Args:
            filter: The query filter to apply, in addition to the tenant_id.
            *args: Positional arguments passed directly to the underlying find.
            **kwargs: Keyword arguments passed directly to the underlying find.

        Returns:
            An AsyncIOMotorCursor for iterating over the matching documents.
        """
        filter = self._add_tenant_filter(filter)
        cursor = self._collection.find(filter, *args, **kwargs)
        logger.debug("find for tenant %s with filter: %s", self._tenant_id, filter)
        return cursor

    async def insert_one(self, document: Dict[str, Any], *args, **kwargs):
        """
        Inserts a single document, automatically adding the tenant_id.

        Behaves like AsyncIOMotorCollection.insert_one, but ensures tenant isolation.

        Args:
            document: The document to insert. The tenant_id will be added to it.
            *args: Positional arguments passed directly to the underlying insert_one.
            **kwargs: Keyword arguments passed directly to the underlying insert_one.

        Returns:
            An InsertOneResult object.
        """
        document = self._add_tenant_to_document(document)
        result = await self._collection.insert_one(document, *args, **kwargs)
        logger.debug("insert_one for tenant %s: inserted_id=%s", self._tenant_id, result.inserted_id)
        return result

    async def insert_many(self, documents: List[Dict[str, Any]], *args, **kwargs):
        """
        Inserts multiple documents, automatically adding the tenant_id to each.

        Behaves like AsyncIOMotorCollection.insert_many, but ensures tenant isolation.

        Args:
            documents: A list of documents to insert. The tenant_id will be added to each.
            *args: Positional arguments passed directly to the underlying insert_many.
            **kwargs: Keyword arguments passed directly to the underlying insert_many.

        Returns:
            An InsertManyResult object.
        """
        documents = [self._add_tenant_to_document(doc) for doc in documents]
        result = await self._collection.insert_many(documents, *args, **kwargs)
        logger.debug("insert_many for tenant %s: inserted %d documents", self._tenant_id, len(result.inserted_ids))
        return result

    async def update_one(
        self, filter: Dict[str, Any], update: Dict[str, Any], *args, **kwargs
    ):
        """
        Update a single document restricted to the current tenant.

        This method wraps `AsyncIOMotorCollection.update_one`. It injects the `tenant_id`
        into the query filter to ensure only documents belonging to the tenant are modified.

        Args:
            filter (`Dict[str, Any]`): The query filter to select the document to update.
            update (`Dict[str, Any]`): The update operations (e.g., `{"$set": ...}`).
            *args: Additional positional arguments passed to Motor.
            **kwargs: Additional keyword arguments passed to Motor (e.g., `upsert`).

        Returns:
            `UpdateResult`: The result of the update operation.

        Example:
            ```python
            # Update user profile
            await tenant_users.update_one(
                {"username": "alice"},
                {"$set": {"last_login": datetime.now()}}
            )
            # Only updates if "username": "alice" AND "tenant_id": "..."
            ```
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.update_one(filter, update, *args, **kwargs)
        logger.debug(
            "update_one for tenant %s: matched=%d, modified=%d",
            self._tenant_id,
            result.matched_count,
            result.modified_count,
        )
        return result

    async def update_many(
        self, filter: Dict[str, Any], update: Dict[str, Any], *args, **kwargs
    ):
        """
        Update multiple documents restricted to the current tenant.

        This method wraps `AsyncIOMotorCollection.update_many`. It injects the `tenant_id`
        into the query filter to ensure only documents belonging to the tenant are modified.

        Args:
            filter (`Dict[str, Any]`): The query filter to select documents to update.
            update (`Dict[str, Any]`): The update operations to apply.
            *args: Additional positional arguments passed to Motor.
            **kwargs: Additional keyword arguments passed to Motor.

        Returns:
            `UpdateResult`: The result of the bulk update operation.

        Example:
            ```python
            # Deactivate all users who haven't logged in for a year
            await tenant_users.update_many(
                {"last_login": {"$lt": one_year_ago}},
                {"$set": {"is_active": False}}
            )
            ```
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.update_many(filter, update, *args, **kwargs)
        logger.debug(
            "update_many for tenant %s: matched=%d, modified=%d",
            self._tenant_id,
            result.matched_count,
            result.modified_count,
        )
        return result

    async def delete_one(self, filter: Dict[str, Any], *args, **kwargs):
        """
        Delete a single document restricted to the current tenant.

        This method wraps `AsyncIOMotorCollection.delete_one`. It injects the `tenant_id`
        into the query filter to ensure only documents belonging to the tenant are deleted.

        Args:
            filter (`Dict[str, Any]`): The query filter to select the document to delete.
            *args: Additional positional arguments passed to Motor.
            **kwargs: Additional keyword arguments passed to Motor.

        Returns:
            `DeleteResult`: The result of the delete operation.

        Example:
            ```python
            # Delete a specific user
            await tenant_users.delete_one({"username": "malicious_user"})
            ```
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.delete_one(filter, *args, **kwargs)
        logger.debug("delete_one for tenant %s: deleted=%d", self._tenant_id, result.deleted_count)
        return result

    async def delete_many(self, filter: Dict[str, Any], *args, **kwargs):
        """
        Delete multiple documents restricted to the current tenant.

        This method wraps `AsyncIOMotorCollection.delete_many`. It injects the `tenant_id`
        into the query filter to ensure only documents belonging to the tenant are deleted.

        Args:
            filter (`Dict[str, Any]`): The query filter to select documents to delete.
            *args: Additional positional arguments passed to Motor.
            **kwargs: Additional keyword arguments passed to Motor.

        Returns:
            `DeleteResult`: The result of the bulk delete operation.

        Example:
            ```python
            # Delete all archived items
            await tenant_items.delete_many({"status": "archived"})
            ```
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.delete_many(filter, *args, **kwargs)
        logger.debug("delete_many for tenant %s: deleted=%d", self._tenant_id, result.deleted_count)
        return result

    async def find_one_and_update(
        self,
        filter: Dict[str, Any],
        update: Dict[str, Any],
        *args,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Find a single document and update it, restricted to the current tenant.

        This method wraps `AsyncIOMotorCollection.find_one_and_update`. It injects the
        `tenant_id` into the query filter.

        Args:
            filter (`Dict[str, Any]`): The query filter to select the document.
            update (`Dict[str, Any]`): The update operations to apply.
            *args: Additional positional arguments passed to Motor.
            **kwargs: Additional keyword arguments passed to Motor (e.g., `return_document`, `projection`).

        Returns:
            `Optional[Dict[str, Any]]`: The document (before or after update, depending on `return_document`).
            Returns `None` if no matching document is found.

        Example:
            ```python
            # Atomically increment login count and return new value
            user = await tenant_users.find_one_and_update(
                {"username": "alice"},
                {"$inc": {"login_count": 1}},
                return_document=ReturnDocument.AFTER
            )
            ```
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.find_one_and_update(filter, update, *args, **kwargs)
        logger.debug("find_one_and_update for tenant %s: %s", self._tenant_id, "found" if result else "not found")
        return result

    async def find_one_and_delete(
        self, filter: Dict[str, Any], *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Find a single document and delete it, restricted to the current tenant.

        This method wraps `AsyncIOMotorCollection.find_one_and_delete`. It injects the
        `tenant_id` into the query filter.

        Args:
            filter (`Dict[str, Any]`): The query filter to select the document.
            *args: Additional positional arguments passed to Motor.
            **kwargs: Additional keyword arguments passed to Motor (e.g., `projection`).

        Returns:
            `Optional[Dict[str, Any]]`: The deleted document, or `None` if not found.

        Example:
            ```python
            # Pop the oldest task from the queue
            task = await tenant_tasks.find_one_and_delete(
                {"status": "pending"},
                sort=[("created_at", 1)]
            )
            ```
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.find_one_and_delete(filter, *args, **kwargs)
        logger.debug("find_one_and_delete for tenant %s: %s", self._tenant_id, "found" if result else "not found")
        return result

    async def count_documents(self, filter: Optional[Dict[str, Any]] = None, *args, **kwargs) -> int:
        """
        Count the number of documents matching the filter for the current tenant.

        This method wraps `AsyncIOMotorCollection.count_documents`. It injects the
        `tenant_id` into the query filter.

        Args:
            filter (`Optional[Dict[str, Any]]`): The query filter. If `None`, counts all
                documents belonging to the tenant.
            *args: Additional positional arguments passed to Motor.
            **kwargs: Additional keyword arguments passed to Motor.

        Returns:
            `int`: The count of matching documents.

        Example:
            ```python
            # Count active users
            count = await tenant_users.count_documents({"is_active": True})
            ```
        """
        filter = self._add_tenant_filter(filter)
        count = await self._collection.count_documents(filter, *args, **kwargs)
        logger.debug("count_documents for tenant %s: %d", self._tenant_id, count)
        return count

    async def aggregate(self, pipeline: List[Dict[str, Any]], *args, **kwargs):
        """
        Run an aggregation pipeline restricted to the current tenant.

        This method wraps `AsyncIOMotorCollection.aggregate`. It automatically prepends
        a `$match` stage to the pipeline that filters by `tenant_id`. This ensures that
        the aggregation only processes documents belonging to the scoped tenant.

        Args:
            pipeline (`List[Dict[str, Any]]`): The aggregation pipeline stages.
            *args: Additional positional arguments passed to Motor.
            **kwargs: Additional keyword arguments passed to Motor.

        Returns:
            `AsyncIOMotorCommandCursor`: A cursor for iterating over the aggregation results.

        Example:
            ```python
            # Calculate average login count per role
            pipeline = [
                {"$group": {"_id": "$role", "avg_logins": {"$avg": "$login_count"}}}
            ]
            cursor = tenant_users.aggregate(pipeline)
            # Actual pipeline: [{"$match": {"tenant_id": "..."}}, {"$group": ...}]
            ```
        """
        # Add tenant filter as first stage in pipeline
        tenant_match = {"$match": {"tenant_id": self._tenant_id}}
        pipeline = [tenant_match] + pipeline
        cursor = self._collection.aggregate(pipeline, *args, **kwargs)
        logger.debug("aggregate for tenant %s with %d stages", self._tenant_id, len(pipeline))
        return cursor

    @property
    def name(self) -> str:
        """
        Get the name of the underlying collection.

        Returns:
            `str`: The collection name (e.g., "users").
        """
        return self._collection.name

    @property
    def tenant_id(self) -> str:
        """
        Get the tenant ID this collection is scoped to.

        Returns:
            `str`: The tenant ID string.
        """
        return self._tenant_id
