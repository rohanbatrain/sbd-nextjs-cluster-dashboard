from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class Subscription(BaseModel):
    """
    Represents a user's subscription to an app service.
    """
    subscription_id: str = Field(..., description="Unique identifier for the subscription")
    user_id: str = Field(..., description="ID of the user who owns the subscription")
    app_id: str = Field(..., description="ID of the app this subscription is for (e.g., 'emotion_tracker')")
    plan_type: str = Field(..., description="Type of plan: 'monthly' or 'yearly'")
    status: str = Field(..., description="Current status: 'active', 'expired', 'cancelled'")
    start_date: datetime = Field(..., description="When the subscription started")
    end_date: datetime = Field(..., description="When the subscription expires or renews")
    auto_renew: bool = Field(True, description="Whether the subscription auto-renews")
    payment_method: str = Field(..., description="Payment method used: 'sbd' or 'razorpay'")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CreateSubscriptionRequest(BaseModel):
    """
    Request model for creating a new subscription.
    """
    app_id: str = Field(..., description="ID of the app to subscribe to")
    plan_type: str = Field(..., description="Plan type: 'monthly' or 'yearly'")
    payment_method: str = Field(..., description="Payment method: 'sbd' (currently only supported)")

class SubscriptionResponse(BaseModel):
    """
    Response model for subscription operations.
    """
    subscription_id: str
    app_id: str
    plan_type: str
    status: str
    start_date: datetime
    end_date: datetime
    auto_renew: bool
    message: Optional[str] = None
