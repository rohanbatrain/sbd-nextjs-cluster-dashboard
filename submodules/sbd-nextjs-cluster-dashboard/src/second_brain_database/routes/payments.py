"""
Payment API Routes.

REST API endpoints for Razorpay payment operations including order creation,
payment verification, webhook handling, and transaction history.
"""

from typing import Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from second_brain_database.docs.models import StandardErrorResponse
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.payment_models import (
    CreatePaymentOrderRequest,
    PaymentOrderResponse,
    TransactionHistoryResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from second_brain_database.routes.auth.dependencies import get_current_user_dep
from second_brain_database.services.razorpay_service import razorpay_service

router = APIRouter(prefix="/payments", tags=["Payments"])
logger = get_logger(prefix="[PAYMENT_ROUTES]")


@router.post(
    "/orders",
    response_model=PaymentOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create payment order",
    description="""
    Create a Razorpay payment order for purchasing SBD tokens.
    
    **Flow:**
    1. User specifies amount in INR
    2. System creates Razorpay order
    3. Returns order details for frontend checkout
    4. User completes payment on Razorpay
    5. Call /payments/verify to confirm
    
    **Limits:**
    - Minimum: ₹5
    - Maximum: ₹10,000
    
    **Example:**
    ```json
    {
        "amount_inr": 100,
        "purpose": "sbd_token_purchase"
    }
    ```
    """,
    responses={
        201: {"description": "Order created successfully"},
        400: {"description": "Invalid amount", "model": StandardErrorResponse},
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        500: {"description": "Order creation failed", "model": StandardErrorResponse},
    },
)
async def create_payment_order(
    request: CreatePaymentOrderRequest,
    current_user: Dict = Depends(get_current_user_dep),
):
    """Create a Razorpay payment order."""
    try:
        user_id = current_user["user_id"]
        
        logger.info(
            f"Creating payment order for user {user_id}: ₹{request.amount_inr}"
        )
        
        # Create order
        order_data = await razorpay_service.create_order(
            user_id=user_id,
            amount_inr=request.amount_inr,
            purpose=request.purpose,
            notes=request.notes,
        )
        
        return PaymentOrderResponse(**order_data)
        
    except ValueError as e:
        logger.warning(f"Invalid payment order request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create payment order: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment order",
        )


@router.post(
    "/verify",
    response_model=VerifyPaymentResponse,
    summary="Verify payment completion",
    description="""
    Verify payment signature and credit SBD tokens to user.
    
    **Flow:**
    1. User completes payment on Razorpay
    2. Frontend receives payment_id, order_id, signature
    3. Call this endpoint to verify
    4. System verifies signature
    5. Credits SBD tokens to user's family account
    
    **Security:**
    - HMAC SHA256 signature verification
    - Idempotent (safe to retry)
    - Prevents double-crediting
    
    **Example:**
    ```json
    {
        "order_id": "order_xxxxx",
        "payment_id": "pay_xxxxx",
        "signature": "xxxxx"
    }
    ```
    """,
    responses={
        200: {"description": "Payment verified and tokens credited"},
        400: {"description": "Invalid signature", "model": StandardErrorResponse},
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        404: {"description": "Transaction not found", "model": StandardErrorResponse},
        500: {"description": "Verification failed", "model": StandardErrorResponse},
    },
)
async def verify_payment(
    request: VerifyPaymentRequest,
    current_user: Dict = Depends(get_current_user_dep),
):
    """Verify payment and credit SBD tokens."""
    try:
        user_id = current_user["user_id"]
        
        logger.info(
            f"Verifying payment for user {user_id}: {request.payment_id}"
        )
        
        # Capture and verify payment
        result = await razorpay_service.capture_payment(
            user_id=user_id,
            order_id=request.order_id,
            payment_id=request.payment_id,
            signature=request.signature,
        )
        
        return VerifyPaymentResponse(**result)
        
    except ValueError as e:
        logger.warning(f"Payment verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Payment verification error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment verification failed",
        )


@router.post(
    "/webhooks",
    summary="Razorpay webhook handler",
    description="""
    Handle Razorpay webhook events.
    
    **Events Handled:**
    - payment.captured: Payment successfully captured
    - payment.failed: Payment failed
    - order.paid: Order marked as paid
    
    **Security:**
    - Webhook signature verification
    - Idempotent processing
    
    **Note:** This endpoint is called by Razorpay, not by frontend.
    """,
    responses={
        200: {"description": "Webhook processed successfully"},
        400: {"description": "Invalid signature", "model": StandardErrorResponse},
        500: {"description": "Webhook processing failed", "model": StandardErrorResponse},
    },
)
async def handle_webhook(
    request: Request,
    x_razorpay_signature: str = Header(..., alias="X-Razorpay-Signature"),
):
    """Handle Razorpay webhook events."""
    try:
        # Get webhook payload
        event_data = await request.json()
        
        logger.info(f"Received webhook: {event_data.get('event')}")
        
        # Process webhook
        result = await razorpay_service.handle_webhook(
            event_data=event_data,
            signature=x_razorpay_signature,
        )
        
        return JSONResponse(content=result)
        
    except ValueError as e:
        logger.warning(f"Invalid webhook signature: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        )


@router.get(
    "/history",
    response_model=TransactionHistoryResponse,
    summary="Get payment transaction history",
    description="""
    Get user's payment transaction history.
    
    **Returns:**
    - List of all payment transactions
    - Total amount spent (INR)
    - Total SBD tokens purchased
    - Transaction count
    
    **Filters:**
    - Limit: Maximum 50 transactions
    - Sorted by most recent first
    """,
    responses={
        200: {"description": "Transaction history retrieved"},
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        500: {"description": "Failed to retrieve history", "model": StandardErrorResponse},
    },
)
async def get_transaction_history(
    current_user: Dict = Depends(get_current_user_dep),
    limit: int = 50,
):
    """Get user's payment transaction history."""
    try:
        user_id = current_user["user_id"]
        
        logger.debug(f"Fetching transaction history for user {user_id}")
        
        # Get transaction history
        history = await razorpay_service.get_transaction_history(
            user_id=user_id,
            limit=limit,
        )
        
        return TransactionHistoryResponse(**history)
        
    except Exception as e:
        logger.error(f"Failed to get transaction history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transaction history",
        )


@router.get(
    "/status/{transaction_id}",
    summary="Get transaction status",
    description="""
    Get status of a specific payment transaction.
    
    **Statuses:**
    - pending: Order created, payment not completed
    - completed: Payment successful, tokens credited
    - failed: Payment failed
    - refunded: Payment refunded
    """,
    responses={
        200: {"description": "Transaction status retrieved"},
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        404: {"description": "Transaction not found", "model": StandardErrorResponse},
    },
)
async def get_transaction_status(
    transaction_id: str,
    current_user: Dict = Depends(get_current_user_dep),
):
    """Get status of a specific transaction."""
    try:
        user_id = current_user["user_id"]
        
        # Get transaction from database
        from second_brain_database.database import db_manager
        db = await db_manager.get_database()
        
        transaction = await db["payment_transactions"].find_one({
            "transaction_id": transaction_id,
            "user_id": user_id,
        })
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found",
            )
        
        # Remove MongoDB _id field
        transaction.pop("_id", None)
        
        return JSONResponse(content=transaction)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get transaction status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transaction status",
        )
