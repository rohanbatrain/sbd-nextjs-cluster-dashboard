"""
Security utilities for distributed SBD architecture.

This module provides helpers for mTLS configuration, SSL context creation,
and other security-related functions.
"""

import ssl
from typing import Any, Dict, Optional, Tuple

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()


def create_ssl_context(
    verify_mode: ssl.VerifyMode = ssl.CERT_REQUIRED,
) -> Optional[ssl.SSLContext]:
    """
    Create an SSL context for mTLS communication.

    Returns:
        SSLContext if mTLS is enabled and configured, None otherwise.
    """
    if not settings.CLUSTER_MTLS_ENABLED:
        return None

    try:
        if not settings.CLUSTER_MTLS_CA_FILE or not settings.CLUSTER_MTLS_CERT_FILE or not settings.CLUSTER_MTLS_KEY_FILE:
            logger.warning("mTLS enabled but certificates not fully configured")
            return None

        context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=settings.CLUSTER_MTLS_CA_FILE)
        context.load_cert_chain(certfile=settings.CLUSTER_MTLS_CERT_FILE, keyfile=settings.CLUSTER_MTLS_KEY_FILE)
        context.verify_mode = verify_mode
        
        return context

    except Exception as e:
        logger.error(f"Failed to create SSL context: {e}")
        return None


def get_client_ssl_params() -> Dict[str, Any]:
    """
    Get SSL parameters for httpx client.
    """
    if not settings.CLUSTER_MTLS_ENABLED:
        return {}
        
    return {
        "verify": settings.CLUSTER_MTLS_CA_FILE,
        "cert": (settings.CLUSTER_MTLS_CERT_FILE, settings.CLUSTER_MTLS_KEY_FILE)
    }
