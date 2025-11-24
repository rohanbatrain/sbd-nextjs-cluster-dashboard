"""
# Migration Metrics Service

This module provides **Prometheus Metrics** for the migration system.
It enables real-time monitoring of performance, throughput, and error rates.

## Domain Overview

Observability is key for reliable data migrations.
- **Throughput**: Tracking bytes/sec and documents/sec.
- **Latency**: Measuring duration of export/import operations.
- **Reliability**: Counting errors, retries, and validation failures.

## Key Features

### 1. Metric Types
- **Counters**: Total operations, documents processed, errors.
- **Histograms**: Operation duration, package sizes.
- **Gauges**: Currently active migrations.

### 2. Dimensions (Labels)
- **Operation Type**: `export`, `import`, `transfer`.
- **Status**: `success`, `failed`.
- **Collection**: Granular tracking per database collection.

## Usage Example

```python
# Record the start of an operation
migration_metrics.record_operation_start("export")

# Record completion with stats
migration_metrics.record_operation_complete(
    operation_type="export",
    status="success",
    user_id="user_123",
    duration=45.2,
    package_size=1024000
)
```
"""

from typing import Optional
from prometheus_client import Counter, Gauge, Histogram
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[MigrationMetrics]")

class MigrationMetrics:
    """
    Prometheus metrics for real-time migration monitoring.

    Provides comprehensive observability for migration operations including
    throughput, errors, duration, and resource usage.

    **Metrics Types:**
    - **Counters**: Total operations, documents processed, errors
    - **Histograms**: Operation duration, package sizes
    - **Gauges**: Active migrations, last operation timestamp

    **Integration:** Metrics are automatically scraped by Prometheus at `/metrics` endpoint.
    """

    def __init__(self):
        """Initialize metrics."""
        # Counters
        self.operations_total = Counter(
            "migration_operations_total",
            "Total number of migration operations",
            ["type", "status", "user_id"]
        )
        
        self.documents_processed = Counter(
            "migration_documents_processed_total",
            "Total number of documents processed",
            ["collection", "operation_type"]
        )
        
        self.errors_total = Counter(
            "migration_errors_total",
            "Total number of migration errors",
            ["type", "error_code"]
        )
        
        self.rate_limit_violations = Counter(
            "migration_rate_limit_violations_total",
            "Total number of rate limit violations",
            ["operation"]
        )
        
        self.validation_failures = Counter(
            "migration_validation_failures_total",
            "Total number of package validation failures",
            ["reason"]
        )

        # Histograms
        self.operation_duration = Histogram(
            "migration_duration_seconds",
            "Duration of migration operations",
            ["type"],
            buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600)
        )
        
        self.package_size = Histogram(
            "migration_package_size_bytes",
            "Size of migration packages",
            ["type"],
            buckets=(1024*1024, 10*1024*1024, 100*1024*1024, 1024*1024*1024)  # 1MB, 10MB, 100MB, 1GB
        )

        # Gauges
        self.active_migrations = Gauge(
            "migration_active_count",
            "Number of currently active migrations",
            ["type"]
        )
        
        self.last_operation_timestamp = Gauge(
            "migration_last_operation_timestamp",
            "Timestamp of last successful operation",
            ["type"]
        )

        logger.info("Migration metrics initialized")

    def record_operation_start(self, operation_type: str):
        """Record start of an operation."""
        self.active_migrations.labels(type=operation_type).inc()

    def record_operation_complete(
        self, 
        operation_type: str, 
        status: str, 
        user_id: str, 
        duration: float,
        package_size: Optional[int] = None
    ):
        """Record completion of an operation."""
        self.active_migrations.labels(type=operation_type).dec()
        self.operations_total.labels(
            type=operation_type, 
            status=status, 
            user_id=user_id
        ).inc()
        
        self.operation_duration.labels(type=operation_type).observe(duration)
        
        if package_size is not None:
            self.package_size.labels(type=operation_type).observe(package_size)

    def record_documents_processed(self, collection: str, count: int, operation_type: str):
        """Record number of documents processed."""
        self.documents_processed.labels(
            collection=collection, 
            operation_type=operation_type
        ).inc(count)

    def record_error(self, operation_type: str, error_code: str):
        """Record an error."""
        self.errors_total.labels(
            type=operation_type, 
            error_code=error_code
        ).inc()

    def record_rate_limit_violation(self, operation: str):
        """Record rate limit violation."""
        self.rate_limit_violations.labels(operation=operation).inc()

    def record_validation_failure(self, reason: str):
        """Record validation failure."""
        self.validation_failures.labels(reason=reason).inc()


# Global metrics instance
migration_metrics = MigrationMetrics()
