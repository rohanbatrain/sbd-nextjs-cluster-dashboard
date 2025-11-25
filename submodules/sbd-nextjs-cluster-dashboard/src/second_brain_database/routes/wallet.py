from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from second_brain_database.models.wallet_models import (
    CreateRecurringDebitRequest,
    RecurringDebitResponse,
    WalletNotification,
    WalletSettings,
    TransactionCategory
)
from second_brain_database.services.wallet_service import WalletService
from second_brain_database.routes.auth import enforce_all_lockdowns

router = APIRouter(prefix="/wallet", tags=["Wallet"])

# Dependency to get WalletService
async def get_wallet_service():
    return WalletService()

# Mock user dependency - replace with actual auth
async def get_current_user_id(current_user: dict = Depends(enforce_all_lockdowns)):
    return str(current_user["_id"])

# --- Recurring Debits ---

@router.post("/recurring-debits", response_model=RecurringDebitResponse)
async def create_recurring_debit(
    request: CreateRecurringDebitRequest,
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Create a new recurring debit schedule.
    """
    try:
        debit = await service.create_recurring_debit(user_id, request)
        return RecurringDebitResponse(
            debit_id=debit.debit_id,
            type=debit.type,
            amount=debit.amount,
            frequency=debit.frequency,
            next_debit_date=debit.next_debit_date,
            status=debit.status,
            description=debit.description
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recurring-debits")
async def get_recurring_debits(
    status: Optional[str] = Query(None, description="Filter by status"),
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get all recurring debits for the current user.
    """
    debits = await service.get_user_recurring_debits(user_id, status)
    return {
        "debits": [
            RecurringDebitResponse(
                debit_id=d.debit_id,
                type=d.type,
                amount=d.amount,
                frequency=d.frequency,
                next_debit_date=d.next_debit_date,
                status=d.status,
                description=d.description
            ) for d in debits
        ]
    }

@router.post("/recurring-debits/{debit_id}/pause")
async def pause_recurring_debit(
    debit_id: str,
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Pause a recurring debit.
    """
    success = await service.pause_recurring_debit(debit_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recurring debit not found or already paused")
    return {"message": "Recurring debit paused successfully"}

@router.post("/recurring-debits/{debit_id}/resume")
async def resume_recurring_debit(
    debit_id: str,
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Resume a paused recurring debit.
    """
    success = await service.resume_recurring_debit(debit_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recurring debit not found or not paused")
    return {"message": "Recurring debit resumed successfully"}

@router.delete("/recurring-debits/{debit_id}")
async def cancel_recurring_debit(
    debit_id: str,
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Cancel a recurring debit.
    """
    success = await service.cancel_recurring_debit(debit_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recurring debit not found")
    return {"message": "Recurring debit cancelled successfully"}

# --- Notifications ---

@router.get("/notifications", response_model=List[WalletNotification])
async def get_notifications(
    unread_only: bool = Query(False, description="Get only unread notifications"),
    limit: int = Query(50, description="Maximum number of notifications to return"),
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get wallet notifications for the current user.
    """
    notifications = await service.get_user_notifications(user_id, unread_only, limit)
    return notifications

@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Mark a notification as read.
    """
    success = await service.mark_notification_read(notification_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification marked as read"}

@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Mark all notifications as read.
    """
    count = await service.mark_all_notifications_read(user_id)
    return {"message": f"Marked {count} notifications as read"}

# --- Wallet Settings ---

@router.get("/settings", response_model=WalletSettings)
async def get_wallet_settings(
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get wallet settings for the current user.
    """
    settings = await service.get_wallet_settings(user_id)
    return settings

@router.patch("/settings")
async def update_wallet_settings(
    settings_update: dict,
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Update wallet settings.
    """
    settings = await service.update_wallet_settings(user_id, settings_update)
    return settings

# --- Transaction Categories ---

@router.get("/categories", response_model=List[TransactionCategory])
async def get_transaction_categories(
    service: WalletService = Depends(get_wallet_service),
    user_id: str = Depends(get_current_user_id)
):
    """
    Get all transaction categories (system + custom).
    """
    categories = await service.get_transaction_categories(user_id)
    return categories
