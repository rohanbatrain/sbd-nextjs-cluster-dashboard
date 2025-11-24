"""
# Scheduled Migration Service

This module enables **Automated Recurring Migrations** using cron-based scheduling.
It's ideal for backups, multi-environment syncs, and disaster recovery workflows.

## Domain Overview

Manual migrations are error-prone and time-consuming.
- **Automation**: Schedule migrations to run at specific times (e.g., daily backups at 2 AM).
- **Cron Expressions**: Industry-standard scheduling syntax (e.g., `"0 2 * * *"`).
- **Persistence**: Schedules survive server restarts by storing them in MongoDB.

## Key Features

### 1. Cron-Based Scheduling
- **Flexible**: Supports any cron expression (minute, hourly, daily, weekly, etc.).
- **APScheduler**: Built on the robust APScheduler library for async execution.

### 2. Schedule Management
- **Enable/Disable**: Pause schedules without deleting them.
- **Tracking**: Records `last_run` and `next_run` timestamps for monitoring.

### 3. Automatic Execution
- **Background Jobs**: Runs migrations in the background without blocking the API.
- **Error Handling**: Logs failures and continues with the next scheduled run.

## Usage Example

```python
# Schedule a daily backup at 2 AM UTC
schedule = await scheduled_migration_service.create_schedule(
    owner_id="user_123",
    from_instance_id="prod",
    to_instance_id="backup",
    cron_expression="0 2 * * *"
)
```
"""

from datetime import datetime, timezone
from typing import List, Optional
import secrets

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.migration_advanced_models import ScheduledTransfer

logger = get_logger(prefix="[ScheduledMigration]")


class ScheduledMigrationService:
    """
    Service for scheduling recurring database migrations using cron expressions.

    Built on APScheduler, supports automatic recurring transfers for backup,
    replication, and multi-environment synchronization workflows.

    **Features:**
    - Cron-based scheduling (e.g., daily backups at 2 AM)
    - Persistent schedule storage in MongoDB
    - Enable/disable schedules without deletion
    - Automatic execution tracking (last_run, next_run)
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.collection_name = "scheduled_migrations"

    def start(self):
        """Start the APScheduler instance."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduled migration service started")

    def stop(self):
        """Stop the APScheduler and cancel all pending jobs."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduled migration service stopped")

    async def create_schedule(
        self,
        owner_id: str,
        from_instance_id: str,
        to_instance_id: str,
        cron_expression: str,
        collections: Optional[List[str]] = None
    ) -> ScheduledTransfer:
        """
        Create a new scheduled migration job.

        Parses the cron expression, calculates the next run time, and registers
        the job with APScheduler.

        Args:
            owner_id: User ID creating the schedule.
            from_instance_id: Source instance identifier.
            to_instance_id: Target instance identifier.
            cron_expression: Standard cron string (e.g., `"0 2 * * *"` for daily at 2 AM UTC).
            collections: Optional list of collections to migrate (defaults to all).

        Returns:
            A `ScheduledTransfer` object with the created schedule details.
        """
        schedule_id = secrets.token_urlsafe(16)
        
        # Parse cron and get next run time
        trigger = CronTrigger.from_crontab(cron_expression)
        next_run = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
        
        schedule = ScheduledTransfer(
            schedule_id=schedule_id,
            owner_id=owner_id,
            from_instance_id=from_instance_id,
            to_instance_id=to_instance_id,
            cron_expression=cron_expression,
            collections=collections,
            enabled=True,
            next_run=next_run
        )
        
        # Store in database
        collection = await db_manager.get_collection(self.collection_name)
        await collection.insert_one(schedule.model_dump())
        
        # Add to scheduler
        self.scheduler.add_job(
            self._execute_scheduled_transfer,
            trigger=trigger,
            id=schedule_id,
            args=[schedule_id],
            name=f"Migration: {from_instance_id} → {to_instance_id}"
        )
        
        logger.info(f"Created scheduled migration {schedule_id}: {cron_expression}")
        return schedule

    async def _execute_scheduled_transfer(self, schedule_id: str):
        """Execute a scheduled transfer."""
        try:
            logger.info(f"Executing scheduled transfer {schedule_id}")
            
            # Get schedule from database
            collection = await db_manager.get_collection(self.collection_name)
            doc = await collection.find_one({"schedule_id": schedule_id})
            
            if not doc or not doc.get("enabled"):
                logger.warning(f"Schedule {schedule_id} not found or disabled")
                return
            
            # Import migration service (avoid circular import)
            from second_brain_database.services.migration_instance_service import MigrationInstanceService
            from second_brain_database.models.migration_instance_models import DirectTransferRequest
            
            service = MigrationInstanceService()
            
            # Initiate transfer
            request = DirectTransferRequest(
                from_instance_id=doc["from_instance_id"],
                to_instance_id=doc["to_instance_id"],
                collections=doc.get("collections"),
                include_indexes=True
            )
            
            result = await service.initiate_direct_transfer(request, doc["owner_id"])
            
            # Update last_run
            await collection.update_one(
                {"schedule_id": schedule_id},
                {"$set": {"last_run": datetime.now(timezone.utc)}}
            )
            
            logger.info(f"Scheduled transfer {schedule_id} completed: {result.transfer_id}")
            
        except Exception as e:
            logger.error(f"Scheduled transfer {schedule_id} failed: {e}", exc_info=True)

    async def list_schedules(self, owner_id: str) -> List[ScheduledTransfer]:
        """List all schedules for a user."""
        collection = await db_manager.get_collection(self.collection_name)
        cursor = collection.find({"owner_id": owner_id})
        
        schedules = []
        async for doc in cursor:
            schedules.append(ScheduledTransfer(**doc))
        
        return schedules

    async def delete_schedule(self, schedule_id: str, owner_id: str) -> bool:
        """Delete a schedule."""
        # Remove from scheduler
        self.scheduler.remove_job(schedule_id)
        
        # Remove from database
        collection = await db_manager.get_collection(self.collection_name)
        result = await collection.delete_one({
            "schedule_id": schedule_id,
            "owner_id": owner_id
        })
        
        if result.deleted_count > 0:
            logger.info(f"Deleted schedule {schedule_id}")
            return True
        return False

    async def toggle_schedule(self, schedule_id: str, owner_id: str, enabled: bool) -> bool:
        """Enable or disable a schedule."""
        collection = await db_manager.get_collection(self.collection_name)
        result = await collection.update_one(
            {"schedule_id": schedule_id, "owner_id": owner_id},
            {"$set": {"enabled": enabled}}
        )
        
        if enabled:
            # Resume job
            self.scheduler.resume_job(schedule_id)
        else:
            # Pause job
            self.scheduler.pause_job(schedule_id)
        
        return result.modified_count > 0


# Global instance
scheduled_migration_service = ScheduledMigrationService()
