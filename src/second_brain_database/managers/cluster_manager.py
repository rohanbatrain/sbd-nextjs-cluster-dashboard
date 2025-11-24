"""
Cluster manager for distributed SBD architecture.

This module provides core cluster management functionality including node discovery,
health monitoring, leader election, and topology management.
"""

import asyncio
import hashlib
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from second_brain_database.utils.security_utils import get_client_ssl_params

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.services.cluster_audit_service import cluster_audit_service
from second_brain_database.utils.security_utils import get_client_ssl_params
from second_brain_database.models.cluster_models import (
    ClusterHealth,
    ClusterNode,
    ClusterTopology,
    NodeHealth,
    NodeRole,
    NodeStatus,
    ReplicationMetrics,
    TopologyType,
)

logger = get_logger()


class ClusterManager:
    """
    Manages distributed cluster operations for high-availability SBD deployments.

    Provides complete cluster orchestration including:
    - **Node discovery**: Automatic registration and health tracking
    - **Leader election**: Priority-based leader selection for coordination
    - **Health monitoring**: Continuous heartbeat and failure detection
    - **Topology management**: Master/replica role management
    - **Failover**: Automatic promotion/demotion on node failures

    **Architecture:**
    - **Master nodes**: Handle writes, participate in leader election
    - **Replica nodes**: Read-only, replicate from masters
    - **Heartbeat**: Periodic health checks (configurable interval)
    - **Failure detection**: Stale heartbeat threshold triggers unhealthy status

    **Background Tasks:**
    - Heartbeat loop: Updates node health every N seconds
    - Health check loop: Monitors all nodes for failures
    - Leader election loop: Ensures cluster always has a healthy leader

    **Configuration:**
    - `CLUSTER_ENABLED`: Enable/disable cluster mode
    - `CLUSTER_NODE_ID`: Unique node identifier
    - `CLUSTER_NODE_ROLE`: `master` or `replica`
    - `CLUSTER_HEARTBEAT_INTERVAL`: Seconds between heartbeats
    - `CLUSTER_FAILURE_THRESHOLD`: Missed heartbeats before unhealthy
    """

    def __init__(self):
        """Initialize cluster manager."""
        self.node_id: Optional[str] = None
        self.is_initialized: bool = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._leader_election_task: Optional[asyncio.Task] = None
        self._current_leader: Optional[str] = None
        self._election_timeout: float = 0.0

    async def initialize(self) -> bool:
        """
        Initialize cluster manager and register this node.

        Returns:
            bool: True if initialization successful
        """
        try:
            if not settings.CLUSTER_ENABLED:
                logger.info("Cluster mode is disabled")
                return False

            # Generate or use configured node ID
            self.node_id = settings.CLUSTER_NODE_ID or self._generate_node_id()
            logger.info(f"Initializing cluster manager for node: {self.node_id}")

            # Create cluster collections if they don't exist
            await self._ensure_collections()

            # Register this node
            await self.register_node()

            # Start background tasks
            await self._start_background_tasks()

            self.is_initialized = True
            logger.info(f"Cluster manager initialized successfully for node {self.node_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize cluster manager: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown cluster manager and cleanup resources."""
        try:
            logger.info(f"Shutting down cluster manager for node {self.node_id}")

            # Cancel background tasks
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            if self._health_check_task:
                self._health_check_task.cancel()
            if self._leader_election_task:
                self._leader_election_task.cancel()

            # Update node status to offline
            if self.node_id:
                await self._update_node_status(NodeStatus.OFFLINE)

            self.is_initialized = False
            logger.info("Cluster manager shutdown complete")

        except Exception as e:
            logger.error(f"Error during cluster manager shutdown: {e}", exc_info=True)

    async def register_node(
        self,
        hostname: Optional[str] = None,
        port: Optional[int] = None,
        owner_user_id: Optional[str] = None,
    ) -> str:
        """
        Register this node in the cluster.

        Args:
            hostname: Node hostname (defaults to advertise address)
            port: Node port (defaults to configured port)
            owner_user_id: Owner user ID for validation

        Returns:
            str: Node ID
        """
        try:
            collection = db_manager.get_collection("cluster_nodes")

            # Prepare node data
            hostname = hostname or settings.CLUSTER_ADVERTISE_ADDRESS or settings.HOST
            port = port or settings.PORT

            node_data = {
                "node_id": self.node_id,
                "hostname": hostname,
                "port": port,
                "role": settings.CLUSTER_NODE_ROLE,
                "status": NodeStatus.JOINING,
                "capabilities": {
                    "max_connections": 1000,
                    "storage_gb": 500.0,
                    "cpu_cores": 4,
                    "memory_gb": 16.0,
                    "supports_writes": settings.cluster_is_master,
                    "supports_reads": True,
                    "priority": 100 if settings.cluster_is_master else 50,
                },
                "health": {
                    "last_heartbeat": datetime.now(timezone.utc),
                    "uptime_seconds": 0,
                    "cpu_usage": 0.0,
                    "memory_usage": 0.0,
                    "disk_usage": 0.0,
                    "active_connections": 0,
                    "requests_per_second": 0.0,
                },
                "replication": {
                    "lag_seconds": 0.0,
                    "events_pending": 0,
                    "events_replicated": 0,
                    "events_failed": 0,
                    "last_sync": None,
                    "throughput_events_per_sec": 0.0,
                },
                "owner_user_id": owner_user_id,
                "cluster_token_hash": self._hash_cluster_token() if settings.CLUSTER_AUTH_TOKEN else None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            # Upsert node
            await collection.update_one(
                {"node_id": self.node_id},
                {"$set": node_data},
                upsert=True
            )

            # Update status to healthy after successful registration
            await self._update_node_status(NodeStatus.HEALTHY)

            # Audit log
            await cluster_audit_service.log_event(
                event_type="node_registered",
                node_id=self.node_id,
                details={"role": settings.CLUSTER_NODE_ROLE, "hostname": hostname, "port": port},
                user_id=owner_user_id
            )

            logger.info(f"Node {self.node_id} registered successfully as {settings.CLUSTER_NODE_ROLE}")
            return self.node_id

        except Exception as e:
            logger.error(f"Failed to register node {self.node_id}: {e}", exc_info=True)
            raise

    async def get_node(self, node_id: str) -> Optional[ClusterNode]:
        """
        Get node information by ID.

        Args:
            node_id: Node ID

        Returns:
            ClusterNode or None if not found
        """
        try:
            collection = db_manager.get_collection("cluster_nodes")
            node_data = await collection.find_one({"node_id": node_id})

            if not node_data:
                return None

            return ClusterNode(**node_data)

        except Exception as e:
            logger.error(f"Failed to get node {node_id}: {e}", exc_info=True)
            return None

    async def list_nodes(
        self,
        role: Optional[NodeRole] = None,
        status: Optional[NodeStatus] = None,
    ) -> List[ClusterNode]:
        """
        List all nodes in the cluster.

        Args:
            role: Filter by node role
            status: Filter by node status

        Returns:
            List of ClusterNode objects
        """
        try:
            collection = db_manager.get_collection("cluster_nodes")

            query = {}
            if role:
                query["role"] = role
            if status:
                query["status"] = status

            cursor = collection.find(query)
            nodes = []

            async for node_data in cursor:
                try:
                    nodes.append(ClusterNode(**node_data))
                except Exception as e:
                    logger.warning(f"Failed to parse node data: {e}")
                    continue

            return nodes

        except Exception as e:
            logger.error(f"Failed to list nodes: {e}", exc_info=True)
            return []

    async def remove_node(self, node_id: str) -> bool:
        """
        Remove a node from the cluster.

        Args:
            node_id: Node ID to remove

        Returns:
            bool: True if successful
        """
        try:
            collection = db_manager.get_collection("cluster_nodes")

            # Update status to leaving first
            await collection.update_one(
                {"node_id": node_id},
                {"$set": {"status": NodeStatus.LEAVING, "updated_at": datetime.now(timezone.utc)}}
            )

            # Delete the node
            result = await collection.delete_one({"node_id": node_id})

            if result.deleted_count > 0:
                # Audit log
                await cluster_audit_service.log_event(
                    event_type="node_removed",
                    node_id=node_id,
                    details={"reason": "manual_removal"},
                    severity="warning"
                )
                logger.info(f"Node {node_id} removed from cluster")
                return True
            else:
                logger.warning(f"Node {node_id} not found for removal")
                return False

        except Exception as e:
            logger.error(f"Failed to remove node {node_id}: {e}", exc_info=True)
            return False

    async def get_cluster_health(self) -> ClusterHealth:
        """
        Get aggregated cluster health status.

        Returns:
            ClusterHealth object
        """
        try:
            nodes = await self.list_nodes()

            total_nodes = len(nodes)
            healthy_nodes = sum(1 for n in nodes if n.status == NodeStatus.HEALTHY)
            degraded_nodes = sum(1 for n in nodes if n.status == NodeStatus.DEGRADED)
            unhealthy_nodes = sum(1 for n in nodes if n.status == NodeStatus.UNHEALTHY)
            offline_nodes = sum(1 for n in nodes if n.status == NodeStatus.OFFLINE)
            master_count = sum(1 for n in nodes if n.role == NodeRole.MASTER)
            replica_count = sum(1 for n in nodes if n.role == NodeRole.REPLICA)

            # Calculate replication metrics
            replication_lags = [n.replication.lag_seconds for n in nodes if n.replication.lag_seconds > 0]
            avg_replication_lag = sum(replication_lags) / len(replication_lags) if replication_lags else 0.0
            max_replication_lag = max(replication_lags) if replication_lags else 0.0

            total_events_pending = sum(n.replication.events_pending for n in nodes)
            total_events_failed = sum(n.replication.events_failed for n in nodes)

            return ClusterHealth(
                cluster_id=self._get_cluster_id(),
                total_nodes=total_nodes,
                healthy_nodes=healthy_nodes,
                degraded_nodes=degraded_nodes,
                unhealthy_nodes=unhealthy_nodes,
                offline_nodes=offline_nodes,
                master_count=master_count,
                replica_count=replica_count,
                avg_replication_lag=avg_replication_lag,
                max_replication_lag=max_replication_lag,
                total_events_pending=total_events_pending,
                total_events_failed=total_events_failed,
                last_updated=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.error(f"Failed to get cluster health: {e}", exc_info=True)
            return ClusterHealth(
                cluster_id=self._get_cluster_id(),
                last_updated=datetime.now(timezone.utc),
            )

    async def promote_node(self, node_id: str, force: bool = False) -> bool:
        """
        Promote a replica node to master.

        Args:
            node_id: Node ID to promote
            force: Force promotion even if unhealthy

        Returns:
            bool: True if successful
        """
        try:
            collection = db_manager.get_collection("cluster_nodes")

            # Get node
            node = await self.get_node(node_id)
            if not node:
                logger.error(f"Node {node_id} not found")
                return False

            # Check if already master
            if node.role == NodeRole.MASTER:
                logger.warning(f"Node {node_id} is already a master")
                return True

            # Check health unless forced
            if not force and node.status != NodeStatus.HEALTHY:
                logger.error(f"Cannot promote unhealthy node {node_id} without force flag")
                return False

            # Update node role
            await collection.update_one(
                {"node_id": node_id},
                {
                    "$set": {
                        "role": NodeRole.MASTER,
                        "capabilities.supports_writes": True,
                        "capabilities.priority": 100,
                        "updated_at": datetime.now(timezone.utc),
                    }
                }
            )

            # Audit log
            await cluster_audit_service.log_event(
                event_type="node_promoted",
                node_id=node_id,
                details={"new_role": "master", "force": force},
                severity="warning"
            )

            logger.info(f"Node {node_id} promoted to master")
            return True

        except Exception as e:
            logger.error(f"Failed to promote node {node_id}: {e}", exc_info=True)
            return False

    async def demote_node(self, node_id: str) -> bool:
        """
        Demote a master node to replica.

        Args:
            node_id: Node ID to demote

        Returns:
            bool: True if successful
        """
        try:
            collection = db_manager.get_collection("cluster_nodes")

            # Get node
            node = await self.get_node(node_id)
            if not node:
                logger.error(f"Node {node_id} not found")
                return False

            # Check if already replica
            if node.role == NodeRole.REPLICA:
                logger.warning(f"Node {node_id} is already a replica")
                return True

            # Update node role
            await collection.update_one(
                {"node_id": node_id},
                {
                    "$set": {
                        "role": NodeRole.REPLICA,
                        "capabilities.supports_writes": False,
                        "capabilities.priority": 50,
                        "updated_at": datetime.now(timezone.utc),
                    }
                }
            )

            # Audit log
            await cluster_audit_service.log_event(
                event_type="node_demoted",
                node_id=node_id,
                details={"new_role": "replica"},
                severity="warning"
            )

            logger.info(f"Node {node_id} demoted to replica")
            return True

        except Exception as e:
            logger.error(f"Failed to demote node {node_id}: {e}", exc_info=True)
            return False

    async def elect_leader(self) -> Optional[str]:
        """
        Perform leader election using priority-based selection.

        Returns:
            str: Elected leader node ID or None
        """
        try:
            # Get all healthy master nodes
            masters = await self.list_nodes(role=NodeRole.MASTER, status=NodeStatus.HEALTHY)

            if not masters:
                logger.warning("No healthy master nodes available for leader election")
                return None

            # Sort by priority (highest first)
            masters.sort(key=lambda n: n.capabilities.priority, reverse=True)

            # Select leader (highest priority)
            leader = masters[0]
            self._current_leader = leader.node_id

            # Audit log
            await cluster_audit_service.log_event(
                event_type="leader_elected",
                node_id=leader.node_id,
                details={"priority": leader.capabilities.priority},
                severity="info"
            )

            logger.info(f"Leader elected: {leader.node_id} (priority: {leader.capabilities.priority})")
            return leader.node_id

        except Exception as e:
            logger.error(f"Failed to elect leader: {e}", exc_info=True)
            return None

    async def get_current_leader(self) -> Optional[str]:
        """
        Get current cluster leader.

        Returns:
            str: Leader node ID or None
        """
        if not self._current_leader:
            self._current_leader = await self.elect_leader()
        return self._current_leader

    # Private helper methods

    def _generate_node_id(self) -> str:
        """Generate a unique node ID."""
        return f"node-{uuid.uuid4().hex[:12]}"

    def _get_cluster_id(self) -> str:
        """Get cluster ID (based on topology or default)."""
        return "cluster-default"

    def _hash_cluster_token(self) -> str:
        """Hash the cluster authentication token."""
        if not settings.CLUSTER_AUTH_TOKEN:
            return ""
        token = settings.CLUSTER_AUTH_TOKEN.get_secret_value()
        return hashlib.sha256(token.encode()).hexdigest()

    async def _ensure_collections(self) -> None:
        """Ensure cluster collections exist with proper indexes."""
        try:
            # Create indexes for cluster_nodes
            nodes_collection = db_manager.get_collection("cluster_nodes")
            await nodes_collection.create_index("node_id", unique=True)
            await nodes_collection.create_index("role")
            await nodes_collection.create_index("status")
            await nodes_collection.create_index("updated_at")

            # Create indexes for cluster_topology
            topology_collection = db_manager.get_collection("cluster_topology")
            await topology_collection.create_index("topology_id", unique=True)

            # Create indexes for cluster_events
            events_collection = db_manager.get_collection("cluster_events")
            await events_collection.create_index("timestamp")
            await events_collection.create_index("event_type")
            await events_collection.create_index("node_id")

            logger.info("Cluster collections and indexes created successfully")

        except Exception as e:
            logger.error(f"Failed to ensure cluster collections: {e}", exc_info=True)

    async def _update_node_status(self, status: NodeStatus) -> None:
        """Update this node's status."""
        try:
            collection = db_manager.get_collection("cluster_nodes")
            await collection.update_one(
                {"node_id": self.node_id},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.now(timezone.utc),
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to update node status: {e}", exc_info=True)

    async def _start_background_tasks(self) -> None:
        """Start background tasks for heartbeat and health checks."""
        try:
            # Start heartbeat task
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Start health check task
            self._health_check_task = asyncio.create_task(self._health_check_loop())

            # Start leader election task if master
            if settings.cluster_is_master:
                self._leader_election_task = asyncio.create_task(self._leader_election_loop())

            logger.info("Cluster background tasks started")

        except Exception as e:
            logger.error(f"Failed to start background tasks: {e}", exc_info=True)

    async def _send_heartbeat(self, node: ClusterNode) -> bool:
        """Send heartbeat to a node."""
        try:
            headers = {}
            if settings.CLUSTER_AUTH_TOKEN:
                headers["X-Cluster-Token"] = settings.CLUSTER_AUTH_TOKEN.get_secret_value()

            # Get SSL params
            ssl_params = get_client_ssl_params()

            async with httpx.AsyncClient(timeout=2.0, **ssl_params) as client:
                response = await client.get(
                    f"{node.endpoint}/cluster/health",
                    headers=headers
                )
                return response.status_code == 200

        except Exception:
            return False

    async def _heartbeat_loop(self) -> None:
        """Periodic heartbeat to update node health."""
        while True:
            try:
                await asyncio.sleep(settings.CLUSTER_HEARTBEAT_INTERVAL)

                collection = db_manager.get_collection("cluster_nodes")
                await collection.update_one(
                    {"node_id": self.node_id},
                    {
                        "$set": {
                            "health.last_heartbeat": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                        },
                        "$inc": {
                            "health.uptime_seconds": settings.CLUSTER_HEARTBEAT_INTERVAL,
                        }
                    }
                )

            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}", exc_info=True)

    async def _health_check_loop(self) -> None:
        """Periodic health check of all nodes."""
        while True:
            try:
                await asyncio.sleep(settings.CLUSTER_HEARTBEAT_INTERVAL * 2)

                # Check all nodes for stale heartbeats
                collection = db_manager.get_collection("cluster_nodes")
                threshold = datetime.now(timezone.utc).timestamp() - (
                    settings.CLUSTER_HEARTBEAT_INTERVAL * settings.CLUSTER_FAILURE_THRESHOLD
                )

                # Mark nodes as unhealthy if heartbeat is stale
                await collection.update_many(
                    {
                        "health.last_heartbeat": {"$lt": datetime.fromtimestamp(threshold, tz=timezone.utc)},
                        "status": {"$ne": NodeStatus.OFFLINE},
                    },
                    {
                        "$set": {
                            "status": NodeStatus.UNHEALTHY,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    }
                )

            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)

    async def _leader_election_loop(self) -> None:
        """Periodic leader election check."""
        while True:
            try:
                # Random election timeout to prevent split votes
                self._election_timeout = random.uniform(
                    settings.CLUSTER_ELECTION_TIMEOUT_MIN / 1000,
                    settings.CLUSTER_ELECTION_TIMEOUT_MAX / 1000,
                )
                await asyncio.sleep(self._election_timeout)

                # Check if leader is still healthy
                if self._current_leader:
                    leader_node = await self.get_node(self._current_leader)
                    if not leader_node or leader_node.status != NodeStatus.HEALTHY:
                        logger.warning(f"Leader {self._current_leader} is unhealthy, triggering re-election")
                        await self.elect_leader()
                else:
                    # No leader, trigger election
                    await self.elect_leader()

            except asyncio.CancelledError:
                logger.info("Leader election loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in leader election loop: {e}", exc_info=True)


# Global cluster manager instance
cluster_manager = ClusterManager()
