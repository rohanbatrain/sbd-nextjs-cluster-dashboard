# Distributed SBD Cluster Deployment Guide

This guide details how to deploy and manage the Second Brain Database (SBD) in a distributed cluster configuration.

## Prerequisites

- **MongoDB**: A MongoDB Replica Set (v4.0+) is required for change streams. Standalone MongoDB is not supported for clustering.
- **Redis**: A Redis instance (v5.0+) is required for pub/sub messaging and distributed locking.
- **Network**: Low-latency network connectivity between all nodes.

## Configuration

Configure the cluster using environment variables or the `.env` file.

### Core Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `CLUSTER_ENABLED` | Enable cluster mode | `false` |
| `CLUSTER_NODE_ID` | Unique ID for the node (auto-generated if empty) | `""` |
| `CLUSTER_NODE_ROLE` | Initial role (`master` or `replica`) | `replica` |
| `CLUSTER_ADVERTISE_ADDRESS` | Hostname/IP reachable by other nodes | `localhost` |
| `CLUSTER_AUTH_TOKEN` | Shared secret for cluster authentication | `""` |

### Replication Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `CLUSTER_REPLICATION_ENABLED` | Enable data replication | `true` |
| `CLUSTER_REPLICATION_MODE` | `async` or `sync` | `async` |
| `CLUSTER_BATCH_SIZE` | Max events per replication batch | `100` |

### Security Settings (mTLS)

| Variable | Description |
|----------|-------------|
| `CLUSTER_MTLS_ENABLED` | Enable mutual TLS |
| `CLUSTER_MTLS_CA_FILE` | Path to CA certificate |
| `CLUSTER_MTLS_CERT_FILE` | Path to node certificate |
| `CLUSTER_MTLS_KEY_FILE` | Path to node private key |

## Deployment Strategies

### Docker Compose (Local/Testing)

```yaml
version: '3.8'

services:
  sbd-node-1:
    image: second-brain-database:latest
    environment:
      - CLUSTER_ENABLED=true
      - CLUSTER_NODE_ID=node-1
      - CLUSTER_NODE_ROLE=master
      - CLUSTER_ADVERTISE_ADDRESS=sbd-node-1
      - CLUSTER_AUTH_TOKEN=secret-token
    ports:
      - "8000:8000"

  sbd-node-2:
    image: second-brain-database:latest
    environment:
      - CLUSTER_ENABLED=true
      - CLUSTER_NODE_ID=node-2
      - CLUSTER_NODE_ROLE=replica
      - CLUSTER_ADVERTISE_ADDRESS=sbd-node-2
      - CLUSTER_AUTH_TOKEN=secret-token
    ports:
      - "8001:8000"
```

### Kubernetes (Production)

Deploy as a StatefulSet to ensure stable network identities.

1.  **ConfigMap**: Store non-sensitive config.
2.  **Secret**: Store `CLUSTER_AUTH_TOKEN` and mTLS certificates.
3.  **StatefulSet**: Define the pod spec with `CLUSTER_ENABLED=true`.
4.  **Service**: Headless service for peer discovery.

## Monitoring & Management

### Owner Dashboard

Access the cluster dashboard at `/dashboard` (if configured) or via the dedicated Next.js app.

- **Overview**: View cluster health, replication lag, and throughput.
- **Nodes**: Manage node roles (promote/demote) and remove dead nodes.
- **Settings**: Configure load balancing algorithms and failover thresholds.

### Prometheus Metrics

Metrics are exposed at `/metrics`. Key metrics to watch:

- `sbd_cluster_nodes_count`: Number of healthy nodes.
- `sbd_replication_lag_seconds`: Replication lag per node.
- `sbd_replication_events_total`: Total events processed.

## Troubleshooting

### Split Brain

If multiple nodes claim to be MASTER:
1.  Check network connectivity between nodes.
2.  Use the Dashboard to manually demote incorrect masters.
3.  Ensure `CLUSTER_ELECTION_TIMEOUT` is configured correctly for your network latency.

### High Replication Lag

1.  Check network bandwidth.
2.  Increase `CLUSTER_BATCH_SIZE`.
3.  Check MongoDB write performance.

### Node Not Joining

1.  Verify `CLUSTER_AUTH_TOKEN` matches across all nodes.
2.  Check if `CLUSTER_ADVERTISE_ADDRESS` is reachable from other nodes.
3.  Check logs for mTLS handshake errors if enabled.
