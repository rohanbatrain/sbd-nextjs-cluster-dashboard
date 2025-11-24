"""
HTTP connection pool for efficient node-to-node communication.

This module provides a connection pool manager to reduce overhead
of creating new HTTP connections for every cluster operation.
"""

import asyncio
from typing import Dict, Optional
import httpx

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.security_utils import get_client_ssl_params

logger = get_logger()


class ConnectionPoolManager:
    """
    Manages HTTP connection pools for cluster nodes.
    
    Benefits:
    - Reduces connection overhead (TCP handshake, TLS negotiation)
    - Improves latency for node-to-node communication
    - Configurable pool size and timeouts
    - Automatic connection health monitoring
    """

    def __init__(
        self,
        pool_size: int = 10,
        timeout: float = 30.0,
        keepalive_expiry: float = 30.0
    ):
        """
        Initialize connection pool manager.
        
        Args:
            pool_size: Maximum connections per node (default: 10)
            timeout: Request timeout in seconds (default: 30)
            keepalive_expiry: Keep-alive time in seconds (default: 30)
        """
        self.pool_size = pool_size
        self.timeout = timeout
        self.keepalive_expiry = keepalive_expiry
        
        # Pool of clients per endpoint
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._lock = asyncio.Lock()

    async def get_client(self, endpoint: str) -> httpx.AsyncClient:
        """
        Get or create an HTTP client for the given endpoint.
        
        Args:
            endpoint: Node endpoint URL
            
        Returns:
            httpx.AsyncClient: Pooled async HTTP client
        """
        async with self._lock:
            if endpoint not in self._clients or self._clients[endpoint].is_closed:
                # Create new client with connection pooling
                ssl_params = get_client_ssl_params()
                
                limits = httpx.Limits(
                    max_keepalive_connections=self.pool_size,
                    max_connections=self.pool_size,
                    keepalive_expiry=self.keepalive_expiry
                )
                
                self._clients[endpoint] = httpx.AsyncClient(
                    timeout=self.timeout,
                    limits=limits,
                    **ssl_params
                )
                
                logger.debug(f"Created connection pool for {endpoint} (size={self.pool_size})")
            
            return self._clients[endpoint]

    async def remove_client(self, endpoint: str):
        """
        Remove and close client for an endpoint.
        
        Args:
            endpoint: Node endpoint URL
        """
        async with self._lock:
            if endpoint in self._clients:
                await self._clients[endpoint].aclose()
                del self._clients[endpoint]
                logger.debug(f"Removed connection pool for {endpoint}")

    async def close_all(self):
        """Close all pooled connections."""
        async with self._lock:
            for endpoint, client in list(self._clients.items()):
                await client.aclose()
                logger.debug(f"Closed connection pool for {endpoint}")
            
            self._clients.clear()
            logger.info("Closed all connection pools")

    def get_stats(self) -> Dict:
        """Get connection pool statistics."""
        return {
            "active_pools": len(self._clients),
            "pool_size": self.pool_size,
            "timeout": self.timeout,
            "endpoints": list(self._clients.keys())
        }


# Global connection pool manager
connection_pool = ConnectionPoolManager(
    pool_size=getattr(settings, "CLUSTER_CONNECTION_POOL_SIZE", 10),
    timeout=settings.CLUSTER_REQUEST_TIMEOUT,
    keepalive_expiry=30.0
)
