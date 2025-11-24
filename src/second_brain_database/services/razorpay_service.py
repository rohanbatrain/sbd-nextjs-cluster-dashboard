"""
Razorpay Payment Service.

Core service layer for handling Razorpay payment operations including
order creation, payment verification, webhook processing, and refunds.
"""

import hashlib
import hmac
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

import razorpay

from second_brain_database.config.razorpay_config import razorpay_config
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.payment_models import (
    PaymentPurpose,
    PaymentStatus,
    PaymentTransaction,
)
from second_brain_database.utils.currency_exchange import currency_to_sbd

logger = get_logger(prefix="[RAZORPAY_SERVICE]")


class RazorpayService:
    """Service for Razorpay payment operations."""
    
    def __init__(self):
        """Initialize Razorpay client."""
        self.client = razorpay.Client(
            auth=(razorpay_config.key_id, razorpay_config.key_secret)
        )
        self.currency = razorpay_config.currency
        
    async def create_order(
        self,
        user_id: str,
        amount_inr: Decimal,
        purpose: PaymentPurpose = PaymentPurpose.SBD_TOKEN_PURCHASE,
        notes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Create a Razorpay payment order.
        
        Args:
            user_id: User ID making the payment
            amount_inr: Amount in INR
            purpose: Purpose of payment
            notes: Additional metadata
            
        Returns:
            Dict containing order details
            
        Raises:
            Exception: If order creation fails
        """
        try:
            # Convert INR to paise (smallest currency unit)
            amount_paise = int(amount_inr * 100)
            
            # Generate unique receipt ID
            receipt = f"rcpt_{uuid.uuid4().hex[:12]}"
            
            # Prepare notes
            order_notes = {
                "user_id": user_id,
                "purpose": purpose.value,
                **(notes or {})
            }
            
            # Create Razorpay order
            order_data = {
                "amount": amount_paise,
                "currency": self.currency,
                "receipt": receipt,
                "notes": order_notes,
            }
            
            razorpay_order = self.client.order.create(data=order_data)
            
            # Calculate SBD equivalent
            from second_brain_database.utils.currency_exchange import Currency
            sbd_equivalent = currency_to_sbd(amount_inr, Currency.INR)
            
            # Create transaction record
            transaction_id = f"txn_{uuid.uuid4().hex[:16]}"
            transaction = {
                "transaction_id": transaction_id,
                "user_id": user_id,
                "order_id": razorpay_order["id"],
                "amount_inr": float(amount_inr),
                "amount_sbd": float(sbd_equivalent),
                "status": PaymentStatus.PENDING.value,
                "purpose": purpose.value,
                "notes": order_notes,
                "created_at": datetime.utcnow(),
            }
            
            # Save to database
            db = await db_manager.get_database()
            await db["payment_transactions"].insert_one(transaction)
            
            logger.info(
                f"Created payment order: {razorpay_order['id']} for user {user_id}, "
                f"amount: ₹{amount_inr}, SBD: {sbd_equivalent}"
            )
            
            return {
                "order_id": razorpay_order["id"],
                "amount": amount_inr,
                "currency": self.currency,
                "sbd_equivalent": sbd_equivalent,
                "status": razorpay_order["status"],
                "receipt": receipt,
                "transaction_id": transaction_id,
                "created_at": datetime.utcnow(),
            }
            
        except Exception as e:
            logger.error(f"Failed to create payment order: {e}", exc_info=True)
            raise
    
    def verify_payment_signature(
        self,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> bool:
        """
        Verify Razorpay payment signature.
        
        Args:
            order_id: Razorpay order ID
            payment_id: Razorpay payment ID
            signature: Payment signature to verify
            
        Returns:
            bool: True if signature is valid
        """
        try:
            # Create signature string
            message = f"{order_id}|{payment_id}"
            
            # Generate expected signature
            expected_signature = hmac.new(
                razorpay_config.key_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            is_valid = hmac.compare_digest(expected_signature, signature)
            
            if is_valid:
                logger.info(f"Payment signature verified: {payment_id}")
            else:
                logger.warning(f"Invalid payment signature: {payment_id}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Signature verification failed: {e}", exc_info=True)
            return False
    
    async def capture_payment(
        self,
        user_id: str,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> Dict[str, Any]:
        """
        Capture and process a verified payment.
        
        Args:
            user_id: User ID
            order_id: Razorpay order ID
            payment_id: Razorpay payment ID
            signature: Payment signature
            
        Returns:
            Dict containing transaction details
            
        Raises:
            ValueError: If signature is invalid or transaction not found
        """
        try:
            # Verify signature
            if not self.verify_payment_signature(order_id, payment_id, signature):
                raise ValueError("Invalid payment signature")
            
            # Get transaction from database
            db = await db_manager.get_database()
            transaction = await db["payment_transactions"].find_one({
                "order_id": order_id,
                "user_id": user_id,
            })
            
            if not transaction:
                raise ValueError(f"Transaction not found for order: {order_id}")
            
            # Check if already processed
            if transaction["status"] in [PaymentStatus.COMPLETED.value, PaymentStatus.CAPTURED.value]:
                logger.warning(f"Payment already processed: {payment_id}")
                return {
                    "status": "already_processed",
                    "transaction_id": transaction["transaction_id"],
                    "sbd_credited": transaction["amount_sbd"],
                }
            
            # Update transaction status
            await db["payment_transactions"].update_one(
                {"transaction_id": transaction["transaction_id"]},
                {
                    "$set": {
                        "payment_id": payment_id,
                        "razorpay_signature": signature,
                        "status": PaymentStatus.COMPLETED.value,
                        "completed_at": datetime.utcnow(),
                    }
                }
            )
            
            # Credit SBD tokens to user
            sbd_amount = Decimal(str(transaction["amount_sbd"]))
            await self._credit_sbd_tokens(user_id, sbd_amount, transaction["transaction_id"])
            
            logger.info(
                f"Payment captured successfully: {payment_id}, "
                f"credited {sbd_amount} SBD to user {user_id}"
            )
            
            return {
                "status": "success",
                "transaction_id": transaction["transaction_id"],
                "sbd_credited": sbd_amount,
                "payment_verified": True,
                "message": f"Successfully credited {sbd_amount:,.2f} SBD tokens",
            }
            
        except Exception as e:
            logger.error(f"Payment capture failed: {e}", exc_info=True)
            
            # Update transaction with error
            if 'transaction' in locals():
                db = await db_manager.get_database()
                await db["payment_transactions"].update_one(
                    {"transaction_id": transaction["transaction_id"]},
                    {
                        "$set": {
                            "status": PaymentStatus.FAILED.value,
                            "error_message": str(e),
                        }
                    }
                )
            
            raise
    
    async def _credit_sbd_tokens(
        self,
        user_id: str,
        sbd_amount: Decimal,
        transaction_id: str,
    ) -> None:
        """
        Credit SBD tokens to user's family account.
        
        Args:
            user_id: User ID
            sbd_amount: Amount of SBD tokens to credit
            transaction_id: Transaction ID for reference
        """
        try:
            db = await db_manager.get_database()
            
            # Find user's family
            member = await db["family_members"].find_one({"user_id": user_id})
            
            if not member:
                raise ValueError(f"User {user_id} is not part of any family")
            
            family_id = member["family_id"]
            
            # Credit tokens to family account
            result = await db["families"].update_one(
                {"family_id": family_id},
                {"$inc": {"sbd_account.balance": float(sbd_amount)}}
            )
            
            if result.modified_count == 0:
                raise ValueError(f"Failed to credit tokens to family {family_id}")
            
            # Log transaction
            await db["family_transactions"].insert_one({
                "transaction_id": f"fam_txn_{uuid.uuid4().hex[:12]}",
                "family_id": family_id,
                "user_id": user_id,
                "amount": float(sbd_amount),
                "type": "deposit",
                "source": "razorpay_purchase",
                "reference_id": transaction_id,
                "created_at": datetime.utcnow(),
                "description": f"SBD token purchase via Razorpay",
            })
            
            logger.info(f"Credited {sbd_amount} SBD to family {family_id}")
            
        except Exception as e:
            logger.error(f"Failed to credit SBD tokens: {e}", exc_info=True)
            raise
    
    async def handle_webhook(
        self,
        event_data: Dict[str, Any],
        signature: str,
    ) -> Dict[str, Any]:
        """
        Handle Razorpay webhook events.
        
        Args:
            event_data: Webhook event payload
            signature: Webhook signature for verification
            
        Returns:
            Dict containing processing result
        """
        try:
            # Verify webhook signature
            if not self._verify_webhook_signature(event_data, signature):
                raise ValueError("Invalid webhook signature")
            
            event_type = event_data.get("event")
            payload = event_data.get("payload", {})
            
            logger.info(f"Processing webhook event: {event_type}")
            
            if event_type == "payment.captured":
                return await self._handle_payment_captured(payload)
            elif event_type == "payment.failed":
                return await self._handle_payment_failed(payload)
            elif event_type == "order.paid":
                return await self._handle_order_paid(payload)
            else:
                logger.warning(f"Unhandled webhook event: {event_type}")
                return {"status": "ignored", "event": event_type}
                
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}", exc_info=True)
            raise
    
    def _verify_webhook_signature(
        self,
        event_data: Dict[str, Any],
        signature: str,
    ) -> bool:
        """Verify webhook signature."""
        try:
            # Implementation depends on Razorpay webhook signature format
            # This is a placeholder - actual implementation may vary
            return True  # TODO: Implement proper webhook signature verification
        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False
    
    async def _handle_payment_captured(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle payment.captured webhook event."""
        payment = payload.get("payment", {}).get("entity", {})
        order_id = payment.get("order_id")
        payment_id = payment.get("id")
        
        logger.info(f"Payment captured webhook: {payment_id} for order {order_id}")
        
        # Payment already handled in capture_payment endpoint
        # This is a confirmation event
        return {"status": "acknowledged", "payment_id": payment_id}
    
    async def _handle_payment_failed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle payment.failed webhook event."""
        payment = payload.get("payment", {}).get("entity", {})
        order_id = payment.get("order_id")
        payment_id = payment.get("id")
        error = payment.get("error_description", "Unknown error")
        
        logger.warning(f"Payment failed: {payment_id}, error: {error}")
        
        # Update transaction status
        db = await db_manager.get_database()
        await db["payment_transactions"].update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "payment_id": payment_id,
                    "status": PaymentStatus.FAILED.value,
                    "error_message": error,
                }
            }
        )
        
        return {"status": "processed", "payment_id": payment_id}
    
    async def _handle_order_paid(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle order.paid webhook event."""
        order = payload.get("order", {}).get("entity", {})
        order_id = order.get("id")
        
        logger.info(f"Order paid webhook: {order_id}")
        
        return {"status": "acknowledged", "order_id": order_id}
    
    async def get_transaction_history(
        self,
        user_id: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get user's payment transaction history.
        
        Args:
            user_id: User ID
            limit: Maximum number of transactions to return
            
        Returns:
            Dict containing transaction history
        """
        try:
            db = await db_manager.get_database()
            
            # Get transactions
            cursor = db["payment_transactions"].find(
                {"user_id": user_id}
            ).sort("created_at", -1).limit(limit)
            
            transactions = await cursor.to_list(length=limit)
            
            # Calculate totals
            total_spent = sum(
                Decimal(str(t["amount_inr"]))
                for t in transactions
                if t["status"] == PaymentStatus.COMPLETED.value
            )
            
            total_sbd = sum(
                Decimal(str(t["amount_sbd"]))
                for t in transactions
                if t["status"] == PaymentStatus.COMPLETED.value
            )
            
            return {
                "transactions": transactions,
                "total_spent_inr": total_spent,
                "total_sbd_purchased": total_sbd,
                "transaction_count": len(transactions),
            }
            
        except Exception as e:
            logger.error(f"Failed to get transaction history: {e}", exc_info=True)
            raise


# Global service instance
razorpay_service = RazorpayService()
