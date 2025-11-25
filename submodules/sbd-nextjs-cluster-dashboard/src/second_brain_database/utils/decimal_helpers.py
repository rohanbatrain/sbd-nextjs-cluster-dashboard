"""
Decimal Helper Utilities for SBD Tokens.

This module provides utility functions for handling SBD token amounts with decimal precision.
All SBD token amounts use 2 decimal places (like currency) to prevent floating-point precision issues.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Union


def validate_sbd_amount(amount: Union[Decimal, float, int, str]) -> Decimal:
    """
    Validate and normalize an SBD token amount to 2 decimal places.

    Args:
        amount: The amount to validate (can be Decimal, float, int, or string)

    Returns:
        Decimal: The validated amount rounded to 2 decimal places

    Raises:
        ValueError: If the amount is negative or invalid

    Examples:
        >>> validate_sbd_amount(100)
        Decimal('100.00')
        >>> validate_sbd_amount(50.755)
        Decimal('50.76')
        >>> validate_sbd_amount("99.99")
        Decimal('99.99')
    """
    try:
        # Convert to Decimal
        if isinstance(amount, Decimal):
            decimal_amount = amount
        else:
            decimal_amount = Decimal(str(amount))

        # Check for negative values
        if decimal_amount < 0:
            raise ValueError(f"SBD token amount must be non-negative, got: {amount}")

        # Round to 2 decimal places using banker's rounding
        normalized = decimal_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return normalized

    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"Invalid SBD token amount: {amount}. Error: {str(e)}")


def format_sbd_display(amount: Union[Decimal, float, int]) -> str:
    """
    Format an SBD token amount for display.

    Args:
        amount: The amount to format

    Returns:
        str: Formatted string with thousands separators and 2 decimal places

    Examples:
        >>> format_sbd_display(Decimal('1234.50'))
        '1,234.50'
        >>> format_sbd_display(100)
        '100.00'
        >>> format_sbd_display(0.5)
        '0.50'
    """
    # Validate first
    validated = validate_sbd_amount(amount)

    # Format with thousands separator and 2 decimal places
    return f"{validated:,.2f}"


def add_sbd_amounts(*amounts: Union[Decimal, float, int]) -> Decimal:
    """
    Add multiple SBD token amounts with proper decimal handling.

    Args:
        *amounts: Variable number of amounts to add

    Returns:
        Decimal: Sum of all amounts, rounded to 2 decimal places

    Examples:
        >>> add_sbd_amounts(10.50, 20.25, 5.00)
        Decimal('35.75')
    """
    total = Decimal('0.00')
    for amount in amounts:
        total += validate_sbd_amount(amount)

    return validate_sbd_amount(total)


def subtract_sbd_amounts(minuend: Union[Decimal, float, int], subtrahend: Union[Decimal, float, int]) -> Decimal:
    """
    Subtract one SBD amount from another with proper decimal handling.

    Args:
        minuend: The amount to subtract from
        subtrahend: The amount to subtract

    Returns:
        Decimal: The difference, rounded to 2 decimal places

    Raises:
        ValueError: If the result would be negative

    Examples:
        >>> subtract_sbd_amounts(100.00, 25.50)
        Decimal('74.50')
    """
    validated_minuend = validate_sbd_amount(minuend)
    validated_subtrahend = validate_sbd_amount(subtrahend)

    result = validated_minuend - validated_subtrahend

    if result < 0:
        raise ValueError(
            f"Insufficient SBD tokens: cannot subtract {subtrahend} from {minuend}"
        )

    return validate_sbd_amount(result)


def multiply_sbd_amount(amount: Union[Decimal, float, int], multiplier: Union[Decimal, float, int]) -> Decimal:
    """
    Multiply an SBD amount by a multiplier with proper decimal handling.

    Args:
        amount: The SBD amount
        multiplier: The multiplier (can be decimal for percentages)

    Returns:
        Decimal: The product, rounded to 2 decimal places

    Examples:
        >>> multiply_sbd_amount(100, 1.5)
        Decimal('150.00')
        >>> multiply_sbd_amount(99.99, 0.1)  # 10% of 99.99
        Decimal('10.00')
    """
    validated_amount = validate_sbd_amount(amount)
    validated_multiplier = Decimal(str(multiplier))

    result = validated_amount * validated_multiplier

    return validate_sbd_amount(result)


def compare_sbd_amounts(amount1: Union[Decimal, float, int], amount2: Union[Decimal, float, int]) -> int:
    """
    Compare two SBD amounts.

    Args:
        amount1: First amount
        amount2: Second amount

    Returns:
        int: -1 if amount1 < amount2, 0 if equal, 1 if amount1 > amount2

    Examples:
        >>> compare_sbd_amounts(100.50, 100.49)
        1
        >>> compare_sbd_amounts(50.00, 50.00)
        0
        >>> compare_sbd_amounts(25.25, 30.00)
        -1
    """
    validated_amount1 = validate_sbd_amount(amount1)
    validated_amount2 = validate_sbd_amount(amount2)

    if validated_amount1 < validated_amount2:
        return -1
    elif validated_amount1 > validated_amount2:
        return 1
    else:
        return 0


def is_valid_sbd_amount(amount: Union[Decimal, float, int, str]) -> bool:
    """
    Check if a value is a valid SBD token amount.

    Args:
        amount: The value to check

    Returns:
        bool: True if valid, False otherwise

    Examples:
        >>> is_valid_sbd_amount(100.50)
        True
        >>> is_valid_sbd_amount(-10)
        False
        >>> is_valid_sbd_amount("invalid")
        False
    """
    try:
        validate_sbd_amount(amount)
        return True
    except (ValueError, InvalidOperation):
        return False
