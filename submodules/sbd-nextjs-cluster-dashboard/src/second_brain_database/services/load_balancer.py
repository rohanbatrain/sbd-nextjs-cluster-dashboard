"""
# Load Balancer Service

This module provides **Application-Level Load Balancing** for the distributed cluster.
It intelligently routes requests to healthy nodes to ensure high availability and performance.

## Domain Overview

In a distributed system, traffic must be distributed efficiently.
- **Algorithms**: Round Robin, Least Connections, Weighted Round Robin, IP Hash, Least Response Time.
- **Health Awareness**: Only routes traffic to nodes confirmed as healthy.
- **Circuit Breaker**: Fails fast when a node is struggling to prevent cascading failures.

## Key Features

### 1. Traffic Distribution
- **Dynamic Routing**: Selects the best node for each request based on real-time stats.
- **Sticky Sessions**: Ensures a client stays connected to the same node (optional).

### 2. Resilience Patterns
- **Circuit Breaker**: Automatically stops sending traffic to failing nodes.
- **Half-Open State**: Gradually tests recovering nodes before full reintegration.

## Usage Example

```python
# Select a node for a read operation
node = await load_balancer.select_node(
    client_id="client_123",
    operation="read"
)

if node:
    # Perform request...
    await load_balancer.record_request(node.node_id, success=True, duration=0.05)
```
"""

import asyncio
import hashlib
import time
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from second_brain_database.config import settings
from second_brain_database.managers.cluster_manager import cluster_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.cluster_models import (
    ClusterNode,
    LoadBalancingAlgorithm,
    NodeStatus,
)

logger = get_logger()


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class LoadBalancer:
    """
    Application-level load balancer with multiple algorithms and circuit breaker pattern.

    Distributes requests across healthy cluster nodes using various load balancing strategies.
    Implements circuit breaker pattern to prevent cascading failures.

    **Supported Algorithms:**
    - **Round Robin**: Distributes requests sequentially across nodes.
    - **Least Connections**: Routes to node with fewest active connections.
    - **Weighted Round Robin**: Uses node priority as weight.
    - **IP Hash**: Consistent hashing based on client ID.
    - **Least Response Time**: Routes to fastest responding node.

    **Circuit Breaker Pattern:**
    - **CLOSED**: Normal operation, requests flow through.
    - **OPEN**: Too many failures, requests fail fast.
    - **HALF_OPEN**: Testing if service recovered.

    **Features:**
    - Sticky sessions support (session affinity)
    - Health-aware routing (excludes unhealthy nodes)
    - Automatic failure tracking
    - Configurable circuit breaker thresholds
    """

    def __init__(self):
        """Initialize load balancer."""
        self.algorithm = LoadBalancingAlgorithm(settings.CLUSTER_LOAD_BALANCING_ALGORITHM)
        self._round_robin_index: int = 0
        self._connection_counts: Dict[str, int] = defaultdict(int)
        self._response_times: Dict[str, List[float]] = defaultdict(list)
        self._circuit_states: Dict[str, CircuitState] = defaultdict(lambda: CircuitState.CLOSED)
        self._circuit_failures: Dict[str, int] = defaultdict(int)
        self._circuit_opened_at: Dict[str, float] = {}
        self._sticky_sessions: Dict[str, str] = {}  # client_id -> node_id
        self._circuit_breaker_failures: Dict[str, List[datetime]] = defaultdict(list)
        self._circuit_breaker_state: Dict[str, str] = defaultdict(lambda: "closed")
        self._circuit_breaker_open_time: Dict[str, datetime] = {}


    async def select_node(
        self,
        nodes: Optional[List[ClusterNode]] = None,
        client_id: Optional[str] = None,
        operation: str = "read",
    ) -> Optional[ClusterNode]:
        """
        Select a node using the configured load balancing algorithm.

        Filters out unhealthy nodes and those with open circuits, then applies
        the selected algorithm. Supports sticky sessions for client affinity.

        Args:
            nodes: List of available nodes (defaults to all healthy nodes).
            client_id: Client identifier for sticky sessions (enables session affinity).
            operation: Operation type (`read` or `write`). Writes always go to master.

        Returns:
            The selected `ClusterNode`, or `None` if no nodes are available.
        """
        try:
            # Get available nodes if not provided
            if nodes is None:
                nodes = await self._get_available_nodes(operation)

            if not nodes:
                logger.warning("No available nodes for load balancing")
                return None

            # Filter out nodes with open circuits
            nodes = self._filter_circuit_breaker(nodes)

            if not nodes:
                logger.warning("All nodes have open circuits")
                return None

            # Check for sticky session
            if settings.CLUSTER_STICKY_SESSIONS and client_id:
                sticky_node = self._get_sticky_node(client_id, nodes)
                if sticky_node:
                    return sticky_node

            # Select node based on algorithm
            if self.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
                node = self._round_robin(nodes)
            elif self.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
                node = self._least_connections(nodes)
            elif self.algorithm == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
                node = self._weighted_round_robin(nodes)
            elif self.algorithm == LoadBalancingAlgorithm.IP_HASH:
                node = self._ip_hash(nodes, client_id or "default")
            elif self.algorithm == LoadBalancingAlgorithm.LEAST_RESPONSE_TIME:
                node = self._least_response_time(nodes)
            else:
                logger.warning(f"Unknown algorithm {self.algorithm}, using round robin")
                node = self._round_robin(nodes)

            # Set sticky session if enabled
            if settings.CLUSTER_STICKY_SESSIONS and client_id and node:
                self._sticky_sessions[client_id] = node.node_id

            return node

        except Exception as e:
            logger.error(f"Failed to select node: {e}", exc_info=True)
            return None

    async def record_request(
        self,
        node_id: str,
        success: bool,
        duration: float,
    ) -> None:
        """
        Record the result of a request for metrics and circuit breaker tracking.

        Updates connection counts, response time statistics, and circuit breaker state.
        Successes may close half-open circuits; failures may open circuits.

        Args:
            node_id: The ID of the node that processed the request.
            success: Whether the request succeeded.
            duration: Request duration in seconds.
        """
        # Update connection count
        current_conns = self._connection_counts.get(node_id, 0)
        if current_conns > 0:
            self._connection_counts[node_id] = current_conns - 1

        # Update response times
        if node_id not in self._response_times:
            self._response_times[node_id] = []
        self._response_times[node_id].append(duration)

        # Keep only last N response times
        if len(self._response_times[node_id]) > 100:
            self._response_times[node_id] = self._response_times[node_id][-100:]

        # Update circuit breaker
        if success:
            await self._record_success(node_id)
        else:
            await self._record_failure(node_id)


    async def increment_connection(self, node_id: str) -> None:
        """
        Increment the active connection count for a node.

        Used to track concurrent requests for the Least Connections algorithm.

        Args:
            node_id: The node ID.
        """
        self._connection_counts[node_id] += 1

    async def get_node_stats(self, node_id: str) -> Dict[str, Any]:
        """
        Get load balancing and health statistics for a specific node.

        Args:
            node_id: The node ID.

        Returns:
            A dictionary containing node statistics (connections, circuit state, response times).
        """
        response_times = self._response_times.get(node_id, [])
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0

        return {
            "node_id": node_id,
            "active_connections": self._connection_counts.get(node_id, 0),
            "circuit_state": self._circuit_states.get(node_id, CircuitState.CLOSED),
            "circuit_failures": self._circuit_failures.get(node_id, 0),
            "avg_response_time": avg_response_time,
            "total_requests": len(response_times),
        }

    async def reset_circuit(self, node_id: str) -> None:
        """
        Manually reset the circuit breaker for a node.

        Useful for administrative intervention after resolving node issues.

        Args:
            node_id: The node ID.
        """
        self._circuit_states[node_id] = CircuitState.CLOSED
        self._circuit_failures[node_id] = 0
        if node_id in self._circuit_opened_at:
            del self._circuit_opened_at[node_id]
        logger.info(f"Circuit breaker reset for node {node_id}")

    # Load balancing algorithms

    def _round_robin(self, nodes: List[ClusterNode]) -> ClusterNode:
        """
        Select the next node using round-robin distribution.

        Args:
            nodes: List of available nodes.

        Returns:
            The selected node.
        """
        node = nodes[self._round_robin_index % len(nodes)]
        self._round_robin_index += 1
        return node

    def _least_connections(self, nodes: List[ClusterNode]) -> ClusterNode:
        """
        Select the node with the fewest active connections.

        Args:
            nodes: List of available nodes.

        Returns:
            The node with the minimum connection count.
        """
        return min(nodes, key=lambda n: self._connection_counts.get(n.node_id, 0))

    def _weighted_round_robin(self, nodes: List[ClusterNode]) -> ClusterNode:
        """
        Select a node using weighted round-robin based on node priority.

        Higher priority nodes receive proportionally more requests.

        Args:
            nodes: List of available nodes.

        Returns:
            The selected node.
        """
        # Calculate total weight
        total_weight = sum(node.capabilities.priority for node in nodes)

        if total_weight == 0:
            return self._round_robin(nodes)

        # Generate weighted list
        weighted_nodes = []
        for node in nodes:
            weight = node.capabilities.priority
            weighted_nodes.extend([node] * weight)

        if not weighted_nodes:
            return nodes[0]

        node = weighted_nodes[self._round_robin_index % len(weighted_nodes)]
        self._round_robin_index += 1
        return node

    def _ip_hash(self, nodes: List[ClusterNode], client_id: str) -> ClusterNode:
        """
        Select a node using consistent hashing based on client ID.

        Ensures the same client always routes to the same node (when available).

        Args:
            nodes: List of available nodes.
            client_id: The client identifier.

        Returns:
            The selected node.
        """
        hash_value = int(hashlib.md5(client_id.encode()).hexdigest(), 16)
        index = hash_value % len(nodes)
        return nodes[index]

    def _least_response_time(self, nodes: List[ClusterNode]) -> ClusterNode:
        """
        Select the node with the lowest average response time.

        Nodes with no history are preferred (response time = 0).

        Args:
            nodes: Listof available nodes.

        Returns:
            The node with the best average response time.
        """
        def get_avg_response_time(node: ClusterNode) -> float:
            response_times = self._response_times.get(node.node_id, [])
            if not response_times:
                return 0.0  # Prefer nodes with no history
            return sum(response_times) / len(response_times)

        return min(nodes, key=get_avg_response_time)

    # Helper methods

    async def _get_available_nodes(self, operation: str) -> List[ClusterNode]:
        """
        Retrieve available nodes based on operation type.

        - **Write operations**: Only healthy master nodes that support writes.
        - **Read operations**: Any healthy node that supports reads.

        Args:
            operation: The operation type (`write` or `read`).

        Returns:
            List of eligible nodes.
        """
        try:
            if operation == "write":
                # Writes go to masters only
                nodes = await cluster_manager.list_nodes(status=NodeStatus.HEALTHY)
                return [n for n in nodes if n.is_master and n.capabilities.supports_writes]
            else:
                # Reads can go to any healthy node
                nodes = await cluster_manager.list_nodes(status=NodeStatus.HEALTHY)
                return [n for n in nodes if n.capabilities.supports_reads]

        except Exception as e:
            logger.error(f"Failed to get available nodes: {e}", exc_info=True)
            return []

    def _get_sticky_node(
        self,
        client_id: str,
        nodes: List[ClusterNode],
    ) -> Optional[ClusterNode]:
        """
        Retrieve the sticky session node for a client.

        Args:
            client_id: The client identifier.
            nodes: List of available nodes.

        Returns:
            The sticky node if found and available, otherwise `None`.
        """
        sticky_node_id = self._sticky_sessions.get(client_id)
        if sticky_node_id:
            for node in nodes:
                if node.node_id == sticky_node_id:
                    return node
        return None

    def _filter_circuit_breaker(self, nodes: List[ClusterNode]) -> List[ClusterNode]:
        """
        Filter out nodes with open circuit breakers.

        Circuits transition to HALF_OPEN after timeout for recovery testing.

        Args:
            nodes: List of nodes to filter.

        Returns:
            List of nodes with closed or half-open circuits.
        """
        if not settings.CLUSTER_CIRCUIT_BREAKER_ENABLED:
            return nodes

        available_nodes = []
        current_time = time.time()

        for node in nodes:
            circuit_state = self._circuit_states.get(node.node_id, CircuitState.CLOSED)

            if circuit_state == CircuitState.CLOSED:
                available_nodes.append(node)
            elif circuit_state == CircuitState.OPEN:
                # Check if timeout has passed
                opened_at = self._circuit_opened_at.get(node.node_id, 0)
                if current_time - opened_at >= settings.CLUSTER_CIRCUIT_BREAKER_TIMEOUT:
                    # Transition to half-open
                    self._circuit_states[node.node_id] = CircuitState.HALF_OPEN
                    available_nodes.append(node)
            elif circuit_state == CircuitState.HALF_OPEN:
                # Allow limited requests in half-open state
                available_nodes.append(node)

        return available_nodes

    async def _record_failure(self, node_id: str) -> None:
        """
        Record a request failure for circuit breaker tracking.

        Increments failure count and opens the circuit if threshold exceeded.

        Args:
            node_id: The node ID.
        """
        if not settings.CLUSTER_CIRCUIT_BREAKER_ENABLED:
            return

            self._circuit_opened_at[node_id] = time.time()
            logger.warning(f"Circuit breaker reopened for node {node_id}")

    async def _record_success(self, node_id: str) -> None:
        """
        Record a request success for circuit breaker tracking.

        Closes the circuit if in HALF_OPEN state; decrements failure count if CLOSED.

        Args:
            node_id: The node ID.
        """
        if not settings.CLUSTER_CIRCUIT_BREAKER_ENABLED:
            return

        circuit_state = self._circuit_states.get(node_id, CircuitState.CLOSED)

        if circuit_state == CircuitState.HALF_OPEN:
            # Success in half-open state, close circuit
            self._circuit_states[node_id] = CircuitState.CLOSED
            self._circuit_failures[node_id] = 0
            if node_id in self._circuit_opened_at:
                del self._circuit_opened_at[node_id]
            logger.info(f"Circuit breaker closed for node {node_id}")
        elif circuit_state == CircuitState.CLOSED:
            # Reset failure count on success
            self._circuit_failures[node_id] = max(0, self._circuit_failures[node_id] - 1)


# Global load balancer instance
load_balancer = LoadBalancer()
