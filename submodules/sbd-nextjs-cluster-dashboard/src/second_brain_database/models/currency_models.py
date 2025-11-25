"""
Currency Exchange Models.

Pydantic models for currency exchange requests and responses.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator

from second_brain_database.utils.currency_exchange import Currency
from second_brain_database.utils.decimal_helpers import validate_sbd_amount


class ExchangeRateResponse(BaseModel):
    """
    Response model for exchange rate information.
    
    Example:
        {
            "from_currency": "SBD",
            "to_currency": "INR",
            "rate": 0.000001,
            "inverse_rate": 1000000,
            "last_updated": "2024-01-01T00:00:00Z"
        }
    """
    
    from_currency: str
    to_currency: str
    rate: Decimal = Field(..., description="Exchange rate (1 from_currency = X to_currency)")
    inverse_rate: Decimal = Field(..., description="Inverse rate (1 to_currency = X from_currency)")
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class CurrencyConversionRequest(BaseModel):
    """
    Request model for currency conversion.
    
    Example:
        {
            "amount": 1000000.00,
            "from_currency": "SBD",
            "to_currency": "INR"
        }
    """
    
    amount: Decimal = Field(..., gt=0, description="Amount to convert")
    from_currency: Currency = Field(..., description="Source currency")
    to_currency: Currency = Field(..., description="Target currency")
    
    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount is positive and properly formatted."""
        return validate_sbd_amount(v)


class CurrencyConversionResponse(BaseModel):
    """
    Response model for currency conversion.
    
    Example:
        {
            "original_amount": 1000000.00,
            "original_currency": "SBD",
            "converted_amount": 1.00,
            "converted_currency": "INR",
            "exchange_rate": 0.000001,
            "formatted_original": "1,000,000.00 SBD",
            "formatted_converted": "₹1.00"
        }
    """
    
    original_amount: Decimal
    original_currency: str
    converted_amount: Decimal
    converted_currency: str
    exchange_rate: Decimal
    formatted_original: str
    formatted_converted: str


class ExchangeTransactionRequest(BaseModel):
    """
    Request model for executing a currency exchange transaction.
    
    This would be used for actual exchange operations (buying/selling SBD with INR).
    
    Example:
        {
            "family_id": "family_123",
            "amount": 1000000.00,
            "from_currency": "SBD",
            "to_currency": "INR",
            "payment_method": "upi"
        }
    """
    
    family_id: str = Field(..., description="Family ID for the transaction")
    amount: Decimal = Field(..., gt=0, description="Amount to exchange")
    from_currency: Currency = Field(..., description="Currency to exchange from")
    to_currency: Currency = Field(..., description="Currency to exchange to")
    payment_method: Optional[str] = Field(None, description="Payment method (for INR transactions)")
    notes: Optional[str] = Field(None, max_length=500, description="Optional transaction notes")
    
    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount is positive and properly formatted."""
        return validate_sbd_amount(v)


class ExchangeTransactionResponse(BaseModel):
    """
    Response model for exchange transaction.
    
    Example:
        {
            "transaction_id": "exch_123456",
            "family_id": "family_123",
            "from_amount": 1000000.00,
            "from_currency": "SBD",
            "to_amount": 1.00,
            "to_currency": "INR",
            "exchange_rate": 0.000001,
            "fee_amount": 10000.00,
            "fee_currency": "SBD",
            "status": "completed",
            "created_at": "2024-01-01T00:00:00Z"
        }
    """
    
    transaction_id: str
    family_id: str
    from_amount: Decimal
    from_currency: str
    to_amount: Decimal
    to_currency: str
    exchange_rate: Decimal
    fee_amount: Decimal
    fee_currency: str
    status: str = Field(..., description="Transaction status: pending, completed, failed")
    payment_method: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class MultiCurrencyBalanceResponse(BaseModel):
    """
    Response model showing balance in multiple currencies.
    
    Example:
        {
            "sbd_balance": 1000000.00,
            "equivalents": {
                "INR": "₹1.00",
                "USD": "$0.01"
            }
        }
    """
    
    sbd_balance: Decimal
    equivalents: Dict[str, str] = Field(..., description="Balance in other currencies (formatted)")
