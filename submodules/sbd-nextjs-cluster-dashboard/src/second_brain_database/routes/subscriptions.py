from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from second_brain_database.models.subscription_models import (
    Subscription,
    CreateSubscriptionRequest,
    SubscriptionResponse
)
from second_brain_database.services.subscription_service import SubscriptionService
# from second_brain_database.auth.dependencies import get_current_user # Assuming auth dependency exists

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

# Dependency to get SubscriptionService
async def get_subscription_service():
    return SubscriptionService()

# Mock user dependency for now, replace with actual auth
async def get_current_user_id():
    return "user_123" # Placeholder

@router.post("/", response_model=SubscriptionResponse)
async def create_subscription(
    request: CreateSubscriptionRequest,
    service: SubscriptionService = Depends(get_subscription_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Create a new subscription.
    """
    try:
        # TODO: Integrate with WalletService to deduct SBD here
        # For now, we assume payment is successful or handled separately
        
        subscription = await service.create_subscription(user_id, request)
        return SubscriptionResponse(
            subscription_id=subscription.subscription_id,
            app_id=subscription.app_id,
            plan_type=subscription.plan_type,
            status=subscription.status,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            auto_renew=subscription.auto_renew,
            message="Subscription created successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/status", response_model=List[SubscriptionResponse])
async def get_subscription_status(
    service: SubscriptionService = Depends(get_subscription_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get all subscriptions for the current user.
    """
    subscriptions = await service.get_user_subscriptions(user_id)
    return [
        SubscriptionResponse(
            subscription_id=sub.subscription_id,
            app_id=sub.app_id,
            plan_type=sub.plan_type,
            status=sub.status,
            start_date=sub.start_date,
            end_date=sub.end_date,
            auto_renew=sub.auto_renew
        ) for sub in subscriptions
    ]

@router.post("/{subscription_id}/cancel")
async def cancel_subscription(
    subscription_id: str,
    service: SubscriptionService = Depends(get_subscription_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Cancel a subscription (disable auto-renew).
    """
    success = await service.cancel_subscription(user_id, subscription_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found or already cancelled")
    
    return {"message": "Subscription cancelled successfully. It will remain active until the end date."}
