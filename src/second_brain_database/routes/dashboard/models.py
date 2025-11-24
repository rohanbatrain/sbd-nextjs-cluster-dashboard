"""
# Dashboard Models

This module defines the **data structures** for the User Dashboard System.
It handles widget configuration, layout preferences, and positioning.

## Domain Overview

The Dashboard allows users to customize their home view with various widgets.
- **Contexts**: Dashboards can be `personal`, `family`, or `team`.
- **Layouts**: Grid-based positioning system (12-column grid).
- **Widgets**: Configurable components (e.g., "Recent Files", "System Status").

## Key Models

### 1. Widget Config
- **Purpose**: Defines a single widget instance.
- **Fields**: `widget_id`, `type`, `position` (x, y, w, h), `settings`.

### 2. Dashboard Layout
- **Purpose**: Container for a set of widgets in a specific context.
- **Fields**: `context`, `context_id`, `widgets`, `grid_columns`.

## Usage Example

```python
position = WidgetPosition(x=0, y=0, w=6, h=4)
widget = WidgetConfig(
    widget_id="w_123",
    widget_type="clock",
    position=position
)
```
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WidgetPosition(BaseModel):
    """Widget position in grid layout."""

    x: int = Field(..., ge=0, description="X position in grid")
    y: int = Field(..., ge=0, description="Y position in grid")
    w: int = Field(..., ge=1, le=12, description="Width in grid units (1-12)")
    h: int = Field(..., ge=1, description="Height in grid units")


class WidgetConfig(BaseModel):
    """Widget configuration."""

    widget_id: str = Field(..., description="Unique widget instance ID")
    widget_type: str = Field(..., description="Widget type identifier")
    position: WidgetPosition = Field(..., description="Widget position in grid")
    visible: bool = Field(default=True, description="Widget visibility")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Widget-specific settings")


class DashboardLayout(BaseModel):
    """Dashboard layout configuration."""

    context: str = Field(..., pattern="^(personal|family|team)$", description="Dashboard context")
    context_id: Optional[str] = Field(None, description="Family ID or Workspace ID for context")
    widgets: List[WidgetConfig] = Field(default_factory=list, description="List of widgets")
    grid_columns: int = Field(default=12, ge=1, le=24, description="Number of grid columns")


class DashboardPreferences(BaseModel):
    """User dashboard preferences."""

    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    layouts: Dict[str, DashboardLayout] = Field(
        default_factory=dict, description="Layouts by context key (e.g., 'personal', 'family:123')"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Request/Response Models


class CreateWidgetRequest(BaseModel):
    """Request to add a widget to dashboard."""

    context: str = Field(..., pattern="^(personal|family|team)$")
    context_id: Optional[str] = None
    widget_type: str = Field(..., description="Widget type to add")
    position: Optional[WidgetPosition] = Field(None, description="Initial position (auto if not provided)")
    settings: Dict[str, Any] = Field(default_factory=dict)


class UpdateWidgetRequest(BaseModel):
    """Request to update widget configuration."""

    position: Optional[WidgetPosition] = None
    visible: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None


class UpdateLayoutRequest(BaseModel):
    """Request to update entire dashboard layout."""

    widgets: List[WidgetConfig] = Field(..., description="Complete widget list")
    grid_columns: Optional[int] = Field(None, ge=1, le=24)


class DashboardPreferencesResponse(BaseModel):
    """Response with dashboard preferences."""

    context: str
    context_id: Optional[str]
    widgets: List[WidgetConfig]
    grid_columns: int


class WidgetResponse(BaseModel):
    """Response for single widget operation."""

    widget_id: str
    widget_type: str
    position: WidgetPosition
    visible: bool
    settings: Dict[str, Any]
