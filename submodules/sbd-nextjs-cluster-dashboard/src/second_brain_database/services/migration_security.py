"""
# Migration Security Service

This module provides **Encryption, Validation, and Access Control** for the migration system.
It secures data at rest (packages) and protects against malicious uploads.

## Domain Overview

Migration packages contain full database dumps. Security is paramount.
- **Encryption**: AES-256-GCM for package files.
- **Validation**: Checksums, size limits, and "decompression bomb" protection.
- **Rate Limiting**: Preventing abuse of export/import endpoints.
- **Locking**: Ensuring only one migration runs per tenant.

## Key Features

### 1. Cryptography
- **AES-256-GCM**: Authenticated encryption for confidentiality and integrity.
- **Key Management**: Generates ephemeral keys for each export.

### 2. Threat Protection
- **Upload Validation**: Scans for zip bombs and invalid file types.
- **Rate Limiting**: Distributed limits via Redis.
- **Distributed Locking**: Prevents race conditions in multi-node clusters.

## Usage Example

```python
# Encrypt a package
metadata = migration_encryption.encrypt_file(
    input_path=Path("export.json"),
    output_path=Path("export.enc"),
    encryption_key=secret_key
)

# Validate an upload
is_valid, error = migration_validator.validate_upload_file(Path("upload.gz"))
```
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[MigrationSecurity]")


class MigrationEncryption:
    """
    Handles AES-256-GCM encryption and decryption of migration packages.

    Provides military-grade encryption for data at rest and in transit,
    ensuring confidentiality and integrity of migration packages.

    **Algorithm:** AES-256-GCM (Galois/Counter Mode)
    - **Key size**: 256 bits
    - **Authentication**: Built-in AEAD (Authenticated Encryption with Associated Data)
    - **Nonce**: 96-bit random nonce per encryption
    """

    def __init__(self):
        """Initialize encryption service."""
        self.key_size = 32  # 256 bits for AES-256
        logger.info("Migration encryption service initialized")

    def generate_encryption_key(self) -> bytes:
        """
        Generate a secure random encryption key.

        Returns:
            32-byte encryption key for AES-256
        """
        key = secrets.token_bytes(self.key_size)
        logger.info("Generated new encryption key")
        return key

    def encrypt_file(
        self, input_path: Path, output_path: Path, encryption_key: bytes
    ) -> Dict[str, str]:
        """
        Encrypt a file using AES-256-GCM.

        Args:
            input_path: Path to file to encrypt
            output_path: Path to save encrypted file
            encryption_key: 32-byte encryption key

        Returns:
            Dict containing encryption metadata (nonce, tag)

        Raises:
            ValueError: If encryption key is invalid
            FileNotFoundError: If input file doesn't exist
        """
        if len(encryption_key) != self.key_size:
            raise ValueError(f"Encryption key must be {self.key_size} bytes")

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        logger.info(f"Encrypting file: {input_path}")

        # Generate nonce (96 bits recommended for GCM)
        nonce = secrets.token_bytes(12)

        # Create AESGCM cipher
        aesgcm = AESGCM(encryption_key)

        # Read input file
        with open(input_path, "rb") as f:
            plaintext = f.read()

        # Encrypt data (includes authentication tag)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)

        # Write encrypted data
        with open(output_path, "wb") as f:
            # Write nonce first (needed for decryption)
            f.write(nonce)
            # Write encrypted data (includes auth tag)
            f.write(ciphertext)

        logger.info(f"File encrypted successfully: {output_path}")

        return {
            "nonce": nonce.hex(),
            "algorithm": "AES-256-GCM",
            "key_size": self.key_size,
        }

    def decrypt_file(
        self, input_path: Path, output_path: Path, encryption_key: bytes
    ) -> bool:
        """
        Decrypt a file using AES-256-GCM.

        Args:
            input_path: Path to encrypted file
            output_path: Path to save decrypted file
            encryption_key: 32-byte encryption key

        Returns:
            True if decryption successful

        Raises:
            ValueError: If encryption key is invalid or decryption fails
            FileNotFoundError: If input file doesn't exist
        """
        if len(encryption_key) != self.key_size:
            raise ValueError(f"Encryption key must be {self.key_size} bytes")

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        logger.info(f"Decrypting file: {input_path}")

        # Read encrypted file
        with open(input_path, "rb") as f:
            # Read nonce (first 12 bytes)
            nonce = f.read(12)
            # Read ciphertext (rest of file, includes auth tag)
            ciphertext = f.read()

        # Create AESGCM cipher
        aesgcm = AESGCM(encryption_key)

        try:
            # Decrypt and verify
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)

            # Write decrypted data
            with open(output_path, "wb") as f:
                f.write(plaintext)

            logger.info(f"File decrypted successfully: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Decryption failed - invalid key or corrupted data")


class MigrationValidator:
    """
    Validates migration packages and uploads for security threats.

    Protects against:
    - **Decompression bombs**: Detects excessive compression ratios
    - **Oversized uploads**: Enforces size limits
    - **Malformed packages**: Validates structure and metadata
    - **Invalid content types**: Restricts to allowed MIME types

    **Limits:**
    - Max compressed size: 100 MB
    - Max decompressed size: 10 GB
    - Max compression ratio: 100:1
    """

    # Maximum file sizes
    MAX_COMPRESSED_SIZE = 100 * 1024 * 1024  # 100 MB
    MAX_DECOMPRESSED_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB
    MAX_DECOMPRESSION_RATIO = 100  # Max 100:1 compression ratio

    # Allowed content types
    ALLOWED_CONTENT_TYPES = [
        "application/gzip",
        "application/x-gzip",
        "application/octet-stream",
    ]

    def __init__(self):
        """Initialize validator."""
        logger.info("Migration validator initialized")

    def validate_upload_file(
        self, file_path: Path, content_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate an uploaded migration package.

        Args:
            file_path: Path to uploaded file
            content_type: MIME content type

        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.info(f"Validating upload file: {file_path}")

        # Check file exists
        if not file_path.exists():
            return False, "File not found"

        # Check file size
        file_size = file_path.stat().st_size
        if file_size > self.MAX_COMPRESSED_SIZE:
            return False, f"File too large: {file_size} bytes (max {self.MAX_COMPRESSED_SIZE})"

        if file_size == 0:
            return False, "File is empty"

        # Check content type
        if content_type and content_type not in self.ALLOWED_CONTENT_TYPES:
            return False, f"Invalid content type: {content_type}"

        # Check for decompression bomb
        try:
            import gzip

            with gzip.open(file_path, "rb") as f:
                # Read in chunks to detect decompression bomb
                decompressed_size = 0
                chunk_size = 1024 * 1024  # 1 MB chunks

                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    decompressed_size += len(chunk)

                    # Check decompression ratio
                    if decompressed_size > file_size * self.MAX_DECOMPRESSION_RATIO:
                        return False, "Potential decompression bomb detected"

                    # Check total decompressed size
                    if decompressed_size > self.MAX_DECOMPRESSED_SIZE:
                        return False, f"Decompressed size exceeds limit: {decompressed_size}"

        except Exception as e:
            return False, f"Invalid gzip file: {str(e)}"

        logger.info("Upload file validation passed")
        return True, None

    def validate_package_structure(self, package_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate migration package structure.

        Args:
            package_data: Parsed package data

        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.info("Validating package structure")

        # Check required fields
        if "metadata" not in package_data:
            return False, "Missing metadata field"

        if "collections" not in package_data:
            return False, "Missing collections field"

        metadata = package_data["metadata"]

        # Validate metadata fields
        required_metadata = [
            "version",
            "sbd_version",
            "export_timestamp",
            "exported_by",
            "checksum",
        ]

        for field in required_metadata:
            if field not in metadata:
                return False, f"Missing metadata field: {field}"

        # Validate collections
        if not isinstance(package_data["collections"], list):
            return False, "Collections must be a list"

        for collection in package_data["collections"]:
            if "collection_name" not in collection:
                return False, "Collection missing name field"

            if "documents" not in collection:
                return False, f"Collection {collection.get('collection_name')} missing documents"

        logger.info("Package structure validation passed")
        return True, None


class MigrationRateLimiter:
    """
    Rate limiting for migration operations to prevent abuse.

    Enforces time-based limits on export/import operations per user,
    using Redis for distributed rate limiting across cluster nodes.

    **Default Limits:**
    - 1 operation per hour per user per operation type
    - Configurable per-operation limits
    - Distributed enforcement via Redis
    """

    def __init__(self, redis_client=None):
        """
        Initialize rate limiter.

        Args:
            redis_client: Redis client for distributed rate limiting
        """
        self.redis_client = redis_client
        self.local_cache: Dict[str, datetime] = {}
        logger.info("Migration rate limiter initialized")

    def check_rate_limit(
        self, user_id: str, operation: str, limit_hours: int = 1
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user has exceeded rate limit.

        Args:
            user_id: User ID
            operation: Operation type (export/import)
            limit_hours: Hours between operations

        Returns:
            Tuple of (is_allowed, error_message)
        """
        cache_key = f"migration_rate_limit:{user_id}:{operation}"

        # Check Redis if available
        if self.redis_client:
            try:
                last_operation = self.redis_client.get(cache_key)
                if last_operation:
                    last_time = datetime.fromisoformat(last_operation.decode())
                    time_since = datetime.now(timezone.utc) - last_time
                    if time_since < timedelta(hours=limit_hours):
                        remaining = timedelta(hours=limit_hours) - time_since
                        return False, f"Rate limit exceeded. Try again in {remaining}"

            except Exception as e:
                logger.warning(f"Redis rate limit check failed: {e}")

        # Fallback to local cache
        else:
            if cache_key in self.local_cache:
                last_time = self.local_cache[cache_key]
                time_since = datetime.now(timezone.utc) - last_time
                if time_since < timedelta(hours=limit_hours):
                    remaining = timedelta(hours=limit_hours) - time_since
                    return False, f"Rate limit exceeded. Try again in {remaining}"

        return True, None

    def record_operation(self, user_id: str, operation: str):
        """
        Record a migration operation.

        Args:
            user_id: User ID
            operation: Operation type
        """
        cache_key = f"migration_rate_limit:{user_id}:{operation}"
        current_time = datetime.now(timezone.utc)

        # Update Redis if available
        if self.redis_client:
            try:
                self.redis_client.setex(
                    cache_key,
                    3600 * 24,  # 24 hours expiry
                    current_time.isoformat(),
                )
            except Exception as e:
                logger.warning(f"Redis operation recording failed: {e}")

        # Update local cache
        self.local_cache[cache_key] = current_time

        logger.info(f"Recorded {operation} operation for user {user_id}")


class MigrationLock:
    """
    Distributed locking for migration operations to prevent conflicts.

    Ensures only one migration can run per tenant at a time, preventing
    data corruption from concurrent operations.

    **Features:**
    - Redis-based distributed locking
    - Automatic timeout (default 1 hour)
    - Fallback to local locks if Redis unavailable
    """

    def __init__(self, redis_client=None):
        """
        Initialize migration lock.

        Args:
            redis_client: Redis client for distributed locking
        """
        self.redis_client = redis_client
        self.local_locks: Dict[str, bool] = {}
        logger.info("Migration lock service initialized")

    async def acquire_lock(
        self, tenant_id: str, timeout_seconds: int = 3600
    ) -> Tuple[bool, Optional[str]]:
        """
        Acquire migration lock for tenant.

        Args:
            tenant_id: Tenant ID
            timeout_seconds: Lock timeout in seconds

        Returns:
            Tuple of (acquired, error_message)
        """
        lock_key = f"migration_lock:{tenant_id}"

        # Use Redis if available
        if self.redis_client:
            try:
                # Try to set lock with NX (only if not exists)
                acquired = self.redis_client.set(
                    lock_key, "locked", ex=timeout_seconds, nx=True
                )

                if not acquired:
                    return False, "Another migration is in progress for this tenant"

                logger.info(f"Acquired migration lock for tenant {tenant_id}")
                return True, None

            except Exception as e:
                logger.error(f"Redis lock acquisition failed: {e}")
                return False, "Failed to acquire lock"

        # Fallback to local locks
        else:
            if lock_key in self.local_locks and self.local_locks[lock_key]:
                return False, "Another migration is in progress for this tenant"

            self.local_locks[lock_key] = True
            logger.info(f"Acquired local migration lock for tenant {tenant_id}")
            return True, None

    async def release_lock(self, tenant_id: str):
        """
        Release migration lock for tenant.

        Args:
            tenant_id: Tenant ID
        """
        lock_key = f"migration_lock:{tenant_id}"

        # Release Redis lock
        if self.redis_client:
            try:
                self.redis_client.delete(lock_key)
                logger.info(f"Released migration lock for tenant {tenant_id}")
            except Exception as e:
                logger.error(f"Redis lock release failed: {e}")

        # Release local lock
        else:
            if lock_key in self.local_locks:
                del self.local_locks[lock_key]
                logger.info(f"Released local migration lock for tenant {tenant_id}")


# Global instances
migration_encryption = MigrationEncryption()
migration_validator = MigrationValidator()
migration_rate_limiter = MigrationRateLimiter()
migration_lock = MigrationLock()
