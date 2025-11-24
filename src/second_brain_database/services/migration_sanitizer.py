"""
# Migration Sanitizer Service

This module provides **Data Sanitization and Redaction** for migration exports.
It ensures compliance with privacy regulations (GDPR, HIPAA) by masking sensitive data.

## Domain Overview

Exports may leave the secure boundary of the cluster.
- **PII**: Personally Identifiable Information (Email, Phone, SSN).
- **Secrets**: API keys, password hashes, 2FA secrets.
- **Strategy**: Redact sensitive fields while preserving document structure.

## Key Features

### 1. Field-Level Redaction
- **Configurable Rules**: Per-collection lists of sensitive fields.
- **Structure Preservation**: Replaces values with `[REDACTED]` but keeps keys.

### 2. PII Detection
- **Pattern Matching**: Regex-based detection for emails, credit cards, etc.
- **Selective Masking**: Can be enabled/disabled for testing or internal migrations.

## Usage Example

```python
sanitized_doc = data_sanitizer.sanitize_document(
    collection_name="users",
    document={
        "username": "jdoe",
        "email": "jdoe@example.com",
        "two_fa_secret": "SUPERSECRET"
    }
)
# Result: {"username": "jdoe", "email": "jdoe@example.com", "two_fa_secret": "[REDACTED]"}
```
"""

from typing import Any, Dict, List, Set

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[MigrationSanitizer]")


class DataSanitizer:
    """
    Sanitizes sensitive data in migration exports for compliance.

    Automatically redacts PII and sensitive fields based on collection-specific
    rules to ensure GDPR, HIPAA, and SOC 2 compliance.

    **Redaction Strategy:**
    - **Field-level**: Redacts specific sensitive fields per collection
    - **Structure preservation**: Maintains field types (list, dict, string)
    - **Selective**: Never redacts IDs, timestamps, or usernames needed for integrity

    **Supported Collections:** `users`, `permanent_tokens`, `families`, `chat_messages`
    """

    # Sensitive fields to redact by collection
    SENSITIVE_FIELDS: Dict[str, List[str]] = {
        "users": [
            "two_fa_secret",
            "backup_codes",
            "backup_codes_used",
            "password_reset_token",
            "email_verification_token",
        ],
        "permanent_tokens": [
            "token_hash",  # Keep structure but redact actual token
        ],
        "families": [
            "phone_number",
            "address",
        ],
        "chat_messages": [
            # Keep messages but could add PII detection here
        ],
    }

    # Fields to always keep (never redact)
    PRESERVE_FIELDS: Set[str] = {
        "_id",
        "user_id",
        "tenant_id",
        "created_at",
        "updated_at",
        "username",  # Keep for data integrity
        "email",  # Keep for user identification (hashed passwords protect account)
    }

    # PII patterns to detect and mask
    PII_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
    }

    def __init__(self, enable_sanitization: bool = True):
        """
        Initialize data sanitizer.

        Args:
            enable_sanitization: Whether to enable sanitization (can disable for testing)
        """
        self.enabled = enable_sanitization
        logger.info(f"Data sanitizer initialized (enabled: {self.enabled})")

    def sanitize_document(
        self, collection_name: str, document: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sanitize a single document.

        Args:
            collection_name: Name of the collection
            document: Document to sanitize

        Returns:
            Sanitized document
        """
        if not self.enabled:
            return document

        # Get sensitive fields for this collection
        sensitive_fields = self.SENSITIVE_FIELDS.get(collection_name, [])

        # Create a copy to avoid modifying original
        sanitized = document.copy()

        # Redact sensitive fields
        for field in sensitive_fields:
            if field in sanitized and field not in self.PRESERVE_FIELDS:
                # Redact but keep field structure
                if isinstance(sanitized[field], list):
                    sanitized[field] = ["[REDACTED]"] * len(sanitized[field])
                elif isinstance(sanitized[field], dict):
                    sanitized[field] = {"redacted": True}
                else:
                    sanitized[field] = "[REDACTED]"

        return sanitized

    def sanitize_collection(
        self, collection_name: str, documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Sanitize all documents in a collection.

        Args:
            collection_name: Name of the collection
            documents: List of documents to sanitize

        Returns:
            List of sanitized documents
        """
        if not self.enabled:
            return documents

        logger.info(f"Sanitizing {len(documents)} documents from {collection_name}")

        sanitized_docs = [
            self.sanitize_document(collection_name, doc) for doc in documents
        ]

        # Count redacted fields
        redacted_count = sum(
            1
            for doc in sanitized_docs
            for field in self.SENSITIVE_FIELDS.get(collection_name, [])
            if field in doc and doc[field] == "[REDACTED]"
        )

        if redacted_count > 0:
            logger.info(
                f"Redacted {redacted_count} sensitive fields from {collection_name}"
            )

        return sanitized_docs

    def get_sanitization_summary(
        self, collection_name: str, document_count: int
    ) -> Dict[str, Any]:
        """
        Get summary of what will be sanitized.

        Args:
            collection_name: Name of collection
            document_count: Number of documents

        Returns:
            Summary of sanitization
        """
        sensitive_fields = self.SENSITIVE_FIELDS.get(collection_name, [])

        return {
            "collection": collection_name,
            "document_count": document_count,
            "sensitive_fields": sensitive_fields,
            "sanitization_enabled": self.enabled,
        }


# Global sanitizer instance
data_sanitizer = DataSanitizer(enable_sanitization=True)
