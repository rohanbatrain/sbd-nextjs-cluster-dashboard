"""
# Admin Models

This module defines the **data structures** for the Administrative Interface.
It includes models for abuse detection, whitelist/blocklist management, and event review.

## Domain Overview

The Admin System allows privileged users to:
- **Monitor Abuse**: Track suspicious activities like password reset spam.
- **Manage Access**: Whitelist or blocklist specific IP/Email pairs.
- **Review Events**: Audit and resolve security incidents.

## Key Models

### 1. Abuse Event
- **Purpose**: Represents a security incident requiring admin attention.
- **Fields**: `email`, `ip`, `event_type`, `timestamp`, `resolved`.
- **Usage**: Stored in MongoDB for audit trails and review queues.

### 2. Email/IP Pair
- **Purpose**: A simple tuple for whitelist/blocklist operations.
- **Fields**: `email`, `ip`.
- **Usage**: Used in Redis sets for high-speed access control checks.

## Usage Example

```python
event = AbuseEvent(
    email="user@example.com",
    ip="192.168.1.1",
    event_type="reset_spam",
    timestamp=datetime.utcnow()
)
```
"""

from datetime import datetime
from typing import Dict, Optional, TypedDict

from pydantic import BaseModel, Field


class EmailIpPairDict(TypedDict):
    """TypedDict for (email, ip) pair used in Redis and service logic."""

    email: str
    ip: str


class AbuseEvent(BaseModel):
    """
    Model representing a password reset abuse event for admin review.

    Attributes:
        id: Optional MongoDB document ID (alias: _id).
        email: Email address involved in the event.
        ip: IP address associated with the event.
        event_type: Type of abuse event (e.g., 'reset', 'block', etc.).
        timestamp: UTC timestamp of the event.
        resolved: Whether the event has been resolved by an admin.
        resolution_notes: Optional notes about the resolution.
        details: Optional extra metadata (e.g., user agent, geo info).
    """

    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")
    email: str = Field(..., description="Email address involved in the event")
    ip: str = Field(..., description="IP address associated with the event")
    event_type: str = Field(..., description="Type of abuse event (e.g., 'reset', 'block')")
    timestamp: datetime = Field(..., description="UTC timestamp of the event")
    resolved: bool = Field(False, description="Whether the event has been resolved by an admin")
    resolution_notes: Optional[str] = Field(None, description="Optional notes about the resolution")
    details: Optional[Dict] = Field(None, description="Optional extra metadata (e.g., user agent, geo info)")


class EmailIpPair(BaseModel):
    """Model for (email, ip) pair used in whitelist/blocklist endpoints."""

    email: str = Field(..., description="Email address")
    ip: str = Field(..., description="IP address")


class AbuseEventResolveRequest(BaseModel):
    """Model for resolving an abuse event."""

    event_id: str = Field(..., description="Abuse event ID")
    notes: Optional[str] = Field(None, description="Resolution notes")
