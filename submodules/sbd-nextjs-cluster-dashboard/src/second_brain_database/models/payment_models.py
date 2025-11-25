"""
Payment Models for Razorpay Integration.

Pydantic models for payment orders, verification, webhooks, and transaction history.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from second_brain_database.utils.decimal_helpers import validate_sbd_amount


class PaymentStatus(str, Enum):
    """Payment transaction status."""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentPurpose(str, Enum):
    """Purpose of payment."""
    SBD_TOKEN_PURCHASE = "sbd_token_purchase"
    SHOP_ITEM_PURCHASE = "shop_item_purchase"
    SUBSCRIPTION = "subscription"


class CreatePaymentOrderRequest(BaseModel):
    """
    Request to create a Razorpay payment order.
    
    Example:
        {
            "amount_inr": 100.00,
            "purpose": "sbd_token_purchase",
            "notes": {"user_id": "user_123"}
        }
    """
    
    amount_inr: Decimal = Field(..., gt=0, description="Amount in INR")
    purpose: PaymentPurpose = Field(default=PaymentPurpose.SBD_TOKEN_PURCHASE)
    notes: Optional[Dict[str, str]] = Field(default=None, description="Additional metadata")
    
    @field_validator("amount_inr")
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount is within limits."""
        if v < Decimal("5"):
            raise ValueError("Minimum payment amount is ₹5")
        if v > Decimal("10000"):
            raise ValueError("Maximum payment amount is ₹10,000")
        return v.quantize(Decimal("0.01"))


class PaymentOrderResponse(BaseModel):
    """
    Response after creating payment order.
    
    Example:
        {
            "order_id": "order_xxxxx",
            "amount": 100.00,
            "currency": "INR",
            "sbd_equivalent": 100000000.00,
            "status": "created"
        }
    """
    
    order_id: str
    amount: Decimal
    currency: str
    sbd_equivalent: Decimal
    status: str
    created_at: datetime
    receipt: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    """
    Request to verify payment completion.
    
    Example:
        {
            "order_id": "order_xxxxx",
            "payment_id": "pay_xxxxx",
            "signature": "xxxxx"
        }
    """
    
    order_id: str = Field(..., description="Razorpay order ID")
    payment_id: str = Field(..., description="Razorpay payment ID")
    signature: str = Field(..., description="Payment signature for verification")


class VerifyPaymentResponse(BaseModel):
    """
    Response after payment verification.
    
    Example:
        {
            "status": "success",
            "transaction_id": "txn_123",
            "sbd_credited": 100000000.00,
            "payment_verified": true
        }
    """
    
    status: str
    transaction_id: str
    sbd_credited: Decimal
    payment_verified: bool
    message: str


class PaymentWebhookEvent(BaseModel):
    """
    Razorpay webhook event payload.
    
    Example:
        {
            "event": "payment.captured",
            "payload": {
                "payment": {...},
                "order": {...}
            }
        }
    """
    
    event: str
    payload: Dict[str, Any]
    created_at: Optional[int] = None


class RefundRequest(BaseModel):
    """
    Request to initiate refund.
    
    Example:
        {
            "transaction_id": "txn_123",
            "reason": "Customer request",
            "amount": 100.00
        }
    """
    
    transaction_id: str
    reason: str = Field(..., min_length=10, max_length=500)
    amount: Optional[Decimal] = Field(None, description="Partial refund amount (optional)")


class RefundResponse(BaseModel):
    """
    Response after refund initiation.
    
    Example:
        {
            "refund_id": "rfnd_xxxxx",
            "status": "processing",
            "amount": 100.00
        }
    """
    
    refund_id: str
    status: str
    amount: Decimal
    created_at: datetime


class PaymentTransaction(BaseModel):
    """
    Complete payment transaction record.
    
    Example:
        {
            "transaction_id": "txn_123",
            "user_id": "user_123",
            "order_id": "order_xxxxx",
            "payment_id": "pay_xxxxx",
            "amount_inr": 100.00,
            "amount_sbd": 100000000.00,
            "status": "completed",
            "purpose": "sbd_token_purchase",
            "created_at": "2024-01-01T00:00:00Z"
        }
    """
    
    transaction_id: str
    user_id: str
    order_id: str
    payment_id: Optional[str] = None
    amount_inr: Decimal
    amount_sbd: Decimal
    status: PaymentStatus
    purpose: PaymentPurpose
    payment_method: Optional[str] = None
    razorpay_signature: Optional[str] = None
    error_message: Optional[str] = None
    notes: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None


class TransactionHistoryResponse(BaseModel):
    """
    User's payment transaction history.
    
    Example:
        {
            "transactions": [...],
            "total_spent_inr": 500.00,
            "total_sbd_purchased": 500000000.00,
            "transaction_count": 5
        }
    """
    
    transactions: List[PaymentTransaction]
    total_spent_inr: Decimal
    total_sbd_purchased: Decimal
    transaction_count: int
