from datetime import datetime, timedelta
from typing import Optional, List
import uuid

from second_brain_database.models.subscription_models import Subscription, CreateSubscriptionRequest
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[SubscriptionService]")

class SubscriptionService:
    """
    Service for managing app subscriptions with wallet integration.
    """

    def __init__(self):
        self.collection_name = "subscriptions"

    async def create_subscription(self, user_id: str, request: CreateSubscriptionRequest) -> Subscription:
        """
        Creates a new subscription for a user and sets up recurring payment.
        """
        # 1. Check for existing active subscription
        existing = await self.check_active_subscription(user_id, request.app_id)
        if existing:
            raise ValueError(f"User already has an active subscription for {request.app_id}")

        # 2. Calculate dates
        start_date = datetime.utcnow()
        if request.plan_type == "monthly":
            end_date = start_date + timedelta(days=30)
        elif request.plan_type == "yearly":
            end_date = start_date + timedelta(days=365)
        else:
            raise ValueError("Invalid plan type")

        # 3. Create subscription object
        subscription = Subscription(
            subscription_id=f"sub_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            app_id=request.app_id,
            plan_type=request.plan_type,
            status="active",
            start_date=start_date,
            end_date=end_date,
            auto_renew=True, # Default to auto-renew
            payment_method=request.payment_method
        )

        # 4. Save to database
        subscriptions_collection = db_manager.get_collection(self.collection_name)
        await subscriptions_collection.insert_one(subscription.dict())

        # 5. Set up recurring payment if payment method is SBD
        if request.payment_method == "sbd":
            await self._setup_recurring_payment(subscription)

        logger.info(f"Created subscription {subscription.subscription_id} for user {user_id}")
        return subscription

    async def _setup_recurring_payment(self, subscription: Subscription):
        """
        Set up recurring payment for a subscription.
        """
        from second_brain_database.services.wallet_service import WalletService
        from second_brain_database.models.wallet_models import CreateRecurringDebitRequest

        wallet_service = WalletService()

        # Determine amount based on plan type
        # These prices match the subscription pricing (₹49/month, ₹499/year with 5% SBD discount)
        if subscription.plan_type == "monthly":
            amount = 47500000  # 47.5M SBD
            frequency = "monthly"
        elif subscription.plan_type == "yearly":
            amount = 475000000  # 475M SBD
            frequency = "yearly"
        else:
            raise ValueError(f"Invalid plan type: {subscription.plan_type}")

        # Create recurring debit
        recurring_debit_request = CreateRecurringDebitRequest(
            type="subscription",
            subscription_id=subscription.subscription_id,
            amount=amount,
            frequency=frequency,
            description=f"{subscription.app_id} {subscription.plan_type} subscription",
            start_date=subscription.end_date  # First renewal at end_date
        )

        await wallet_service.create_recurring_debit(subscription.user_id, recurring_debit_request)
        logger.info(f"Set up recurring payment for subscription {subscription.subscription_id}")

    async def check_active_subscription(self, user_id: str, app_id: str) -> Optional[Subscription]:
        """
        Checks if a user has an active subscription for a specific app.
        Returns the subscription if active, None otherwise.
        """
        query = {
            "user_id": user_id,
            "app_id": app_id,
            "status": "active",
            "end_date": {"$gt": datetime.utcnow()}
        }
        subscriptions_collection = db_manager.get_collection(self.collection_name)
        doc = await subscriptions_collection.find_one(query)
        if doc:
            return Subscription(**doc)
        return None

    async def cancel_subscription(self, user_id: str, subscription_id: str) -> bool:
        """
        Cancels a subscription (turns off auto-renew and cancels recurring payment). 
        The subscription remains active until the end_date.
        """
        query = {
            "subscription_id": subscription_id,
            "user_id": user_id
        }
        update = {
            "$set": {
                "auto_renew": False,
                "updated_at": datetime.utcnow()
            }
        }
        subscriptions_collection = db_manager.get_collection(self.collection_name)
        result = await subscriptions_collection.update_one(query, update)

        if result.modified_count > 0:
            # Cancel associated recurring debit
            await self._cancel_recurring_payment(subscription_id)
            logger.info(f"Cancelled subscription {subscription_id}")

        return result.modified_count > 0

    async def _cancel_recurring_payment(self, subscription_id: str):
        """
        Cancel the recurring payment associated with a subscription.
        """
        from second_brain_database.services.wallet_service import WalletService

        wallet_service = WalletService()
        recurring_debits_collection = db_manager.get_collection("recurring_debits")

        # Find recurring debit for this subscription
        debit = await recurring_debits_collection.find_one({"subscription_id": subscription_id})
        if debit:
            # Cancel it (we need user_id but we can get it from the debit)
            await wallet_service.cancel_recurring_debit(debit["debit_id"], debit["user_id"])
            logger.info(f"Cancelled recurring payment for subscription {subscription_id}")

    async def get_user_subscriptions(self, user_id: str) -> List[Subscription]:
        """
        Gets all subscriptions for a user.
        """
        query = {"user_id": user_id}
        subscriptions_collection = db_manager.get_collection(self.collection_name)
        cursor = subscriptions_collection.find(query)
        docs = await cursor.to_list(length=None)
        return [Subscription(**doc) for doc in docs]

    async def renew_subscription(self, subscription_id: str) -> bool:
        """
        Renew a subscription (called after successful recurring payment).
        """
        subscriptions_collection = db_manager.get_collection(self.collection_name)
        subscription_doc = await subscriptions_collection.find_one({"subscription_id": subscription_id})

        if not subscription_doc:
            return False

        subscription = Subscription(**subscription_doc)

        # Calculate new end date
        if subscription.plan_type == "monthly":
            new_end_date = subscription.end_date + timedelta(days=30)
        elif subscription.plan_type == "yearly":
            new_end_date = subscription.end_date + timedelta(days=365)
        else:
            return False

        # Update subscription
        result = await subscriptions_collection.update_one(
            {"subscription_id": subscription_id},
            {"$set": {
                "end_date": new_end_date,
                "updated_at": datetime.utcnow()
            }}
        )

        if result.modified_count > 0:
            logger.info(f"Renewed subscription {subscription_id} until {new_end_date}")

        return result.modified_count > 0
