from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class RecurringDebit(BaseModel):
    """
    Model for recurring debit/payment schedules.
    """
    debit_id: str = Field(..., description="Unique identifier for the recurring debit")
    user_id: str = Field(..., description="User ID who owns this recurring debit")
    type: str = Field(..., description="Type: 'subscription' or 'custom'")
    subscription_id: Optional[str] = Field(None, description="Subscription ID if type is 'subscription'")
    amount: int = Field(..., description="Amount to debit in SBD tokens")
    frequency: str = Field(..., description="Frequency: 'daily', 'weekly', 'monthly', 'yearly'")
    next_debit_date: datetime = Field(..., description="Next scheduled debit date")
    last_debit_date: Optional[datetime] = Field(None, description="Last successful debit date")
    status: str = Field("active", description="Status: 'active', 'paused', 'cancelled', 'failed'")
    retry_count: int = Field(0, description="Number of retry attempts for failed payments")
    max_retries: int = Field(3, description="Maximum retry attempts")
    grace_period_days: int = Field(3, description="Grace period in days after failure")
    description: Optional[str] = Field(None, description="Description of the recurring debit")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class WalletNotification(BaseModel):
    """
    Model for wallet-related notifications.
    """
    notification_id: str = Field(..., description="Unique notification ID")
    user_id: str = Field(..., description="User ID")
    type: str = Field(..., description="Type: 'top_up', 'debit', 'low_balance', 'recurring_payment', 'budget_alert'")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    amount: Optional[int] = Field(None, description="Transaction amount if applicable")
    transaction_id: Optional[str] = Field(None, description="Related transaction ID")
    read: bool = Field(False, description="Whether notification has been read")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TransactionCategory(BaseModel):
    """
    Model for transaction categories.
    """
    category_id: str = Field(..., description="Unique category ID")
    user_id: Optional[str] = Field(None, description="User ID if custom category, None for system categories")
    name: str = Field(..., description="Category name")
    color: str = Field("#6B7280", description="Category color (hex)")
    icon: str = Field("tag", description="Category icon identifier")
    is_system: bool = Field(False, description="Whether this is a system category")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WalletSettings(BaseModel):
    """
    Model for user wallet settings and preferences.
    """
    user_id: str = Field(..., description="User ID")
    notifications: Dict[str, Any] = Field(
        default_factory=lambda: {
            "top_up_enabled": True,
            "recurring_payment_enabled": True,
            "low_balance_enabled": True,
            "low_balance_threshold": 10000000,  # 10 SBD
            "notification_channels": ["in_app"]
        }
    )
    budgets: Dict[str, Any] = Field(
        default_factory=lambda: {
            "monthly_limit": None,
            "category_limits": {}
        }
    )
    security: Dict[str, Any] = Field(
        default_factory=lambda: {
            "require_2fa_above": 100000000,  # 100 SBD
            "velocity_limit": {
                "max_transactions_per_hour": 10,
                "max_amount_per_hour": 1000000000
            }
        }
    )
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CreateRecurringDebitRequest(BaseModel):
    """
    Request model for creating a recurring debit.
    """
    type: str = Field(..., description="Type: 'subscription' or 'custom'")
    subscription_id: Optional[str] = Field(None, description="Subscription ID if type is 'subscription'")
    amount: int = Field(..., description="Amount to debit")
    frequency: str = Field(..., description="Frequency: 'daily', 'weekly', 'monthly', 'yearly'")
    description: Optional[str] = Field(None, description="Description")
    start_date: Optional[datetime] = Field(None, description="Start date (defaults to now)")

class RecurringDebitResponse(BaseModel):
    """
    Response model for recurring debit operations.
    """
    debit_id: str
    type: str
    amount: int
    frequency: str
    next_debit_date: datetime
    status: str
    description: Optional[str] = None

class WalletAnalytics(BaseModel):
    """
    Model for wallet spending analytics.
    """
    user_id: str
    period: str  # "week", "month", "year"
    total_spent: int
    total_received: int
    net_change: int
    category_breakdown: Dict[str, int]
    top_categories: List[Dict[str, Any]]
    transaction_count: int
    average_transaction: int
    budget_status: Optional[Dict[str, Any]] = None
