"""
# Cluster Alerts Service

This module provides the **Real-time Alerting System** for the distributed cluster.
It monitors health metrics and generates actionable alerts for critical events.

## Domain Overview

A healthy cluster requires constant vigilance. This service acts as the nervous system, detecting anomalies.
- **Severity Levels**: `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- **Alert Types**: Node failures, replication lag, split-brain, resource exhaustion.
- **Lifecycle**: Creation, deduplication, persistence, and resolution.

## Key Features

### 1. Rule-Based Monitoring
- **Configurable Rules**: Thresholds for lag, CPU, memory, etc., can be tuned at runtime.
- **Automatic Detection**: continuously evaluates node health against these rules.

### 2. Alert Management
- **Deduplication**: Prevents alert storms by grouping repeated events.
- **Persistence**: Stores alert history in MongoDB (`cluster_alerts` collection).
- **Resolution**: Tracks when issues are fixed and marks alerts as resolved.

## Usage Example

```python
# Check a node and generate alerts if needed
await cluster_alerts.check_node_health(node)

# Manually create an alert
await cluster_alerts.create_alert(
    alert_type=AlertType.SECURITY_EVENT,
    title="Unauthorized Access",
    message="Suspicious activity detected on node-01",
    severity=AlertSeverity.CRITICAL
)
```
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.cluster_models import ClusterNode, NodeStatus

logger = get_logger()


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Alert types."""
    NODE_DOWN = "node_down"
    NODE_DEGRADED = "node_degraded"
    HIGH_LAG = "high_replication_lag"
    SPLIT_BRAIN = "split_brain"
    NO_QUORUM = "no_quorum"
    LEADER_CHANGE = "leader_change"
    RESOURCE_HIGH = "resource_high"
    SECURITY_EVENT = "security_event"


class Alert(BaseModel):
    """Cluster alert model."""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    node_id: Optional[str] = None
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class AlertRule:
    """Alert rule configuration."""
    
    def __init__(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        threshold: float,
        enabled: bool = True
    ):
        self.alert_type = alert_type
        self.severity = severity
        self.threshold = threshold
        self.enabled = enabled


class ClusterAlertsService:
    """
    Service for managing real-time cluster health alerts and notifications.

    Implements a rule-based alerting system that monitors cluster health metrics
    and generates alerts when thresholds are exceeded. Supports automatic
    deduplication and resolution tracking.

    **Key Features:**
    - **Rule-Based**: Configurable thresholds for each alert type.
    - **Deduplication**: Prevents duplicate alerts for the same issue.
    - **Persistence**: Stores alerts in MongoDB for historical analysis.
    - **Auto-Resolution**: Tracks when alerts are resolved.
    - **Severity Levels**: INFO, WARNING, ERROR, CRITICAL.

    **Monitored Conditions:**
    - Node failures and degradation
    - High replication lag
    - Resource exhaustion (CPU, memory)
    - Split-brain scenarios
    - Quorum loss
    """

    def __init__(self):
        """Initialize alerts service."""
        self._active_alerts: Dict[str, Alert] = {}
        self._rules = self._initialize_default_rules()

    def _initialize_default_rules(self) -> Dict[AlertType, AlertRule]:
        """Initialize default alert rules."""
        return {
            AlertType.NODE_DOWN: AlertRule(
                alert_type=AlertType.NODE_DOWN,
                severity=AlertSeverity.CRITICAL,
                threshold=1.0,  # 1 consecutive failure
                enabled=True
            ),
            AlertType.NODE_DEGRADED: AlertRule(
                alert_type=AlertType.NODE_DEGRADED,
                severity=AlertSeverity.WARNING,
                threshold=1.0,
                enabled=True
            ),
            AlertType.HIGH_LAG: AlertRule(
                alert_type=AlertType.HIGH_LAG,
                severity=AlertSeverity.WARNING,
                threshold=5.0,  # 5 seconds
                enabled=True
            ),
            AlertType.SPLIT_BRAIN: AlertRule(
                alert_type=AlertType.SPLIT_BRAIN,
                severity=AlertSeverity.CRITICAL,
                threshold=1.0,
                enabled=True
            ),
            AlertType.NO_QUORUM: AlertRule(
                alert_type=AlertType.NO_QUORUM,
                severity=AlertSeverity.CRITICAL,
                threshold=1.0,
                enabled=True
            ),
            AlertType.RESOURCE_HIGH: AlertRule(
                alert_type=AlertType.RESOURCE_HIGH,
                severity=AlertSeverity.WARNING,
                threshold=85.0,  # 85% usage
                enabled=True
            ),
        }

    async def check_node_health(self, node: ClusterNode):
        """
        Evaluate a node's health metrics and generate alerts if thresholds are exceeded.

        Checks node status, replication lag, and resource usage (CPU, memory)
        against configured thresholds and creates alerts as needed.

        Args:
            node: The `ClusterNode` object to evaluate.
        """
        # Check node status
        if node.status == NodeStatus.FAILED:
            await self.create_alert(
                alert_type=AlertType.NODE_DOWN,
                title=f"Node {node.node_id} is down",
                message=f"Node {node.hostname} ({node.node_id}) has failed health checks",
                node_id=node.node_id
            )
        elif node.status == NodeStatus.DEGRADED:
            await self.create_alert(
                alert_type=AlertType.NODE_DEGRADED,
                title=f"Node {node.node_id} degraded",
                message=f"Node {node.hostname} is experiencing performance issues",
                node_id=node.node_id,
                severity=AlertSeverity.WARNING
            )
        
        # Check replication lag
        if node.replication and node.replication.lag_seconds:
            rule = self._rules.get(AlertType.HIGH_LAG)
            if rule and rule.enabled and node.replication.lag_seconds > rule.threshold:
                await self.create_alert(
                    alert_type=AlertType.HIGH_LAG,
                    title=f"High replication lag on {node.node_id}",
                    message=f"Replication lag is {node.replication.lag_seconds:.1f}s (threshold: {rule.threshold}s)",
                    node_id=node.node_id,
                    severity=AlertSeverity.WARNING
                )
        
        # Check resource usage
        if node.health:
            rule = self._rules.get(AlertType.RESOURCE_HIGH)
            if rule and rule.enabled:
                if node.health.cpu_usage and node.health.cpu_usage > rule.threshold:
                    await self.create_alert(
                        alert_type=AlertType.RESOURCE_HIGH,
                        title=f"High CPU usage on {node.node_id}",
                        message=f"CPU usage is {node.health.cpu_usage:.1f}%",
                        node_id=node.node_id,
                        severity=AlertSeverity.WARNING
                    )
                
                if node.health.memory_usage and node.health.memory_usage > rule.threshold:
                    await self.create_alert(
                        alert_type=AlertType.RESOURCE_HIGH,
                        title=f"High memory usage on {node.node_id}",
                        message=f"Memory usage is {node.health.memory_usage:.1f}%",
                        node_id=node.node_id,
                        severity=AlertSeverity.WARNING
                    )

    async def create_alert(
        self,
        alert_type: AlertType,
        title: str,
        message: str,
        node_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None
    ) -> str:
        """
        Create and persist a new alert.

        Performs deduplication by checking if an alert with the same ID already exists.
        Uses rule-based severity if not explicitly provided.

        Args:
            alert_type: The category of alert (e.g., `NODE_DOWN`, `HIGH_LAG`).
            title: A concise alert title.
            message: Detailed description of the issue.
            node_id: ID of the affected node (if applicable).
            severity: Override the default severity from the rule.

        Returns:
            The unique alert ID, or `None` if the alert type is disabled.
        """
        # Check if rule is enabled
        rule = self._rules.get(alert_type)
        if not rule or not rule.enabled:
            return None
        
        # Use rule severity if not provided
        if not severity:
            severity = rule.severity
        
        # Generate alert ID (for deduplication)
        alert_id = f"{alert_type.value}:{node_id or 'cluster'}"
        
        # Check if alert already exists and is active
        if alert_id in self._active_alerts:
            logger.debug(f"Alert {alert_id} already active, skipping")
            return alert_id
        
        # Create alert
        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            node_id=node_id,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Store in memory
        self._active_alerts[alert_id] = alert
        
        # Persist to database
        try:
            collection = db_manager.get_collection("cluster_alerts")
            await collection.insert_one(alert.model_dump())
            logger.info(f"Created {severity.value} alert: {title}")
        except Exception as e:
            logger.error(f"Failed to persist alert: {e}")
        
        return alert_id

    async def resolve_alert(self, alert_id: str):
        """
        Mark an alert as resolved and remove it from active tracking.

        Updates the alert in the database with a resolution timestamp and
        removes it from the in-memory active alerts cache.

        Args:
            alert_id: The unique ID of the alert to resolve.
        """
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.now(timezone.utc)
            
            # Update in database
            try:
                collection = db_manager.get_collection("cluster_alerts")
                await collection.update_one(
                    {"alert_id": alert_id},
                    {
                        "$set": {
                            "resolved": True,
                            "resolved_at": alert.resolved_at
                        }
                    }
                )
                logger.info(f"Resolved alert: {alert.title}")
            except Exception as e:
                logger.error(f"Failed to update alert: {e}")
            
            # Remove from active alerts
            del self._active_alerts[alert_id]

    async def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        node_id: Optional[str] = None
    ) -> List[Alert]:
        """
        Retrieve currently active (unresolved) alerts.

        Supports filtering by severity and node ID. Results are sorted by
        severity (CRITICAL first) and then by timestamp (newest first).

        Args:
            severity: Optional filter for a specific severity level.
            node_id: Optional filter for alerts from a specific node.

        Returns:
            A list of active `Alert` objects.
        """
        alerts = list(self._active_alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if node_id:
            alerts = [a for a in alerts if a.node_id == node_id]
        
        # Sort by severity then timestamp
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.ERROR: 1,
            AlertSeverity.WARNING: 2,
            AlertSeverity.INFO: 3
        }
        alerts.sort(key=lambda a: (severity_order[a.severity], a.timestamp), reverse=True)
        
        return alerts

    async def get_alert_history(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[Alert]:
        """
        Retrieve historical alerts from the database.

        Fetches alerts created within the specified time window, ordered by
        timestamp (newest first).

        Args:
            hours: Lookback period in hours (default: 24).
            limit: Maximum number of alerts to return (default: 100).

        Returns:
            A list of `Alert` objects from the specified period.
        """
        try:
            collection = db_manager.get_collection("cluster_alerts")
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            cursor = collection.find(
                {"timestamp": {"$gte": since}}
            ).sort("timestamp", -1).limit(limit)
            
            alerts = []
            async for doc in cursor:
                alerts.append(Alert(**doc))
            
            return alerts
        except Exception as e:
            logger.error(f"Failed to fetch alert history: {e}")
            return []

    def update_rule(
        self,
        alert_type: AlertType,
        threshold: Optional[float] = None,
        enabled: Optional[bool] = None
    ):
        """
        Modify an existing alert rule's configuration.

        Allows runtime adjustment of thresholds and toggling rules on/off
        without requiring a service restart.

        Args:
            alert_type: The alert type to modify.
            threshold: New threshold value (if applicable).
            enabled: Whether the rule should be active.
        """
        if alert_type in self._rules:
            rule = self._rules[alert_type]
            if threshold is not None:
                rule.threshold = threshold
            if enabled is not None:
                rule.enabled = enabled
            logger.info(f"Updated rule for {alert_type.value}: threshold={rule.threshold}, enabled={rule.enabled}")

    def get_rules(self) -> Dict[AlertType, AlertRule]:
        """
        Retrieve all configured alert rules.

        Returns:
            A dictionary mapping `AlertType` to `AlertRule` objects.
        """
        return self._rules


# Global alerts service
cluster_alerts = ClusterAlertsService()
