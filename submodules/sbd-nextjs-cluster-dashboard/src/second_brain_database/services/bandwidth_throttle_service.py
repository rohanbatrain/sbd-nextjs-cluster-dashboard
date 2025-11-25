"""
# Bandwidth Throttle Service

This module provides **rate limiting** for data transfers, primarily used during migrations.
It ensures that large data movements do not saturate the network or overwhelm target instances.

## Domain Overview

Migrations involve moving large volumes of data between instances.
- **Token Bucket**: Implements a token-bucket-like algorithm to control byte flow.
- **Dynamic Throttling**: Adjusts sleep times based on real-time throughput calculations.
- **Concurrency**: Manages multiple independent throttlers for parallel transfers.

## Key Features

### 1. Transfer Rate Control
- **Mbps Limits**: Configurable speed limits in Megabits per second.
- **Burst Handling**: Smooths out transfer bursts to maintain average speed.

### 2. Multi-Transfer Management
- **Registry**: Tracks active throttlers by transfer ID.
- **Lifecycle**: Creates, retrieves, and cleans up throttlers as transfers complete.

## Usage Example

```python
# Create a throttler limited to 10 Mbps
throttler = bandwidth_throttle_service.create_throttler("tx_123", max_mbps=10.0)

# In the transfer loop
await socket.send(chunk)
await throttler.throttle(len(chunk))
```
"""

import asyncio
import time
from typing import Optional

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[BandwidthThrottle]")


class BandwidthThrottler:
    """
    Throttles data transfer rates to respect bandwidth limits.

    Implements token-bucket-style rate limiting by tracking bytes sent over time
    and introducing delays when the transfer rate exceeds the configured maximum.

    **Use Case**: Prevents network saturation during large data migrations.

    Attributes:
        max_bytes_per_second (float): Maximum allowed transfer rate in bytes/second.
        bytes_sent (int): Total bytes sent since initialization or last reset.
        start_time (float): Timestamp when throttler was initialized or last reset.
        enabled (bool): Whether throttling is active.
    """

    def __init__(self, max_mbps: float = 10.0):
        """
        Initialize the bandwidth throttler.

        Args:
            max_mbps: Maximum transfer speed in megabits per second (default: 10.0).
        """
        self.max_bytes_per_second = (max_mbps * 1_000_000) / 8  # Convert Mbps to bytes/s
        self.bytes_sent = 0
        self.start_time = time.time()
        self.enabled = max_mbps > 0

    async def throttle(self, chunk_size: int):
        """
        Apply throttling after sending a data chunk.

        Calculates the current transfer rate and introduces an `asyncio.sleep` delay
        if the rate exceeds the configured limit.

        Args:
            chunk_size: Size of the chunk just sent, in bytes.
        """
        if not self.enabled:
            return

        self.bytes_sent += chunk_size
        elapsed = time.time() - self.start_time
        
        if elapsed > 0:
            current_rate = self.bytes_sent / elapsed
            
            if current_rate > self.max_bytes_per_second:
                # Calculate sleep time to slow down
                excess_rate = current_rate - self.max_bytes_per_second
                sleep_time = (chunk_size / excess_rate) if excess_rate > 0 else 0
                
                if sleep_time > 0:
                    logger.debug(f"Throttling: sleeping {sleep_time:.3f}s")
                    await asyncio.sleep(sleep_time)

    def reset(self):
        """
        Reset the throttler's statistics.

        Clears the byte counter and resets the start time. Useful for reusing
        the throttler across multiple transfer phases.
        """
        self.bytes_sent = 0
        self.start_time = time.time()

    def get_current_speed(self) -> float:
        """
        Calculate the current average transfer speed.

        Returns:
            The transfer speed in megabits per second (Mbps).
        """
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            bytes_per_sec = self.bytes_sent / elapsed
            return (bytes_per_sec * 8) / 1_000_000  # Convert to Mbps
        return 0.0


class BandwidthThrottleService:
    """
    Service for managing multiple bandwidth throttlers.

    Maintains a registry of `BandwidthThrottler` instances keyed by transfer ID,
    enabling concurrent throttled transfers with independent rate limits.
    """

    def __init__(self):
        self.throttlers = {}  # transfer_id -> BandwidthThrottler

    def create_throttler(self, transfer_id: str, max_mbps: float) -> BandwidthThrottler:
        """
        Create and register a new throttler for a transfer.

        Args:
            transfer_id: Unique identifier for the transfer.
            max_mbps: Maximum speed limit for this transfer.

        Returns:
            The created `BandwidthThrottler` instance.
        """
        throttler = BandwidthThrottler(max_mbps)
        self.throttlers[transfer_id] = throttler
        logger.info(f"Created bandwidth throttler for {transfer_id}: {max_mbps} Mbps")
        return throttler

    def get_throttler(self, transfer_id: str) -> Optional[BandwidthThrottler]:
        """
        Retrieve an existing throttler by transfer ID.

        Args:
            transfer_id: The ID of the transfer.

        Returns:
            The `BandwidthThrottler` instance, or `None` if not found.
        """
        return self.throttlers.get(transfer_id)

    def remove_throttler(self, transfer_id: str):
        """
        Remove a throttler from the registry.

        Cleans up resources after a transfer completes.

        Args:
            transfer_id: The ID of the transfer to remove.
        """
        if transfer_id in self.throttlers:
            del self.throttlers[transfer_id]
            logger.info(f"Removed bandwidth throttler for {transfer_id}")


# Global instance
bandwidth_throttle_service = BandwidthThrottleService()
