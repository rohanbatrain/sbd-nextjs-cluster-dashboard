# Cluster Management API Documentation

This document details the REST API endpoints for managing the distributed SBD cluster.

## Authentication

All cluster endpoints require authentication via the `X-Cluster-Token` header:

```
X-Cluster-Token: <your-cluster-auth-token>
```

## Endpoints

### Health & Status

#### GET `/cluster/health`

Get aggregated cluster health status.

**Response:**
```json
{
  "cluster_id": "cluster-default",
  "total_nodes": 3,
  "healthy_nodes": 3,
  "degraded_nodes": 0,
  "unhealthy_nodes": 0,
  "offline_nodes": 0,
  "master_count": 1,
  "replica_count": 2,
  "avg_replication_lag": 0.5,
  "max_replication_lag": 1.2,
  "total_events_pending": 10,
  "total_events_failed": 0,
  "last_updated": "2025-11-23T15:00:00Z"
}
```

### Node Management

#### GET `/cluster/nodes`

List all nodes in the cluster.

**Query Parameters:**
- `role` (optional): Filter by role (`master` or `replica`)
- `status` (optional): Filter by status (`healthy`, `degraded`, `unhealthy`, `offline`)

**Response:**
```json
[
  {
    "node_id": "node-1",
    "hostname": "sbd-node-1",
    "port": 8000,
    "role": "master",
    "status": "healthy",
    "capabilities": {
      "max_connections": 1000,
      "supports_writes": true,
      "supports_reads": true,
      "priority": 100
    },
    "health": {
      "last_heartbeat": "2025-11-23T15:00:00Z",
      "cpu_usage": 0.45,
      "memory_usage": 0.60,
      "disk_usage": 0.30
    },
    "replication": {
      "lag_seconds": 0.5,
      "events_pending": 5
    }
  }
]
```

#### GET `/cluster/nodes/{node_id}`

Get details for a specific node.

**Response:** Same as individual node object above.

#### POST `/cluster/register`

Register a new node in the cluster (internal endpoint).

**Request:**
```json
{
  "hostname": "sbd-node-3",
  "port": 8000,
  "owner_user_id": "user-123",
  "cluster_token": "secret-token"
}
```

**Response:** `"node-abc123"` (node ID)

#### DELETE `/cluster/nodes/{node_id}`

Remove a node from the cluster.

**Response:**
```json
{
  "status": "success",
  "message": "Node node-2 removed"
}
```

### Node Role Management

#### POST `/cluster/nodes/promote`

Promote a replica node to master.

**Request:**
```json
{
  "node_id": "node-2",
  "force": false
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Node node-2 promoted to master"
}
```

#### POST `/cluster/nodes/{node_id}/demote`

Demote a master node to replica.

**Response:**
```json
{
  "status": "success",
  "message": "Node node-1 demoted to replica"
}
```

### Owner Validation

#### POST `/cluster/validate-owner`

Validate owner account existence across cluster nodes.

**Request:**
```json
{
  "owner_user_id": "user-123",
  "target_nodes": ["node-1", "node-2"]
}
```

**Response:**
```json
{
  "owner_user_id": "user-123",
  "total_nodes": 2,
  "validated_nodes": 2,
  "failed_nodes": [],
  "validation_errors": {},
  "is_valid": true
}
```

### Replication

#### POST `/cluster/replication/apply`

Apply a replication event (internal endpoint).

**Request:**
```json
{
  "event_id": "evt-abc123",
  "sequence_number": 42,
  "operation": "insert",
  "collection": "users",
  "document_id": "doc-123",
  "data": {"name": "John Doe"},
  "timestamp": "2025-11-23T15:00:00Z",
  "source_node": "node-1",
  "target_nodes": ["node-2"]
}
```

**Response:**
```json
{
  "status": "success"
}
```

#### GET `/cluster/replication/lag`

Get replication lag for the current node.

**Response:**
```json
{
  "lag_seconds": 0.5
}
```

### Configuration

#### POST `/cluster/configure`

Update cluster configuration (future implementation).

**Request:**
```json
{
  "topology_type": "master_slave",
  "replication_factor": 2
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Configuration updated"
}
```

## Error Codes

| Code | Description |
|------|-------------|
| 401 | Missing cluster token |
| 403 | Invalid cluster token |
| 404 | Node not found |
| 500 | Internal server error |
| 503 | Service unavailable (cluster routing failed) |
