"""
# Skill Tracking Models

This module defines the data structures for the **Personal Skill Log**, a system for tracking
professional development, learning progress, and mastery over time. It supports hierarchical
skill trees, evidence-based logging, and detailed analytics.

## Domain Model Overview

The skill tracking system is built around:

- **Skill**: A specific competency (e.g., "Python", "Public Speaking").
- **Skill Tree**: Hierarchical organization allowing skills to have parents and children.
- **Log Entry**: A record of activity, practice, or achievement related to a skill.
- **Evidence**: Concrete proof of skill application (notes, links, projects).

## Key Features

### 1. Hierarchical Organization
- **Parent/Child Links**: Skills can be organized into trees (e.g., "Backend Dev" → "Python" → "FastAPI").
- **Rollup Analytics**: Progress in child skills contributes to parent skill statistics.

### 2. Evidence-Based Tracking
- **Log Types**: Track `learning`, `practicing`, `used`, or `mastered` states.
- **Context**: Attach metadata like duration, confidence level, and related projects.

### 3. Analytics
- **Velocity**: Track learning hours over time.
- **Proficiency**: Numeric levels (1-5) and confidence scores (1-10).
- **Staleness**: Identify skills that haven't been practiced recently.

## Usage Examples

### Creating a Skill

```python
skill = CreateSkillRequest(
    name="FastAPI",
    category="Backend Development",
    difficulty="intermediate",
    parent_skill_ids=["skill_python_123"]
)
```

### Logging Progress

```python
log = CreateSkillLogRequest(
    progress_state="practicing",
    duration_hours=2.5,
    notes="Implemented OAuth2 flow in the new project",
    confidence_level=8
)
```

## Module Attributes

Attributes:
    None: This module relies on Pydantic models and does not define global constants.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field


# --- Core Skill Models ---

class SkillMetadata(BaseModel):
    """Extensible metadata for skills.

    Attributes:
        category (Optional[str]): Skill category (e.g., 'programming', 'design').
        difficulty (Optional[Literal]): Self-assessed difficulty level.
        priority (Optional[Literal]): Importance priority.
        custom_fields (Optional[Dict]): User-defined custom metadata.
    """

    category: Optional[str] = Field(None, description="Skill category (e.g., 'programming', 'design')")
    difficulty: Optional[Literal["beginner", "intermediate", "advanced", "expert"]] = Field(
        None, description="Self-assessed difficulty level"
    )
    priority: Optional[Literal["low", "medium", "high", "critical"]] = Field(
        None, description="Importance priority"
    )
    custom_fields: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="User-defined custom metadata"
    )


# --- Skill Log Models ---

class SkillEvidence(BaseModel):
    """Evidence attached to skill log entries.

    Attributes:
        type (Literal): Type of evidence (note, link, reflection, achievement).
        content (str): Evidence content.
        metadata (Optional[Dict]): Additional evidence metadata (e.g., URL for links).
    """

    type: Literal["note", "link", "reflection", "achievement"] = Field(
        ..., description="Type of evidence"
    )
    content: str = Field(..., min_length=1, max_length=5000, description="Evidence content")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional evidence metadata (e.g., URL for links)"
    )


class SkillLogContext(BaseModel):
    """Contextual information for skill log entries.

    Attributes:
        quarter (Optional[str]): Time period (e.g., 'Q1 2025').
        year (Optional[int]): Year of the activity.
        duration_hours (Optional[float]): Time spent in hours.
        confidence_level (Optional[int]): Self-assessed confidence level (1-10).
    """

    quarter: Optional[str] = Field(None, description="Time period (e.g., 'Q1 2025')")
    year: Optional[int] = Field(None, description="Year of the activity")
    duration_hours: Optional[float] = Field(None, gt=0, description="Time spent in hours")
    confidence_level: Optional[int] = Field(
        None, ge=1, le=10, description="Self-assessed confidence level (1-10)"
    )


class SkillLogDocument(BaseModel):
    """Embedded log entry within skill document.

    Attributes:
        log_id (str): Unique log entry identifier.
        project_id (Optional[str]): Optional project linkage.
        progress_state (Literal): Current progress state.
        numeric_level (Optional[int]): Optional numeric proficiency level (1-5).
        timestamp (datetime): When this activity occurred.
        notes (Optional[str]): Personal notes and reflections.
        context (SkillLogContext): Situational context.
        created_at (datetime): Creation timestamp.
    """

    log_id: str = Field(..., description="Unique log entry identifier")
    project_id: Optional[str] = Field(None, description="Optional project linkage")
    progress_state: Literal["learning", "practicing", "used", "mastered"] = Field(
        ..., description="Current progress state"
    )
    numeric_level: Optional[int] = Field(
        None, ge=1, le=5, description="Optional numeric proficiency level (1-5)"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When this activity occurred")
    # SIMPLIFIED: Single notes field instead of complex evidence
    notes: Optional[str] = Field(None, max_length=2000, description="Personal notes and reflections")
    context: SkillLogContext = Field(
        default_factory=SkillLogContext, description="Situational context"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SkillDocument(BaseModel):
    """Database document model for the user_skills collection.

    Attributes:
        skill_id (str): Unique skill identifier (user-scoped).
        user_id (str): Owner of the skill.
        name (str): Skill name.
        description (Optional[str]): Optional skill description.
        parent_skill_ids (List[str]): IDs of parent skills (multiple inheritance supported).
        tags (List[str]): Categorization tags.
        metadata (SkillMetadata): Extensible skill metadata.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
        is_active (bool): Soft delete flag.
        logs (List[SkillLogDocument]): Embedded skill log entries.
    """

    skill_id: str = Field(..., description="Unique skill identifier (user-scoped)")
    user_id: str = Field(..., description="Owner of the skill")
    name: str = Field(..., min_length=1, max_length=200, description="Skill name")
    description: Optional[str] = Field(None, max_length=1000, description="Optional skill description")
    parent_skill_ids: List[str] = Field(
        default_factory=list, description="IDs of parent skills (multiple inheritance supported)"
    )
    # child_skill_ids removed - computed on-demand via queries to avoid consistency issues
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    metadata: SkillMetadata = Field(default_factory=SkillMetadata, description="Extensible skill metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(True, description="Soft delete flag")
    # EMBEDDED LOGS - No separate collection
    logs: List[SkillLogDocument] = Field(
        default_factory=list, description="Embedded skill log entries"
    )


# --- Analytics Models ---

class SkillRollupStats(BaseModel):
    """Roll-up statistics for parent skills aggregating child data.

    Attributes:
        child_count (int): Total number of child skills.
        active_children (int): Number of active child skills.
        total_child_logs (int): Total log entries across all children.
        average_child_level (Optional[float]): Average numeric level of children.
        last_child_activity (Optional[datetime]): Most recent activity in child tree.
    """

    child_count: int = Field(0, description="Total number of child skills")
    active_children: int = Field(0, description="Number of active child skills")
    total_child_logs: int = Field(0, description="Total log entries across all children")
    average_child_level: Optional[float] = Field(None, description="Average numeric level of children")
    last_child_activity: Optional[datetime] = Field(None, description="Most recent activity in child tree")


class SkillAnalyticsStats(BaseModel):
    """Computed analytics for a skill.

    Attributes:
        total_logs (int): Total number of log entries.
        current_state (Optional[str]): Most recent progress state.
        last_activity (Optional[datetime]): Most recent log timestamp.
        project_count (int): Number of unique projects linked.
        total_hours (float): Total hours logged.
        average_confidence (Optional[float]): Average confidence level.
        parent_rollup (SkillRollupStats): Aggregated child skill statistics.
    """

    total_logs: int = Field(0, description="Total number of log entries")
    current_state: Optional[str] = Field(None, description="Most recent progress state")
    last_activity: Optional[datetime] = Field(None, description="Most recent log timestamp")
    project_count: int = Field(0, description="Number of unique projects linked")
    total_hours: float = Field(0.0, description="Total hours logged")
    average_confidence: Optional[float] = Field(None, description="Average confidence level")
    parent_rollup: SkillRollupStats = Field(
        default_factory=SkillRollupStats, description="Aggregated child skill statistics"
    )


class SkillAnalyticsDocument(BaseModel):
    """Database document model for the skill_analytics_cache collection.

    Attributes:
        user_id (str): Owner of the analytics.
        skill_id (str): Skill being analyzed.
        last_updated (datetime): Last update timestamp.
        stats (SkillAnalyticsStats): Computed analytics data.
    """

    user_id: str = Field(..., description="Owner of the analytics")
    skill_id: str = Field(..., description="Skill being analyzed")
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    stats: SkillAnalyticsStats = Field(..., description="Computed analytics data")


# --- API Request/Response Models ---

class CreateSkillRequest(BaseModel):
    """Request model for creating a new skill.

    Attributes:
        name (str): Skill name.
        description (Optional[str]): Optional skill description.
        parent_skill_ids (List[str]): IDs of parent skills.
        tags (List[str]): Categorization tags.
        metadata (Optional[SkillMetadata]): Extensible skill metadata.
    """

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    parent_skill_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    metadata: Optional[SkillMetadata] = None


class UpdateSkillRequest(BaseModel):
    """Request model for updating an existing skill.

    Attributes:
        name (Optional[str]): Skill name.
        description (Optional[str]): Optional skill description.
        tags (Optional[List[str]]): Categorization tags.
        metadata (Optional[SkillMetadata]): Extensible skill metadata.
    """

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None
    metadata: Optional[SkillMetadata] = None


class SkillResponse(BaseModel):
    """Response model for skill data.

    Attributes:
        skill_id (str): Unique skill identifier.
        name (str): Skill name.
        description (Optional[str]): Skill description.
        parent_skill_ids (List[str]): IDs of parent skills.
        child_skill_ids (List[str]): Computed children IDs.
        tags (List[str]): Categorization tags.
        metadata (SkillMetadata): Extensible skill metadata.
        created_at (str): Creation timestamp string.
        updated_at (str): Last update timestamp string.
        analytics (Optional[SkillAnalyticsStats]): Computed analytics data.
    """

    skill_id: str
    name: str
    description: Optional[str]
    parent_skill_ids: List[str]
    child_skill_ids: List[str] = Field(default_factory=list, description="Computed children - not stored")
    tags: List[str]
    metadata: SkillMetadata
    created_at: str
    updated_at: str
    analytics: Optional[SkillAnalyticsStats] = None


class SkillTreeNode(BaseModel):
    """Node in the skill hierarchy tree.

    Attributes:
        skill (SkillResponse): The skill data for this node.
        children (List[SkillTreeNode]): Child nodes in the hierarchy.
    """

    skill: SkillResponse
    children: List['SkillTreeNode'] = Field(default_factory=list)


class CreateSkillLogRequest(BaseModel):
    """Request model for creating a skill log entry.

    Attributes:
        project_id (Optional[str]): Optional project linkage.
        progress_state (Literal): Current progress state.
        numeric_level (Optional[int]): Optional numeric proficiency level (1-5).
        timestamp (Optional[datetime]): When this activity occurred.
        notes (Optional[str]): Personal notes and reflections.
        context (Optional[SkillLogContext]): Situational context.
    """

    project_id: Optional[str] = None
    progress_state: Literal["learning", "practicing", "used", "mastered"]
    numeric_level: Optional[int] = Field(None, ge=1, le=5)
    timestamp: Optional[datetime] = None
    # SIMPLIFIED: Single notes field instead of complex evidence
    notes: Optional[str] = Field(None, max_length=2000)
    context: Optional[SkillLogContext] = None


class SkillLogResponse(BaseModel):
    """Response model for skill log entries.

    Attributes:
        log_id (str): Unique log entry identifier.
        skill_id (str): ID of the skill this log belongs to.
        project_id (Optional[str]): Optional project linkage.
        progress_state (str): Current progress state.
        numeric_level (Optional[int]): Optional numeric proficiency level.
        timestamp (str): Timestamp string.
        notes (Optional[str]): Personal notes and reflections.
        context (SkillLogContext): Situational context.
        created_at (str): Creation timestamp string.
    """

    log_id: str
    skill_id: str
    project_id: Optional[str]
    progress_state: str
    numeric_level: Optional[int]
    timestamp: str
    # SIMPLIFIED: Single notes field instead of complex evidence
    notes: Optional[str]
    context: SkillLogContext
    created_at: str


class SkillAnalyticsSummary(BaseModel):
    """Summary analytics for a user's skill log.

    Attributes:
        total_skills (int): Total number of skills tracked.
        active_skills (int): Number of currently active skills.
        skills_by_state (Dict[str, int]): Count of skills in each state.
        recent_activity (List[Dict]): List of recent activity items.
        stale_skills (List[Dict]): List of skills needing attention.
        total_log_entries (int): Total number of logs.
        average_confidence (Optional[float]): Average confidence score.
        total_hours_logged (float): Total hours spent learning/practicing.
    """

    total_skills: int
    active_skills: int
    skills_by_state: Dict[str, int]
    recent_activity: List[Dict[str, Any]]
    stale_skills: List[Dict[str, Any]]
    total_log_entries: int
    average_confidence: Optional[float]
    total_hours_logged: float


class LinkSkillRequest(BaseModel):
    """Request model for linking skills in hierarchy.

    Attributes:
        parent_skill_id (str): ID of the parent skill to link to.
    """

    parent_skill_id: str = Field(..., description="ID of the parent skill to link to")


class BatchSkillOperation(BaseModel):
    """Base model for batch skill operations.

    Attributes:
        skill_ids (List[str]): List of skill IDs to operate on.
    """

    skill_ids: List[str] = Field(..., description="List of skill IDs to operate on")


# Update forward reference for SkillTreeNode
SkillTreeNode.model_rebuild()
