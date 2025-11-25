"""
Currency Exchange API Routes.

This module provides REST API endpoints for currency exchange operations,
including rate queries, conversions, and balance displays in multiple currencies.
"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from second_brain_database.docs.models import StandardErrorResponse
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.currency_models import (
    CurrencyConversionRequest,
    CurrencyConversionResponse,
    ExchangeRateResponse,
    MultiCurrencyBalanceResponse,
)
from second_brain_database.routes.auth.dependencies import get_current_user_dep
from second_brain_database.utils.currency_exchange import (
    Currency,
    ExchangeRateConfig,
    currency_to_sbd,
    format_currency,
    get_exchange_info,
    sbd_to_currency,
)

router = APIRouter(prefix="/currency", tags=["Currency Exchange"])
logger = get_logger(prefix="[CURRENCY_EXCHANGE]")


@router.get(
    "/rates/{currency}",
    response_model=ExchangeRateResponse,
    summary="Get exchange rate for a currency",
    description="""
    Get the current exchange rate between SBD tokens and a specified currency.
    
    **Supported Currencies:**
    - INR (Indian Rupees)
    
    **Exchange Rate:**
    - 1 SBD = 0.000001 INR
    - 1 INR = 1,000,000 SBD
    
    **Example:**
    ```
    GET /currency/rates/INR
    ```
    """,
    responses={
        200: {"description": "Exchange rate retrieved successfully"},
        400: {"description": "Invalid currency", "model": StandardErrorResponse},
        404: {"description": "Currency not supported", "model": StandardErrorResponse},
    },
)
async def get_exchange_rate(currency: str):
    """Get exchange rate for a specific currency."""
    try:
        # Validate currency
        try:
            target_currency = Currency(currency.upper())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid currency: {currency}. Supported: {[c.value for c in Currency]}",
            )
        
        if target_currency == Currency.SBD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot get exchange rate for SBD to SBD",
            )
        
        # Get rates
        rate = ExchangeRateConfig.get_rate(target_currency)
        inverse_rate = ExchangeRateConfig.get_inverse_rate(target_currency)
        
        logger.info(f"Retrieved exchange rate for {currency}: 1 SBD = {rate} {currency}")
        
        return ExchangeRateResponse(
            from_currency="SBD",
            to_currency=currency.upper(),
            rate=rate,
            inverse_rate=inverse_rate,
            last_updated=datetime.utcnow(),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get exchange rate: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve exchange rate",
        )


@router.post(
    "/convert",
    response_model=CurrencyConversionResponse,
    summary="Convert between currencies",
    description="""
    Convert an amount from one currency to another.
    
    **Supported Conversions:**
    - SBD ↔ INR
    
    **Example Request:**
    ```json
    {
        "amount": 1000000.00,
        "from_currency": "SBD",
        "to_currency": "INR"
    }
    ```
    
    **Example Response:**
    ```json
    {
        "original_amount": 1000000.00,
        "original_currency": "SBD",
        "converted_amount": 1.00,
        "converted_currency": "INR",
        "exchange_rate": 0.000001,
        "formatted_original": "1,000,000.00 SBD",
        "formatted_converted": "₹1.00"
    }
    ```
    """,
    responses={
        200: {"description": "Conversion successful"},
        400: {"description": "Invalid request", "model": StandardErrorResponse},
    },
)
async def convert_currency(request: CurrencyConversionRequest):
    """Convert amount between currencies."""
    try:
        # Validate same currency conversion
        if request.from_currency == request.to_currency:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot convert currency to itself",
            )
        
        # Perform conversion
        if request.from_currency == Currency.SBD:
            converted_amount = sbd_to_currency(request.amount, request.to_currency)
            exchange_rate = ExchangeRateConfig.get_rate(request.to_currency)
        else:
            converted_amount = currency_to_sbd(request.amount, request.from_currency)
            exchange_rate = ExchangeRateConfig.get_inverse_rate(request.from_currency)
        
        # Format amounts
        formatted_original = format_currency(request.amount, request.from_currency)
        formatted_converted = format_currency(converted_amount, request.to_currency)
        
        logger.info(
            f"Converted {formatted_original} to {formatted_converted} "
            f"(rate: {exchange_rate})"
        )
        
        return CurrencyConversionResponse(
            original_amount=request.amount,
            original_currency=request.from_currency.value,
            converted_amount=converted_amount,
            converted_currency=request.to_currency.value,
            exchange_rate=exchange_rate,
            formatted_original=formatted_original,
            formatted_converted=formatted_converted,
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Currency conversion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Currency conversion failed",
        )


@router.get(
    "/balance/{sbd_amount}",
    response_model=MultiCurrencyBalanceResponse,
    summary="Get balance in multiple currencies",
    description="""
    Get an SBD balance displayed in multiple supported currencies.
    
    **Example:**
    ```
    GET /currency/balance/1000000.00
    ```
    
    **Response:**
    ```json
    {
        "sbd_balance": 1000000.00,
        "equivalents": {
            "INR": "₹1.00"
        }
    }
    ```
    """,
    responses={
        200: {"description": "Balance retrieved successfully"},
        400: {"description": "Invalid amount", "model": StandardErrorResponse},
    },
)
async def get_multi_currency_balance(sbd_amount: Decimal):
    """Get SBD balance in multiple currencies."""
    try:
        if sbd_amount < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be non-negative",
            )
        
        # Get exchange info for all currencies
        equivalents = get_exchange_info(sbd_amount)
        
        # Remove SBD from equivalents (it's already in sbd_balance)
        equivalents.pop("SBD", None)
        
        logger.debug(f"Retrieved multi-currency balance for {sbd_amount} SBD")
        
        return MultiCurrencyBalanceResponse(
            sbd_balance=sbd_amount,
            equivalents=equivalents,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get multi-currency balance: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve balance information",
        )


@router.get(
    "/rates",
    summary="Get all exchange rates",
    description="""
    Get exchange rates for all supported currencies.
    
    **Response:**
    ```json
    {
        "base_currency": "SBD",
        "rates": {
            "INR": {
                "rate": 0.000001,
                "inverse_rate": 1000000,
                "formatted": "1 SBD = ₹0.000001"
            }
        },
        "last_updated": "2024-01-01T00:00:00Z"
    }
    ```
    """,
)
async def get_all_exchange_rates():
    """Get all available exchange rates."""
    try:
        rates_info = {}
        
        for currency in ExchangeRateConfig.RATES.keys():
            rate = ExchangeRateConfig.get_rate(currency)
            inverse_rate = ExchangeRateConfig.get_inverse_rate(currency)
            
            rates_info[currency.value] = {
                "rate": float(rate),
                "inverse_rate": float(inverse_rate),
                "formatted": f"1 SBD = {format_currency(rate, currency)}",
            }
        
        return JSONResponse(
            content={
                "base_currency": "SBD",
                "rates": rates_info,
                "last_updated": datetime.utcnow().isoformat(),
            }
        )
    
    except Exception as e:
        logger.error(f"Failed to get all exchange rates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve exchange rates",
        )
