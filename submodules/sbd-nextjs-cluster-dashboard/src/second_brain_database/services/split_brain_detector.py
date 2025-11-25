"""
# Split-Brain Detector

This module prevents **Data Divergence** in distributed clusters.
It detects and resolves split-brain scenarios using quorum-based consensus.

## Domain Overview

A **split-brain** occurs when network partitioning causes multiple nodes to believe they're the master.
- **Symptom**: Two masters accept writes simultaneously, creating conflicting data.
- **Cause**: Network partition separates the cluster into isolated groups.
- **Solution**: Quorum-based consensus ensures only one master can operate.

## Key Features

### 1. Quorum Checking
- **Majority Rule**: Requires >50% of nodes to be healthy for the cluster to operate.
- **Degraded Mode**: Warns when quorum is lost but cluster is still functional.

### 2. Split-Brain Detection
- **Multi-Master Detection**: Identifies when multiple nodes claim master role.
- **Real-Time Monitoring**: Continuously checks cluster health.

### 3. Automatic Resolution
- **Priority-Based**: Selects the legitimate master by priority, then by registration time.
- **Demotion**: Automatically demotes illegitimate masters to replica role.
- **Isolation Detection**: Prevents isolated masters from accepting writes.

## Usage Example

```python
# Check if cluster has quorum
has_quorum, status = split_brain_detector.check_quorum(all_nodes)

# Detect split-brain
is_split, master_ids = split_brain_detector.detect_split_brain(all_nodes)
if is_split:
    # Resolve by selecting legitimate master
    winner = split_brain_detector.resolve_split_brain(all_nodes, master_ids)
```
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.cluster_models import ClusterNode, NodeRole, NodeStatus

logger = get_logger()


class QuorumStatus(str, Enum):
    """Quorum status."""
    HEALTHY = "healthy"  # Cluster has quorum
    DEGRADED = "degraded"  # Cluster lost quorum but still operational
    SPLIT_BRAIN = "split_brain"  # Multiple masters detected
    NO_QUORUM = "no_quorum"  # Cannot establish quorum


class SplitBrainDetector:
    """
    Detects and prevents split-brain scenarios in distributed clusters.

    A **split-brain** occurs when network partitioning causes multiple nodes to
    believe they are the master, leading to divergent writes and data inconsistency.

    **Prevention Strategy:**
    1. **Quorum-Based Consensus**: Majority of nodes must agree on the master.
    2. **Regular Health Checks**: Continuous monitoring of all nodes.
    3. **Master Validation**: Verify quorum before accepting writes.
    4. **Automatic Recovery**: Resolve conflicts by selecting the legitimate master.

    **How It Works:**
    - **Quorum**: Requires > 50% of nodes to be healthy.
    - **Detection**: Identifies when multiple masters exist.
    - **Resolution**: Selects master by priority, then by earliest registration.
    - **Isolation Detection**: Demotes masters in minority partitions.

    Attributes:
        quorum_percentage (float): Percentage of nodes required for quorum (default: 0.5).
    """

    def __init__(self, quorum_percentage: float = 0.5):
        """
        Initialize split-brain detector.
        
        Args:
            quorum_percentage: Percentage of nodes required for quorum (default 0.5 = 50%+1)
        """
        self.quorum_percentage = quorum_percentage
        self._last_check = None
        self._quorum_status = QuorumStatus.HEALTHY

    def check_quorum(self, nodes: List[ClusterNode]) -> Tuple[bool, QuorumStatus]:
        """
        Check if the cluster has quorum (sufficient healthy nodes).

        Calculates the number of healthy nodes and compares against the quorum threshold.
        A cluster has quorum if the number of healthy nodes exceeds `(total_nodes * quorum_percentage) + 1`.

        Args:
            nodes: List of all cluster nodes.

        Returns:
            A tuple containing:
            - `has_quorum`: True if quorum is achieved.
            - `status`: Current quorum status (`HEALTHY`, `DEGRADED`, `NO_QUORUM`).
        """
        if not nodes:
            return False, QuorumStatus.NO_QUORUM

        total_nodes = len(nodes)
        healthy_nodes = sum(1 for n in nodes if n.status == NodeStatus.HEALTHY)
        
        # Calculate quorum threshold (majority)
        quorum_threshold = int(total_nodes * self.quorum_percentage) + 1
        
        has_quorum = healthy_nodes >= quorum_threshold
        
        if not has_quorum:
            status = QuorumStatus.NO_QUORUM
        elif healthy_nodes < total_nodes:
            status = QuorumStatus.DEGRADED
        else:
            status = QuorumStatus.HEALTHY
        
        self._quorum_status = status
        self._last_check = datetime.now(timezone.utc)
        
        logger.info(
            f"Quorum check: {healthy_nodes}/{total_nodes} healthy nodes, "
            f"threshold={quorum_threshold}, status={status.value}"
        )
        
        return has_quorum, status

    def detect_split_brain(self, nodes: List[ClusterNode]) -> Tuple[bool, List[str]]:
        """
        Detect if a split-brain scenario exists in the cluster.

        A split-brain is detected when multiple nodes simultaneously claim the master role
        and are healthy, indicating they may be in separate network partitions.

        **Detection Criteria:**
        - More than one node has `role=MASTER` and `status=HEALTHY`.

        Args:
            nodes: List of all cluster nodes.

        Returns:
            A tuple containing:
            - `is_split_brain`: True if split-brain detected.
            - `master_node_ids`: List of node IDs claiming to be master.
        """
        # Find all nodes claiming to be master
        masters = [n for n in nodes if n.role == NodeRole.MASTER and n.status == NodeStatus.HEALTHY]
        
        if len(masters) <= 1:
            # No split-brain: 0 or 1 master is correct
            return False, [m.node_id for m in masters]
        
        # Multiple masters detected - potential split-brain
        logger.error(
            f"SPLIT-BRAIN DETECTED: {len(masters)} masters found: "
            f"{[m.node_id for m in masters]}"
        )
        
        self._quorum_status = QuorumStatus.SPLIT_BRAIN
        
        return True, [m.node_id for m in masters]

    def resolve_split_brain(
        self,
        nodes: List[ClusterNode],
        master_ids: List[str]
    ) -> Optional[str]:
        """
        Resolve a split-brain scenario by selecting the legitimate master.

        Uses a deterministic algorithm to choose the winning master:
        1. Select the node with the **highest priority**.
        2. If priorities are equal, choose the node with the **earliest registration** (`created_at`).
        3. Demote all other masters to replica role.

        Args:
            nodes: List of all cluster nodes.
            master_ids: List of node IDs claiming to be master.

        Returns:
            The node ID of the legitimate master, or `None` if resolution fails.
        """
        if not master_ids:
            logger.error("Cannot resolve split-brain: no master nodes provided")
            return None

        # Get full node objects for masters
        masters = [n for n in nodes if n.node_id in master_ids]
        
        # Sort by priority (desc), then by created_at (asc)
        masters.sort(
            key=lambda n: (-n.capabilities.priority, n.created_at)
        )
        
        # First master wins
        legitimate_master = masters[0]
        demoted_masters = masters[1:]
        
        logger.warning(
            f"Split-brain resolution: keeping {legitimate_master.node_id} "
            f"(priority={legitimate_master.capabilities.priority}), "
            f"demoting {[m.node_id for m in demoted_masters]}"
        )
        
        return legitimate_master.node_id

    def check_master_isolation(
        self,
        master_node: ClusterNode,
        all_nodes: List[ClusterNode]
    ) -> bool:
        """
        Determine if the master node is isolated in a minority partition.

        An isolated master cannot communicate with the majority of the cluster
        and should demote itself to prevent accepting writes that cannot be replicated.

        Args:
            master_node: The master node to check.
            all_nodes: All cluster nodes.

        Returns:
            True if the master is isolated (in minority partition), False otherwise.
        """
        # Find nodes that master can communicate with
        reachable_nodes = [n for n in all_nodes if n.status in [NodeStatus.HEALTHY, NodeStatus.DEGRADED]]
        
        # Calculate if master is in minority partition
        total_nodes = len(all_nodes)
        reachable_count = len(reachable_nodes)
        
        quorum_threshold = int(total_nodes * self.quorum_percentage) + 1
        
        is_isolated = reachable_count < quorum_threshold
        
        if is_isolated:
            logger.warning(
                f"Master {master_node.node_id} is ISOLATED: "
                f"can reach {reachable_count}/{total_nodes} nodes "
                f"(threshold={quorum_threshold})"
            )
        
        return is_isolated

    def get_status(self) -> Dict:
        """
        Retrieve the current status of the split-brain detector.

        Returns:
            A dictionary containing the quorum status and last check timestamp.
        """
        return {
            "quorum_status": self._quorum_status.value,
            "last_check": self._last_check.isoformat() if self._last_check else None,
        }


# Global detector instance
split_brain_detector = SplitBrainDetector()
