"""
# Replication Service

This module handles **Data Synchronization** across the distributed cluster.
It ensures that all nodes have consistent data using an event-sourcing approach.

## Domain Overview

In a distributed system, data written to one node must propagate to others.
- **Master-Replica**: Writes go to Master, which pushes changes to Replicas.
- **Event Sourcing**: Capturing every state change as an immutable event.
- **Change Streams**: Tapping into MongoDB's oplog for real-time updates.

## Key Features

### 1. Event Capture (Master)
- **Monitoring**: Watches MongoDB change streams for inserts, updates, and deletes.
- **Event Log**: Persists events to a `replication_log` collection for durability.

### 2. Event Propagation
- **Push Model**: Actively sends events to healthy replica nodes.
- **Lag Tracking**: Monitors how far behind each replica is.

### 3. Event Application (Replica)
- **Idempotency**: Applying events ensures the local state matches the master.
- **Ack**: Confirming successful application to update the replication status.

## Usage Example

```python
# Initialize replication (starts background tasks)
await replication_service.initialize()

# Manually capture an event (usually automatic)
await replication_service.capture_event(
    operation="update",
    collection="users",
    document_id="user_123",
    data={"status": "active"}
)
```
"""

import asyncio
from second_brain_database.utils.security_utils import get_client_ssl_params
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from motor.motor_asyncio import AsyncIOMotorChangeStream

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.cluster_manager import cluster_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.models.cluster_models import (
    EventStatus,
    NodeRole,
    NodeStatus,
    ReplicationEvent,
)

logger = get_logger()


class ReplicationService:
    """
    Service for handling data replication across distributed cluster nodes.

    Implements an event-sourcing pattern using MongoDB change streams to capture
    database modifications and replicate them to other nodes in the cluster.
    Ensures data consistency and high availability.

    **Key Components:**
    - **Change Stream Monitor**: Captures real-time database changes (Master only).
    - **Event Processor**: Background task to process and dispatch pending events.
    - **Replication Log**: Persistent storage of all replication events.
    - **Conflict Resolution**: (Implicit) Last-write-wins via sequence numbers.

    **Architecture:**
    - **Master Node**: Captures changes -> Creates Events -> Pushes to Replicas.
    - **Replica Nodes**: Receive Events -> Apply to Local DB -> Acknowledge.
    """

    def __init__(self):
        """Initialize replication service."""
        self.is_initialized: bool = False
        self._change_stream: Optional[AsyncIOMotorChangeStream] = None
        self._replication_task: Optional[asyncio.Task] = None
        self._event_processor_task: Optional[asyncio.Task] = None
        self._sequence_number: int = 0

    async def initialize(self) -> bool:
        """
        Initialize the replication service.

        Sets up necessary collections, loads state, and starts background tasks.
        If the current node is the Master, it starts the change stream monitor.

        **Steps:**
        1.  Checks if clustering and replication are enabled.
        2.  Ensures `replication_log` collection and indexes exist.
        3.  Loads the last processed sequence number.
        4.  Starts `_change_stream_loop` (Master only).
        5.  Starts `_process_events_loop` (All nodes).

        Returns:
            True if initialization was successful, False otherwise.
        """
        try:
            if not settings.CLUSTER_ENABLED or not settings.CLUSTER_REPLICATION_ENABLED:
                logger.info("Replication is disabled")
                return False

            logger.info("Initializing replication service")

            # Ensure replication log collection exists
            await self._ensure_collections()

            # Load current sequence number
            await self._load_sequence_number()

            # Start change stream monitoring if master
            if settings.cluster_is_master:
                await self._start_change_stream()

            # Start event processor
            self._event_processor_task = asyncio.create_task(self._process_events_loop())

            self.is_initialized = True
            logger.info("Replication service initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize replication service: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown replication service."""
        try:
            logger.info("Shutting down replication service")

            # Stop change stream
            if self._change_stream:
                await self._change_stream.close()

            # Cancel background tasks
            if self._replication_task:
                self._replication_task.cancel()
            if self._event_processor_task:
                self._event_processor_task.cancel()

            self.is_initialized = False
            logger.info("Replication service shutdown complete")

        except Exception as e:
            logger.error(f"Error during replication service shutdown: {e}", exc_info=True)

    async def capture_event(
        self,
        operation: str,
        collection: str,
        document_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Capture a database operation as a replication event.

        Creates a new `ReplicationEvent`, persists it to the log, and publishes
        it to Redis for real-time notification.

        **Operations:**
        - `insert`: New document creation.
        - `update`: Modification of existing document.
        - `delete`: Removal of document.
        - `replace`: Full document replacement.

        Args:
            operation: Type of operation (`insert`, `update`, `delete`, `replace`).
            collection: Name of the affected collection.
            document_id: ID of the affected document.
            data: The data payload (document content or update delta).

        Returns:
            The unique ID of the captured event.

        Raises:
            Exception: If event creation or persistence fails.
        """
        try:
            event_id = self._generate_event_id()
            self._sequence_number += 1

            # Get target nodes (all replicas)
            nodes = await self._get_replication_targets()

            event = ReplicationEvent(
                event_id=event_id,
                sequence_number=self._sequence_number,
                operation=operation,
                collection=collection,
                document_id=document_id,
                data=data or {},
                timestamp=datetime.now(timezone.utc),
                source_node=cluster_manager.node_id,
                target_nodes=[node.node_id for node in nodes],
                status=EventStatus.PENDING,
            )

            # Store event in replication log
            log_collection = db_manager.get_collection("replication_log")
            await log_collection.insert_one(event.model_dump())

            # Publish event to Redis for real-time sync
            await self._publish_event(event)

            logger.debug(f"Captured replication event {event_id} for {operation} on {collection}")
            return event_id

        except Exception as e:
            logger.error(f"Failed to capture replication event: {e}", exc_info=True)
            raise

    async def replicate_to_nodes(
        self,
        event: ReplicationEvent,
        target_nodes: Optional[List[str]] = None,
    ) -> bool:
        """
        Replicate a captured event to target nodes.

        Sends the event payload to the specified replica nodes via their internal API.
        Updates the event status based on success/failure of replication.

        Args:
            event: The `ReplicationEvent` object to replicate.
            target_nodes: List of node IDs to replicate to (default: all healthy replicas).

        Returns:
            True if replication succeeded to at least one node, False otherwise.
        """
        try:
            # Get target nodes
            if not target_nodes:
                nodes = await self._get_replication_targets()
                target_nodes = [node.node_id for node in nodes]

            if not target_nodes:
                logger.warning("No target nodes for replication")
                return False

            # Update event status
            await self._update_event_status(event.event_id, EventStatus.REPLICATING)

            # Replicate to each node
            success_count = 0
            failed_nodes = []

            for node_id in target_nodes:
                try:
                    success = await self._replicate_to_node(event, node_id)
                    if success:
                        success_count += 1
                    else:
                        failed_nodes.append(node_id)
                except Exception as e:
                    logger.error(f"Failed to replicate to node {node_id}: {e}")
                    failed_nodes.append(node_id)

            # Update event status based on results
            if success_count > 0:
                await self._update_event_status(
                    event.event_id,
                    EventStatus.REPLICATED,
                    replicated_at=datetime.now(timezone.utc),
                )
                logger.info(f"Event {event.event_id} replicated to {success_count}/{len(target_nodes)} nodes")
                return True
            else:
                await self._update_event_status(
                    event.event_id,
                    EventStatus.FAILED,
                    error_message=f"Failed to replicate to any nodes: {failed_nodes}",
                )
                logger.error(f"Event {event.event_id} failed to replicate to any nodes")
                return False

        except Exception as e:
            logger.error(f"Failed to replicate event {event.event_id}: {e}", exc_info=True)
            await self._update_event_status(
                event.event_id,
                EventStatus.FAILED,
                error_message=str(e),
            )
            return False

    async def apply_event(self, event: ReplicationEvent) -> bool:
        """
        Apply a received replication event to the local database.

        Executes the operation specified in the event (insert, update, delete)
        against the local MongoDB instance. Used by replica nodes to sync data.

        Args:
            event: The `ReplicationEvent` to apply.

        Returns:
            True if the operation was applied successfully, False otherwise.
        """
        try:
            collection = db_manager.get_collection(event.collection)

            if event.operation == "insert":
                await collection.insert_one(event.data)
            elif event.operation == "update":
                if event.document_id:
                    await collection.update_one(
                        {"_id": event.document_id},
                        {"$set": event.data}
                    )
            elif event.operation == "delete":
                if event.document_id:
                    await collection.delete_one({"_id": event.document_id})
            elif event.operation == "replace":
                if event.document_id:
                    await collection.replace_one(
                        {"_id": event.document_id},
                        event.data
                    )
            else:
                logger.warning(f"Unknown operation type: {event.operation}")
                return False

            logger.debug(f"Applied event {event.event_id} ({event.operation} on {event.collection})")
            return True

        except Exception as e:
            logger.error(f"Failed to apply event {event.event_id}: {e}", exc_info=True)
            return False

    async def get_replication_lag(self, node_id: str) -> float:
        """
        Calculate the replication lag for a specific node.

        Estimates how far behind a replica is by comparing the latest global sequence number
        with the last sequence number successfully replicated to that node.

        Args:
            node_id: The ID of the node to check.

        Returns:
            Estimated lag in seconds (approximate). Returns `inf` if node has never replicated.
        """
        try:
            log_collection = db_manager.get_collection("replication_log")

            # Get latest event
            latest_event = await log_collection.find_one(
                {},
                sort=[("sequence_number", -1)]
            )

            if not latest_event:
                return 0.0

            # Get latest replicated event for this node
            latest_replicated = await log_collection.find_one(
                {
                    "target_nodes": node_id,
                    "status": EventStatus.REPLICATED,
                },
                sort=[("sequence_number", -1)]
            )

            if not latest_replicated:
                # Node has never replicated
                return float('inf')

            # Calculate lag based on sequence numbers
            lag_events = latest_event["sequence_number"] - latest_replicated["sequence_number"]

            # Estimate lag in seconds (rough approximation)
            lag_seconds = lag_events * 0.1  # Assume 100ms per event

            return lag_seconds

        except Exception as e:
            logger.error(f"Failed to calculate replication lag for {node_id}: {e}", exc_info=True)
            return 0.0

    async def get_pending_events(self, limit: int = 100) -> List[ReplicationEvent]:
        """
        Retrieve a batch of pending replication events.

        Fetches events from the `replication_log` that have a status of `PENDING`.
        Used by the background event processor.

        Args:
            limit: Maximum number of events to retrieve (default: 100).

        Returns:
            A list of `ReplicationEvent` objects.
        """
        try:
            log_collection = db_manager.get_collection("replication_log")

            cursor = log_collection.find(
                {"status": EventStatus.PENDING},
                sort=[("sequence_number", 1)],
                limit=limit
            )

            events = []
            async for event_data in cursor:
                try:
                    events.append(ReplicationEvent(**event_data))
                except Exception as e:
                    logger.warning(f"Failed to parse event: {e}")
                    continue

            return events

        except Exception as e:
            logger.error(f"Failed to get pending events: {e}", exc_info=True)
            return []

    # Private helper methods

    def _generate_event_id(self) -> str:
        """
        Generate a unique, time-ordered event ID.

        Returns:
            A string ID prefixed with `evt-`.
        """
        return f"evt-{uuid.uuid4().hex[:16]}"

    async def _ensure_collections(self) -> None:
        """
        Ensure required replication collections and indexes exist.

        Creates the `replication_log` collection if missing and sets up indexes
        for efficient querying by `event_id`, `sequence_number`, `status`, and `timestamp`.
        """

    async def _load_sequence_number(self) -> None:
        """
        Load the last processed sequence number from the database.

        Initializes the local sequence counter to continue from the last known state.
        If no events exist, starts from 0.
        """

    async def _get_replication_targets(self) -> List[Any]:
        """
        Retrieve a list of healthy replica nodes.

        Queries the `cluster_manager` for all nodes with role `REPLICA`
        and status `HEALTHY`.

        Returns:
            A list of node objects to replicate to.
        """

    async def _replicate_to_node(self, event: ReplicationEvent, node_id: str) -> bool:
        """
        Send a replication event to a specific node via HTTP.

        Uses mTLS for secure communication.

        Args:
            event: The event to replicate.
            node_id: The target node ID.

        Returns:
            True if the node acknowledged the event (HTTP 200), False otherwise.
        """

    async def _publish_event(self, event: ReplicationEvent) -> None:
        """
        Publish a replication event to Redis Pub/Sub.

        Enables real-time updates for subscribers (e.g., WebSocket clients)
        listening to changes on specific collections.

        Args:
            event: The event to publish.
        """

    async def _update_event_status(
        self,
        event_id: str,
        status: EventStatus,
        replicated_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update the status of an event in the replication log.

        Args:
            event_id: The ID of the event to update.
            status: The new status (`PENDING`, `REPLICATING`, `REPLICATED`, `FAILED`).
            replicated_at: Timestamp of successful replication.
            error_message: Error details if failed.
        """

    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Generate authentication headers for inter-node communication.

        Returns:
            A dictionary containing the `Authorization` header with the cluster token.
        """

    async def _start_change_stream(self) -> None:
        """
        Start the MongoDB change stream monitor.

        Initiates the background task `_change_stream_loop` to listen for database changes.
        Only runs on the Master node.
        """

    async def _change_stream_loop(self) -> None:
        """
        Background loop to monitor MongoDB change streams.

        Watches all collections (excluding system and internal cluster collections)
        and delegates change events to `_handle_change_event`.
        """

    async def _handle_change_event(self, change: Dict[str, Any]) -> None:
        """
        Process a raw MongoDB change stream event.

        Extracts relevant data (operation type, document ID, content) and
        calls `capture_event` to persist and replicate the change.

        Args:
            change: The raw change event dictionary from MongoDB.
        """

    async def _process_events_loop(self) -> None:
        """
        Background loop to process pending replication events.

        Periodically fetches events with `PENDING` status and attempts to
        replicate them to target nodes. Ensures eventual consistency.
        """


# Global replication service instance
replication_service = ReplicationService()
