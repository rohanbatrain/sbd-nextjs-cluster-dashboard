"""
# Advanced Migration Models

This module defines **advanced control structures** for the migration system, enabling
fine-grained management of data transfers. It supports bandwidth throttling,
transfer checkpoints for resumability, and automated scheduling.

## Domain Model Overview

The advanced migration features allow for:

- **Flow Control**: Pause, resume, or cancel ongoing transfers.
- **Throttling**: Limit bandwidth usage to prevent network saturation.
- **Resumability**: Checkpoints track progress to recover from failures.
- **Automation**: Cron-based scheduling for recurring migration jobs.

## Key Features

### 1. Transfer Control
- **Actions**: `pause`, `resume`, `cancel`.
- **Bandwidth Limits**: Dynamic adjustment of transfer speed (Mbps).

### 2. Reliability
- **Checkpoints**: Records the last processed document ID per collection.
- **State Tracking**: Detailed status monitoring for long-running jobs.

### 3. Scheduling
- **Cron Expressions**: Standard syntax for defining recurring schedules.
- **Job Management**: Enable/disable scheduled transfers.

## Usage Examples

### Pausing a Transfer

```python
control = TransferControlRequest(
    action=TransferAction.PAUSE,
    reason="High network load detected"
)
```

### Scheduling a Daily Backup

```python
job = ScheduledTransfer(
    schedule_id="daily_backup",
    owner_id="admin",
    from_instance_id="prod_db",
    to_instance_id="backup_db",
    cron_expression="0 2 * * *"  # Every day at 2 AM
)
```

## Module Attributes

Attributes:
    TransferAction (Enum): Control actions (Pause, Resume, Cancel).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TransferAction(str, Enum):
    """Enumeration of actions that can be performed on an active transfer.

    Attributes:
        PAUSE: Temporarily halt the transfer.
        RESUME: Continue a paused transfer.
        CANCEL: Permanently stop the transfer.
    """
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"


class BandwidthLimit(BaseModel):
    """Configuration for limiting network bandwidth usage during migration.

    Attributes:
        enabled (bool): Whether bandwidth limiting is active.
        max_mbps (float): Maximum allowed transfer speed in Megabits per second.
    """
    enabled: bool = Field(default=False, description="Enable bandwidth throttling")
    max_mbps: float = Field(default=10.0, ge=0.1, le=1000.0, description="Max transfer speed in Mbps")


class TransferCheckpoint(BaseModel):
    """Model representing a recovery point for a migration transfer.

    Used to resume interrupted transfers from the last successful batch.

    Attributes:
        checkpoint_id (str): Unique identifier for the checkpoint.
        transfer_id (str): ID of the transfer this checkpoint belongs to.
        collection (str): The collection being processed at this checkpoint.
        last_document_id (Optional[str]): ID of the last successfully transferred document.
        documents_processed (int): Total count of documents processed in this collection so far.
        created_at (datetime): Timestamp when the checkpoint was created.
    """
    checkpoint_id: str = Field(..., description="Unique checkpoint ID")
    transfer_id: str = Field(..., description="Related transfer ID")
    collection: str = Field(..., description="Collection name")
    last_document_id: Optional[str] = Field(None, description="Last processed document ID")
    documents_processed: int = Field(0, description="Count of processed documents")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Checkpoint timestamp")


class TransferControlRequest(BaseModel):
    """Request model for controlling the state of an active transfer.

    Attributes:
        action (TransferAction): The action to perform (pause/resume/cancel).
        reason (Optional[str]): Optional explanation for the action (e.g., for audit logs).
    """
    action: TransferAction = Field(..., description="Action to perform")
    reason: Optional[str] = Field(None, description="Reason for the action")


class ScheduledTransfer(BaseModel):
    """Model representing a recurring migration job.

    Attributes:
        schedule_id (str): Unique identifier for the schedule.
        owner_id (str): User ID of the schedule owner.
        from_instance_id (str): Source instance ID.
        to_instance_id (str): Target instance ID.
        cron_expression (str): Schedule frequency in Cron format.
        collections (Optional[List[str]]): Specific collections to transfer. If None, transfers all.
        enabled (bool): Whether the schedule is currently active.
        last_run (Optional[datetime]): Timestamp of the last execution.
        next_run (Optional[datetime]): Timestamp of the next scheduled execution.
        created_at (datetime): Creation timestamp.
    """
    schedule_id: str = Field(..., description="Unique schedule ID")
    owner_id: str = Field(..., description="Owner user ID")
    from_instance_id: str = Field(..., description="Source instance ID")
    to_instance_id: str = Field(..., description="Target instance ID")
    cron_expression: str = Field(..., description="Cron expression, e.g., '0 2 * * *'")
    collections: Optional[List[str]] = Field(None, description="Collections to transfer")
    enabled: bool = Field(True, description="Is schedule enabled")
    last_run: Optional[datetime] = Field(None, description="Last run timestamp")
    next_run: Optional[datetime] = Field(None, description="Next run timestamp")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
