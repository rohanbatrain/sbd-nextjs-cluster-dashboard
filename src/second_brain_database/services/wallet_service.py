from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import uuid

from second_brain_database.database import db_manager
from second_brain_database.models.wallet_models import (
    RecurringDebit,
    WalletNotification,
    TransactionCategory,
    WalletSettings,
    CreateRecurringDebitRequest
)
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[WalletService]")

# System transaction categories
SYSTEM_CATEGORIES = [
    {"category_id": "cat_subscription", "name": "Subscriptions", "color": "#8B5CF6", "icon": "subscription", "is_system": True},
    {"category_id": "cat_shop", "name": "Shop Purchases", "color": "#10B981", "icon": "shopping", "is_system": True},
    {"category_id": "cat_transfer", "name": "Transfers", "color": "#3B82F6", "icon": "transfer", "is_system": True},
    {"category_id": "cat_topup", "name": "Top-ups", "color": "#F59E0B", "icon": "plus", "is_system": True},
    {"category_id": "cat_refund", "name": "Refunds", "color": "#EF4444", "icon": "refund", "is_system": True},
    {"category_id": "cat_other", "name": "Other", "color": "#6B7280", "icon": "tag", "is_system": True},
]

class WalletService:
    """
    Service for managing wallet enhancements: recurring debits, notifications, analytics.
    """

    def __init__(self):
        self.recurring_debits_collection = "recurring_debits"
        self.notifications_collection = "wallet_notifications"
        self.categories_collection = "transaction_categories"
        self.wallet_settings_collection = "wallet_settings"

    # --- Recurring Debits ---

    async def create_recurring_debit(
        self, user_id: str, request: CreateRecurringDebitRequest
    ) -> RecurringDebit:
        """
        Create a new recurring debit schedule.
        """
        # Calculate next debit date based on frequency
        start_date = request.start_date or datetime.now(timezone.utc)
        next_debit_date = self._calculate_next_debit_date(start_date, request.frequency)

        recurring_debit = RecurringDebit(
            debit_id=f"rd_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            type=request.type,
            subscription_id=request.subscription_id,
            amount=request.amount,
            frequency=request.frequency,
            next_debit_date=next_debit_date,
            description=request.description,
            status="active"
        )

        collection = db_manager.get_collection(self.recurring_debits_collection)
        await collection.insert_one(recurring_debit.dict())

        logger.info(f"Created recurring debit {recurring_debit.debit_id} for user {user_id}")
        return recurring_debit

    async def get_user_recurring_debits(
        self, user_id: str, status: Optional[str] = None
    ) -> List[RecurringDebit]:
        """
        Get all recurring debits for a user.
        """
        collection = db_manager.get_collection(self.recurring_debits_collection)
        query = {"user_id": user_id}
        if status:
            query["status"] = status

        cursor = collection.find(query).sort("created_at", -1)
        debits = []
        async for doc in cursor:
            debits.append(RecurringDebit(**doc))
        return debits

    async def pause_recurring_debit(self, debit_id: str, user_id: str) -> bool:
        """
        Pause a recurring debit.
        """
        collection = db_manager.get_collection(self.recurring_debits_collection)
        result = await collection.update_one(
            {"debit_id": debit_id, "user_id": user_id},
            {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0

    async def resume_recurring_debit(self, debit_id: str, user_id: str) -> bool:
        """
        Resume a paused recurring debit.
        """
        collection = db_manager.get_collection(self.recurring_debits_collection)
        result = await collection.update_one(
            {"debit_id": debit_id, "user_id": user_id, "status": "paused"},
            {"$set": {"status": "active", "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0

    async def cancel_recurring_debit(self, debit_id: str, user_id: str) -> bool:
        """
        Cancel a recurring debit.
        """
        collection = db_manager.get_collection(self.recurring_debits_collection)
        result = await collection.update_one(
            {"debit_id": debit_id, "user_id": user_id},
            {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}}
        )
        return result.modified_count > 0

    async def process_due_recurring_debits(self) -> Dict[str, int]:
        """
        Process all recurring debits that are due.
        This should be called by a background task.
        """
        collection = db_manager.get_collection(self.recurring_debits_collection)
        now = datetime.now(timezone.utc)

        # Find all active debits that are due
        cursor = collection.find({
            "status": "active",
            "next_debit_date": {"$lte": now}
        })

        processed = 0
        failed = 0

        async for debit_doc in cursor:
            debit = RecurringDebit(**debit_doc)
            try:
                success = await self._execute_recurring_debit(debit)
                if success:
                    processed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Failed to process recurring debit {debit.debit_id}: {e}")
                failed += 1

        logger.info(f"Processed {processed} recurring debits, {failed} failed")
        return {"processed": processed, "failed": failed}

    async def _execute_recurring_debit(self, debit: RecurringDebit) -> bool:
        """
        Execute a single recurring debit.
        """
        users_collection = db_manager.get_collection("users")
        collection = db_manager.get_collection(self.recurring_debits_collection)

        # Check user balance
        user = await users_collection.find_one(
            {"_id": debit.user_id},
            {"sbd_tokens": 1}
        )

        if not user or user.get("sbd_tokens", 0) < debit.amount:
            # Insufficient balance - increment retry count
            new_retry_count = debit.retry_count + 1
            
            if new_retry_count >= debit.max_retries:
                # Max retries reached - mark as failed
                await collection.update_one(
                    {"debit_id": debit.debit_id},
                    {"$set": {
                        "status": "failed",
                        "retry_count": new_retry_count,
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
                
                # Send notification
                await self.create_notification(
                    user_id=debit.user_id,
                    type="recurring_payment",
                    title="Recurring Payment Failed",
                    message=f"Your recurring payment of {debit.amount:,} SBD failed due to insufficient balance.",
                    amount=debit.amount
                )
                
                # If it's a subscription, cancel it
                if debit.type == "subscription" and debit.subscription_id:
                    from second_brain_database.services.subscription_service import SubscriptionService
                    sub_service = SubscriptionService()
                    await sub_service.cancel_subscription(debit.user_id, debit.subscription_id)
                
                return False
            else:
                # Retry later
                next_retry = datetime.now(timezone.utc) + timedelta(days=1)
                await collection.update_one(
                    {"debit_id": debit.debit_id},
                    {"$set": {
                        "retry_count": new_retry_count,
                        "next_debit_date": next_retry,
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
                return False

        # Deduct tokens
        transaction_id = f"txn_{uuid.uuid4().hex}"
        now_iso = datetime.now(timezone.utc).isoformat()

        send_txn = {
            "type": "send",
            "to": "recurring_debit_system",
            "amount": debit.amount,
            "timestamp": now_iso,
            "transaction_id": transaction_id,
            "note": debit.description or f"Recurring {debit.frequency} payment",
            "category": "cat_subscription" if debit.type == "subscription" else "cat_other",
            "recurring_debit_id": debit.debit_id
        }

        result = await users_collection.update_one(
            {"_id": debit.user_id, "sbd_tokens": {"$gte": debit.amount}},
            {
                "$inc": {"sbd_tokens": -debit.amount},
                "$push": {"sbd_tokens_transactions": send_txn}
            }
        )

        if result.modified_count == 0:
            return False

        # Update recurring debit - calculate next debit date and reset retry count
        next_debit_date = self._calculate_next_debit_date(datetime.now(timezone.utc), debit.frequency)
        await collection.update_one(
            {"debit_id": debit.debit_id},
            {"$set": {
                "last_debit_date": datetime.now(timezone.utc),
                "next_debit_date": next_debit_date,
                "retry_count": 0,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        # If it's a subscription, renew it
        if debit.type == "subscription" and debit.subscription_id:
            from second_brain_database.services.subscription_service import SubscriptionService
            sub_service = SubscriptionService()
            await sub_service.renew_subscription(debit.subscription_id)

        # Send success notification
        await self.create_notification(
            user_id=debit.user_id,
            type="recurring_payment",
            title="Recurring Payment Successful",
            message=f"Your recurring payment of {debit.amount:,} SBD was processed successfully.",
            amount=debit.amount,
            transaction_id=transaction_id
        )

        return True

    def _calculate_next_debit_date(self, current_date: datetime, frequency: str) -> datetime:
        """
        Calculate the next debit date based on frequency.
        """
        if frequency == "daily":
            return current_date + timedelta(days=1)
        elif frequency == "weekly":
            return current_date + timedelta(weeks=1)
        elif frequency == "monthly":
            return current_date + timedelta(days=30)
        elif frequency == "yearly":
            return current_date + timedelta(days=365)
        else:
            raise ValueError(f"Invalid frequency: {frequency}")

    # --- Notifications ---

    async def create_notification(
        self,
        user_id: str,
        type: str,
        title: str,
        message: str,
        amount: Optional[int] = None,
        transaction_id: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> WalletNotification:
        """
        Create a wallet notification.
        """
        notification = WalletNotification(
            notification_id=f"notif_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            amount=amount,
            transaction_id=transaction_id,
            metadata=metadata or {}
        )

        collection = db_manager.get_collection(self.notifications_collection)
        await collection.insert_one(notification.dict())

        logger.info(f"Created notification {notification.notification_id} for user {user_id}")
        return notification

    async def get_user_notifications(
        self, user_id: str, unread_only: bool = False, limit: int = 50
    ) -> List[WalletNotification]:
        """
        Get notifications for a user.
        """
        collection = db_manager.get_collection(self.notifications_collection)
        query = {"user_id": user_id}
        if unread_only:
            query["read"] = False

        cursor = collection.find(query).sort("created_at", -1).limit(limit)
        notifications = []
        async for doc in cursor:
            notifications.append(WalletNotification(**doc))
        return notifications

    async def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        """
        Mark a notification as read.
        """
        collection = db_manager.get_collection(self.notifications_collection)
        result = await collection.update_one(
            {"notification_id": notification_id, "user_id": user_id},
            {"$set": {"read": True}}
        )
        return result.modified_count > 0

    async def mark_all_notifications_read(self, user_id: str) -> int:
        """
        Mark all notifications as read for a user.
        """
        collection = db_manager.get_collection(self.notifications_collection)
        result = await collection.update_many(
            {"user_id": user_id, "read": False},
            {"$set": {"read": True}}
        )
        return result.modified_count

    # --- Wallet Settings ---

    async def get_wallet_settings(self, user_id: str) -> WalletSettings:
        """
        Get wallet settings for a user (creates default if not exists).
        """
        collection = db_manager.get_collection(self.wallet_settings_collection)
        settings_doc = await collection.find_one({"user_id": user_id})

        if not settings_doc:
            # Create default settings
            settings = WalletSettings(user_id=user_id)
            await collection.insert_one(settings.dict())
            return settings

        return WalletSettings(**settings_doc)

    async def update_wallet_settings(
        self, user_id: str, settings_update: Dict[str, Any]
    ) -> WalletSettings:
        """
        Update wallet settings for a user.
        """
        collection = db_manager.get_collection(self.wallet_settings_collection)
        
        settings_update["updated_at"] = datetime.now(timezone.utc)
        
        await collection.update_one(
            {"user_id": user_id},
            {"$set": settings_update},
            upsert=True
        )

        return await self.get_wallet_settings(user_id)

    # --- Transaction Categorization ---

    async def initialize_system_categories(self):
        """
        Initialize system transaction categories.
        """
        collection = db_manager.get_collection(self.categories_collection)
        
        for category in SYSTEM_CATEGORIES:
            await collection.update_one(
                {"category_id": category["category_id"]},
                {"$setOnInsert": {**category, "created_at": datetime.now(timezone.utc)}},
                upsert=True
            )

        logger.info("Initialized system transaction categories")

    async def get_transaction_categories(self, user_id: str) -> List[TransactionCategory]:
        """
        Get all categories (system + user custom categories).
        """
        collection = db_manager.get_collection(self.categories_collection)
        
        # Get system categories and user's custom categories
        cursor = collection.find({
            "$or": [
                {"is_system": True},
                {"user_id": user_id}
            ]
        })

        categories = []
        async for doc in cursor:
            categories.append(TransactionCategory(**doc))
        return categories
