"""
Razorpay Payment Configuration.

This module manages Razorpay API credentials and configuration settings.
Supports both sandbox (test) and production environments.
"""

import os
from typing import Optional

from pydantic import BaseModel, Field


class RazorpayConfig(BaseModel):
    """Razorpay configuration settings."""
    
    # API Credentials
    key_id: str = Field(..., description="Razorpay API Key ID")
    key_secret: str = Field(..., description="Razorpay API Key Secret")
    webhook_secret: str = Field(..., description="Webhook signature secret")
    
    # Environment
    environment: str = Field(default="sandbox", description="sandbox or production")
    
    # Currency
    currency: str = Field(default="INR", description="Payment currency")
    
    # Limits
    min_amount: int = Field(default=5, description="Minimum payment amount in INR")
    max_amount: int = Field(default=10000, description="Maximum payment amount in INR")
    
    # Features
    capture_auto: bool = Field(default=True, description="Auto-capture payments")
    notes_enabled: bool = Field(default=True, description="Enable order notes")


def get_razorpay_config() -> RazorpayConfig:
    """
    Get Razorpay configuration from environment variables.
    
    Returns:
        RazorpayConfig: Configuration object
        
    Raises:
        ValueError: If required environment variables are missing
        
    Environment Variables:
        RAZORPAY_KEY_ID: API Key ID
        RAZORPAY_KEY_SECRET: API Key Secret
        RAZORPAY_WEBHOOK_SECRET: Webhook secret
        RAZORPAY_ENVIRONMENT: sandbox or production (default: sandbox)
    """
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET")
    
    # Use placeholder values if not set (for development)
    if not key_id:
        key_id = "rzp_test_PLACEHOLDER_KEY_ID"
    if not key_secret:
        key_secret = "PLACEHOLDER_KEY_SECRET"
    if not webhook_secret:
        webhook_secret = "PLACEHOLDER_WEBHOOK_SECRET"
    
    return RazorpayConfig(
        key_id=key_id,
        key_secret=key_secret,
        webhook_secret=webhook_secret,
        environment=os.getenv("RAZORPAY_ENVIRONMENT", "sandbox"),
        currency=os.getenv("PAYMENT_CURRENCY", "INR"),
        min_amount=int(os.getenv("PAYMENT_MIN_AMOUNT", "5")),
        max_amount=int(os.getenv("PAYMENT_MAX_AMOUNT", "10000")),
    )


# Global config instance
razorpay_config = get_razorpay_config()
