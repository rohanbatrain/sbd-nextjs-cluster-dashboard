"""
# LangGraph Models

This module defines the **Pydantic models** compatible with the LangGraph Cloud API.
These models ensure that the backend response matches what the `@langchain/langgraph-sdk` expects.

## Domain Overview

LangGraph uses a specific schema for Threads, Runs, and State.
- **Thread**: Represents a conversation history.
- **ThreadValues**: The current state (messages) of the thread.
- **StreamRequest**: Configuration for running a graph.

## Key Models

### 1. Thread Models
- **Thread**: The main container for conversation state.
- **ThreadMetadata**: Arbitrary key-value pairs attached to a thread.

### 2. Execution Models
- **RunInput**: Input data for starting a graph run.
- **StreamRequest**: Parameters for streaming execution (stream mode, config).

## Usage Example

```python
thread = Thread(
    thread_id="session_123",
    created_at=datetime.now(),
    metadata=ThreadMetadata(user_id="user_1")
)
```
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class ThreadMetadata(BaseModel):
    """Metadata for a thread (maps to session metadata)."""

    graph_id: Optional[str] = None
    assistant_id: Optional[str] = None
    user_id: Optional[str] = None
    session_type: Optional[str] = None


class ThreadValues(BaseModel):
    """Current state values of a thread."""

    messages: List[Dict[str, Any]] = Field(default_factory=list)


class Thread(BaseModel):
    """LangGraph SDK Thread format.

    Maps to ChatSession in the existing backend.
    """

    thread_id: str = Field(..., description="Unique thread identifier")
    created_at: datetime = Field(..., description="Thread creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    metadata: ThreadMetadata = Field(
        default_factory=ThreadMetadata, description="Thread metadata"
    )
    values: Optional[ThreadValues] = Field(None, description="Current thread state")


class ThreadCreate(BaseModel):
    """Request to create a new thread."""

    metadata: Optional[ThreadMetadata] = None


class ThreadSearchRequest(BaseModel):
    """Request to search/list threads."""

    metadata: Optional[ThreadMetadata] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class GraphInfo(BaseModel):
    """Information about available graphs."""

    graph_id: str
    name: str
    description: str


class InfoResponse(BaseModel):
    """Response for /info endpoint."""

    version: str = "1.0.0"
    graphs: List[GraphInfo]
    api_version: str = "langgraph-sdk-compatible"


class StreamMode(str):
    """Stream mode options."""

    VALUES = "values"
    UPDATES = "updates"
    MESSAGES = "messages"


class RunInput(BaseModel):
    """Input for running a graph."""

    messages: Optional[List[Dict[str, Any]]] = None
    input: Optional[Dict[str, Any]] = None


class StreamRequest(BaseModel):
    """Request to stream a graph run."""

    input: Optional[Union[RunInput, Dict[str, Any]]] = None
    config: Optional[Dict[str, Any]] = None
    stream_mode: Optional[List[str]] = Field(default_factory=lambda: ["values"])
    metadata: Optional[Dict[str, Any]] = None
    assistant_id: Optional[str] = None


class ThreadStateResponse(BaseModel):
    """Response for thread state."""

    values: ThreadValues
    next: List[str] = Field(default_factory=list)
    checkpoint: Optional[Dict[str, Any]] = None
