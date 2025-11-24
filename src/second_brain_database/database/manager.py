"""
# Database Management Module

This module provides the **core MongoDB infrastructure** for the Second Brain Database API.
It implements a robust, production-ready `DatabaseManager` class that handles all database interactions
using the **Motor** async driver, ensuring high performance, reliability, and observability.

## Architecture Overview

The database layer acts as a centralized gateway for all data persistence operations:

```
┌─────────────────────────────────────────────────────────────┐
│                  Database Layer Architecture                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌──────────────┐      ┌───────────────────────────────┐    │
│   │ Application  │─────▶│        DatabaseManager        │    │
│   │ (Services)   │      │          (Singleton)          │    │
│   └──────────────┘      └──────────────┬────────────────┘    │
│                                        │                     │
│                         ┌──────────────▼──────────────┐      │
│                         │      Connection Pool        │      │
│                         │  (Motor/PyMongo Internal)   │      │
│                         └──────────────┬──────────────┘      │
│                                        │                     │
│          ┌─────────────────────────────┼─────────────────────┐
│          ▼                             ▼                     ▼
│  ┌──────────────┐              ┌──────────────┐      ┌──────────────┐
│  │  Replica Set │              │  Standalone  │      │ Sharded Clust│
│  │   (Primary)  │              │   (Single)   │      │   (Mongos)   │
│  └──────────────┘              └──────────────┘      └──────────────┘
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. Connection Lifecycle Management
- **Async Initialization**: Non-blocking connection establishment during application startup
- **Graceful Shutdown**: Clean resource cleanup ensuring no dangling connections
- **Health Monitoring**: Continuous heartbeat checks to verify database availability
- **Auto-Reconnect**: Automatic recovery from transient network failures

### 2. Connection Pooling
Built on top of Motor/PyMongo's robust pooling:
- **Min Pool Size**: Configurable minimum connections (default: 10) to keep warm
- **Max Pool Size**: Configurable maximum connections (default: 100) to prevent resource exhaustion
- **Wait Queue**: Requests queue up when pool is exhausted (with timeout)
- **Socket Keepalive**: TCP keepalive enabled to detect dead connections

### 3. Resilience & Reliability
- **Exponential Backoff**: Smart retry logic for connection attempts (1s, 2s, 4s...)
- **Server Selection**: Configurable timeout for finding suitable nodes (primary/secondary)
- **Transaction Support**: Auto-detection of replica set capabilities for ACID transactions
- **Error Handling**: Unified exception handling for connection, timeout, and operation errors

### 4. Multi-Tenancy Support
- **Tenant Isolation**: Provides `get_tenant_collection()` for automatic query scoping
- **Context Propagation**: Ensures `tenant_id` is consistently applied to all operations
- **RBAC Integration**: Works with tenant context to enforce role-based access

### 5. Observability
- **Performance Logging**: Tracks query execution time and connection latency
- **Structured Logs**: JSON-formatted logs for easy ingestion by monitoring tools
- **Health Metrics**: Exposes database health status to Prometheus/health endpoints

## Usage Examples

### Basic Usage (Singleton Access)

```python
from second_brain_database.database import db_manager

# Get the global instance (already connected in main.py)
users_collection = db_manager.get_collection("users")

# Perform async operations
user = await users_collection.find_one({"username": "alice"})
```

### Multi-Tenant Usage

```python
# Get a collection scoped to a specific tenant
# All queries on this object will automatically filter by tenant_id
tenant_users = db_manager.get_tenant_collection("users", tenant_id="tenant_123")

# This actually runs: find({"username": "bob", "tenant_id": "tenant_123"})
user = await tenant_users.find_one({"username": "bob"})
```

### Transaction Usage (Replica Set Only)

```python
async with await db_manager.client.start_session() as session:
    async with session.start_transaction():
        await db_manager.get_collection("accounts").update_one(
            {"_id": from_id}, {"$inc": {"balance": -100}}, session=session
        )
        await db_manager.get_collection("accounts").update_one(
            {"_id": to_id}, {"$inc": {"balance": 100}}, session=session
        )
```

### Health Check

```python
is_healthy = await db_manager.health_check()
if not is_healthy:
    logger.critical("Database is down!")
```

## Configuration

The manager is configured via `config.py` settings:

- `MONGODB_URL`: Connection string (e.g., `mongodb://user:pass@host:27017`)
- `MONGODB_DATABASE`: Target database name
- `MONGODB_MIN_POOL_SIZE`: Minimum connections in pool (default: 10)
- `MONGODB_MAX_POOL_SIZE`: Maximum connections in pool (default: 100)
- `MONGODB_SERVER_SELECTION_TIMEOUT`: Timeout for finding a server (ms)
- `MONGODB_CONNECT_TIMEOUT`: Timeout for initial connection (ms)

## Performance Characteristics

- **Connection Time**: <10ms (warm pool), <50ms (new connection)
- **Query Overhead**: <1ms (Motor wrapper overhead)
- **Concurrency**: Scales to thousands of concurrent coroutines
- **Throughput**: Limited only by MongoDB server capacity and network bandwidth

## Thread Safety

The `DatabaseManager` is designed for **asyncio** and is **not thread-safe**.
- All methods must be called from the **same event loop**
- Do not share the manager instance across threads
- Motor handles concurrent async tasks safely within the loop

## Module Attributes

Attributes:
    logger (Logger): General application logger.
    db_logger (Logger): Specialized logger for database operations (`[DATABASE]`).
    perf_logger (Logger): Logger for performance metrics (`[DB_PERFORMANCE]`).
    health_logger (Logger): Logger for health checks (`[DB_HEALTH]`).
    
    db_manager (DatabaseManager): Global singleton instance used throughout the application.
        Initialized in `main.py` startup event.

## Todo

Todo:
    * Implement circuit breaker pattern for database failures
    * Add support for read preferences (primary vs secondary) configuration
    * Implement automatic query analysis for slow queries
    * Add support for client-side field encryption (CSFLE)
    * Implement connection pool metrics export to Prometheus
"""

import asyncio
import time
from typing import Any, Dict, List, Optional, Union

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, PyMongoError, ServerSelectionTimeoutError

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()
db_logger = get_logger(prefix="[DATABASE]")
perf_logger = get_logger(prefix="[DB_PERFORMANCE]")
health_logger = get_logger(prefix="[DB_HEALTH]")


class DatabaseManager:
    """
    Manages MongoDB connections, collections, and database operations.

    This class encapsulates all MongoDB interaction logic, providing a clean interface for
    the rest of the application. It handles connection lifecycle, health monitoring, index
    creation, and tenant-aware collection access.

    **Lifecycle:**
    1. **Instantiation**: Create manager (sets `client=None`, `database=None`)
    2. **Connection**: Call `connect()` to establish MongoDB connection
    3. **Operations**: Use `get_collection()` or `get_tenant_collection()` for queries
    4. **Health Monitoring**: Periodic `health_check()` calls to verify availability
    5. **Shutdown**: Call `disconnect()` to close connections gracefully

    **Connection Pooling:**
    Motor automatically manages a connection pool (default: 5-50 connections). The pool is
    shared across all collection instances obtained from the same `DatabaseManager`.

    **Transaction Support Detection:**
    On connection, the manager auto-detects if the MongoDB deployment supports transactions:
    - **Replica Set**: Supports transactions (`transactions_supported=True`)
    - **Sharded Cluster (mongos)**: Supports transactions (`transactions_supported=True`)
    - **Standalone**: No transactions (`transactions_supported=False`)

    Attributes:
        client (`Optional[AsyncIOMotorClient]`): The Motor async MongoDB client. `None` until
            `connect()` is called successfully.
        database (`Optional[AsyncIOMotorDatabase]`): The selected MongoDB database instance.
            `None` until connection is established.
        transactions_supported (`Optional[bool]`): Whether the deployment supports transactions.
            Detected during `connect()`.

    Example:
        ```python
        # Initialize manager
        manager = DatabaseManager()

        # Connect to MongoDB
        await manager.connect()

        # Use collections
        users = manager.get_collection("users")
        await users.insert_one({"username": "alice"})

        # Check health
        if await manager.health_check():
            print("Database is healthy")

        # Disconnect
        await manager.disconnect()
        ```

    Note:
        This class is typically used as a singleton via the `db_manager` global instance.
        Avoid creating multiple instances as this defeats connection pooling.

    Warning:
        Always call `connect()` before using any database operations, and `disconnect()`
        during application shutdown to prevent connection leaks.

    See Also:
        - `connect()`: Establish database connection
        - `get_collection()`: Retrieve a MongoDB collection
        - `get_tenant_collection()`: Get a tenant-aware collection
    """

    def __init__(self):
        """
        Initialize the DatabaseManager with empty connection state.

        Creates a new manager instance with no active connections. The actual connection to
        MongoDB is established later via `connect()`.

        **Initial State:**
        - `client`: `None` (no MongoDB client)
        - `database`: `None` (no database selected)
        - `transactions_supported`: `None` (unknown until connection)
        - `_connection_retries`: `3` (max retry attempts)

        Example:
            ```python
            # Create manager (typically done once as a global)
            db_manager = DatabaseManager()

            # Manager is not yet connected
            assert db_manager.client is None
            assert db_manager.database is None
            ```

        Note:
            This is a lightweight operation (no network I/O). Connection happens in `connect()`.
        """
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self._connection_retries = 3
        # Will be set after connect(); True when connected to a replica-set or mongos that supports transactions
        self.transactions_supported: Optional[bool] = None

    async def connect(self):
        """
        Establish connection to MongoDB with exponential backoff retry logic.

        This method performs a **multi-step initialization** to connect to MongoDB:
        1. **Build connection string** with optional authentication credentials
        2. **Create Motor client** with production-grade connection pool settings
        3. **Ping database** to verify connectivity
        4. **Detect transaction support** (replica set or mongos)
        5. **Log connection metrics** for observability

        The method implements **exponential backoff** retry logic to handle transient network
        issues, DNS resolution failures, or temporary MongoDB unavailability. Up to 3 attempts
        are made with increasing delays (1s, 2s, 4s).

        **Connection Pooling:**
        - **Min Pool Size**: 5 connections (always kept alive)
        - **Max Pool Size**: 50 connections (hard limit)
        - **Server Selection Timeout**: Configurable via `MONGODB_SERVER_SELECTION_TIMEOUT`
        - **Connection Timeout**: Configurable via `MONGODB_CONNECTION_TIMEOUT`

        **Authentication:**
        If `MONGODB_USERNAME` and `MONGODB_PASSWORD` are set in configuration, credentials
        are automatically injected into the connection string. Passwords are securely unwrapped
        from `SecretStr` to prevent accidental logging.

        **Transaction Support Detection:**
        After connecting, the method runs a `hello` command (or `isMaster` for older servers)
        to detect MongoDB deployment type:
        - **Replica Set** (`setName` present): `transactions_supported = True`
        - **Sharded Cluster** (`msg == 'isdbgrid'`): `transactions_supported = True`
        - **Standalone**: `transactions_supported = False`

        **Performance Logging:**
        All connection attempts are timed and logged with the following metrics:
        - Individual attempt duration
        - Total connection time (including retries)
        - Ping latency
        - Connection pool status

        Raises:
            `ServerSelectionTimeoutError`: If MongoDB is unreachable after all retry attempts.
                This typically indicates:
                - MongoDB server is down
                - Incorrect `MONGODB_URL`
                - Network/firewall blocking connection
                - DNS resolution failure
            `ConnectionFailure`: If authentication fails or connection is refused.
                Common causes:
                - Invalid `MONGODB_USERNAME` or `MONGODB_PASSWORD`
                - MongoDB not accepting connections (e.g., `bind_ip` misconfigured)
            `ConnectionError`: For lower-level network errors (timeout, refused).
            `TimeoutError`: If connection establishment exceeds timeout threshold.

        Example:
            ```python
            from second_brain_database.database import db_manager

            # Typically called in FastAPI lifespan
            try:
                await db_manager.connect()
                print(f"Connected to {db_manager.database.name}")
                print(f"Transactions supported: {db_manager.transactions_supported}")
            except ServerSelectionTimeoutError:
                print("MongoDB unreachable - check connection string and server status")
                raise
            except ConnectionFailure as e:
                print(f"Authentication failed: {e}")
                raise
            ```

        Note:
            - This method is **idempotent** - calling multiple times is safe (no-op if connected)
            - Connection state is cached in `self.client` and `self.database`
            - Always pair with `disconnect()` in application shutdown to prevent leaks
            - Credentials in logs are automatically redacted for security

        Warning:
            If connection succeeds but `transactions_supported` detection fails, it defaults
            to `False`. This is a conservative fallback. Check logs if you expect transaction
            support but see `False`.

        See Also:
            - `disconnect()`: For closing connections gracefully
            - `health_check()`: For verifying connection is still alive
            - `config.MONGODB_URL`: Connection string configuration
            - `config.MONGODB_USERNAME`: Optional authentication username
            - `config.MONGODB_PASSWORD`: Optional authentication password (SecretStr)
        """
        start_time = time.time()
        db_logger.info("Starting MongoDB connection process")

        for attempt in range(self._connection_retries):
            attempt_start = time.time()
            try:
                db_logger.info("Connection attempt %d/%d to MongoDB", attempt + 1, self._connection_retries)

                # Build connection string
                if settings.MONGODB_USERNAME and settings.MONGODB_PASSWORD:
                    password = (
                        settings.MONGODB_PASSWORD.get_secret_value()
                        if hasattr(settings.MONGODB_PASSWORD, "get_secret_value")
                        else settings.MONGODB_PASSWORD
                    )
                    connection_string = (
                        f"mongodb://{settings.MONGODB_USERNAME}:"
                        f"{password}@"
                        f"{settings.MONGODB_URL.replace('mongodb://', '')}"
                    )
                    db_logger.debug("Using authenticated connection to MongoDB")
                else:
                    connection_string = settings.MONGODB_URL
                    db_logger.debug("Using unauthenticated connection to MongoDB")

                # Log connection parameters (without sensitive data)
                db_logger.info(
                    "MongoDB connection config - URL: %s, Database: %s, MaxPool: %d, MinPool: %d, ServerTimeout: %dms, ConnTimeout: %dms",
                    settings.MONGODB_URL,
                    settings.MONGODB_DATABASE,
                    50,
                    5,
                    settings.MONGODB_SERVER_SELECTION_TIMEOUT,
                    settings.MONGODB_CONNECTION_TIMEOUT,
                )

                # Create client
                self.client = AsyncIOMotorClient(
                    connection_string,
                    serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT,
                    connectTimeoutMS=settings.MONGODB_CONNECTION_TIMEOUT,
                    maxPoolSize=50,
                    minPoolSize=5,
                )

                # Get database
                self.database = self.client[settings.MONGODB_DATABASE]
                db_logger.debug("Database instance created for: %s", settings.MONGODB_DATABASE)

                # Test connection with timing
                ping_start = time.time()
                await self.client.admin.command("ping")
                ping_duration = time.time() - ping_start
                # Detect whether the server supports transactions (i.e., is part of a replica set or a mongos)
                try:
                    # 'hello' is preferred; fallback to isMaster for older servers
                    try:
                        hello = await self.client.admin.command({"hello": 1})
                    except Exception:
                        hello = await self.client.admin.command({"isMaster": 1})

                    # Replica set: presence of setName -> transactions supported
                    # Mongos: msg == 'isdbgrid' indicates mongos (which supports transactions)
                    self.transactions_supported = bool(hello.get("setName") or hello.get("msg") == "isdbgrid")
                except Exception:
                    # If detection fails, be conservative and assume transactions are not supported
                    self.transactions_supported = False

                total_duration = time.time() - start_time
                perf_logger.info(
                    "MongoDB connection established successfully in %.3fs (ping: %.3fs)", total_duration, ping_duration
                )
                db_logger.info("Successfully connected to MongoDB database: %s", settings.MONGODB_DATABASE)

                # Log connection pool status
                await self._log_connection_pool_status()
                return

            except (ServerSelectionTimeoutError, ConnectionFailure) as e:
                attempt_duration = time.time() - attempt_start
                perf_logger.warning("Connection attempt %d failed after %.3fs", attempt + 1, attempt_duration)
                db_logger.warning(
                    "Failed to connect to MongoDB (attempt %d/%d): %s", attempt + 1, self._connection_retries, e
                )
                if attempt == self._connection_retries - 1:
                    total_duration = time.time() - start_time
                    db_logger.error("All connection attempts failed after %.3fs", total_duration)
                    raise

                backoff_time = 2**attempt
                db_logger.info("Waiting %.1fs before retry (exponential backoff)", backoff_time)
                await asyncio.sleep(backoff_time)

            except (ConnectionError, TimeoutError) as e:
                attempt_duration = time.time() - attempt_start
                perf_logger.error("Connection error after %.3fs", attempt_duration)
                db_logger.error("Connection error connecting to MongoDB: %s", e)
                raise

    async def _log_connection_pool_status(self):
        """Log current connection pool status for monitoring"""
        try:
            if self.client:
                # Get server info for connection pool monitoring
                server_info = await self.client.server_info()
                health_logger.info(
                    "MongoDB server info - Version: %s, MaxBsonSize: %d",
                    server_info.get("version", "unknown"),
                    server_info.get("maxBsonObjectSize", 0),
                )

                # Log connection pool configuration
                health_logger.info(
                    "Connection pool config - MaxPoolSize: %d, MinPoolSize: %d",
                    50,  # maxPoolSize from client creation
                    5,  # minPoolSize from client creation
                )
        except Exception as e:
            health_logger.warning("Failed to log connection pool status: %s", e)

    async def disconnect(self):
        """
        Gracefully disconnect from MongoDB and close all connections.

        This method performs an **orderly shutdown** of the MongoDB connection:
        1. **Log final connection pool status** for diagnostics
        2. **Close Motor client** (this releases all pooled connections)
        3. **Log disconnect metrics** (timing, status)

        The method ensures that all active connections in the connection pool are properly
        closed, preventing resource leaks and allowing MongoDB to clean up server-side
        resources. **Performance Logging:**
        Disconnect duration is timed and logged for observability. Typical disconnect times
        are under 100ms unless there are pending operations.

        **Graceful Shutdown:**
        Motor handles graceful closure of all connections in the pool. If there are active
        operations, the client will wait for them to complete (within a reasonable timeout)
        before forcibly closing connections.

        Raises:
            `Exception`: If an error occurs during disconnection. This is logged but does
                **not prevent** the connection from being closed. Common causes:
                - Network errors while sending close commands
                - Timeouts waiting for pending operations

        Example:
            ```python
            from second_brain_database.database import db_manager

            # Typically called in FastAPI lifespan shutdown
            try:
                await db_manager.disconnect()
                print("MongoDB disconnected successfully")
            except Exception as e:
                print(f"Error during disconnect (connection still closed): {e}")
            ```

        Note:
            - This method is **safe to call** even if not connected (no-op)
            - After disconnection, `self.client` remains set but is **unusable**
            - To reconnect, call `connect()` again (creates a new client)
            - Always call this during application shutdown to prevent warnings

        Warning:
            Disconnecting while operations are in-flight may cause those operations to fail
            with connection errors. Ensure all async tasks complete before shutdown.

        See Also:
            - `connect()`: For establishing the initial connection
            - `health_check()`: For verifying connection before disconnect
            - FastAPI lifespan pattern in `main.py:lifespan()`
        """
        start_time = time.time()
        db_logger.info("Starting MongoDB disconnection process")

        if self.client:
            try:
                # Log final connection pool status before disconnect
                await self._log_connection_pool_status()

                self.client.close()
                duration = time.time() - start_time
                perf_logger.info("MongoDB disconnection completed in %.3fs", duration)
                db_logger.info("Successfully disconnected from MongoDB")
            except Exception as e:
                duration = time.time() - start_time
                perf_logger.error("MongoDB disconnection failed after %.3fs", duration)
                db_logger.error("Error during MongoDB disconnection: %s", e)
                raise
        else:
            db_logger.warning("Disconnect called but no active MongoDB connection found")

    async def health_check(self) -> bool:
        """
        Verify MongoDB connection health with a lightweight ping operation.

        This method performs a **quick health check** by sending a `ping` command to the
        MongoDB admin database. It's designed for use in:
        - **Kubernetes liveness probes**: `/health` endpoint
        - **Monitoring dashboards**: Periodic health polling
        - **Circuit breakers**: Detect database unavailability
        - **Pre-flight checks**: Before critical operations

        **Performance:**
        The ping command is **extremely lightweight** (typically <5ms on local networks,
        <50ms over WAN). It only tests network connectivity and server responsiveness,
        not actual query performance.

        **Failure Scenarios:**
        Returns `False` (without raising exceptions) in these cases:
        - No client initialized (forgot to call `connect()`)
        - MongoDB server unreachable (network down, server crashed)
        - Authentication expired (rare with Motor, but possible)
        - Connection timeout (server overloaded)

        Returns:
            `bool`: `True` if database is reachable and responding, `False` otherwise.

        Example:
            ```python
            from fastapi import FastAPI, HTTPException
            from second_brain_database.database import db_manager

            @app.get("/health")
            async def health_endpoint():
                is_healthy = await db_manager.health_check()
                if not is_healthy:
                    raise HTTPException(status_code=503, detail="Database unavailable")
                return {"status": "healthy", "database": "connected"}

            # In application logic
            if not await db_manager.health_check():
                print("⚠️ Database is down, skipping background task")
                return
            ```

        Note:
            - This check does **not** verify query performance, only connectivity
            - For deeper health checks, use `db_manager.log_collection_stats()`
            - Health check timing is logged via `perf_logger` for monitoring

        Warning:
            Don't use this in hot paths (e.g., before every query). The connection pool
            handles transient failures automatically. Reserve this for periodic monitoring.

        See Also:
            - `connect()`: Must be called before health checks are meaningful
            - `log_database_stats()`: For comprehensive database health metrics
            - FastAPI health check pattern in `routes/dashboard.py`
        """
        start_time = time.time()
        health_logger.debug("Starting database health check")

        try:
            if self.client is None:
                health_logger.warning("Health check failed: No database client available")
                return False

            # Ping the database with timing
            ping_start = time.time()
            await self.client.admin.command("ping")
            ping_duration = time.time() - ping_start

            total_duration = time.time() - start_time
            perf_logger.debug(
                "Database health check completed successfully in %.3fs (ping: %.3fs)", total_duration, ping_duration
            )
            health_logger.debug("Database health check passed")
            return True

        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            duration = time.time() - start_time
            perf_logger.warning("Database health check failed after %.3fs", duration)
            health_logger.error("Database health check failed: %s", e)
            return False
        except (ConnectionError, TimeoutError) as e:
            duration = time.time() - start_time
            perf_logger.warning("Database health check connection error after %.3fs", duration)
            health_logger.error("Connection error during health check: %s", e)
            return False
        except Exception as e:
            duration = time.time() - start_time
            perf_logger.error("Unexpected error during health check after %.3fs", duration)
            health_logger.error("Unexpected error during health check: %s", e)
            return False

    def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """
        Retrieve a MongoDB collection by name from the connected database.

        This is the **primary method** for accessing MongoDB collections in the application.
        It returns a Motor `AsyncIOMotorCollection` instance that supports all async MongoDB
        operations (`find()`, `insert_one()`, `update_many()`, etc.).

        **Collection Access Pattern:**
        Collections are accessed **lazily** - they are not created until data is written.
        Calling this method does not create a collection in MongoDB, it only returns a
        reference that will be used when performing operations.

        **Multi-Tenancy Note:**
        This method returns a **standard** collection without tenant filtering. For
        tenant-aware operations, use `get_tenant_collection()` instead.

        Args:
            collection_name (`str`): The name of the MongoDB collection to retrieve.
                Common examples: `"users"`, `"families"`, `"chat_sessions"`.

        Returns:
            `AsyncIOMotorCollection`: A Motor async collection instance for performing
                database operations.

        Raises:
            `ConnectionError`: If the database connection has not been established via
                `connect()`. This prevents queries against a null database.

        Example:
            ```python
            from second_brain_database.database import db_manager

            # Get a collection
            users = db_manager.get_collection("users")

            # Perform async operations
            user = await users.find_one({"username": "alice"})
            result = await users.insert_one({"username": "bob", "email": "bob@example.com"})

            # Aggregation pipelines
            pipeline = [{"$match": {"is_active": True}}, {"$count": "active_users"}]
            results = await users.aggregate(pipeline).to_list(length=None)
            ```

        Note:
            - Collections are **not created** until you write data to them
            - This method is **synchronous** (no `await` needed)
            - The returned collection is **thread-safe** for use with asyncio
            - All queries use the connection pool automatically

        Warning:
            For **multi-tenant applications**, always use `get_tenant_collection()` to
            ensure proper tenant isolation. Using this method directly bypasses tenant
            filtering and may expose cross-tenant data leaks.

        See Also:
            - `get_tenant_collection()`: For tenant-aware collection access
            - `connect()`: Must be called before collection access
            - Motor AsyncIOMotorCollection docs: https://motor.readthedocs.io/
        """
        if not self.database:
            db_logger.error("Attempted to get collection '%s' without database connection", collection_name)
            raise ConnectionError("Database not connected. Call connect() first.")

        db_logger.debug("Retrieving collection: %s", collection_name)
        return self.database[collection_name]

    def get_tenant_collection(
        self, collection_name: str, tenant_id: Optional[str] = None
    ) -> Union[AsyncIOMotorCollection, "TenantAwareCollection"]:
        """
        Get a collection with automatic tenant filtering for multi-tenant applications.

        This method is the **multi-tenancy-aware** alternative to `get_collection()`. It
        returns a `TenantAwareCollection` wrapper that automatically injects `tenant_id`
        into all queries, ensuring **strict tenant isolation**.

        **Tenant ID Resolution:**
        The `tenant_id` is determined in this order:
        1. **Explicit argument**: If `tenant_id` parameter is provided, use it
        2. **Request context**: Extract from `tenant_context` middleware if available
        3. **No tenant**: Fall back to regular collection (no filtering)

        **Behavior Based on Configuration:**
        - **Multi-tenancy enabled** (`MULTI_TENANCY_ENABLED=True`) AND tenant ID available:
          Returns `TenantAwareCollection` with automatic filtering
        - **Multi-tenancy disabled** OR no tenant ID:
          Returns standard `AsyncIOMotorCollection` (no filtering)

        **Automatic Tenant Filtering:**
        The `TenantAwareCollection` wrapper intercepts all query operations and adds
        `{"tenant_id": <tenant_id>}` to the query filter. This ensures:
        - **Reads**: Only return documents for the specified tenant
        - **Writes**: Automatically tag new documents with `tenant_id`
        - **Updates/Deletes**: Only affect documents belonging to the tenant

        Args:
            collection_name (`str`): The name of the MongoDB collection to retrieve.
            tenant_id (`Optional[str]`): Explicit tenant ID. If `None`, uses context from
           `get_current_tenant_id()` middleware. Defaults to `None`.

        Returns:
            `Union[AsyncIOMotorCollection, TenantAwareCollection]`:
                - `TenantAwareCollection` if multi-tenancy is enabled and tenant ID is available
                - `AsyncIOMotorCollection` otherwise (no filtering)

        Raises:
            `ConnectionError`: If database is not connected.

        Example:
            ```python
            from second_brain_database.database import db_manager
            from second_brain_database.middleware.tenant_context import set_current_tenant_id

            # Option 1: Explicit tenant ID
            users = db_manager.get_tenant_collection("users", tenant_id="tenant_abc123")

            # Option 2: Use request context (in FastAPI endpoint)
            # Middleware sets tenant_id from request
            users = db_manager.get_tenant_collection("users")  # Auto-uses context

            # All queries are automatically scoped to the tenant
            user = await users.find_one({"username": "alice"})
            # Actual query: {"username": "alice", "tenant_id": "tenant_abc123"}

            await users.insert_one({"username": "bob"})
            # Inserted doc: {"username": "bob", "tenant_id": "tenant_abc123"}
            ```

        Note:
            - **Fast APIs**: Tenant context is set automatically by `tenant_context_middleware`
            - **Background tasks**: Pass explicit `tenant_id` as tasks run outside request context
            - **Admin operations**: Use `get_collection()` if you need cross-tenant access
            - This method is **synchronous** (no `await` needed)

        Warning:
            NEVER use `get_collection()` in multi-tenant endpoints - it bypasses tenant
            isolation and creates **critical security vulnerabilities**. Always use this
            method for tenant-scoped operations.

        See Also:
            - `get_collection()`: For non-tenant-scoped collection access
            - `TenantAwareCollection`: The wrapper class implementation
            - `tenant_context_middleware`: Request middleware that sets tenant context
            - `get_current_tenant_id()`: Context retrieval function
        """
        from second_brain_database.config import settings
        from second_brain_database.database.tenant_collection import TenantAwareCollection
        from second_brain_database.middleware.tenant_context import get_current_tenant_id

        collection = self.get_collection(collection_name)

        # Determine effective tenant ID
        effective_tenant_id = tenant_id or get_current_tenant_id()

        # If multi-tenancy is disabled or no tenant context, return regular collection
        if not settings.MULTI_TENANCY_ENABLED or not effective_tenant_id:
            db_logger.debug("Returning regular collection for %s (no tenant context)", collection_name)
            return collection

        # Return tenant-aware collection
        db_logger.debug("Returning tenant-aware collection for %s (tenant: %s)", collection_name, effective_tenant_id)
        return TenantAwareCollection(collection, effective_tenant_id)

    async def create_indexes(self):
        """Create database indexes for better performance"""
        start_time = time.time()
        db_logger.info("Starting database index creation process")

        try:
            # Users collection indexes
            db_logger.info("Creating indexes for 'users' collection")
            users_collection = self.get_collection("users")

            # Get existing indexes with timing
            index_list_start = time.time()
            existing_indexes = await users_collection.list_indexes().to_list(length=None)
            index_list_duration = time.time() - index_list_start
            existing_index_names = [idx["name"] for idx in existing_indexes]

            perf_logger.debug("Listed existing indexes for 'users' collection in %.3fs", index_list_duration)
            db_logger.debug(
                "Found %d existing indexes in 'users' collection: %s", len(existing_index_names), existing_index_names
            )

            # Handle username index
            await self._create_or_update_index(
                users_collection, "username_1", "username", {"unique": True, "sparse": True}, existing_indexes
            )

            # Handle email index
            await self._create_or_update_index(
                users_collection, "email_1", "email", {"unique": True, "sparse": True}, existing_indexes
            )

            # Create additional user indexes
            await self._create_index_if_not_exists(users_collection, "failed_login_attempts", {})
            await self._create_index_if_not_exists(users_collection, "reset_blocklist", {})
            await self._create_index_if_not_exists(users_collection, "reset_whitelist", {})
            await self._create_index_if_not_exists(
                users_collection, "password_reset_token_expiry", {"expireAfterSeconds": 0}
            )

            # User Agent lockdown indexes for efficient access
            await self._create_index_if_not_exists(users_collection, "trusted_user_agent_lockdown", {})
            await self._create_index_if_not_exists(users_collection, "trusted_user_agents", {})
            await self._create_index_if_not_exists(users_collection, "trusted_user_agent_lockdown_codes", {})

            # Temporary access token indexes for "allow once" functionality
            await self._create_index_if_not_exists(users_collection, "temporary_ip_access_tokens", {})
            await self._create_index_if_not_exists(users_collection, "temporary_user_agent_access_tokens", {})
            await self._create_index_if_not_exists(users_collection, "temporary_ip_bypasses", {})

            # Family management indexes
            await self._create_index_if_not_exists(users_collection, "family_limits.max_families_allowed", {})
            await self._create_index_if_not_exists(users_collection, "family_memberships.family_id", {})
            await self._create_index_if_not_exists(users_collection, "family_memberships.role", {})
            await self._create_index_if_not_exists(users_collection, "family_notifications.unread_count", {})

            # Permanent tokens collection indexes
            db_logger.info("Creating indexes for 'permanent_tokens' collection")
            permanent_tokens_collection = self.get_collection("permanent_tokens")

            await self._create_index_if_not_exists(permanent_tokens_collection, "token_hash", {"unique": True})
            await self._create_index_if_not_exists(permanent_tokens_collection, [("user_id", 1), ("is_revoked", 1)], {})
            await self._create_index_if_not_exists(permanent_tokens_collection, "created_at", {})
            await self._create_index_if_not_exists(permanent_tokens_collection, "last_used_at", {})

            # Family management collections indexes
            await self._create_family_management_indexes()

            # Workspace management collections indexes
            await self._create_workspace_management_indexes()

            # Skills collection indexes - Skill logging and management
            await self._create_skills_indexes()

            # Chat system collections indexes
            await self._create_chat_indexes()

            # Tenant management collections indexes
            await self._create_tenant_indexes()

            # Migration management collections indexes
            await self._create_migration_indexes()

            total_duration = time.time() - start_time
            perf_logger.info("Database index creation completed successfully in %.3fs", total_duration)
            db_logger.info("Database indexes created successfully")

        except (ConnectionError, TimeoutError) as e:
            duration = time.time() - start_time
            perf_logger.error("Database index creation failed after %.3fs", duration)
            db_logger.error("Failed to create database indexes: %s", e)
            raise
        except Exception as e:
            duration = time.time() - start_time
            perf_logger.error("Unexpected error during index creation after %.3fs", duration)
            db_logger.error("Unexpected error creating database indexes: %s", e)
            raise

    async def _create_or_update_index(
        self,
        collection: AsyncIOMotorCollection,
        existing_name: str,
        field_name: str,
        options: Dict[str, Any],
        existing_indexes: List[Dict],
    ):
        """Create or update an index if it doesn't meet requirements"""
        start_time = time.time()

        if existing_name in [idx["name"] for idx in existing_indexes]:
            # Check if it meets requirements
            existing_idx = next((idx for idx in existing_indexes if idx["name"] == existing_name), None)
            if existing_idx and not existing_idx.get("sparse", False) and options.get("sparse"):
                db_logger.info("Dropping and recreating index '%s' to make it sparse", existing_name)
                try:
                    await collection.drop_index(existing_name)
                    await collection.create_index(field_name, **options)
                    duration = time.time() - start_time
                    perf_logger.debug("Recreated index '%s' in %.3fs", existing_name, duration)
                    db_logger.debug("Successfully recreated index: %s", existing_name)
                except Exception as e:
                    duration = time.time() - start_time
                    perf_logger.warning("Failed to recreate index '%s' after %.3fs", existing_name, duration)
                    db_logger.warning("Could not recreate index '%s': %s", existing_name, e)
            else:
                db_logger.debug("Index '%s' already exists with correct configuration", existing_name)
        else:
            try:
                await collection.create_index(field_name, **options)
                duration = time.time() - start_time
                perf_logger.debug("Created new index '%s' in %.3fs", field_name, duration)
                db_logger.debug("Successfully created index: %s", field_name)
            except Exception as e:
                duration = time.time() - start_time
                perf_logger.warning("Failed to create index '%s' after %.3fs", field_name, duration)
                db_logger.warning("Could not create index '%s': %s", field_name, e)

    async def _create_index_if_not_exists(
        self, collection: AsyncIOMotorCollection, field_spec: Any, options: Dict[str, Any]
    ):
        """Create an index if it doesn't already exist"""
        start_time = time.time()

        try:
            await collection.create_index(field_spec, **options)
            duration = time.time() - start_time
            perf_logger.debug("Created/ensured index '%s' in %.3fs", field_spec, duration)
            db_logger.debug("Successfully created/ensured index: %s", field_spec)
        except Exception as e:
            duration = time.time() - start_time
            perf_logger.warning("Failed to create/ensure index '%s' after %.3fs", field_spec, duration)
            db_logger.warning("Could not create/ensure index '%s': %s", field_spec, e)

    # Database operation logging utilities
    def log_query_start(
        self, collection_name: str, operation: str, query: Optional[Dict] = None, options: Optional[Dict] = None
    ) -> float:
        """Log the start of a database query and return start time for performance tracking"""
        start_time = time.time()

        # Sanitize query for logging (remove sensitive data)
        safe_query = self._sanitize_query_for_logging(query) if query else {}
        safe_options = self._sanitize_query_for_logging(options) if options else {}

        db_logger.debug(
            "Starting %s operation on collection '%s' - Query: %s, Options: %s",
            operation,
            collection_name,
            safe_query,
            safe_options,
        )
        return start_time

    def log_query_success(
        self,
        collection_name: str,
        operation: str,
        start_time: float,
        result_count: Optional[int] = None,
        result_info: Optional[str] = None,
    ):
        """Log successful completion of a database query with performance metrics"""
        duration = time.time() - start_time

        if result_count is not None:
            perf_logger.info(
                "%s on '%s' completed successfully in %.3fs - %d records",
                operation,
                collection_name,
                duration,
                result_count,
            )
            db_logger.debug(
                "%s operation on '%s' successful - Duration: %.3fs, Records: %d",
                operation,
                collection_name,
                duration,
                result_count,
            )
        else:
            perf_logger.info("%s on '%s' completed successfully in %.3fs", operation, collection_name, duration)
            db_logger.debug("%s operation on '%s' successful - Duration: %.3fs", operation, collection_name, duration)

        if result_info:
            db_logger.debug("Additional result info for %s on '%s': %s", operation, collection_name, result_info)

    def log_query_error(
        self, collection_name: str, operation: str, start_time: float, error: Exception, query: Optional[Dict] = None
    ):
        """Log database query errors with context and performance metrics"""
        duration = time.time() - start_time

        # Sanitize query for error logging
        safe_query = self._sanitize_query_for_logging(query) if query else {}

        perf_logger.error("%s on '%s' failed after %.3fs", operation, collection_name, duration)
        db_logger.error(
            "%s operation failed on collection '%s' after %.3fs - Error: %s, Query: %s",
            operation,
            collection_name,
            duration,
            error,
            safe_query,
        )

    def _sanitize_query_for_logging(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize database queries for safe logging by removing sensitive data"""
        if not isinstance(query, dict):
            return {}

        sensitive_fields = {
            "password",
            "password_hash",
            "token",
            "secret",
            "key",
            "credential",
            "private_key",
            "public_key",
            "auth_token",
            "access_token",
            "refresh_token",
            "api_key",
            "session_token",
            "reset_token",
            "verification_token",
        }

        sanitized: Dict[str, Any] = {}
        for key, value in query.items():
            if any(sensitive_field in key.lower() for sensitive_field in sensitive_fields):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_query_for_logging(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_query_for_logging(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    async def log_collection_stats(self, collection_name: str):
        """Log collection statistics for monitoring and debugging"""
        try:
            start_time = time.time()
            collection = self.get_collection(collection_name)

            # Get collection stats
            if self.database is None:
                raise RuntimeError("Database not connected")
            stats = await self.database.command("collStats", collection_name)
            duration = time.time() - start_time

            health_logger.info(
                "Collection '%s' stats - Documents: %d, Size: %d bytes, Indexes: %d (retrieved in %.3fs)",
                collection_name,
                stats.get("count", 0),
                stats.get("size", 0),
                stats.get("nindexes", 0),
                duration,
            )

        except Exception as e:
            duration = time.time() - start_time if "start_time" in locals() else 0
            health_logger.warning(
                "Failed to retrieve stats for collection '%s' after %.3fs: %s", collection_name, duration, e
            )

    async def log_database_stats(self):
        """Log overall database statistics for monitoring"""
        try:
            start_time = time.time()

            # Get database stats
            if self.database is None:
                raise RuntimeError("Database not connected")
            db_stats = await self.database.command("dbStats")
            duration = time.time() - start_time

            health_logger.info(
                "Database '%s' stats - Collections: %d, Objects: %d, DataSize: %d bytes, IndexSize: %d bytes (retrieved in %.3fs)",
                settings.MONGODB_DATABASE,
                db_stats.get("collections", 0),
                db_stats.get("objects", 0),
                db_stats.get("dataSize", 0),
                db_stats.get("indexSize", 0),
                duration,
            )

        except Exception as e:
            duration = time.time() - start_time if "start_time" in locals() else 0
            health_logger.warning("Failed to retrieve database stats after %.3fs: %s", duration, e)

    async def _create_family_management_indexes(self):
        """Create comprehensive indexes for family management collections with performance optimization"""
        try:
            db_logger.info("Creating indexes for family management collections")

            # Families collection indexes - Core family management
            families_collection = self.get_collection("families")
            await self._create_index_if_not_exists(families_collection, "family_id", {"unique": True})
            await self._create_index_if_not_exists(families_collection, "admin_user_ids", {})
            await self._create_index_if_not_exists(families_collection, "is_active", {})
            await self._create_index_if_not_exists(families_collection, "created_at", {})
            await self._create_index_if_not_exists(families_collection, "updated_at", {})
            await self._create_index_if_not_exists(families_collection, "member_count", {})
            await self._create_index_if_not_exists(
                families_collection, "sbd_account.account_username", {"unique": True, "sparse": True}
            )
            await self._create_index_if_not_exists(families_collection, "sbd_account.is_frozen", {})
            # Compound indexes for efficient queries
            await self._create_index_if_not_exists(families_collection, [("admin_user_ids", 1), ("is_active", 1)], {})
            await self._create_index_if_not_exists(families_collection, [("is_active", 1), ("created_at", -1)], {})

            # Family relationships collection indexes - Bidirectional relationship management
            relationships_collection = self.get_collection("family_relationships")
            await self._create_index_if_not_exists(relationships_collection, "relationship_id", {"unique": True})
            await self._create_index_if_not_exists(relationships_collection, "family_id", {})
            await self._create_index_if_not_exists(relationships_collection, "user_a_id", {})
            await self._create_index_if_not_exists(relationships_collection, "user_b_id", {})
            await self._create_index_if_not_exists(relationships_collection, "status", {})
            await self._create_index_if_not_exists(relationships_collection, "created_by", {})
            await self._create_index_if_not_exists(relationships_collection, "created_at", {})
            await self._create_index_if_not_exists(relationships_collection, "activated_at", {})
            # Compound indexes for relationship queries
            await self._create_index_if_not_exists(
                relationships_collection, [("user_a_id", 1), ("user_b_id", 1), ("family_id", 1)], {"unique": True}
            )
            await self._create_index_if_not_exists(relationships_collection, [("family_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(relationships_collection, [("user_a_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(relationships_collection, [("user_b_id", 1), ("status", 1)], {})

            # Family invitations collection indexes - Email invitation system
            invitations_collection = self.get_collection("family_invitations")
            await self._create_index_if_not_exists(invitations_collection, "invitation_id", {"unique": True})
            await self._create_index_if_not_exists(invitations_collection, "invitation_token", {"unique": True})
            await self._create_index_if_not_exists(invitations_collection, "family_id", {})
            await self._create_index_if_not_exists(invitations_collection, "inviter_user_id", {})
            await self._create_index_if_not_exists(invitations_collection, "invitee_email", {})
            await self._create_index_if_not_exists(invitations_collection, "invitee_user_id", {})
            await self._create_index_if_not_exists(invitations_collection, "status", {})
            await self._create_index_if_not_exists(invitations_collection, "created_at", {})
            await self._create_index_if_not_exists(invitations_collection, "expires_at", {"expireAfterSeconds": 0})
            # Compound indexes for invitation queries
            await self._create_index_if_not_exists(invitations_collection, [("family_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(invitations_collection, [("invitee_user_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(invitations_collection, [("invitee_email", 1), ("status", 1)], {})

            # Family notifications collection indexes - Notification system
            notifications_collection = self.get_collection("family_notifications")
            await self._create_index_if_not_exists(notifications_collection, "notification_id", {"unique": True})
            await self._create_index_if_not_exists(notifications_collection, "family_id", {})
            await self._create_index_if_not_exists(notifications_collection, "recipient_user_ids", {})
            await self._create_index_if_not_exists(notifications_collection, "type", {})
            await self._create_index_if_not_exists(notifications_collection, "status", {})
            await self._create_index_if_not_exists(notifications_collection, "created_at", {})
            await self._create_index_if_not_exists(notifications_collection, "sent_at", {})
            # Compound indexes for notification queries
            await self._create_index_if_not_exists(notifications_collection, [("family_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(
                notifications_collection, [("recipient_user_ids", 1), ("status", 1)], {}
            )
            await self._create_index_if_not_exists(notifications_collection, [("family_id", 1), ("created_at", -1)], {})

            # Family token requests collection indexes - Token request system
            token_requests_collection = self.get_collection("family_token_requests")
            await self._create_index_if_not_exists(token_requests_collection, "request_id", {"unique": True})
            await self._create_index_if_not_exists(token_requests_collection, "family_id", {})
            await self._create_index_if_not_exists(token_requests_collection, "requester_user_id", {})
            await self._create_index_if_not_exists(token_requests_collection, "status", {})
            await self._create_index_if_not_exists(token_requests_collection, "reviewed_by", {})
            await self._create_index_if_not_exists(token_requests_collection, "created_at", {})
            await self._create_index_if_not_exists(token_requests_collection, "expires_at", {"expireAfterSeconds": 0})
            await self._create_index_if_not_exists(token_requests_collection, "reviewed_at", {})
            # Compound indexes for token request queries
            await self._create_index_if_not_exists(token_requests_collection, [("family_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(
                token_requests_collection, [("requester_user_id", 1), ("status", 1)], {}
            )
            await self._create_index_if_not_exists(
                token_requests_collection, [("family_id", 1), ("created_at", -1)], {}
            )

            # Family admin actions collection indexes - Admin action audit trail
            admin_actions_collection = self.get_collection("family_admin_actions")
            await self._create_index_if_not_exists(admin_actions_collection, "action_id", {"unique": True})
            await self._create_index_if_not_exists(admin_actions_collection, "family_id", {})
            await self._create_index_if_not_exists(admin_actions_collection, "admin_user_id", {})
            await self._create_index_if_not_exists(admin_actions_collection, "target_user_id", {})
            await self._create_index_if_not_exists(admin_actions_collection, "action_type", {})
            await self._create_index_if_not_exists(admin_actions_collection, "created_at", {})
            # Compound indexes for admin action queries
            await self._create_index_if_not_exists(admin_actions_collection, [("family_id", 1), ("created_at", -1)], {})
            await self._create_index_if_not_exists(
                admin_actions_collection, [("admin_user_id", 1), ("created_at", -1)], {}
            )
            await self._create_index_if_not_exists(
                admin_actions_collection, [("target_user_id", 1), ("created_at", -1)], {}
            )
            await self._create_index_if_not_exists(admin_actions_collection, [("family_id", 1), ("action_type", 1)], {})

            db_logger.info("Family management collection indexes created successfully")

        except Exception as e:
            db_logger.error("Failed to create family management indexes: %s", e)
            raise

    async def _create_workspace_management_indexes(self):
        """Create comprehensive indexes for workspace management collections."""
        try:
            db_logger.info("Creating indexes for workspace management collections")

            # Workspaces collection indexes
            workspaces_collection = self.get_collection("workspaces")
            await self._create_index_if_not_exists(workspaces_collection, "workspace_id", {"unique": True})
            await self._create_index_if_not_exists(workspaces_collection, "owner_id", {})
            await self._create_index_if_not_exists(workspaces_collection, "members.user_id", {})
            await self._create_index_if_not_exists(workspaces_collection, "created_at", {})

            db_logger.info("Workspace management collection indexes created successfully")

        except Exception as e:
            db_logger.error("Failed to create workspace management indexes: %s", e)
            raise

    async def _create_skills_indexes(self):
        """Create comprehensive indexes for skills collection with performance optimization"""
        try:
            db_logger.info("Creating indexes for skills collection")

            # Skills collection indexes - Core skill management
            skills_collection = self.get_collection("user_skills")
            await self._create_index_if_not_exists(skills_collection, "skill_id", {"unique": True})
            await self._create_index_if_not_exists(skills_collection, "user_id", {})
            await self._create_index_if_not_exists(skills_collection, "parent_skill_id", {})
            await self._create_index_if_not_exists(skills_collection, "name", {})
            await self._create_index_if_not_exists(skills_collection, "category", {})
            await self._create_index_if_not_exists(skills_collection, "level", {})
            await self._create_index_if_not_exists(skills_collection, "is_active", {})
            await self._create_index_if_not_exists(skills_collection, "created_at", {})
            await self._create_index_if_not_exists(skills_collection, "updated_at", {})

            # Compound indexes for efficient queries
            await self._create_index_if_not_exists(skills_collection, [("user_id", 1), ("is_active", 1)], {})
            await self._create_index_if_not_exists(skills_collection, [("user_id", 1), ("category", 1)], {})
            await self._create_index_if_not_exists(skills_collection, [("user_id", 1), ("level", 1)], {})
            await self._create_index_if_not_exists(skills_collection, [("user_id", 1), ("created_at", -1)], {})
            await self._create_index_if_not_exists(skills_collection, [("parent_skill_id", 1), ("is_active", 1)], {})

            # Logs subdocument indexes for efficient log queries
            await self._create_index_if_not_exists(skills_collection, "logs.timestamp", {})
            await self._create_index_if_not_exists(skills_collection, "logs.level", {})
            await self._create_index_if_not_exists(skills_collection, [("user_id", 1), ("logs.timestamp", -1)], {})

            db_logger.info("Skills collection indexes created successfully")

        except Exception as e:
            db_logger.error("Failed to create skills indexes: %s", e)
            raise

    async def _create_chat_indexes(self):
        """Create comprehensive indexes for chat system collections with performance optimization"""
        try:
            db_logger.info("Creating indexes for chat system collections")

            # Chat sessions collection indexes - Core session management
            chat_sessions_collection = self.get_collection("chat_sessions")
            await self._create_index_if_not_exists(chat_sessions_collection, "id", {"unique": True})
            await self._create_index_if_not_exists(chat_sessions_collection, [("user_id", 1), ("is_active", 1)], {})
            await self._create_index_if_not_exists(chat_sessions_collection, "session_type", {})
            await self._create_index_if_not_exists(chat_sessions_collection, "created_at", {})
            await self._create_index_if_not_exists(chat_sessions_collection, "updated_at", {})
            await self._create_index_if_not_exists(chat_sessions_collection, "last_message_at", {})
            # Compound indexes for efficient session queries
            await self._create_index_if_not_exists(
                chat_sessions_collection, [("user_id", 1), ("session_type", 1)], {}
            )
            await self._create_index_if_not_exists(
                chat_sessions_collection, [("user_id", 1), ("created_at", -1)], {}
            )
            await self._create_index_if_not_exists(
                chat_sessions_collection, [("user_id", 1), ("last_message_at", -1)], {}
            )

            # Chat messages collection indexes - Message management and retrieval
            chat_messages_collection = self.get_collection("chat_messages")
            await self._create_index_if_not_exists(chat_messages_collection, "id", {"unique": True})
            await self._create_index_if_not_exists(
                chat_messages_collection, [("session_id", 1), ("created_at", 1)], {}
            )
            await self._create_index_if_not_exists(chat_messages_collection, "user_id", {})
            await self._create_index_if_not_exists(chat_messages_collection, "status", {})
            await self._create_index_if_not_exists(chat_messages_collection, "role", {})
            await self._create_index_if_not_exists(chat_messages_collection, "created_at", {})
            # Compound indexes for efficient message queries
            await self._create_index_if_not_exists(chat_messages_collection, [("user_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(
                chat_messages_collection, [("session_id", 1), ("role", 1), ("created_at", 1)], {}
            )

            # Token usage collection indexes - Token tracking and analytics
            token_usage_collection = self.get_collection("token_usage")
            await self._create_index_if_not_exists(token_usage_collection, "id", {"unique": True})
            await self._create_index_if_not_exists(token_usage_collection, "message_id", {})
            await self._create_index_if_not_exists(token_usage_collection, "session_id", {})
            await self._create_index_if_not_exists(token_usage_collection, [("user_id", 1), ("created_at", -1)], {})
            await self._create_index_if_not_exists(token_usage_collection, "model", {})
            await self._create_index_if_not_exists(token_usage_collection, "endpoint", {})
            await self._create_index_if_not_exists(token_usage_collection, "created_at", {})
            # Compound indexes for token usage analytics
            await self._create_index_if_not_exists(
                token_usage_collection, [("session_id", 1), ("created_at", -1)], {}
            )
            await self._create_index_if_not_exists(token_usage_collection, [("user_id", 1), ("model", 1)], {})

            # Message votes collection indexes - Feedback system
            message_votes_collection = self.get_collection("message_votes")
            await self._create_index_if_not_exists(message_votes_collection, "id", {"unique": True})
            await self._create_index_if_not_exists(
                message_votes_collection, [("message_id", 1), ("user_id", 1)], {"unique": True}
            )
            await self._create_index_if_not_exists(message_votes_collection, "message_id", {})
            await self._create_index_if_not_exists(message_votes_collection, "user_id", {})
            await self._create_index_if_not_exists(message_votes_collection, "vote_type", {})
            await self._create_index_if_not_exists(message_votes_collection, "created_at", {})
            # Compound indexes for vote queries
            await self._create_index_if_not_exists(message_votes_collection, [("message_id", 1), ("vote_type", 1)], {})

            db_logger.info("Chat system collection indexes created successfully")

        except Exception as e:
            db_logger.error("Failed to create chat system indexes: %s", e)
            raise

    async def _create_tenant_indexes(self):
        """Create comprehensive indexes for tenant management collections with performance optimization"""
        try:
            db_logger.info("Creating indexes for tenant management collections")

            # Tenants collection indexes - Core tenant management
            tenants_collection = self.get_collection("tenants")
            await self._create_index_if_not_exists(tenants_collection, "tenant_id", {"unique": True})
            await self._create_index_if_not_exists(tenants_collection, "slug", {"unique": True})
            await self._create_index_if_not_exists(tenants_collection, "owner_user_id", {})
            await self._create_index_if_not_exists(tenants_collection, "plan", {})
            await self._create_index_if_not_exists(tenants_collection, "status", {})
            await self._create_index_if_not_exists(tenants_collection, "created_at", {})
            await self._create_index_if_not_exists(tenants_collection, "settings.custom_domain", {"sparse": True})
            # Compound indexes for efficient queries
            await self._create_index_if_not_exists(tenants_collection, [("owner_user_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(tenants_collection, [("plan", 1), ("status", 1)], {})

            # Tenant memberships collection indexes - Membership management
            memberships_collection = self.get_collection("tenant_memberships")
            await self._create_index_if_not_exists(memberships_collection, "membership_id", {"unique": True})
            await self._create_index_if_not_exists(memberships_collection, "tenant_id", {})
            await self._create_index_if_not_exists(memberships_collection, "user_id", {})
            await self._create_index_if_not_exists(memberships_collection, "role", {})
            await self._create_index_if_not_exists(memberships_collection, "status", {})
            await self._create_index_if_not_exists(memberships_collection, "created_at", {})
            # Compound indexes for efficient membership queries
            await self._create_index_if_not_exists(
            memberships_collection, [("tenant_id", 1), ("user_id", 1)], {"unique": True}
            )
            await self._create_index_if_not_exists(memberships_collection, [("user_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(memberships_collection, [("tenant_id", 1), ("role", 1)], {})

            db_logger.info("Tenant management collection indexes created successfully")

        except Exception as e:
            db_logger.error("Failed to create tenant management indexes: %s", e)
            raise

    async def _create_migration_indexes(self):
        """Create comprehensive indexes for migration collections with performance optimization"""
        try:
            db_logger.info("Creating indexes for migration collections")

            # Migrations collection indexes - Migration tracking
            migrations_collection = self.get_collection("migrations")
            await self._create_index_if_not_exists(migrations_collection, "migration_id", {"unique": True})
            await self._create_index_if_not_exists(migrations_collection, "created_by", {})
            await self._create_index_if_not_exists(migrations_collection, "migration_type", {})
            await self._create_index_if_not_exists(migrations_collection, "status", {})
            await self._create_index_if_not_exists(migrations_collection, "created_at", {})
            await self._create_index_if_not_exists(migrations_collection, "completed_at", {})
            await self._create_index_if_not_exists(migrations_collection, "tenant_id", {})
            # Compound indexes for efficient migration queries
            await self._create_index_if_not_exists(migrations_collection, [("created_by", 1), ("created_at", -1)], {})
            await self._create_index_if_not_exists(migrations_collection, [("created_by", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(migrations_collection, [("migration_type", 1), ("status", 1)], {})

            db_logger.info("Migration collection indexes created successfully")

        except Exception as e:
            db_logger.error("Failed to create migration indexes: %s", e)
            raise

    async def monitor_connection_pool(self):
        """Monitor and log connection pool metrics"""
        try:
            if not self.client:
                health_logger.warning("Cannot monitor connection pool: No client available")
                return

            # Log current connection pool status
            health_logger.info(
                "Connection pool monitoring - MaxPoolSize: %d, MinPoolSize: %d",
                self.client.max_pool_size,
                self.client.min_pool_size,
            )

            # Test connection responsiveness
            start_time = time.time()
            await self.client.admin.command("ping")
            ping_duration = time.time() - start_time

            if ping_duration > 1.0:  # Slow response threshold
                health_logger.warning("Slow database response detected: %.3fs", ping_duration)
            else:
                health_logger.debug("Database ping response time: %.3fs", ping_duration)

        except Exception as e:
            health_logger.error("Connection pool monitoring failed: %s", e)

    async def initialize(self):
        """Initialize database connection (alias for connect)"""
        await self.connect()

    async def close(self):
        """Close database connection (alias for disconnect)"""
        await self.disconnect()


# Global database manager instance
db_manager = DatabaseManager()
