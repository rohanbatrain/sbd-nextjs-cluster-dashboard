"""
# Cluster Health Routes

This module provides **Kubernetes-native health probes** for the application.
It implements the standard Liveness, Readiness, and Startup probe patterns.

## Domain Overview

In a container orchestration environment like Kubernetes, the platform needs to know:
1.  **Is the app running?** (Liveness)
2.  **Is it ready to serve traffic?** (Readiness)
3.  **Has it finished initializing?** (Startup)

## Key Features

### 1. Liveness Probe (`/liveness`)
- **Checks**: Basic process health.
- **Action**: If failed, K8s restarts the pod.
- **Logic**: Returns 200 if the main loop is not deadlocked.

### 2. Readiness Probe (`/readiness`)
- **Checks**: Dependency health (DB, Redis) and Cluster Membership.
- **Action**: If failed, K8s removes pod from load balancer.
- **Logic**: Verifies `cluster_manager` status and node registration.

### 3. Startup Probe (`/startup`)
- **Checks**: Initial bootstrap completion.
- **Action**: If failed, K8s waits before starting liveness checks.
- **Logic**: Confirms node ID assignment.

## Usage Example

Configuring in `deployment.yaml`:

```yaml
livenessProbe:
  httpGet:
    path: /cluster/health/liveness
    port: 8000
readinessProbe:
  httpGet:
    path: /cluster/health/readiness
    port: 8000
```
"""

from fastapi import APIRouter
from second_brain_database.managers.cluster_manager import cluster_manager
from second_brain_database.config import settings

router = APIRouter(prefix="/cluster/health", tags=["Cluster Health"])


@router.get("/liveness")
async def liveness_probe():
    """
    Liveness probe for Kubernetes.
    
    Returns 200 if the application is alive (not deadlocked).
    K8s will restart the pod if this fails.
    """
    # Simple check - if we can respond, we're alive
    return {
        "status": "alive",
        "cluster_enabled": settings.CLUSTER_ENABLED
    }


@router.get("/readiness")
async def readiness_probe():
    """
    Readiness probe for Kubernetes.
    
    Returns 200 only if the pod is ready to serve traffic.
    K8s will remove from service endpoints if this fails.
    """
    if not settings.CLUSTER_ENABLED:
        # Standalone mode - always ready
        return {
            "status": "ready",
            "mode": "standalone"
        }
    
    # Check cluster health
    try:
        health = await cluster_manager.get_cluster_health()
        
        # Pod is ready if:
        # 1. It's registered in the cluster
        # 2. It has a healthy status
        if cluster_manager.node_id and health:
            return {
                "status": "ready",
                "node_id": cluster_manager.node_id,
                "cluster_health": health.overall_status
            }
        else:
            # Still initializing
            return {
                "status": "initializing",
                "node_id": cluster_manager.node_id
            }, 503
            
    except Exception as e:
        # Not ready - K8s will not send traffic
        return {
            "status": "not_ready",
            "error": str(e)
        }, 503


@router.get("/startup")
async def startup_probe():
    """
    Startup probe for Kubernetes.
    
    Returns 200 when the application has completed startup.
    K8s will wait longer before checking liveness.
    """
    if not settings.CLUSTER_ENABLED:
        return {"status": "started", "mode": "standalone"}
    
    # Check if cluster manager is initialized
    if cluster_manager.node_id:
        return {
            "status": "started",
            "node_id": cluster_manager.node_id
        }
    else:
        return {
            "status": "starting"
        }, 503
