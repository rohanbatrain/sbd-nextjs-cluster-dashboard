"""
# Request Router Service

This module acts as the **Traffic Controller** for the distributed cluster.
It intelligently routes HTTP requests to the appropriate node based on role and health.

## Domain Overview

Not all nodes are equal.
- **Master**: Handles Writes and Reads.
- **Replica**: Handles Reads only.
- **Routing**: Directing "Write" requests to Master and load-balancing "Read" requests.

## Key Features

### 1. Role-Based Routing
- **Write Splitting**: Automatically detects `POST`/`PUT`/`DELETE` and forwards to Master.
- **Read Distribution**: Distributes `GET` requests across Replicas for scaling.

### 2. Intelligent Forwarding
- **mTLS**: Secures inter-node communication with mutual TLS.
- **Headers**: Preserves original request context (User ID, Auth Token).
- **Fallback**: Tries to handle locally if routing fails (best effort).

## Usage Example

```python
# In a FastAPI middleware or endpoint
response = await request_router.route_request(request)
if response:
    # Request was forwarded and handled by another node
    return response
# Else: Handle locally
```
"""

import asyncio
from typing import Any, Dict, Optional

import httpx
from fastapi import Request, Response, HTTPException

from second_brain_database.config import settings
from second_brain_database.managers.cluster_manager import cluster_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.cluster_models import ClusterNode, NodeRole
from second_brain_database.services.load_balancer import load_balancer
from second_brain_database.utils.security_utils import get_client_ssl_params

logger = get_logger()


class RequestRouter:
    """
    Intelligent request routing for distributed SBD deployments.

    Routes incoming requests to the appropriate cluster node based on operation type
    and consistency requirements. Implements read/write splitting and automatic failover.

    **Routing Rules:**
    - **Write Operations** (`POST`, `PUT`, `PATCH`, `DELETE`): Always routed to master nodes.
    - **Read Operations** (`GET`): Distributed across replicas or masters based on read preference.

    **Features:**
    - Health-aware routing via load balancer
    - Automatic local fallback if no suitable nodes
    - Request forwarding with mTLS support
    - Performance metrics tracking
    """

    async def route_request(self, request: Request) -> Optional[Response]:
        """
        Route an incoming request to the appropriate cluster node.

        Determines whether the request should be handled locally or forwarded
        to another node based on operation type and current node role.

        Args:
            request: FastAPI `Request` object containing HTTP method, headers, and body.

        Returns:
            A `Response` if the request was forwarded to another node,
            or `None` if it should be handled by the current node.

        Raises:
            HTTPException: If routing fails and no fallback is available (503).
        """
        try:
            if not settings.CLUSTER_ENABLED:
                return None

            # Determine if this is a write or read operation
            is_write = request.method in ["POST", "PUT", "PATCH", "DELETE"]
            route_type = "write" if is_write else "read"

            # Get appropriate target role
            if is_write:
                # Route writes to masters
                target_role = NodeRole.MASTER
            else:
                # Route reads to replicas (or masters if no replicas)
                target_role = NodeRole.REPLICA

            # Select target node
            target_node = await load_balancer.select_node(
                algorithm=settings.CLUSTER_LOAD_BALANCING_ALGORITHM,
                client_ip=request.client.host if request.client else None,
                operation=route_type, # Pass operation type for selection logic
            )

            if not target_node:
                logger.warning("No nodes available for routing")
                # If no node is available, try to handle locally as a fallback
                if self._can_handle_locally_fallback(route_type):
                    request_routing_total.labels(
                        route_type=route_type,
                        target_role="local_fallback"
                    ).inc()
                    return None
                raise HTTPException(status_code=503, detail="No suitable node available for routing")

            # Check if we should route or handle locally
            if target_node.node_id == cluster_manager.node_id:
                # Handle locally
                return None

            # Forward request
            response = await self._forward_request(request, target_node)

            return response

        except Exception as e:
            logger.error(f"Failed to route request: {e}", exc_info=True)
            # Fallback to local handling if possible
            if self._can_handle_locally_fallback(route_type if 'route_type' in locals() else "unknown"):
                return None
            raise HTTPException(status_code=503, detail="Request routing failed")


    def _can_handle_locally(self, operation: str) -> bool:
        """
        Determine if the current node can handle the operation.

        Masters can handle all operations. Replicas can only handle reads,
        and writes always require forwarding to a master.

        Args:
            operation: The operation type (`write` or `read`).

        Returns:
            True if the current node can handle the operation.
        """
        if operation == "write":
            return settings.cluster_is_master
        else:
            # Reads can be handled by any node, but we might want to offload
            # if we are a master and have replicas available
            if settings.cluster_is_master and settings.CLUSTER_READ_PREFERENCE == "secondary":
                return False
            return True

    def _can_handle_locally_fallback(self, operation: str) -> bool:
        """
        Determine if the current node can handle the operation as a fallback.

        Used when routing fails. Only masters can handle writes even in fallback mode,
        but any node can handle reads.

        Args:
            operation: The operation type (`write` or `read`).

        Returns:
            True if fallback handling is allowed.
        """
        if operation == "write":
            # Only masters can write, even as fallback
            return settings.cluster_is_master
        else:
            # Any node can read as fallback
            return True

    def _get_client_id(self, request: Request) -> str:
        """
        Extract a unique client identifier for sticky sessions.

        Attempts to use session cookie first, then falls back to IP address
        (considering `X-Forwarded-For` header for proxied requests).

        Args:
            request: FastAPI `Request` object.

        Returns:
            A string identifier for the client.
        """
        # Try to get from session cookie
        session_id = request.cookies.get("session_id")
        if session_id:
            return session_id

        # Fallback to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0]
        
        return request.client.host if request.client else "unknown"

    async def _forward_request(self, request: Request, target_node: ClusterNode) -> Response:
        """
        Forward an HTTP request to a target cluster node.

        Reconstructs the request with proper headers (including cluster authentication)
        and sends it via mTLS if configured. Tracks request duration and success rate
        for load balancer metrics.

        Args:
            request: The original FastAPI `Request`.
            target_node: The target `ClusterNode` to forward to.

        Returns:
            A `Response` object with the content from the target node.

        Raises:
            HTTPException: If forwarding fails (503).
        """
        import time
        start_time = time.time()
        success = False

        try:
            # Prepare URL
            url = f"{target_node.endpoint}{request.url.path}"
            if request.url.query:
                url += f"?{request.url.query}"

            # Prepare headers
            headers = dict(request.headers)
            headers.pop("host", None)
            headers.pop("content-length", None)
            headers["X-Forwarded-From"] = cluster_manager.node_id
            
            if settings.CLUSTER_AUTH_TOKEN:
                headers["X-Cluster-Token"] = settings.CLUSTER_AUTH_TOKEN.get_secret_value()

            # Get request body
            body = await request.body()

            # Get SSL params
            ssl_params = get_client_ssl_params()

            # Forward request
            async with httpx.AsyncClient(timeout=settings.CLUSTER_REQUEST_TIMEOUT, **ssl_params) as client:
                response = await client.request(
                    method=request.method,
                    url=f"{target_node.endpoint}{request.url.path}",
                    headers=headers,
                    content=body,
                    params=request.query_params,
                )

            # Record success before returning
            success = response.status_code < 500
            
            # Return response
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
            )

        except Exception as e:
            logger.error(f"Failed to forward request to {target_node.node_id}: {e}")
            raise HTTPException(status_code=503, detail="Upstream node unavailable")
        finally:
            duration = time.time() - start_time
            await load_balancer.record_request(target_node.node_id, success, duration)


# Global request router instance
request_router = RequestRouter()
