"""
# Cluster Migration Helper

This module provides **Topology-Aware Logic** for the migration system.
It optimizes data transfers by understanding the cluster relationship between source and target.

## Domain Overview

Migrations can happen within a cluster or between different clusters.
- **Intra-Cluster**: Moving data between nodes in the same cluster.
- **Inter-Cluster**: Moving data to a completely separate SBD deployment.
- **Optimization**: Intra-cluster moves can use efficient internal replication instead of full HTTP transfers.

## Key Features

### 1. Topology Detection
- **Cluster Membership**: Determines if two instance URLs belong to the same cluster.
- **Node Discovery**: Resolves instance URLs to specific cluster nodes.

### 2. Strategy Selection
- **Smart Routing**: Recommends `cluster_replication` vs `direct_transfer` based on topology.
- **Health Checks**: Validates cluster health before allowing complex migration operations.

## Usage Example

```python
strategy = await cluster_migration_helper.get_optimal_transfer_strategy(
    from_url="https://node1.sbd.local",
    to_url="https://node2.sbd.local"
)
if strategy == "cluster_replication":
    # Use internal replication protocol
    pass
```
"""

from typing import Optional, List
from second_brain_database.managers.cluster_manager import cluster_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[ClusterMigration]")


class ClusterMigrationHelper:
    """
    Helper service for cluster-aware migration operations.

    Detects cluster topology and optimizes migration strategies by identifying
    whether source and target instances belong to the same cluster.

    **Optimizations:**
    - Uses cluster's built-in replication for intra-cluster migrations.
    - Falls back to direct transfer for cross-cluster migrations.
    - Validates cluster health before initiating transfers.
    """

    async def are_instances_in_same_cluster(
        self, instance1_url: str, instance2_url: str
    ) -> bool:
        """
        Check if two instances are part of the same SBD cluster.

        Args:
            instance1_url: URL of the first instance.
            instance2_url: URL of the second instance.

        Returns:
            True if both instances are in the same cluster.
        """
        try:
            # Get all cluster nodes
            nodes = await cluster_manager.list_nodes()
            
            # Extract hostnames from nodes
            cluster_hosts = {node.hostname for node in nodes}
            
            # Extract hostnames from instance URLs
            def extract_hostname(url: str) -> str:
                # Remove protocol
                url = url.replace("https://", "").replace("http://", "")
                # Remove port
                return url.split(":")[0]
            
            host1 = extract_hostname(instance1_url)
            host2 = extract_hostname(instance2_url)
            
            # Check if both are in cluster
            return host1 in cluster_hosts and host2 in cluster_hosts
        except Exception as e:
            logger.warning(f"Failed to check cluster membership: {e}")
            return False

    async def get_optimal_transfer_strategy(
        self, from_url: str, to_url: str
    ) -> str:
        """
        Determine the optimal transfer strategy based on cluster topology.

        Selects between cluster-native replication (for same-cluster transfers)
        and direct HTTP transfer (for cross-cluster transfers).

        Args:
            from_url: Source instance URL.
            to_url: Target instance URL.

        Returns:
            - `"cluster_replication"`: Use cluster's built-in replication.
            - `"direct_transfer"`: Use migration system's direct transfer.
        """
        same_cluster = await self.are_instances_in_same_cluster(from_url, to_url)
        
        if same_cluster:
            logger.info("Instances in same cluster - can use cluster replication")
            return "cluster_replication"
        else:
            logger.info("Instances in different clusters - using direct transfer")
            return "direct_transfer"

    async def validate_cluster_health(self, instance_url: str) -> bool:
        """
        Verify that an instance's cluster is healthy before migration.

        Args:
            instance_url: URL of the instance to check.

        Returns:
            True if the cluster is healthy, or if the instance is standalone.
        """
        try:
            nodes = await cluster_manager.list_nodes()
            
            # Extract hostname
            url = instance_url.replace("https://", "").replace("http://", "")
            hostname = url.split(":")[0]
            
            # Find node
            for node in nodes:
                if node.hostname == hostname:
                    return node.is_healthy
            
            # Not in cluster = standalone = healthy by default
            return True
        except Exception as e:
            logger.warning(f"Failed to validate cluster health: {e}")
            return True  # Assume healthy if can't verify

    async def get_cluster_nodes_for_instance(
        self, instance_url: str
    ) -> Optional[List[str]]:
        """
        Retrieve all cluster node endpoints associated with an instance.

        Useful for multi-target migrations where data should be replicated
        to all nodes in the cluster.

        Args:
            instance_url: URL of the instance.

        Returns:
            List of endpoint URLs for all nodes in the cluster, or `None` if standalone.
        """
        try:
            nodes = await cluster_manager.list_nodes()
            
            # Extract hostname
            url = instance_url.replace("https://", "").replace("http://", "")
            hostname = url.split(":")[0]
            
            # Find cluster members
            for node in nodes:
                if node.hostname == hostname:
                    # Return all nodes in same cluster
                    return [n.endpoint for n in nodes]
            
            return None
        except Exception:
            return None


# Global instance
cluster_migration_helper = ClusterMigrationHelper()
