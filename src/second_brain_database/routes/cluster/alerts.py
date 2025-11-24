"""
# Cluster Alerts Routes

This module provides **API endpoints** for monitoring and managing Cluster Alerts.
It allows administrators to view active alerts, review history, and configure alert rules.

## Domain Overview

In a distributed cluster, proactive monitoring is essential.
This module exposes the interface for the **Cluster Alert System**, which tracks:
- **Node Failures**: Heartbeat timeouts and connectivity issues.
- **Resource Exhaustion**: High CPU/Memory usage or disk space warnings.
- **Replication Lag**: Delays in data synchronization between nodes.

## Key Features

### 1. Alert Management
- **Active Alerts**: Real-time view of currently unresolved issues.
- **History**: Historical log of past alerts for post-mortem analysis.
- **Resolution**: Manual acknowledgement and resolution of alerts.

### 2. Rule Configuration
- **Thresholds**: Dynamic adjustment of trigger thresholds (e.g., CPU > 90%).
- **Toggles**: Enable/Disable specific alert types without code changes.

## API Endpoints

- `GET /alerts/active` - View current problems
- `GET /alerts/history` - View past problems
- `POST /alerts/{id}/resolve` - Acknowledge an alert
- `GET /alerts/rules` - View configuration
- `PUT /alerts/rules/{type}` - Update configuration

## Usage Example

```python
# Get critical active alerts
alerts = await client.get("/alerts/active", params={"severity": "critical"})

# Update CPU threshold to 95%
await client.put("/alerts/rules/high_cpu", params={"threshold": 95.0})
```
"""

from typing import List, Optional

from fastapi import APIRouter, Query

from second_brain_database.services.cluster_alerts import (
    Alert,
    AlertSeverity,
    AlertType,
    cluster_alerts,
)

router = APIRouter(prefix="/alerts", tags=["Cluster Alerts"])


@router.get("/active", response_model=List[Alert])
async def get_active_alerts(
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    node_id: Optional[str] = Query(None, description="Filter by node ID")
):
    """
    Get all active (unresolved) cluster alerts.
    
    Args:
        severity: Optional filter by severity level
        node_id: Optional filter by node ID
        
    Returns:
        List of active alerts sorted by severity and timestamp
    """
    return await cluster_alerts.get_active_alerts(severity=severity, node_id=node_id)


@router.get("/history", response_model=List[Alert])
async def get_alert_history(
    hours: int = Query(24, description="Hours of history to fetch"),
    limit: int = Query(100, description="Maximum number of alerts to return")
):
    """
    Get alert history from the last N hours.
    
    Args:
        hours: Number of hours of history (default: 24)
        limit: Maximum alerts to return (default: 100)
        
    Returns:
        List of historical alerts
    """
    return await cluster_alerts.get_alert_history(hours=hours, limit=limit)


@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """
    Mark an alert as resolved.
    
    Args:
        alert_id: Alert ID to resolve
        
    Returns:
        Success message
    """
    await cluster_alerts.resolve_alert(alert_id)
    return {"message": f"Alert {alert_id} resolved successfully"}


@router.get("/rules")
async def get_alert_rules():
    """
    Get all alert rule configurations.
    
    Returns:
        Dictionary of alert rules with thresholds and enabled status
    """
    rules = cluster_alerts.get_rules()
    return {
        alert_type.value: {
            "severity": rule.severity.value,
            "threshold": rule.threshold,
            "enabled": rule.enabled
        }
        for alert_type, rule in rules.items()
    }


@router.put("/rules/{alert_type}")
async def update_alert_rule(
    alert_type: AlertType,
    threshold: Optional[float] = Query(None, description="New threshold value"),
    enabled: Optional[bool] = Query(None, description="Enable/disable rule")
):
    """
    Update an alert rule configuration.
    
    Args:
        alert_type: Type of alert rule to update
        threshold: New threshold value
        enabled: Enable or disable the rule
        
    Returns:
        Success message
    """
    cluster_alerts.update_rule(
        alert_type=alert_type,
        threshold=threshold,
        enabled=enabled
    )
    return {"message": f"Alert rule {alert_type.value} updated successfully"}
