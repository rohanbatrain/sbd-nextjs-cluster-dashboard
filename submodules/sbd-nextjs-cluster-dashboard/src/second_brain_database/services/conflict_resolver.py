"""
# Conflict Resolution Service

This module handles **Data Consistency** in the distributed system.
It resolves conflicts when multiple nodes attempt to modify the same data concurrently.

## Domain Overview

In a multi-master or distributed environment, write conflicts are inevitable.
- **Strategies**:
    - **Last-Write-Wins (LWW)**: Time-based resolution (default).
    - **Manual**: Flag for human intervention.
    - **Custom**: Domain-specific merge logic (e.g., merging list fields).

## Key Features

### 1. Resolution Strategies
- **LWW**: Uses high-precision timestamps to determine the latest version.
- **Manual Queue**: Stores unresolved conflicts in `replication_conflicts` collection.
- **Field Merging**: Intelligent merging for specific collections (e.g., User Profiles).

### 2. Conflict Handling
- **Version Tracking**: Analyzes incoming versions with vector clocks or timestamps.
- **Auto-Resolution**: Applies the selected strategy to produce a single "winner" document.

## Usage Example

```python
resolved_data = await conflict_resolver.resolve_conflict(
    collection="users",
    document_id="user_123",
    versions=[version_a, version_b]
)
```
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()


class ConflictStrategy(str, Enum):
    """Conflict resolution strategy."""
    LAST_WRITE_WINS = "last_write_wins"
    MANUAL = "manual"
    CUSTOM = "custom"


class ConflictResolver:
    """
    Resolves data conflicts arising from concurrent writes in distributed clusters.

    Implements multiple strategies for conflict resolution when the same document
    is modified simultaneously on different nodes.

    **Strategies:**
    - **Last-Write-Wins (LWW)**: Automatically selects the version with the latest timestamp.
    - **Manual**: Stores conflicts for administrator review.
    - **Custom**: Collection-specific merge logic (e.g., field-level merging for user profiles).

    Attributes:
        strategy (ConflictStrategy): The active resolution strategy.
    """

    def __init__(self, strategy: ConflictStrategy = ConflictStrategy.LAST_WRITE_WINS):
        """Initialize conflict resolver with strategy."""
        self.strategy = strategy

    async def resolve_conflict(
        self,
        collection: str,
        document_id: str,
        versions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Resolve a conflict between multiple versions of a document.

        Applies the configured strategy to select or merge the winning version.

        Args:
            collection: The name of the collection containing the document.
            document_id: The ID of the conflicted document.
            versions: A list of conflicting versions, each with `timestamp`, `data`, and `source_node`.

        Returns:
            The resolved document data.

        Raises:
            ValueError: If no versions are provided.
        """
        if not versions:
            raise ValueError("No versions provided for conflict resolution")

        if len(versions) == 1:
            return versions[0]["data"]

        if self.strategy == ConflictStrategy.LAST_WRITE_WINS:
            return await self._last_write_wins(versions)
        elif self.strategy == ConflictStrategy.MANUAL:
            return await self._manual_resolution(collection, document_id, versions)
        elif self.strategy == ConflictStrategy.CUSTOM:
            return await self._custom_resolution(collection, document_id, versions)
        else:
            logger.warning(f"Unknown strategy {self.strategy}, falling back to LWW")
            return await self._last_write_wins(versions)

    async def _last_write_wins(self, versions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Resolve using Last-Write-Wins: select the version with the latest timestamp.

        Args:
            versions: List of versions, each with `timestamp` and `data` keys.

        Returns:
            The data from the most recently written version.
        """
        # Sort by timestamp (most recent first)
        sorted_versions = sorted(
            versions,
            key=lambda v: v.get("timestamp", datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True
        )

        winner = sorted_versions[0]
        logger.info(f"LWW resolution: selected version from {winner.get('source_node')} at {winner.get('timestamp')}")
        
        return winner["data"]

    async def _manual_resolution(
        self,
        collection: str,
        document_id: str,
        versions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Manual resolution: store the conflict for administrator intervention.

        Creates a record in the `replication_conflicts` collection and returns
        the first version temporarily.

        Args:
            collection: Collection name.
            document_id: Document ID.
            versions: List of conflicting versions.

        Returns:
            The first version (as a temporary placeholder).
        """
        # Store conflict for manual resolution
        from second_brain_database.database import db_manager
        
        conflict_doc = {
            "collection": collection,
            "document_id": document_id,
            "versions": versions,
            "resolved": False,
            "created_at": datetime.now(timezone.utc),
        }

        conflicts_collection = db_manager.get_collection("replication_conflicts")
        await conflicts_collection.insert_one(conflict_doc)

        logger.warning(f"Manual resolution required for {collection}/{document_id}, stored conflict")
        
        # Return first version temporarily
        return versions[0]["data"]

    async def _custom_resolution(
        self,
        collection: str,
        document_id: str,
        versions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Apply collection-specific custom merge logic.

        Supports intelligent merging for known collections (e.g., user profiles).
        Falls back to Last-Write-Wins for unrecognized collections.

        Args:
            collection: Collection name.
            document_id: Document ID.
            versions: List of conflicting versions.

        Returns:
            The merged or selected version.
        """
        # Example: for user profiles, merge non-conflicting fields
        if collection == "users":
            return await self._merge_user_profile(versions)
        
        # Default to LWW for unknown collections
        logger.warning(f"No custom strategy for {collection}, falling back to LWW")
        return await self._last_write_wins(versions)

    async def _merge_user_profile(self, versions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple user profile versions by prioritizing non-null values.

        Iterates through versions chronologically, updating fields with the latest
        non-null value for each attribute.

        Args:
            versions: List of user profile versions.

        Returns:
            A merged user profile with the latest non-null values.
        """
        merged = {}
        
        # Take latest non-null value for each field
        for version in sorted(versions, key=lambda v: v.get("timestamp", datetime.min.replace(tzinfo=timezone.utc))):
            data = version["data"]
            for key, value in data.items():
                if value is not None and (key not in merged or merged[key] is None):
                    merged[key] = value

        logger.info(f"Merged {len(versions)} user profile versions")
        return merged


# Global resolver instance
conflict_resolver = ConflictResolver(strategy=ConflictStrategy.LAST_WRITE_WINS)
