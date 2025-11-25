"""
Configuration validation for distributed cluster settings.

This module validates cluster configuration at startup to prevent
misconfigurations and ensure optimal performance.
"""

from typing import List, Optional, Tuple

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()


class ConfigValidator:
    """Validates cluster configuration settings."""

    @staticmethod
    def validate_all() -> Tuple[bool, List[str]]:
        """
        Validate all cluster configuration settings.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if not settings.CLUSTER_ENABLED:
            return True, []

        # Validate node configuration
        errors.extend(ConfigValidator._validate_node_config())

        # Validate replication settings
        errors.extend(ConfigValidator._validate_replication_config())

        # Validate load balancing
        errors.extend(ConfigValidator._validate_load_balancing_config())

        # Validate security
        errors.extend(ConfigValidator._validate_security_config())

        # Validate timeouts and thresholds
        errors.extend(ConfigValidator._validate_timeouts())

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def _validate_node_config() -> List[str]:
        """Validate node configuration."""
        errors = []

        # Check node role
        if settings.CLUSTER_NODE_ROLE not in ["master", "replica"]:
            errors.append(
                f"Invalid CLUSTER_NODE_ROLE: {settings.CLUSTER_NODE_ROLE}. "
                "Must be 'master' or 'replica'"
            )

        # Check advertise address
        if not settings.CLUSTER_ADVERTISE_ADDRESS:
            errors.append(
                "CLUSTER_ADVERTISE_ADDRESS not set. Other nodes won't be able to reach this node."
            )

        return errors

    @staticmethod
    def _validate_replication_config() -> List[str]:
        """Validate replication configuration."""
        errors = []

        if not settings.CLUSTER_REPLICATION_ENABLED:
            return errors

        # Check replication mode
        if settings.CLUSTER_REPLICATION_MODE not in ["async", "sync"]:
            errors.append(
                f"Invalid CLUSTER_REPLICATION_MODE: {settings.CLUSTER_REPLICATION_MODE}. "
                "Must be 'async' or 'sync'"
            )

        # Check batch size
        if settings.CLUSTER_BATCH_SIZE <= 0:
            errors.append(
                f"CLUSTER_BATCH_SIZE must be positive, got {settings.CLUSTER_BATCH_SIZE}"
            )
        elif settings.CLUSTER_BATCH_SIZE > 1000:
            logger.warning(
                f"CLUSTER_BATCH_SIZE is very large ({settings.CLUSTER_BATCH_SIZE}). "
                "This may impact performance. Recommended: 100-500"
            )

        return errors

    @staticmethod
    def _validate_load_balancing_config() -> List[str]:
        """Validate load balancing configuration."""
        errors = []

        # Check algorithm
        valid_algorithms = ["round_robin", "least_connections", "weighted", "ip_hash", "least_response_time"]
        if settings.CLUSTER_LOAD_BALANCING_ALGORITHM not in valid_algorithms:
            errors.append(
                f"Invalid CLUSTER_LOAD_BALANCING_ALGORITHM: {settings.CLUSTER_LOAD_BALANCING_ALGORITHM}. "
                f"Must be one of: {', '.join(valid_algorithms)}"
            )

        return errors

    @staticmethod
    def _validate_security_config() -> List[str]:
        """Validate security configuration."""
        errors = []

        # Check cluster token
        if not settings.CLUSTER_AUTH_TOKEN:
            logger.warning(
                "CLUSTER_AUTH_TOKEN not set. Cluster communication is not authenticated. "
                "This is a security risk in production."
            )

        # Check mTLS configuration
        if settings.CLUSTER_MTLS_ENABLED:
            if not settings.CLUSTER_MTLS_CA_FILE:
                errors.append("CLUSTER_MTLS_CA_FILE required when CLUSTER_MTLS_ENABLED=true")
            if not settings.CLUSTER_MTLS_CERT_FILE:
                errors.append("CLUSTER_MTLS_CERT_FILE required when CLUSTER_MTLS_ENABLED=true")
            if not settings.CLUSTER_MTLS_KEY_FILE:
                errors.append("CLUSTER_MTLS_KEY_FILE required when CLUSTER_MTLS_ENABLED=true")

        return errors

    @staticmethod
    def _validate_timeouts() -> List[str]:
        """Validate timeout and threshold settings."""
        errors = []

        # Check heartbeat interval
        if settings.CLUSTER_HEARTBEAT_INTERVAL <= 0:
            errors.append(
                f"CLUSTER_HEARTBEAT_INTERVAL must be positive, got {settings.CLUSTER_HEARTBEAT_INTERVAL}"
            )
        elif settings.CLUSTER_HEARTBEAT_INTERVAL > 60:
            logger.warning(
                f"CLUSTER_HEARTBEAT_INTERVAL is very high ({settings.CLUSTER_HEARTBEAT_INTERVAL}s). "
                "This may delay failure detection. Recommended: 5-30 seconds"
            )

        # Check failure threshold
        if settings.CLUSTER_FAILURE_THRESHOLD <= 0:
            errors.append(
                f"CLUSTER_FAILURE_THRESHOLD must be positive, got {settings.CLUSTER_FAILURE_THRESHOLD}"
            )

        # Check request timeout
        if settings.CLUSTER_REQUEST_TIMEOUT <= 0:
            errors.append(
                f"CLUSTER_REQUEST_TIMEOUT must be positive, got {settings.CLUSTER_REQUEST_TIMEOUT}"
            )

        # Check circuit breaker settings
        if settings.CLUSTER_CIRCUIT_BREAKER_ENABLED:
            if settings.CLUSTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD <= 0:
                errors.append(
                    f"CLUSTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD must be positive, "
                    f"got {settings.CLUSTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD}"
                )

        return errors

    @staticmethod
    def print_warnings_and_errors() -> bool:
        """
        Validate configuration and print warnings/errors.

        Returns:
            True if valid, False otherwise
        """
        is_valid, errors = ConfigValidator.validate_all()

        if errors:
            logger.error("❌ Cluster configuration validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return False
        else:
            logger.info("✅ Cluster configuration validation passed")
            return True


# Validate on module import (optional - can be moved to startup)
def validate_cluster_config() -> bool:
    """Validate cluster configuration at startup."""
    if not settings.CLUSTER_ENABLED:
        return True
    
    return ConfigValidator.print_warnings_and_errors()
