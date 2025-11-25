"""
# Cluster Management Models

This module defines the **distributed system primitives** for the Second Brain Database.
It handles node coordination, leader election, data replication, and health monitoring
across a multi-node cluster.

## Domain Model Overview

The cluster architecture consists of:

- **Nodes**: Individual instances of the SBD service (Master/Replica/Standalone).
- **Topology**: The structural configuration of the cluster (e.g., Master-Slave, Multi-Master).
- **Replication**: The mechanism for synchronizing data changes between nodes.
- **Failover**: Automated recovery procedures when a master node fails.

## Key Features

### 1. Node Roles & Lifecycle
- **Master**: Handles writes and replicates to replicas.
- **Replica**: Read-only copy of the data.
- **Standalone**: Isolated instance (default for dev).
- **Status Transitions**: `joining` → `healthy` → `degraded` → `unhealthy` → `offline`.

### 2. Replication Strategies
- **Async**: Fire-and-forget replication (high performance, eventual consistency).
- **Sync**: Wait for acknowledgement from replicas (strong consistency, higher latency).
- **Semi-Sync**: Wait for at least one replica.

### 3. High Availability
- **Load Balancing**: Strategies like Round Robin, Least Connections.
- **Circuit Breakers**: Prevent cascading failures by isolating unhealthy nodes.
- **Leader Election**: Priority-based promotion of replicas to master.

## Usage Examples

### Configuring a Cluster Topology

```python
topology = ClusterTopology(
    topology_id="topo_primary",
    topology_type=TopologyType.MASTER_SLAVE,
    replication_factor=3,
    failover=FailoverConfig(
        auto_failover=True,
        min_healthy_replicas=1
    )
)
```

### Registering a New Node

```python
node = NodeRegistrationRequest(
    hostname="10.0.1.5",
    role=NodeRole.REPLICA,
    cluster_token="secret-token-123",
    owner_user_id="admin_user"
)
```

## Module Attributes

Attributes:
    NodeRole (Enum): Roles a node can take (Master, Replica, Standalone).
    NodeStatus (Enum): Health states of a node.
    TopologyType (Enum): Supported cluster architectures.
    ReplicationMode (Enum): Consistency levels for data replication.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class NodeRole(str, Enum):
    """Enumeration of node roles in the cluster.

    Defines the responsibilities and capabilities of a node within the distributed system.

    Attributes:
        STANDALONE: Isolated instance, typically for development or single-node deployments.
        MASTER: Primary node handling write operations and replication coordination.
        REPLICA: Secondary node handling read operations and receiving updates from Master.
    """
    STANDALONE = "standalone"
    MASTER = "master"
    REPLICA = "replica"


class NodeStatus(str, Enum):
    """Enumeration of node health statuses.

    Represents the current operational state of a node in the cluster lifecycle.

    Attributes:
        HEALTHY: Node is fully operational and passing health checks.
        DEGRADED: Node is operational but experiencing issues (e.g., high latency, resource pressure).
        UNHEALTHY: Node is failing health checks or unresponsive.
        OFFLINE: Node is confirmed down or manually taken out of rotation.
        JOINING: Node is in the process of registering and syncing with the cluster.
        LEAVING: Node is gracefully shutting down or being removed from the cluster.
    """
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    JOINING = "joining"
    LEAVING = "leaving"


class TopologyType(str, Enum):
    """Enumeration of cluster topology types.

    Defines the architectural pattern of the cluster.

    Attributes:
        STANDALONE: Single node deployment.
        MASTER_SLAVE: One writer (Master) and multiple readers (Slaves/Replicas).
        MASTER_MASTER: Multiple nodes can handle writes (Active-Active).
        MULTI_MASTER: Complex multi-region or sharded setup with multiple write points.
    """
    STANDALONE = "standalone"
    MASTER_SLAVE = "master-slave"
    MASTER_MASTER = "master-master"
    MULTI_MASTER = "multi-master"


class ReplicationMode(str, Enum):
    """Enumeration of data replication modes.

    Controls the consistency guarantees and performance trade-offs for write operations.

    Attributes:
        ASYNC: Writes return immediately; replication happens in background (Eventual Consistency).
        SYNC: Writes wait for acknowledgement from all replicas (Strong Consistency).
        SEMI_SYNC: Writes wait for acknowledgement from at least one replica (Balanced).
    """
    ASYNC = "async"
    SYNC = "sync"
    SEMI_SYNC = "semi-sync"


class LoadBalancingAlgorithm(str, Enum):
    """Enumeration of load balancing algorithms.

    Strategies for distributing traffic across healthy nodes.

    Attributes:
        ROUND_ROBIN: Cycles through nodes in order.
        LEAST_CONNECTIONS: Sends traffic to the node with the fewest active connections.
        WEIGHTED_ROUND_ROBIN: Round robin weighted by node capacity/priority.
        IP_HASH: Hashes client IP to ensure sticky sessions.
        LEAST_RESPONSE_TIME: Selects node with the lowest latency.
    """
    ROUND_ROBIN = "round-robin"
    LEAST_CONNECTIONS = "least-connections"
    WEIGHTED_ROUND_ROBIN = "weighted-round-robin"
    IP_HASH = "ip-hash"
    LEAST_RESPONSE_TIME = "least-response-time"


class EventStatus(str, Enum):
    """Enumeration of replication event statuses.

    Tracks the lifecycle of a data synchronization event.

    Attributes:
        PENDING: Event created but not yet processed.
        REPLICATING: Event is currently being sent to targets.
        REPLICATED: Event successfully applied to all targets.
        FAILED: Event failed to replicate after retries.
        RETRYING: Event failed but is queued for retry.
    """
    PENDING = "pending"
    REPLICATING = "replicating"
    REPLICATED = "replicated"
    FAILED = "failed"
    RETRYING = "retrying"


class NodeCapabilities(BaseModel):
    """Model representing a node's resource capabilities and limits.

    Used for load balancing decisions and capacity planning.

    Attributes:
        max_connections (int): Maximum concurrent connections allowed. Defaults to 1000.
        storage_gb (float): Total storage capacity in Gigabytes. Defaults to 100.0.
        cpu_cores (int): Number of available CPU cores. Defaults to 4.
        memory_gb (float): Total RAM in Gigabytes. Defaults to 16.0.
        supports_writes (bool): Whether the node can accept write operations.
        supports_reads (bool): Whether the node can accept read operations.
        priority (int): Priority score for leader election (0-100). Higher wins. Defaults to 50.
    """
    max_connections: int = Field(default=1000, ge=1, description="Max concurrent connections.")
    storage_gb: float = Field(default=100.0, ge=0, description="Storage capacity in GB.")
    cpu_cores: int = Field(default=4, ge=1, description="Number of CPU cores.")
    memory_gb: float = Field(default=16.0, ge=0, description="RAM in GB.")
    supports_writes: bool = Field(default=True, description="Can handle writes.")
    supports_reads: bool = Field(default=True, description="Can handle reads.")
    priority: int = Field(default=50, ge=0, le=100, description="Leader election priority.")


class NodeHealth(BaseModel):
    """Model representing real-time node health metrics.

    Collected via heartbeats to monitor cluster stability.

    Attributes:
        last_heartbeat (datetime): Timestamp of the last received heartbeat.
        uptime_seconds (int): Total seconds the node has been running.
        cpu_usage (float): Current CPU utilization percentage (0-100).
        memory_usage (float): Current Memory utilization percentage (0-100).
        disk_usage (float): Current Disk utilization percentage (0-100).
        active_connections (int): Current number of active client connections.
        requests_per_second (float): Current throughput rate.
    """
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last heartbeat timestamp.")
    uptime_seconds: int = Field(default=0, ge=0, description="Uptime in seconds.")
    cpu_usage: float = Field(default=0.0, ge=0, le=100, description="CPU usage %.")
    memory_usage: float = Field(default=0.0, ge=0, le=100, description="Memory usage %.")
    disk_usage: float = Field(default=0.0, ge=0, le=100, description="Disk usage %.")
    active_connections: int = Field(default=0, ge=0, description="Active connections.")
    requests_per_second: float = Field(default=0.0, ge=0, description="Requests/sec.")


class ReplicationMetrics(BaseModel):
    """Model representing replication performance metrics for a node.

    Attributes:
        lag_seconds (float): Time difference between master and replica data.
        events_pending (int): Number of events queued for replication.
        events_replicated (int): Total count of successfully replicated events.
        events_failed (int): Total count of failed replication events.
        last_sync (Optional[datetime]): Timestamp of the last successful synchronization.
        throughput_events_per_sec (float): Rate of event replication.
    """
    lag_seconds: float = Field(default=0.0, ge=0, description="Replication lag in seconds.")
    events_pending: int = Field(default=0, ge=0, description="Pending events count.")
    events_replicated: int = Field(default=0, ge=0, description="Successful events count.")
    events_failed: int = Field(default=0, ge=0, description="Failed events count.")
    last_sync: Optional[datetime] = Field(default=None, description="Last sync timestamp.")
    throughput_events_per_sec: float = Field(default=0.0, ge=0, description="Replication throughput.")


class ClusterNode(BaseModel):
    """Model representing a node within the cluster.

    Contains identity, configuration, status, and metrics for a single SBD instance.

    Attributes:
        node_id (str): Unique identifier for the node.
        hostname (str): Network hostname or IP address.
        port (int): Service port number.
        role (NodeRole): Current role of the node (Master/Replica).
        status (NodeStatus): Current health status.
        capabilities (NodeCapabilities): Resource limits and capabilities.
        health (NodeHealth): Real-time health metrics.
        replication (ReplicationMetrics): Replication performance metrics.
        owner_user_id (Optional[str]): ID of the user who owns this node (for multi-tenancy).
        cluster_token_hash (Optional[str]): Hash of the authentication token used for inter-node communication.
        created_at (datetime): Timestamp when the node was registered.
        updated_at (datetime): Timestamp of the last update.
    """
    node_id: str = Field(..., description="Unique node identifier")
    hostname: str = Field(..., description="Node hostname or IP")
    port: int = Field(default=8000, ge=1, le=65535, description="Service port")
    role: NodeRole = Field(default=NodeRole.STANDALONE, description="Node role")
    status: NodeStatus = Field(default=NodeStatus.JOINING, description="Node status")
    capabilities: NodeCapabilities = Field(default_factory=NodeCapabilities, description="Node capabilities")
    health: NodeHealth = Field(default_factory=NodeHealth, description="Health metrics")
    replication: ReplicationMetrics = Field(default_factory=ReplicationMetrics, description="Replication metrics")
    owner_user_id: Optional[str] = Field(None, description="Owner user ID for validation")
    cluster_token_hash: Optional[str] = Field(None, description="Hashed cluster auth token")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Registration time")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update time")

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, v: str) -> str:
        """Validate that hostname is not empty or whitespace."""
        if not v or not v.strip():
            raise ValueError("Hostname cannot be empty")
        return v.strip()

    @property
    def is_healthy(self) -> bool:
        """Check if the node is in a healthy state."""
        return self.status == NodeStatus.HEALTHY

    @property
    def is_master(self) -> bool:
        """Check if the node is currently a Master."""
        return self.role == NodeRole.MASTER

    @property
    def is_replica(self) -> bool:
        """Check if the node is currently a Replica."""
        return self.role == NodeRole.REPLICA

    @property
    def endpoint(self) -> str:
        """Get the full HTTP endpoint URL for the node."""
        return f"http://{self.hostname}:{self.port}"


class LoadBalancingConfig(BaseModel):
    """Configuration for cluster load balancing.

    Attributes:
        algorithm (LoadBalancingAlgorithm): The strategy to use for distributing requests.
        sticky_sessions (bool): Whether to bind a client to a specific node.
        health_check_enabled (bool): Whether to perform active health checks before routing.
        circuit_breaker_enabled (bool): Whether to stop routing to failing nodes.
        circuit_breaker_threshold (int): Failure count to trip the circuit breaker.
        circuit_breaker_timeout (int): Seconds to wait before testing a tripped node.
    """
    algorithm: LoadBalancingAlgorithm = Field(default=LoadBalancingAlgorithm.ROUND_ROBIN, description="Balancing algorithm.")
    sticky_sessions: bool = Field(default=True, description="Enable sticky sessions.")
    health_check_enabled: bool = Field(default=True, description="Enable active health checks.")
    circuit_breaker_enabled: bool = Field(default=True, description="Enable circuit breaker.")
    circuit_breaker_threshold: int = Field(default=5, ge=1, description="Failure threshold.")
    circuit_breaker_timeout: int = Field(default=60, ge=1, description="Timeout in seconds.")


class FailoverConfig(BaseModel):
    """Configuration for automatic failover and recovery.

    Attributes:
        auto_failover (bool): Whether to automatically promote a replica if master fails.
        failover_timeout (int): Seconds of unresponsiveness before declaring master down.
        min_healthy_replicas (int): Minimum replicas required to safely promote a new master.
        promote_on_master_failure (bool): Whether to trigger promotion logic on failure.
    """
    auto_failover: bool = Field(default=True, description="Enable automatic failover.")
    failover_timeout: int = Field(default=30, ge=1, description="Seconds before failover triggers.")
    min_healthy_replicas: int = Field(default=1, ge=0, description="Min healthy replicas required.")
    promote_on_master_failure: bool = Field(default=True, description="Promote replica on master failure.")


class ClusterTopology(BaseModel):
    """Model representing the overall cluster configuration and state.

    Attributes:
        topology_id (str): Unique identifier for this topology configuration.
        topology_type (TopologyType): The architectural pattern (e.g., Master-Slave).
        replication_factor (int): Target number of copies for data.
        replication_mode (ReplicationMode): Consistency level for replication.
        nodes (List[Dict[str, Any]]): List of raw node data dictionaries.
        load_balancing (LoadBalancingConfig): Load balancing settings.
        failover (FailoverConfig): Failover settings.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """
    topology_id: str = Field(..., description="Unique topology identifier")
    topology_type: TopologyType = Field(default=TopologyType.MASTER_SLAVE, description="Cluster architecture.")
    replication_factor: int = Field(default=2, ge=1, description="Number of replicas.")
    replication_mode: ReplicationMode = Field(default=ReplicationMode.ASYNC, description="Replication consistency mode.")
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="List of node configurations.")
    load_balancing: LoadBalancingConfig = Field(default_factory=LoadBalancingConfig, description="Load balancing config.")
    failover: FailoverConfig = Field(default_factory=FailoverConfig, description="Failover config.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation time.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update time.")

    @field_validator("nodes")
    @classmethod
    def validate_nodes(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate that node IDs are unique within the topology."""
        if not v:
            return v

        # Check for duplicate node IDs
        node_ids = [node.get("node_id") for node in v]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Duplicate node IDs in topology")

        return v

    @property
    def master_nodes(self) -> List[Dict[str, Any]]:
        """Retrieve all nodes configured as Master."""
        return [node for node in self.nodes if node.get("role") == NodeRole.MASTER]

    @property
    def replica_nodes(self) -> List[Dict[str, Any]]:
        """Retrieve all nodes configured as Replica."""
        return [node for node in self.nodes if node.get("role") == NodeRole.REPLICA]


class ReplicationEvent(BaseModel):
    """Model representing a single data change event to be replicated.

    Attributes:
        event_id (str): Unique identifier for the event.
        sequence_number (int): Ordered sequence number for consistency.
        operation (str): Type of operation (insert, update, delete).
        collection (str): Target database collection.
        document_id (Optional[str]): ID of the affected document.
        data (Dict[str, Any]): The payload data to replicate.
        timestamp (datetime): When the event occurred.
        source_node (str): ID of the node where the event originated.
        target_nodes (List[str]): IDs of nodes that should receive this event.
        status (EventStatus): Current replication status.
        replicated_at (Optional[datetime]): When replication was completed.
        retry_count (int): Number of retry attempts.
        error_message (Optional[str]): Error details if failed.
    """
    event_id: str = Field(..., description="Unique event identifier")
    sequence_number: int = Field(..., ge=0, description="Event sequence number")
    operation: str = Field(..., description="Database operation (insert, update, delete)")
    collection: str = Field(..., description="Collection name")
    document_id: Optional[str] = Field(None, description="Document ID")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Event timestamp")
    source_node: str = Field(..., description="Source node ID")
    target_nodes: List[str] = Field(default_factory=list, description="Target node IDs")
    status: EventStatus = Field(default=EventStatus.PENDING, description="Replication status")
    replicated_at: Optional[datetime] = Field(None, description="Completion timestamp")
    retry_count: int = Field(default=0, ge=0, description="Retry attempts")
    error_message: Optional[str] = Field(None, description="Error details")

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, v: str) -> str:
        """Validate that the operation type is supported."""
        valid_ops = {"insert", "update", "delete", "replace"}
        if v.lower() not in valid_ops:
            raise ValueError(f"Invalid operation: {v}. Must be one of {valid_ops}")
        return v.lower()


class ClusterHealth(BaseModel):
    """Model representing the aggregated health status of the entire cluster.

    Attributes:
        cluster_id (str): Identifier for the cluster.
        total_nodes (int): Total number of registered nodes.
        healthy_nodes (int): Count of healthy nodes.
        degraded_nodes (int): Count of degraded nodes.
        unhealthy_nodes (int): Count of unhealthy nodes.
        offline_nodes (int): Count of offline nodes.
        master_count (int): Number of active masters.
        replica_count (int): Number of active replicas.
        avg_replication_lag (float): Average replication lag across all replicas.
        max_replication_lag (float): Maximum replication lag observed.
        total_events_pending (int): Total pending replication events.
        total_events_failed (int): Total failed replication events.
        last_updated (datetime): Timestamp of this health report.
    """
    cluster_id: str = Field(..., description="Cluster identifier")
    total_nodes: int = Field(default=0, ge=0, description="Total nodes count")
    healthy_nodes: int = Field(default=0, ge=0, description="Healthy nodes count")
    degraded_nodes: int = Field(default=0, ge=0, description="Degraded nodes count")
    unhealthy_nodes: int = Field(default=0, ge=0, description="Unhealthy nodes count")
    offline_nodes: int = Field(default=0, ge=0, description="Offline nodes count")
    master_count: int = Field(default=0, ge=0, description="Active masters count")
    replica_count: int = Field(default=0, ge=0, description="Active replicas count")
    avg_replication_lag: float = Field(default=0.0, ge=0, description="Average lag in seconds")
    max_replication_lag: float = Field(default=0.0, ge=0, description="Max lag in seconds")
    total_events_pending: int = Field(default=0, ge=0, description="Total pending events")
    total_events_failed: int = Field(default=0, ge=0, description="Total failed events")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Report timestamp")

    @property
    def health_percentage(self) -> float:
        """Calculate the percentage of healthy nodes in the cluster.

        Returns:
            float: Percentage (0.0 - 100.0).
        """
        if self.total_nodes == 0:
            return 100.0
        return (self.healthy_nodes / self.total_nodes) * 100

    @property
    def is_healthy(self) -> bool:
        """Determine if the cluster is considered healthy overall.

        Criteria:
        - At least 80% of nodes are healthy.
        - At least one Master node is active.

        Returns:
            bool: True if healthy, False otherwise.
        """
        return self.health_percentage >= 80.0 and self.master_count >= 1


class ClusterEvent(BaseModel):
    """Model representing a cluster management event (audit log).

    Used to track administrative actions and system state changes.

    Attributes:
        event_id (str): Unique identifier for the event.
        event_type (str): Category of the event (e.g., 'node_joined', 'failover').
        severity (str): Importance level (debug, info, warning, error, critical).
        node_id (Optional[str]): ID of the node involved, if applicable.
        details (Dict[str, Any]): Structured details about the event.
        performed_by (Optional[str]): ID of the user or system component initiating the event.
        timestamp (datetime): When the event occurred.
    """
    event_id: str = Field(..., description="Unique event identifier")
    event_type: str = Field(..., description="Event type")
    severity: str = Field(default="info", description="Event severity")
    node_id: Optional[str] = Field(None, description="Related node ID")
    details: Dict[str, Any] = Field(default_factory=dict, description="Event details")
    performed_by: Optional[str] = Field(None, description="User ID who performed action")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Event timestamp")

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Validate severity level against standard log levels."""
        valid_severities = {"debug", "info", "warning", "error", "critical"}
        if v.lower() not in valid_severities:
            raise ValueError(f"Invalid severity: {v}. Must be one of {valid_severities}")
        return v.lower()


class OwnerValidationRequest(BaseModel):
    """Request model for validating account ownership across the cluster.

    Attributes:
        owner_user_id (str): The user ID to validate.
        target_nodes (Optional[List[str]]): Specific nodes to check. If None, checks all.
    """
    owner_user_id: str = Field(..., description="Owner user ID to validate")
    target_nodes: Optional[List[str]] = Field(None, description="Specific nodes to validate")


class OwnerValidationResult(BaseModel):
    """Response model for owner validation checks.

    Attributes:
        owner_user_id (str): The user ID that was validated.
        total_nodes (int): Number of nodes checked.
        validated_nodes (int): Number of nodes where validation succeeded.
        failed_nodes (List[str]): IDs of nodes where validation failed.
        validation_errors (Dict[str, str]): Map of node IDs to error messages.
        is_valid (bool): True if validation passed on all checked nodes.
    """
    owner_user_id: str = Field(..., description="Validated user ID")
    total_nodes: int = Field(..., description="Total nodes checked")
    validated_nodes: int = Field(..., description="Successful validations")
    failed_nodes: List[str] = Field(default_factory=list, description="Failed node IDs")
    validation_errors: Dict[str, str] = Field(default_factory=dict, description="Error details per node")
    is_valid: bool = Field(..., description="Overall validation status")

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of validation across nodes.

        Returns:
            float: Percentage (0.0 - 100.0).
        """
        if self.total_nodes == 0:
            return 0.0
        return (self.validated_nodes / self.total_nodes) * 100


class NodeRegistrationRequest(BaseModel):
    """Request model for registering a new node with the cluster.

    Attributes:
        hostname (str): Network address of the new node.
        port (int): Service port.
        role (NodeRole): Intended role for the new node.
        capabilities (Optional[NodeCapabilities]): Resource capabilities of the node.
        owner_user_id (str): User ID owning this node (for validation).
        cluster_token (str): Authentication token to prove cluster membership.
    """
    hostname: str = Field(..., description="Node hostname or IP")
    port: int = Field(default=8000, ge=1, le=65535, description="Service port")
    role: NodeRole = Field(default=NodeRole.REPLICA, description="Intended node role")
    capabilities: Optional[NodeCapabilities] = Field(None, description="Node resource capabilities")
    owner_user_id: str = Field(..., description="Owner user ID for validation")
    cluster_token: str = Field(..., description="Cluster authentication token")


class NodePromotionRequest(BaseModel):
    """Request model for manually promoting a node to Master.

    Attributes:
        node_id (str): ID of the node to promote.
        force (bool): If True, bypasses health checks and safety guards.
    """
    node_id: str = Field(..., description="Node ID to promote")
    force: bool = Field(default=False, description="Force promotion even if unhealthy")


class ClusterConfigurationRequest(BaseModel):
    """Request model for updating cluster-wide settings.

    Attributes:
        topology_type (TopologyType): New topology architecture.
        replication_factor (int): New target replication factor.
        replication_mode (ReplicationMode): New replication consistency mode.
        load_balancing (Optional[LoadBalancingConfig]): New load balancing settings.
        failover (Optional[FailoverConfig]): New failover settings.
    """
    topology_type: TopologyType = Field(..., description="Cluster topology type")
    replication_factor: int = Field(ge=1, description="Replication factor")
    replication_mode: ReplicationMode = Field(default=ReplicationMode.ASYNC, description="Replication mode")
    load_balancing: Optional[LoadBalancingConfig] = Field(None, description="Load balancing config")
    failover: Optional[FailoverConfig] = Field(None, description="Failover config")
