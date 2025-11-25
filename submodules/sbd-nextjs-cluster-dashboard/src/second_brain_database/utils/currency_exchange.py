"""
Currency Exchange Configuration and Utilities.

This module provides currency exchange functionality between SBD tokens and fiat currencies.
Currently supports Indian Rupees (INR) with a fixed exchange rate.

Exchange Rate:
    1 SBD = 0.000001 INR (1 millionth of a rupee)
    1 INR = 1,000,000 SBD
"""

from decimal import Decimal
from enum import Enum
from typing import Dict, Optional

from second_brain_database.utils.decimal_helpers import validate_sbd_amount


class Currency(str, Enum):
    """Supported currencies for exchange."""
    
    SBD = "SBD"  # Second Brain Database tokens
    INR = "INR"  # Indian Rupees
    USD = "USD"  # US Dollars (future)
    EUR = "EUR"  # Euros (future)


class ExchangeRateConfig:
    """
    Configuration for currency exchange rates.
    
    All rates are defined relative to 1 SBD token.
    Rates can be updated dynamically but default to fixed values.
    """
    
    # Fixed exchange rates (1 SBD = X currency)
    RATES: Dict[Currency, Decimal] = {
        Currency.INR: Decimal("0.000001"),  # 1 SBD = 0.000001 INR
        # Future rates can be added here
        # Currency.USD: Decimal("0.00001"),
        # Currency.EUR: Decimal("0.000009"),
    }
    
    # Inverse rates for convenience (1 currency = X SBD)
    INVERSE_RATES: Dict[Currency, Decimal] = {
        Currency.INR: Decimal("1000000"),  # 1 INR = 1,000,000 SBD
    }
    
    @classmethod
    def get_rate(cls, currency: Currency) -> Decimal:
        """
        Get exchange rate for a currency (1 SBD = X currency).
        
        Args:
            currency: The target currency
            
        Returns:
            Decimal: Exchange rate
            
        Raises:
            ValueError: If currency is not supported
            
        Example:
            >>> ExchangeRateConfig.get_rate(Currency.INR)
            Decimal('0.000001')
        """
        if currency == Currency.SBD:
            return Decimal("1")
        
        if currency not in cls.RATES:
            raise ValueError(f"Exchange rate not configured for {currency}")
        
        return cls.RATES[currency]
    
    @classmethod
    def get_inverse_rate(cls, currency: Currency) -> Decimal:
        """
        Get inverse exchange rate (1 currency = X SBD).
        
        Args:
            currency: The source currency
            
        Returns:
            Decimal: Inverse exchange rate
            
        Example:
            >>> ExchangeRateConfig.get_inverse_rate(Currency.INR)
            Decimal('1000000')
        """
        if currency == Currency.SBD:
            return Decimal("1")
        
        if currency not in cls.INVERSE_RATES:
            raise ValueError(f"Inverse exchange rate not configured for {currency}")
        
        return cls.INVERSE_RATES[currency]


def sbd_to_currency(sbd_amount: Decimal, target_currency: Currency) -> Decimal:
    """
    Convert SBD tokens to another currency.
    
    Args:
        sbd_amount: Amount in SBD tokens
        target_currency: Target currency to convert to
        
    Returns:
        Decimal: Equivalent amount in target currency
        
    Example:
        >>> sbd_to_currency(Decimal("1000000"), Currency.INR)
        Decimal('1.00')  # 1,000,000 SBD = 1 INR
        
        >>> sbd_to_currency(Decimal("500000"), Currency.INR)
        Decimal('0.50')  # 500,000 SBD = 0.50 INR
    """
    # Validate SBD amount
    validated_sbd = validate_sbd_amount(sbd_amount)
    
    # Get exchange rate
    rate = ExchangeRateConfig.get_rate(target_currency)
    
    # Calculate converted amount
    converted = validated_sbd * rate
    
    # Round to 2 decimal places for fiat currencies
    return converted.quantize(Decimal("0.01"))


def currency_to_sbd(currency_amount: Decimal, source_currency: Currency) -> Decimal:
    """
    Convert fiat currency to SBD tokens.
    
    Args:
        currency_amount: Amount in source currency
        source_currency: Source currency to convert from
        
    Returns:
        Decimal: Equivalent amount in SBD tokens (rounded to 2 decimal places)
        
    Example:
        >>> currency_to_sbd(Decimal("1.00"), Currency.INR)
        Decimal('1000000.00')  # 1 INR = 1,000,000 SBD
        
        >>> currency_to_sbd(Decimal("0.50"), Currency.INR)
        Decimal('500000.00')  # 0.50 INR = 500,000 SBD
    """
    if currency_amount < 0:
        raise ValueError("Currency amount must be non-negative")
    
    # Get inverse exchange rate
    rate = ExchangeRateConfig.get_inverse_rate(source_currency)
    
    # Calculate converted amount
    converted = currency_amount * rate
    
    # Validate and round to 2 decimal places for SBD
    return validate_sbd_amount(converted)


def format_currency(amount: Decimal, currency: Currency) -> str:
    """
    Format currency amount for display.
    
    Args:
        amount: Amount to format
        currency: Currency type
        
    Returns:
        str: Formatted string with currency symbol
        
    Example:
        >>> format_currency(Decimal("1234.50"), Currency.INR)
        '₹1,234.50'
        
        >>> format_currency(Decimal("1000000.00"), Currency.SBD)
        '1,000,000.00 SBD'
    """
    # Format with thousands separator and 2 decimal places
    formatted_amount = f"{amount:,.2f}"
    
    # Add currency symbol/code
    if currency == Currency.INR:
        return f"₹{formatted_amount}"
    elif currency == Currency.SBD:
        return f"{formatted_amount} SBD"
    elif currency == Currency.USD:
        return f"${formatted_amount}"
    elif currency == Currency.EUR:
        return f"€{formatted_amount}"
    else:
        return f"{formatted_amount} {currency.value}"


def get_exchange_info(sbd_amount: Decimal) -> Dict[str, str]:
    """
    Get exchange information for an SBD amount across all supported currencies.
    
    Args:
        sbd_amount: Amount in SBD tokens
        
    Returns:
        Dict mapping currency codes to formatted amounts
        
    Example:
        >>> get_exchange_info(Decimal("1000000"))
        {
            'SBD': '1,000,000.00 SBD',
            'INR': '₹1.00'
        }
    """
    validated_sbd = validate_sbd_amount(sbd_amount)
    
    exchange_info = {
        "SBD": format_currency(validated_sbd, Currency.SBD)
    }
    
    # Add all configured currencies
    for currency in ExchangeRateConfig.RATES.keys():
        converted = sbd_to_currency(validated_sbd, currency)
        exchange_info[currency.value] = format_currency(converted, currency)
    
    return exchange_info


def calculate_exchange_fee(amount: Decimal, fee_percentage: Decimal = Decimal("0.01")) -> Decimal:
    """
    Calculate exchange fee (default 1%).
    
    Args:
        amount: Amount to calculate fee on
        fee_percentage: Fee as decimal (0.01 = 1%)
        
    Returns:
        Decimal: Fee amount
        
    Example:
        >>> calculate_exchange_fee(Decimal("1000000"))
        Decimal('10000.00')  # 1% of 1,000,000
    """
    validated_amount = validate_sbd_amount(amount)
    fee = validated_amount * fee_percentage
    return validate_sbd_amount(fee)


# Convenience constants
INR_TO_SBD_RATE = ExchangeRateConfig.get_inverse_rate(Currency.INR)
SBD_TO_INR_RATE = ExchangeRateConfig.get_rate(Currency.INR)
