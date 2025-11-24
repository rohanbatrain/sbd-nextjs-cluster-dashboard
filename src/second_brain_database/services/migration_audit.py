"""
# Migration Audit Service

This module provides **Security-Focused Audit Logging** for migration operations.
It generates structured logs suitable for SIEM integration and compliance auditing.

## Domain Overview

Migrations involve sensitive data movement, making audit trails critical.
- **Compliance**: SOC 2, GDPR, HIPAA requirements for tracking data access.
- **Security Events**: Auth failures, rate limits, permission denials, sensitive data access.
- **Format**: Structured JSON logs for machine parsing and analysis.

## Key Features

### 1. Comprehensive Event Taxonomy
- **Operations**: Export/Import start and completion.
- **Security**: Authentication failures, encryption errors, checksum mismatches.
- **Data Access**: Tracking which collections and how many documents were touched.

### 2. Structured Logging
- **Context Rich**: Includes User ID, IP Address, Tenant ID, and detailed metadata.
- **Severity Levels**: Automatically categorizes events (Info, Warning, Error).

## Usage Example

```python
audit_logger.log_security_event(
    event_type=SecurityEventType.EXPORT_STARTED,
    user_id="user_123",
    ip_address="192.168.1.50",
    action="Started full database export",
    collections_accessed=["users", "notes"]
)
```
"""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[MigrationAudit]")


class SecurityEventType(str, Enum):
    """Security event types for audit logging."""

    # Authentication & Authorization
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    PERMISSION_DENIED = "permission_denied"
    ROLE_CHECK_FAILED = "role_check_failed"

    # Migration Operations
    EXPORT_STARTED = "export_started"
    EXPORT_COMPLETED = "export_completed"
    EXPORT_FAILED = "export_failed"
    IMPORT_STARTED = "import_started"
    IMPORT_COMPLETED = "import_completed"
    IMPORT_FAILED = "import_failed"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    VALIDATION_FAILED = "validation_failed"
    ROLLBACK_STARTED = "rollback_started"
    ROLLBACK_COMPLETED = "rollback_completed"
    ROLLBACK_FAILED = "rollback_failed"

    # Security Events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    LOCK_ACQUISITION_FAILED = "lock_acquisition_failed"
    FILE_VALIDATION_FAILED = "file_validation_failed"
    ENCRYPTION_FAILED = "encryption_failed"
    DECRYPTION_FAILED = "decryption_failed"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    DECOMPRESSION_BOMB_DETECTED = "decompression_bomb_detected"

    # Data Access
    DATA_EXPORTED = "data_exported"
    DATA_IMPORTED = "data_imported"
    SENSITIVE_DATA_ACCESSED = "sensitive_data_accessed"

    # Administrative
    MIGRATION_DELETED = "migration_deleted"
    PACKAGE_DOWNLOADED = "package_downloaded"


class AuditLogger:
    """
    Enhanced audit logging for migration operations with SIEM integration.

    Generates structured JSON logs suitable for Security Information and Event Management
    (SIEM) systems, supporting compliance requirements (SOC 2, GDPR, HIPAA).

    **Key Features:**
    - Structured JSON format for machine parsing
    - Comprehensive event taxonomy (auth, operations, security, data access)
    - Automatic severity classification
    - IP tracking and user attribution

    **Event Categories:**
    - **Authentication**: Login attempts, permission denials
    - **Operations**: Export, import, validation, rollback
    - **Security**: Rate limiting, validation failures, encryption errors
    - **Data Access**: Sensitive data tracking
    """

    def __init__(self):
        """Initialize audit logger."""
        self.logger = logger

    def log_security_event(
        self,
        event_type: SecurityEventType,
        user_id: str,
        tenant_id: Optional[str] = None,
        migration_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        action: Optional[str] = None,
        result: str = "success",
        details: Optional[Dict[str, Any]] = None,
        collections_accessed: Optional[list[str]] = None,
        document_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """
        Log a security event in structured JSON format.

        Creates a comprehensive audit trail with all relevant context for security analysis.

        Args:
            event_type: Type of security event from `SecurityEventType` enum.
            user_id: ID of the user performing the action.
            tenant_id: Tenant ID for multi-tenancy support.
            migration_id: Migration package ID (if applicable).
            ip_address: Client IP address for geo-tracking.
            action: Human-readable description of the action.
            result: Outcome of the action (`success`, `failure`, `denied`, `blocked`).
            details: Additional structured metadata.
            collections_accessed: List of MongoDB collections touched.
            document_count: Number of documents affected.
            error_message: Error description if result is `failure`.
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type.value,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "migration_id": migration_id,
            "ip_address": ip_address,
            "action": action or event_type.value.replace("_", " ").title(),
            "result": result,
            "collections_accessed": collections_accessed or [],
            "document_count": document_count or 0,
            "error_message": error_message,
            "details": details or {},
        }

        # Log as structured JSON for SIEM parsing
        event_json = json.dumps(event, default=str)

        if result == "failure" or "failed" in event_type.value:
            self.logger.error(f"SECURITY_EVENT: {event_json}")
        elif "denied" in event_type.value or "exceeded" in event_type.value:
            self.logger.warning(f"SECURITY_EVENT: {event_json}")
        else:
            self.logger.info(f"SECURITY_EVENT: {event_json}")

    def log_export_started(
        self,
        user_id: str,
        tenant_id: Optional[str],
        migration_id: str,
        collections: list[str],
        ip_address: Optional[str] = None,
    ):
        """Log export operation started."""
        self.log_security_event(
            event_type=SecurityEventType.EXPORT_STARTED,
            user_id=user_id,
            tenant_id=tenant_id,
            migration_id=migration_id,
            ip_address=ip_address,
            action="Database export started",
            result="started",
            collections_accessed=collections,
        )

    def log_export_completed(
        self,
        user_id: str,
        tenant_id: Optional[str],
        migration_id: str,
        collections: list[str],
        document_count: int,
        package_size: int,
    ):
        """Log export operation completed."""
        self.log_security_event(
            event_type=SecurityEventType.EXPORT_COMPLETED,
            user_id=user_id,
            tenant_id=tenant_id,
            migration_id=migration_id,
            action="Database export completed",
            result="success",
            collections_accessed=collections,
            document_count=document_count,
            details={"package_size_bytes": package_size},
        )

    def log_import_started(
        self,
        user_id: str,
        tenant_id: Optional[str],
        migration_id: str,
        collections: list[str],
        ip_address: Optional[str] = None,
    ):
        """Log import operation started."""
        self.log_security_event(
            event_type=SecurityEventType.IMPORT_STARTED,
            user_id=user_id,
            tenant_id=tenant_id,
            migration_id=migration_id,
            ip_address=ip_address,
            action="Database import started",
            result="started",
            collections_accessed=collections,
        )

    def log_import_completed(
        self,
        user_id: str,
        tenant_id: Optional[str],
        migration_id: str,
        collections: list[str],
        document_count: int,
    ):
        """Log import operation completed."""
        self.log_security_event(
            event_type=SecurityEventType.IMPORT_COMPLETED,
            user_id=user_id,
            tenant_id=tenant_id,
            migration_id=migration_id,
            action="Database import completed",
            result="success",
            collections_accessed=collections,
            document_count=document_count,
        )

    def log_rate_limit_exceeded(
        self,
        user_id: str,
        operation: str,
        ip_address: Optional[str] = None,
    ):
        """Log rate limit violation."""
        self.log_security_event(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            user_id=user_id,
            ip_address=ip_address,
            action=f"Rate limit exceeded for {operation}",
            result="blocked",
            details={"operation": operation},
        )

    def log_validation_failed(
        self,
        user_id: str,
        migration_id: str,
        error_message: str,
        ip_address: Optional[str] = None,
    ):
        """Log validation failure."""
        self.log_security_event(
            event_type=SecurityEventType.FILE_VALIDATION_FAILED,
            user_id=user_id,
            migration_id=migration_id,
            ip_address=ip_address,
            action="Migration package validation failed",
            result="failure",
            error_message=error_message,
        )

    def log_permission_denied(
        self,
        user_id: str,
        action: str,
        reason: str,
        ip_address: Optional[str] = None,
    ):
        """Log permission denied event."""
        self.log_security_event(
            event_type=SecurityEventType.PERMISSION_DENIED,
            user_id=user_id,
            ip_address=ip_address,
            action=action,
            result="denied",
            error_message=reason,
        )

    def log_package_downloaded(
        self,
        user_id: str,
        migration_id: str,
        package_size: int,
        ip_address: Optional[str] = None,
    ):
        """Log package download event."""
        self.log_security_event(
            event_type=SecurityEventType.PACKAGE_DOWNLOADED,
            user_id=user_id,
            migration_id=migration_id,
            ip_address=ip_address,
            action="Migration package downloaded",
            result="success",
            details={"package_size_bytes": package_size},
        )


# Global audit logger instance
audit_logger = AuditLogger()
