"""
# WebSocket Routes

This module provides the **WebSocket endpoints** for real-time communication.
It handles connection establishment, authentication, and message routing.

## Domain Overview

WebSockets enable bidirectional, real-time data flow for features like:
- **Notifications**: Instant alerts for system events.
- **Chat**: Real-time messaging (future scope).
- **Live Updates**: Dashboard refreshes and progress bars.

## Key Features

### 1. Connection Management
- **Authentication**: JWT-based handshake validation.
- **Session Tracking**: Maps WebSocket connections to User IDs.
- **Lifecycle**: Handles connect, disconnect, and keep-alive.

### 2. Integration
- **Connection Manager**: Uses the global `ConnectionManager` to store active sockets.
- **Broadcasting**: Allows other services to push messages to specific users.

## API Endpoints

- `WS /ws` - Main WebSocket endpoint

## Usage Examples

### Client Connection (JavaScript)

```javascript
const token = "eyJhbG..."; // JWT Token
const ws = new WebSocket(`wss://api.example.com/ws?token=${token}`);

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log("Received update:", data);
};
```

## Module Attributes

Attributes:
    router (APIRouter): FastAPI router for WebSocket endpoints
"""

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from second_brain_database.routes.auth.services.auth.login import get_current_user
from second_brain_database.websocket_manager import manager

router = APIRouter()


async def get_current_user_ws(token: Optional[str] = Query(None)):
    """
    Dependency function to retrieve the current authenticated user for WebSocket connections.
    The token is passed as a query parameter.
    """
    if token is None:
        return None
    return await get_current_user(token)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, current_user: dict = Depends(get_current_user_ws)):
    """
    Establish a WebSocket connection for real-time communication.

    This endpoint allows a client to establish a WebSocket connection with the server.
    Authentication is handled via a JWT token passed as a query parameter.
    Once connected, the server can push real-time updates to the client.

    Args:
        websocket (WebSocket): The WebSocket connection object.
        current_user (dict): The authenticated user, injected by Depends.
    """
    if current_user is None:
        await websocket.close(code=1008)
        return

    user_id = str(current_user["_id"])
    await manager.connect(user_id, websocket)
    try:
        while True:
            # The server can listen for messages from the client if needed
            # For now, we just keep the connection open
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
