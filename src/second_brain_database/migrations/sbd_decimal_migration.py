"""
SBD Token Decimal Migration.

This migration converts all SBD token amounts from integers to decimals with 2 decimal places.
It updates balances, transaction amounts, and spending limits across all family-related collections.

Collections affected:
- families (SBD account balances)
- family_transactions (transaction amounts)
- family_token_requests (requested amounts)
- family_purchase_requests (estimated costs, if applicable)

Migration preserves existing values: 100 → 100.00
"""

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorDatabase

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[SBD_DECIMAL_MIGRATION]")


class SBDDecimalMigration:
    """Migration to convert SBD token amounts from int to Decimal."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize the migration.

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.migration_id = "sbd_decimal_migration_v1"
        self.migration_date = datetime.utcnow()

    async def run(self) -> Dict[str, Any]:
        """
        Execute the migration.

        Returns:
            Dict containing migration results and statistics
        """
        logger.info("Starting SBD decimal migration...")

        results = {
            "migration_id": self.migration_id,
            "started_at": self.migration_date,
            "collections_updated": {},
            "total_documents_updated": 0,
            "errors": [],
        }

        try:
            # Migrate families collection (SBD account balances)
            families_result = await self._migrate_families()
            results["collections_updated"]["families"] = families_result

            # Migrate family_transactions collection
            transactions_result = await self._migrate_transactions()
            results["collections_updated"]["family_transactions"] = transactions_result

            # Migrate family_token_requests collection
            token_requests_result = await self._migrate_token_requests()
            results["collections_updated"]["family_token_requests"] = token_requests_result

            # Calculate total
            results["total_documents_updated"] = sum(
                r["documents_updated"] for r in results["collections_updated"].values()
            )

            # Record migration in history
            await self._record_migration(results)

            results["completed_at"] = datetime.utcnow()
            results["status"] = "success"

            logger.info(
                f"SBD decimal migration completed successfully. "
                f"Updated {results['total_documents_updated']} documents across "
                f"{len(results['collections_updated'])} collections."
            )

        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            results["status"] = "failed"
            results["error"] = str(e)
            results["completed_at"] = datetime.utcnow()

        return results

    async def _migrate_families(self) -> Dict[str, Any]:
        """
        Migrate families collection - convert balance to Decimal.

        Returns:
            Dict with migration statistics
        """
        logger.info("Migrating families collection...")

        collection = self.db["families"]
        updated_count = 0
        errors = []

        # Find all families with SBD accounts
        cursor = collection.find({"sbd_account": {"$exists": True}})

        async for family in cursor:
            try:
                sbd_account = family.get("sbd_account", {})

                # Convert balance from int to Decimal (preserve value)
                if "balance" in sbd_account and isinstance(sbd_account["balance"], int):
                    old_balance = sbd_account["balance"]
                    new_balance = Decimal(str(old_balance))

                    # Update the document
                    await collection.update_one(
                        {"_id": family["_id"]},
                        {"$set": {"sbd_account.balance": new_balance}}
                    )

                    updated_count += 1
                    logger.debug(
                        f"Updated family {family.get('family_id')}: "
                        f"balance {old_balance} → {new_balance}"
                    )

                # Convert spending limits in member_permissions
                if "member_permissions" in sbd_account:
                    for user_id, perms in sbd_account["member_permissions"].items():
                        if "spending_limit" in perms and isinstance(perms["spending_limit"], int):
                            old_limit = perms["spending_limit"]
                            new_limit = Decimal(str(old_limit)) if old_limit != -1 else Decimal("-1")

                            await collection.update_one(
                                {"_id": family["_id"]},
                                {"$set": {f"sbd_account.member_permissions.{user_id}.spending_limit": new_limit}}
                            )

            except Exception as e:
                error_msg = f"Error migrating family {family.get('family_id', 'unknown')}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return {
            "documents_updated": updated_count,
            "errors": errors,
        }

    async def _migrate_transactions(self) -> Dict[str, Any]:
        """
        Migrate family_transactions collection - convert amounts to Decimal.

        Returns:
            Dict with migration statistics
        """
        logger.info("Migrating family_transactions collection...")

        collection = self.db["family_transactions"]
        updated_count = 0
        errors = []

        # Find all transactions with integer amounts
        cursor = collection.find({"amount": {"$type": "int"}})

        async for transaction in cursor:
            try:
                old_amount = transaction["amount"]
                new_amount = Decimal(str(old_amount))

                await collection.update_one(
                    {"_id": transaction["_id"]},
                    {"$set": {"amount": new_amount}}
                )

                updated_count += 1

            except Exception as e:
                error_msg = f"Error migrating transaction {transaction.get('_id')}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return {
            "documents_updated": updated_count,
            "errors": errors,
        }

    async def _migrate_token_requests(self) -> Dict[str, Any]:
        """
        Migrate family_token_requests collection - convert amounts to Decimal.

        Returns:
            Dict with migration statistics
        """
        logger.info("Migrating family_token_requests collection...")

        collection = self.db["family_token_requests"]
        updated_count = 0
        errors = []

        # Find all token requests with integer amounts
        cursor = collection.find({"amount": {"$type": "int"}})

        async for request in cursor:
            try:
                old_amount = request["amount"]
                new_amount = Decimal(str(old_amount))

                await collection.update_one(
                    {"_id": request["_id"]},
                    {"$set": {"amount": new_amount}}
                )

                updated_count += 1

            except Exception as e:
                error_msg = f"Error migrating token request {request.get('request_id')}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        return {
            "documents_updated": updated_count,
            "errors": errors,
        }

    async def _record_migration(self, results: Dict[str, Any]) -> None:
        """
        Record migration in migration_history collection.

        Args:
            results: Migration results to record
        """
        try:
            migration_history = self.db["migration_history"]

            await migration_history.insert_one({
                "migration_id": self.migration_id,
                "migration_type": "sbd_decimal_conversion",
                "executed_at": self.migration_date,
                "results": results,
                "can_rollback": True,
            })

            logger.info(f"Migration recorded in history: {self.migration_id}")

        except Exception as e:
            logger.error(f"Failed to record migration history: {e}")

    async def rollback(self) -> Dict[str, Any]:
        """
        Rollback the migration (convert Decimal back to int).

        Returns:
            Dict containing rollback results

        Warning:
            This will truncate decimal values! Use with caution.
        """
        logger.warning("Starting SBD decimal migration ROLLBACK...")

        results = {
            "migration_id": self.migration_id,
            "rollback_started_at": datetime.utcnow(),
            "collections_rolled_back": {},
            "total_documents_rolled_back": 0,
            "errors": [],
        }

        try:
            # Rollback families
            families_result = await self._rollback_families()
            results["collections_rolled_back"]["families"] = families_result

            # Rollback transactions
            transactions_result = await self._rollback_transactions()
            results["collections_rolled_back"]["family_transactions"] = transactions_result

            # Rollback token requests
            token_requests_result = await self._rollback_token_requests()
            results["collections_rolled_back"]["family_token_requests"] = token_requests_result

            results["total_documents_rolled_back"] = sum(
                r["documents_updated"] for r in results["collections_rolled_back"].values()
            )

            results["rollback_completed_at"] = datetime.utcnow()
            results["status"] = "success"

            logger.info(f"Rollback completed. Reverted {results['total_documents_rolled_back']} documents.")

        except Exception as e:
            logger.error(f"Rollback failed: {e}", exc_info=True)
            results["status"] = "failed"
            results["error"] = str(e)

        return results

    async def _rollback_families(self) -> Dict[str, Any]:
        """Rollback families collection."""
        collection = self.db["families"]
        updated_count = 0

        cursor = collection.find({"sbd_account.balance": {"$type": "decimal"}})

        async for family in cursor:
            sbd_account = family.get("sbd_account", {})
            if "balance" in sbd_account:
                old_balance = sbd_account["balance"]
                new_balance = int(old_balance)  # Truncates decimals!

                await collection.update_one(
                    {"_id": family["_id"]},
                    {"$set": {"sbd_account.balance": new_balance}}
                )
                updated_count += 1

        return {"documents_updated": updated_count, "errors": []}

    async def _rollback_transactions(self) -> Dict[str, Any]:
        """Rollback transactions collection."""
        collection = self.db["family_transactions"]
        updated_count = 0

        cursor = collection.find({"amount": {"$type": "decimal"}})

        async for transaction in cursor:
            old_amount = transaction["amount"]
            new_amount = int(old_amount)

            await collection.update_one(
                {"_id": transaction["_id"]},
                {"$set": {"amount": new_amount}}
            )
            updated_count += 1

        return {"documents_updated": updated_count, "errors": []}

    async def _rollback_token_requests(self) -> Dict[str, Any]:
        """Rollback token requests collection."""
        collection = self.db["family_token_requests"]
        updated_count = 0

        cursor = collection.find({"amount": {"$type": "decimal"}})

        async for request in cursor:
            old_amount = request["amount"]
            new_amount = int(old_amount)

            await collection.update_one(
                {"_id": request["_id"]},
                {"$set": {"amount": new_amount}}
            )
            updated_count += 1

        return {"documents_updated": updated_count, "errors": []}


async def run_migration():
    """Run the SBD decimal migration."""
    db = await db_manager.get_database()
    migration = SBDDecimalMigration(db)
    results = await migration.run()

    print("\n" + "="*60)
    print("SBD DECIMAL MIGRATION RESULTS")
    print("="*60)
    print(f"Status: {results['status']}")
    print(f"Total documents updated: {results['total_documents_updated']}")
    print("\nPer collection:")
    for collection, stats in results["collections_updated"].items():
        print(f"  - {collection}: {stats['documents_updated']} documents")
        if stats["errors"]:
            print(f"    Errors: {len(stats['errors'])}")
    print("="*60 + "\n")

    return results


async def run_rollback():
    """Rollback the SBD decimal migration."""
    db = await db_manager.get_database()
    migration = SBDDecimalMigration(db)
    results = await migration.rollback()

    print("\n" + "="*60)
    print("SBD DECIMAL MIGRATION ROLLBACK RESULTS")
    print("="*60)
    print(f"Status: {results['status']}")
    print(f"Total documents rolled back: {results['total_documents_rolled_back']}")
    print("="*60 + "\n")

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(run_rollback())
    else:
        asyncio.run(run_migration())
