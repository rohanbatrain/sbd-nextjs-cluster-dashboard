"""
# Database Package

The `second_brain_database.database` package provides the **core persistence layer** for the application.
It is built on top of **Motor** (async MongoDB driver) and implements a robust, production-grade
architecture featuring connection pooling, automatic multi-tenancy, and health monitoring.

## Package Architecture

### Core Components

- **`manager`**: The `DatabaseManager` singleton that handles connection lifecycle and pool management.
- **`tenant_collection`**: The `TenantAwareCollection` wrapper for strict data isolation.
- **`family_audit_indexes`**: Specialized indexing strategies for family audit trails.
- **`ipam_indexes`**: Complex hierarchical indexing for IP Address Management.

### Design Patterns

**Singleton Pattern:**
The `db_manager` instance is created as a **module-level singleton**, ensuring a single
connection pool is shared across the entire application. This is critical for performance
and connection limit management.

**Lazy Initialization:**
The `DatabaseManager` is instantiated immediately, but the actual MongoDB connection is
established **lazily** during application startup via `db_manager.connect()`.

## Usage Patterns

### Basic Usage (Application Startup)

```python
from second_brain_database.database import db_manager

# In FastAPI lifespan startup
await db_manager.connect()

# Get a collection
users = db_manager.get_collection("users")
user = await users.find_one({"username": "alice"})

# In FastAPI lifespan shutdown
await db_manager.disconnect()
```

### Multi-Tenant Usage

```python
from second_brain_database.database import db_manager

# All queries automatically scoped to tenant
users = db_manager.get_tenant_collection("users", tenant_id="tenant_123") 
user = await users.find_one({"username": "alice"})
# Actual query: {"username": "alice", "tenant_id": "tenant_123"}
```

## Connection Lifecycle

1.  **Instantiation** (module load): `db_manager` created, no I/O.
2.  **Connection** (startup): `connect()` establishes pool (min: 10, max: 100).
3.  **Operations** (runtime): Requests borrow connections from the pool.
4.  **Disconnection** (shutdown): `disconnect()` closes all sockets.

## Module Attributes

Attributes:
    db_manager (DatabaseManager): The global singleton instance for database access.
    DatabaseManager (class): The main manager class (exported for type hinting).
"""

from second_brain_database.database.manager import DatabaseManager, db_manager

__all__ = ["DatabaseManager", "db_manager"]
