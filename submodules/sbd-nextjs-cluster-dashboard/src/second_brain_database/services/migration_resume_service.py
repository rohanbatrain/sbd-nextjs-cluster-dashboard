"""
# Migration Resume Service

This module provides **Checkpointing and Resume Capabilities** for long-running migrations.
It ensures that interrupted transfers can be resumed without restarting from scratch.

## Domain Overview

Large migrations can take hours. Network blips shouldn't be fatal.
- **Checkpointing**: Periodically saving state (current collection, document count) to Redis.
- **Resume**: Restoring state from the last valid checkpoint.
- **Pause**: Allowing administrators to temporarily halt transfers (e.g., during peak hours).

## Key Features

### 1. State Management
- **Redis Storage**: Uses Redis for fast, ephemeral state tracking with TTL.
- **Granularity**: Tracks progress at the collection level.

### 2. Control Flow
- **Pause/Resume**: Flags in Redis control the active transfer loop.
- **Cleanup**: Automatically removes checkpoints upon successful completion.

## Usage Example

```python
# Save a checkpoint during transfer
await migration_resume_service.save_checkpoint(
    TransferCheckpoint(
        transfer_id="tx_123",
        current_collection="users",
        documents_processed=5000
    )
)

# Check if we should pause
if await migration_resume_service.is_paused("tx_123"):
    await wait_for_resume()
```
"""

import json
from typing import Optional, Dict, Any

from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.migration_advanced_models import TransferCheckpoint

logger = get_logger(prefix="[MigrationResume]")


class MigrationResumeService:
    """
    Manages transfer checkpoints for pause/resume functionality.

    Stores transfer state in Redis to enable resuming interrupted migrations
    from the last successful checkpoint.

    **Features:**
    - Checkpoint persistence in Redis (24-hour TTL)
    - Pause/resume controls
    - Automatic cleanup on completion
    - Collection-level granularity
    """

    def __init__(self):
        self.checkpoint_prefix = "migration:checkpoint:"
        self.checkpoint_ttl = 86400  # 24 hours

    async def save_checkpoint(self, checkpoint: TransferCheckpoint) -> bool:
        """Save a checkpoint to Redis."""
        try:
            key = f"{self.checkpoint_prefix}{checkpoint.transfer_id}"
            value = checkpoint.model_dump_json()
            
            redis_manager.setex(key, self.checkpoint_ttl, value)
            logger.info(f"Saved checkpoint for transfer {checkpoint.transfer_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            return False

    async def get_checkpoint(self, transfer_id: str) -> Optional[TransferCheckpoint]:
        """Get the latest checkpoint for a transfer."""
        try:
            key = f"{self.checkpoint_prefix}{transfer_id}"
            value = redis_manager.get(key)
            
            if value:
                data = json.loads(value)
                return TransferCheckpoint(**data)
            return None
        except Exception as e:
            logger.error(f"Failed to get checkpoint: {e}")
            return None

    async def delete_checkpoint(self, transfer_id: str) -> bool:
        """Delete checkpoint after successful completion."""
        try:
            key = f"{self.checkpoint_prefix}{transfer_id}"
            redis_manager.delete(key)
            logger.info(f"Deleted checkpoint for transfer {transfer_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {e}")
            return False

    async def pause_transfer(self, transfer_id: str) -> bool:
        """Mark transfer as paused in Redis."""
        try:
            key = f"migration:paused:{transfer_id}"
            redis_manager.setex(key, 3600, "1")  # Paused flag for 1 hour
            logger.info(f"Paused transfer {transfer_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause transfer: {e}")
            return False

    async def resume_transfer(self, transfer_id: str) -> bool:
        """Remove paused flag."""
        try:
            key = f"migration:paused:{transfer_id}"
            redis_manager.delete(key)
            logger.info(f"Resumed transfer {transfer_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resume transfer: {e}")
            return False

    async def is_paused(self, transfer_id: str) -> bool:
        """Check if transfer is paused."""
        try:
            key = f"migration:paused:{transfer_id}"
            return redis_manager.exists(key) == 1
        except Exception:
            return False


# Global instance
migration_resume_service = MigrationResumeService()
