"""
# Package Signing Service

This module provides **Digital Signatures** for migration packages.
It ensures the authenticity and integrity of data exported from the system.

## Domain Overview

Migration packages are often transferred over untrusted networks.
- **Integrity**: Verifying that the package content hasn't been altered.
- **Authenticity**: Confirming that the package originated from a trusted source.
- **Algorithm**: RSA-PSS with SHA-256 (Industry standard for secure signatures).

## Key Features

### 1. Signing
- **Private Key**: Uses the system's private key to sign the package hash.
- **Output**: Generates a detached Base64-encoded signature.

### 2. Verification
- **Public Key**: Uses the corresponding public key to verify the signature.
- **Safety**: Prevents importing malicious or corrupted packages.

## Usage Example

```python
# Sign a package
signature = package_signing_service.sign_package(package_bytes)

# Verify a package
is_valid = package_signing_service.verify_signature(package_bytes, signature)
```
"""

import base64
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.config import settings

logger = get_logger(prefix="[PackageSigning]")


class PackageSigningService:
    """
    RSA signature generation and verification for migration packages.

    Provides cryptographic signatures to ensure package integrity and authenticity,
    preventing tampering during transfer.

    **Algorithm:** RSA-PSS with SHA-256
    - **Key size**: 2048 bits
    - **Padding**: PSS (Probabilistic Signature Scheme)
    - **Hash**: SHA-256
    """

    def __init__(self):
        # In production, load from secure key storage
        self.private_key = None
        self.public_key = None
        self._load_or_generate_keys()

    def _load_or_generate_keys(self):
        """Load existing keys or generate new ones."""
        try:
            # Try to load from settings/file
            # For demo, generate new keys
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            self.public_key = self.private_key.public_key()
            logger.info("Generated RSA key pair for package signing")
        except Exception as e:
            logger.error(f"Failed to load/generate keys: {e}")

    def sign_package(self, package_data: bytes) -> str:
        """
        Sign a migration package.
        
        Args:
            package_data: Raw package bytes
            
        Returns:
            Base64-encoded signature
        """
        if not self.private_key:
            raise ValueError("Private key not available")

        signature = self.private_key.sign(
            package_data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode('utf-8')

    def verify_signature(self, package_data: bytes, signature: str) -> bool:
        """
        Verify a package signature.
        
        Args:
            package_data: Raw package bytes
            signature: Base64-encoded signature
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.public_key:
            logger.warning("Public key not available for verification")
            return False

        try:
            signature_bytes = base64.b64decode(signature)
            self.public_key.verify(
                signature_bytes,
                package_data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            logger.warning(f"Signature verification failed: {e}")
            return False

    def export_public_key(self) -> str:
        """Export public key in PEM format."""
        if not self.public_key:
            raise ValueError("Public key not available")
            
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')


# Global instance
package_signing_service = PackageSigningService()
