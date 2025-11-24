# SBD Cluster Auto-Scaling Guide

## Overview

The distributed SBD cluster supports automatic horizontal scaling via Kubernetes HPA (Horizontal Pod Autoscaler). Pods are automatically added/removed based on CPU and memory usage.

## How It Works

```
Low Load (CPU < 70%)     →  3 replicas (minimum)
Medium Load (70-80% CPU) →  Scale up gradually
High Load (CPU > 80%)    →  Scale up to 10 replicas (maximum)
Load Decreases          →  Scale down after 5 min stabilization
```

## Prerequisites

1. **Kubernetes cluster** with metrics-server installed:
```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

2. **kubectl** configured and connected to your cluster

3. **Docker image** built and available:
```bash
docker build -t second-brain-database:latest .
docker tag second-brain-database:latest your-registry/sbd:latest
docker push your-registry/sbd:latest
```

## Deployment Steps

### 1. Create Secrets

```bash
# Generate secure cluster token
CLUSTER_TOKEN=$(openssl rand -base64 32)

# Create Kubernetes secrets
kubectl create secret generic sbd-cluster-secrets \
  --from-literal=cluster-token=$CLUSTER_TOKEN

kubectl create secret generic sbd-secrets \
  --from-literal=mongodb-uri="mongodb://your-mongo:27017/sbd"
```

### 2. Deploy Cluster

```bash
cd k8s
kubectl apply -f cluster-autoscaling.yaml
```

This creates:
- **Deployment** with 3 initial replicas
- **Service** for load balancing
- **HPA** for auto-scaling
- **PodDisruptionBudget** for safe updates

### 3. Verify Deployment

```bash
# Check pods
kubectl get pods -l app=sbd

# Check HPA status
kubectl get hpa sbd-cluster-hpa

# Watch auto-scaling in action
kubectl get hpa sbd-cluster-hpa --watch
```

## Auto-Scaling Configuration

### Scaling Triggers

**Scale UP when**:
- CPU utilization > 70%
- OR Memory utilization > 80%

**Scale DOWN when**:
- CPU/Memory usage drops
- After 5 minute stabilization period

### Scaling Limits

```yaml
minReplicas: 3   # Always keep 3 nodes minimum
maxReplicas: 10  # Never exceed 10 nodes
```

### Scaling Speed

**Scale Up**: Aggressive
- Add up to 100% more pods (double)
- Max 2 pods every 30 seconds

**Scale Down**: Conservative
- Remove max 50% of pods
- Max 1 pod per minute
- Wait 5 minutes before scaling down

## Health Checks

Kubernetes uses 3 types of health probes:

### 1. Liveness Probe
```yaml
path: /cluster/health/liveness
```
- Checks if app is alive (not deadlocked)
- K8s **restarts pod** if fails
- Checks every 10 seconds

### 2. Readiness Probe
```yaml
path: /cluster/health/readiness
```
- Checks if pod can serve traffic
- K8s **removes from service** if fails
- Checks every 5 seconds

### 3. Startup Probe
```yaml
path: /cluster/health/startup
```
- Checks if app finished starting
- Allows 150 seconds for startup
- Prevents premature kill during initialization

## Monitoring Auto-Scaling

### View Current Status

```bash
# HPA status
kubectl describe hpa sbd-cluster-hpa

# Current metrics
kubectl top pods -l app=sbd

# Scaling events
kubectl get events --field-selector involvedObject.name=sbd-cluster-hpa
```

### Example HPA Output

```
NAME              REFERENCE              TARGETS         MINPODS  MAXPODS  REPLICAS
sbd-cluster-hpa   Deployment/sbd-cluster 45%/70%, 60%/80%  3       10       5
```

This shows:
- Current CPU: 45% (target: 70%)
- Current Memory: 60% (target: 80%)
- Current replicas: 5 (scaled up from 3)

## Load Testing Auto-Scaling

Test auto-scaling with load:

```bash
# Run load test (requires hey or similar)
hey -z 5m -c 100 -q 10 http://sbd-cluster:8000/cluster/health

# Watch scaling happen
kubectl get hpa sbd-cluster-hpa --watch
```

Expected behavior:
1. CPU spikes to 80%+
2. HPA scales up (3 → 5 → 7 pods)
3. Load distributes across pods
4. CPU drops to ~60%
5. After 5 minutes, scales back down

## Troubleshooting

### HPA Shows "unknown" for metrics

```bash
# Check metrics-server
kubectl get apiservice v1beta1.metrics.k8s.io

# Restart metrics-server if needed
kubectl rollout restart deployment metrics-server -n kube-system
```

### Pods stuck in Pending

```bash
# Check why
kubectl describe pod <pod-name>

# Common causes:
# - Insufficient cluster resources
# - Missing secrets
# - Image pull errors
```

### Pods fail readiness probe

```bash
# Check logs
kubectl logs <pod-name>

# Common causes:
# - Can't connect to MongoDB/Redis
# - Cluster registration failed
# - Missing environment variables
```

## Custom Metrics (Advanced)

Scale based on custom metrics like replication lag:

```yaml
metrics:
- type: Pods
  pods:
    metric:
      name: replication_lag_seconds
    target:
      type: AverageValue
      averageValue: "2"  # Scale up if lag > 2s
```

Requires Prometheus Adapter installed.

## Production Recommendations

1. **Start Conservative**:
   - minReplicas: 3
   - maxReplicas: 10
   - Monitor for 1 week

2. **Tune Based on Traffic**:
   - Increase maxReplicas if hitting limit
   - Adjust CPU/memory thresholds
   - Modify stabilization windows

3. **Set Resource Limits**:
   - Always set requests AND limits
   - Leave 20% headroom for spikes
   - Monitor actual usage

4. **Monitor Costs**:
   - More pods = higher costs
   - Balance performance vs. budget
   - Consider cluster-autoscaler for nodes

## Next Steps

1. Deploy and monitor for patterns
2. Adjust thresholds based on real traffic
3. Add custom metrics for replication lag
4. Integrate with Prometheus/Grafana alerts
5. Document your specific scaling patterns

Your SBD cluster will now automatically scale to handle traffic spikes! 🚀
