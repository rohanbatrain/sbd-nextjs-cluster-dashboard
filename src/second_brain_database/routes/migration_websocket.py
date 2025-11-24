"""
# Migration WebSocket Routes

This module provides the **WebSocket endpoints** for real-time migration monitoring.
It streams granular progress updates to the frontend during long-running migration tasks.

## Domain Overview

Migrations can take minutes or hours. HTTP polling is inefficient for:
- **Real-Time Feedback**: Users need to see progress bars moving smoothly.
- **Instant Alerts**: Immediate notification of errors or completion.
- **Live Stats**: Streaming transfer speeds, document counts, and ETA.

## Key Features

### 1. Progress Streaming
- **Granular Updates**: Emits events for every batch of documents transferred.
- **Metrics**: Includes percentage, ETA, current collection, and speed.
- **Status Changes**: Pushes state transitions (e.g., `queued` -> `in_progress` -> `completed`).

### 2. Connection Management
- **Broadcasting**: Supports multiple clients monitoring the same transfer.
- **Heartbeats**: Handles connection keep-alives and automatic cleanup.
- **Reconnection**: Clients can reconnect and immediately receive the latest state.

## API Endpoints

### WebSocket
- `WS /migration/ws/{transfer_id}/progress` - Subscribe to transfer updates

## Usage Examples

### Client-Side Subscription

```javascript
const ws = new WebSocket(
    `wss://api.example.com/migration/ws/${transferId}/progress`
);

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(`Progress: ${data.percentage}% - ETA: ${data.eta_seconds}s`);
    updateProgressBar(data.percentage);
};
```

## Module Attributes

Attributes:
    router (APIRouter): FastAPI router with `/migration/ws` prefix
    progress_broadcaster (MigrationProgressBroadcaster): Singleton for managing connections
"""

from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.database import db_manager

logger = get_logger(prefix="[MigrationWebSocket]")

router = APIRouter(prefix="/migration/ws", tags=["migration-websocket"])


class MigrationProgressBroadcaster:
    """Manages WebSocket connections for migration progress updates."""

    def __init__(self):
        # transfer_id -> list of WebSocket connections
        self.active_connections: Dict[str, list[WebSocket]] = {}

    async def connect(self, transfer_id: str, websocket: WebSocket):
        """Register a new WebSocket connection for a transfer."""
        await websocket.accept()
        if transfer_id not in self.active_connections:
            self.active_connections[transfer_id] = []
        self.active_connections[transfer_id].append(websocket)
        logger.info(f"WebSocket connected for transfer {transfer_id}")

    def disconnect(self, transfer_id: str, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if transfer_id in self.active_connections:
            self.active_connections[transfer_id].remove(websocket)
            if not self.active_connections[transfer_id]:
                del self.active_connections[transfer_id]
        logger.info(f"WebSocket disconnected for transfer {transfer_id}")

    async def broadcast_progress(self, transfer_id: str, progress_data: dict):
        """Broadcast progress update to all connected clients."""
        if transfer_id not in self.active_connections:
            return

        dead_connections = []
        for websocket in self.active_connections[transfer_id]:
            try:
                await websocket.send_json(progress_data)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                dead_connections.append(websocket)

        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(transfer_id, ws)


# Global broadcaster instance
progress_broadcaster = MigrationProgressBroadcaster()


@router.websocket("/{transfer_id}/progress")
async def transfer_progress_websocket(websocket: WebSocket, transfer_id: str):
    """
    WebSocket endpoint for real-time transfer progress updates.
    
    Clients connect to this endpoint and receive progress updates as JSON:
    {
        "current_collection": "users",
        "documents_transferred": 1500,
        "total_documents": 5000,
        "percentage": 30.0,
        "status": "in_progress",
        "eta_seconds": 120
    }
    """
    await progress_broadcaster.connect(transfer_id, websocket)
    
    try:
        # Send initial progress
        transfer_collection = await db_manager.get_collection("migration_transfers")
        transfer = await transfer_collection.find_one({"transfer_id": transfer_id})
        
        if transfer:
            await websocket.send_json({
                "status": transfer.get("status"),
                "progress": transfer.get("progress", {}),
                "message": "Connected to progress stream"
            })
        
        # Keep connection alive and wait for disconnect
        while True:
            # Receive messages (for heartbeat/ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        progress_broadcaster.disconnect(transfer_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        progress_broadcaster.disconnect(transfer_id, websocket)
