"""
# Cluster Audit Service

This module provides the **Audit Logging System** for cluster operations.
It creates an immutable record of significant events for compliance, debugging, and security.

## Domain Overview

In a distributed system, knowing "who did what and when" is crucial.
- **Events**: Node joins, leader elections, configuration changes, security incidents.
- **Structure**: Standardized event format with severity, timestamp, and metadata.
- **Storage**: Persisted in the `cluster_events` collection.

## Key Features

### 1. Event Logging
- **Structured Data**: Captures rich context (node ID, user ID, details dict).
- **Severity Tagging**: Categorizes events by importance.

### 2. Audit Retrieval
- **Filtering**: Query logs by severity, node, or time range.
- **History**: Provides a chronological trail of system state changes.

## Usage Example

```python
await cluster_audit_service.log_event(
    event_type="leader_election",
    node_id="node-01",
    details={"previous_leader": "node-02", "term": 5},
    severity="info"
)
```
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.cluster_models import ClusterEvent

logger = get_logger()


class ClusterAuditService:
    """
    Service for managing audit logs of cluster-wide operations.

    Provides a centralized mechanism to record and retrieve significant events
    occurring within the distributed cluster, such as node joins, leader elections,
    and health status changes.

    **Key Features:**
    - **Event Logging**: Persists structured event data to the `cluster_events` collection.
    - **Retrieval**: Supports filtering events by severity and node ID.
    - **Audit Trail**: Maintains a chronological history of system state changes.
    """

    async def log_event(
        self,
        event_type: str,
        node_id: str,
        details: Dict[str, Any],
        severity: str = "info",
        user_id: Optional[str] = None,
    ) -> None:
    async def log_event(
        self,
        event_type: str,
        node_id: str,
        details: Dict[str, Any],
        severity: str = "info",
        user_id: Optional[str] = None,
    ) -> None:
        """
        Record a significant cluster event.

        Creates a `ClusterEvent` object and persists it to the database.
        Used for debugging, auditing, and monitoring system health.

        Args:
            event_type: Category of the event (e.g., `node_joined`, `leader_elected`).
            node_id: The ID of the node where the event originated or applies.
            details: A dictionary containing specific event metadata.
            severity: Importance level (`info`, `warning`, `error`, `critical`).
            user_id: Optional ID of the user who triggered the event (if applicable).
        """
        try:
            event = ClusterEvent(
                event_type=event_type,
                node_id=node_id,
                details=details,
                severity=severity,
                user_id=user_id,
                timestamp=datetime.now(timezone.utc),
            )

            collection = db_manager.get_collection("cluster_events")
            await collection.insert_one(event.model_dump())

            logger.info(f"Cluster event logged: {event_type} - {node_id}")

        except Exception as e:
            logger.error(f"Failed to log cluster event: {e}", exc_info=True)

    async def get_events(
        self,
        limit: int = 100,
        severity: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> List[ClusterEvent]:
    async def get_events(
        self,
        limit: int = 100,
        severity: Optional[str] = None,
        node_id: Optional[str] = None,
    ) -> List[ClusterEvent]:
        """
        Retrieve a list of recent cluster events.

        Supports filtering by severity and node ID to isolate specific issues
        or audit trails. Results are ordered by timestamp (newest first).

        Args:
            limit: Maximum number of events to retrieve (default: 100).
            severity: Optional filter for event severity.
            node_id: Optional filter for a specific node ID.

        Returns:
            A list of `ClusterEvent` objects matching the criteria.
        """
        try:
            query = {}
            if severity:
                query["severity"] = severity
            if node_id:
                query["node_id"] = node_id

            collection = db_manager.get_collection("cluster_events")
            cursor = collection.find(query).sort("timestamp", -1).limit(limit)

            events = []
            async for doc in cursor:
                events.append(ClusterEvent(**doc))

            return events

        except Exception as e:
            logger.error(f"Failed to get cluster events: {e}", exc_info=True)
            return []

# Global instance
cluster_audit_service = ClusterAuditService()
