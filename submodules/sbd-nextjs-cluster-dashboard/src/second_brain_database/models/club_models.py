"""
# University Club Models

This module defines the **hierarchical data structures** for the University Clubs platform.
It models the complex relationships between universities, clubs, verticals (sub-teams), and members,
along with event management and WebRTC integration.

## Domain Model Overview

The club system is organized into a four-level hierarchy:

1.  **University**: The root entity (e.g., "Stanford University"). Verified by domain.
2.  **Club**: A student organization under a university (e.g., "Robotics Club").
3.  **Vertical**: A specialized sub-team within a club (e.g., "Drone Team").
4.  **Member**: A user with a specific role in a club/vertical.

## Key Features

### 1. Role-Based Access Control (RBAC)
- **Owner**: Full control over the club.
- **Admin**: Can manage members and events.
- **Lead**: Manages a specific vertical.
- **Member**: Standard participation rights.

### 2. Event Management
- **Lifecycle**: Draft → Published → Completed/Cancelled.
- **Visibility**: Public, Members Only, or Invite Only.
- **Virtual Events**: Integration with WebRTC for online meetings.

### 3. Verification System
- **Universities**: Verified via email domain (e.g., `@stanford.edu`).
- **Clubs**: Approved by university admins or system admins.

## Usage Examples

### Defining a Club

```python
club = CreateClubRequest(
    name="AI Society",
    category=ClubCategory.TECH,
    university_id="uni_123",
    slug="ai-society"  # Auto-generated if omitted
)
```

### Creating an Event

```python
event = CreateEventRequest(
    title="Intro to ML Workshop",
    event_type=EventType.WORKSHOP,
    start_time=datetime.now() + timedelta(days=7),
    end_time=datetime.now() + timedelta(days=7, hours=2),
    visibility=EventVisibility.PUBLIC
)
```

## Module Attributes

Attributes:
    ClubRole (Enum): Hierarchical roles (Owner > Admin > Lead > Member).
    ClubCategory (Enum): Classification for discovery (Tech, Sports, Arts, etc.).
    UniversityStatus (Enum): Verification state of a university.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import re


class ClubRole(str, Enum):
    """
    Enumeration of club member roles with hierarchical permissions.

    **Hierarchy:**
    *   **OWNER**: Full control, including deletion and transfer of ownership.
    *   **ADMIN**: Can manage members, events, and settings.
    *   **LEAD**: Manages a specific vertical (sub-team).
    *   **MEMBER**: Standard participation rights.
    """
    OWNER = "owner"
    ADMIN = "admin"
    LEAD = "lead"
    MEMBER = "member"


class ClubCategory(str, Enum):
    """
    Enumeration of club categories for organization and discovery.

    Used to filter clubs in the directory.
    """
    TECH = "tech"
    CULTURAL = "cultural"
    SPORTS = "sports"
    ACADEMIC = "academic"
    SOCIAL = "social"
    ENTREPRENEURSHIP = "entrepreneurship"
    ENVIRONMENTAL = "environmental"
    ARTS = "arts"
    OTHER = "other"


class UniversityStatus(str, Enum):
    """
    Enumeration of university verification statuses.

    *   **PENDING**: Submitted but not yet verified.
    *   **VERIFIED**: Domain confirmed and admin approved.
    *   **REJECTED**: Denied by admin.
    """
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


# Document Models (for MongoDB)

class UniversityDocument(BaseModel):
    """
    MongoDB document model for a University/Institution.

    Represents the root entity in the club hierarchy. Universities are verified
    by their email domain (e.g., `@stanford.edu`) to ensure authenticity.

    **Key Fields:**
    *   **domain**: The primary email domain used for verification.
    *   **is_verified**: True if the domain has been confirmed via DNS or admin.
    *   **admin_approved**: True if a platform admin has manually approved the university.
    """
    university_id: str = Field(..., description="Unique university identifier")
    name: str = Field(..., min_length=2, max_length=200, description="University name")
    domain: str = Field(..., description="Primary domain (e.g., university.edu)")
    description: Optional[str] = Field(None, max_length=1000, description="University description")
    location: Optional[str] = Field(None, max_length=200, description="University location")
    website: Optional[str] = Field(None, description="University website URL")
    logo_url: Optional[str] = Field(None, description="University logo URL")
    is_verified: bool = Field(default=False, description="Domain verification status")
    admin_approved: bool = Field(default=False, description="Admin approval status")
    status: UniversityStatus = Field(default=UniversityStatus.PENDING, description="Verification status")
    created_by: str = Field(..., description="User ID who requested university")
    approved_by: Optional[str] = Field(None, description="Admin ID who approved")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    club_count: int = Field(default=0, description="Number of active clubs")
    total_members: int = Field(default=0, description="Total members across all clubs")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator('domain')
    @classmethod
    def validate_domain(cls, v):
        """Validate domain format."""
        if not v:
            raise ValueError('Domain is required')
        # Basic domain validation
        domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, v):
            raise ValueError('Invalid domain format')
        return v.lower()

    @field_validator('website')
    @classmethod
    def validate_website(cls, v):
        """Validate website URL format."""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('Website must start with http:// or https://')
        return v


class ClubDocument(BaseModel):
    """
    MongoDB document model for a Student Club.

    Clubs are organizations under a university. They can have multiple 'verticals'
    (sub-teams) and members with different roles.

    **Key Fields:**
    *   **slug**: URL-friendly identifier (e.g., 'ai-society'). Auto-generated from name.
    *   **university_id**: Reference to the parent university.
    *   **owner_id**: The user who has full control over the club.
    """
    club_id: str = Field(..., description="Unique club identifier")
    name: str = Field(..., min_length=2, max_length=100, description="Club name")
    slug: str = Field(..., description="URL-friendly slug")
    description: Optional[str] = Field(None, max_length=1000, description="Club description")
    category: ClubCategory = Field(..., description="Club category")
    university_id: str = Field(..., description="Parent university ID")
    owner_id: str = Field(..., description="Club owner user ID")
    logo_url: Optional[str] = Field(None, description="Club logo URL")
    banner_url: Optional[str] = Field(None, description="Club banner image URL")
    website_url: Optional[str] = Field(None, description="Club website URL")
    social_links: Dict[str, str] = Field(default_factory=dict, description="Social media links")
    is_active: bool = Field(default=True, description="Club active status")
    is_public: bool = Field(default=True, description="Public visibility")
    member_count: int = Field(default=1, description="Total member count")
    vertical_count: int = Field(default=0, description="Number of verticals")
    max_members: Optional[int] = Field(None, description="Maximum member limit")
    tags: List[str] = Field(default_factory=list, description="Club tags for search")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Club-specific settings")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator('slug')
    @classmethod
    def validate_slug(cls, v):
        """Validate slug format."""
        if not v:
            raise ValueError('Slug is required')
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError('Slug must contain only lowercase letters, numbers, and hyphens')
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Slug must be between 3 and 50 characters')
        return v

    @model_validator(mode='after')
    def generate_slug_from_name(self):
        """Auto-generate slug from name if not provided."""
        if not self.slug and self.name:
            # Generate slug from name
            slug = re.sub(r'[^\w\s-]', '', self.name.lower())
            slug = re.sub(r'[\s_-]+', '-', slug).strip('-')
            self.slug = slug[:50]  # Limit length
        return self


class VerticalDocument(BaseModel):
    """
    MongoDB document model for a Club Vertical (Sub-team).

    Verticals are specialized groups within a club (e.g., "Marketing Team", "Drone Project").
    They allow for more granular organization and leadership roles.

    **Key Fields:**
    *   **lead_id**: The user responsible for this specific vertical.
    *   **color/icon**: Visual identifiers for UI customization.
    """
    vertical_id: str = Field(..., description="Unique vertical identifier")
    club_id: str = Field(..., description="Parent club ID")
    name: str = Field(..., min_length=2, max_length=50, description="Vertical name")
    description: Optional[str] = Field(None, max_length=500, description="Vertical description")
    lead_id: Optional[str] = Field(None, description="Vertical lead user ID")
    member_count: int = Field(default=0, description="Number of members in vertical")
    max_members: Optional[int] = Field(None, description="Maximum member limit")
    color: Optional[str] = Field(None, description="Vertical color/theme")
    icon: Optional[str] = Field(None, description="Vertical icon identifier")
    is_active: bool = Field(default=True, description="Vertical active status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClubMemberDocument(BaseModel):
    """
    MongoDB document model for a Club Membership.

    Links a User to a Club with a specific Role. Can also optionally link to a Vertical.

    **Key Fields:**
    *   **role**: The permission level (Owner, Admin, Lead, Member).
    *   **joined_at**: Timestamp when the invitation was accepted.
    *   **is_alumni**: Flag for former members who want to stay connected.
    """
    member_id: str = Field(..., description="Unique membership identifier")
    club_id: str = Field(..., description="Club ID")
    user_id: str = Field(..., description="User ID")
    role: ClubRole = Field(..., description="Member role in club")
    vertical_id: Optional[str] = Field(None, description="Assigned vertical ID")
    invited_by: str = Field(..., description="User ID who invited this member")
    invited_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    joined_at: Optional[datetime] = Field(None, description="When member accepted invitation")
    is_active: bool = Field(default=True, description="Membership active status")
    is_alumni: bool = Field(default=False, description="Alumni status")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
    contributions: int = Field(default=0, description="Contribution/activity score")
    notes: Optional[str] = Field(None, max_length=500, description="Admin notes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def set_joined_at(self):
        """Set joined_at when membership becomes active."""
        if self.is_active and not self.joined_at:
            self.joined_at = datetime.now(timezone.utc)
        return self


# Request/Response Models (for API)

class CreateUniversityRequest(BaseModel):
    """
    Request model for registering a new university.

    Requires a valid domain for verification.
    """
    name: str = Field(..., min_length=2, max_length=200, description="Official name of the university")
    domain: str = Field(..., description="Primary email domain (e.g., stanford.edu)")
    description: Optional[str] = Field(None, max_length=1000, description="Brief description")
    location: Optional[str] = Field(None, max_length=200, description="City, Country")
    website: Optional[str] = Field(None, description="Official website URL")
    logo_url: Optional[str] = Field(None, description="URL to university logo")


class UniversityResponse(BaseModel):
    """
    Response model for university details.

    Includes verification status and aggregate statistics.
    """
    university_id: str
    name: str
    domain: str
    description: Optional[str]
    location: Optional[str]
    website: Optional[str]
    logo_url: Optional[str]
    is_verified: bool
    admin_approved: bool
    status: UniversityStatus
    club_count: int
    total_members: int
    created_at: datetime
    updated_at: datetime


class CreateClubRequest(BaseModel):
    """
    Request model for creating a new student club.

    **Validation:**
    *   **name**: 2-100 characters.
    *   **max_members**: Optional limit (1-10000).
    """
    name: str = Field(..., min_length=2, max_length=100, description="Club name")
    description: Optional[str] = Field(None, max_length=1000, description="Club mission/description")
    category: ClubCategory = Field(..., description="Primary category")
    university_id: str = Field(..., description="ID of the university this club belongs to")
    logo_url: Optional[str] = Field(None, description="Club logo URL")
    banner_url: Optional[str] = Field(None, description="Club banner URL")
    website_url: Optional[str] = Field(None, description="External website URL")
    social_links: Dict[str, str] = Field(default_factory=dict, description="Map of platform -> URL")
    max_members: Optional[int] = Field(None, gt=0, le=10000, description="Optional member cap")
    tags: List[str] = Field(default_factory=list, description="Search tags")


class ClubResponse(BaseModel):
    """
    Response model for club details.

    Includes public metadata and member counts.
    """
    club_id: str
    name: str
    slug: str
    description: Optional[str]
    category: ClubCategory
    university_id: str
    owner_id: str
    logo_url: Optional[str]
    banner_url: Optional[str]
    website_url: Optional[str]
    social_links: Dict[str, str]
    is_active: bool
    is_public: bool
    member_count: int
    vertical_count: int
    max_members: Optional[int]
    tags: List[str]
    created_at: datetime
    updated_at: datetime


class CreateVerticalRequest(BaseModel):
    """
    Request model for creating a new vertical (sub-team).

    Verticals help organize large clubs into smaller, manageable groups.
    """
    name: str = Field(..., min_length=2, max_length=50, description="Vertical name")
    description: Optional[str] = Field(None, max_length=500, description="Purpose of the vertical")
    lead_id: Optional[str] = Field(None, description="User ID of the vertical lead")
    max_members: Optional[int] = Field(None, gt=0, le=1000, description="Optional member cap")
    color: Optional[str] = Field(None, description="Hex color code for UI")
    icon: Optional[str] = Field(None, description="Icon identifier")


class VerticalResponse(BaseModel):
    """
    Response model for vertical details.
    """
    vertical_id: str
    club_id: str
    name: str
    description: Optional[str]
    lead_id: Optional[str]
    member_count: int
    max_members: Optional[int]
    color: Optional[str]
    icon: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class InviteMemberRequest(BaseModel):
    """
    Request model for inviting a user to a club.

    **Fields:**
    *   **role**: The role to assign upon joining.
    *   **vertical_id**: Optional assignment to a specific sub-team.
    """
    user_id: str = Field(..., description="User ID to invite")
    role: ClubRole = Field(..., description="Role to assign")
    vertical_id: Optional[str] = Field(None, description="Vertical to assign")
    message: Optional[str] = Field(None, max_length=500, description="Invitation message")


class ClubMemberResponse(BaseModel):
    """
    Response model for club member details.

    Includes role, vertical assignment, and activity metrics.
    """
    member_id: str
    club_id: str
    user_id: str
    role: ClubRole
    vertical_id: Optional[str]
    invited_by: str
    invited_at: datetime
    joined_at: Optional[datetime]
    is_active: bool
    is_alumni: bool
    last_activity: Optional[datetime]
    contributions: int
    created_at: datetime
    updated_at: datetime


class ClubSearchRequest(BaseModel):
    """
    Request model for searching clubs.

    Supports filtering by category, university, and tags.
    """
    query: Optional[str] = Field(None, description="Search query")
    category: Optional[ClubCategory] = Field(None, description="Filter by category")
    university_id: Optional[str] = Field(None, description="Filter by university")
    tags: List[str] = Field(default_factory=list, description="Filter by tags")
    page: int = Field(default=1, gt=0, description="Page number")
    limit: int = Field(default=20, gt=0, le=100, description="Results per page")


class ClubAnalyticsResponse(BaseModel):
    """
    Response model for club analytics.

    Provides insights into member growth and engagement.
    """
    club_id: str
    member_growth: List[Dict[str, Any]] = Field(default_factory=list, description="Time-series data of member count")
    vertical_participation: Dict[str, int] = Field(default_factory=dict, description="Member count per vertical")
    activity_metrics: Dict[str, Any] = Field(default_factory=dict, description="Event attendance and contribution stats")
    engagement_score: float = Field(default=0.0, description="Calculated engagement score (0-100)")


class BulkInviteRequest(BaseModel):
    """
    Request model for bulk member invitation.

    Allows inviting up to 50 members at once.
    """
    invites: List[InviteMemberRequest] = Field(..., min_length=1, max_length=50, description="List of invitations")


class TransferMemberRequest(BaseModel):
    """
    Request model for transferring a member between verticals.
    """
    member_id: str = Field(..., description="ID of the member to transfer")
    vertical_id: Optional[str] = Field(None, description="New vertical ID, null to remove from current vertical")


class UpdateMemberRoleRequest(BaseModel):
    """
    Request model for updating a member's role.

    Used for promotions (e.g., Member -> Lead) or demotions.
    """
    role: ClubRole = Field(..., description="New role")
    vertical_id: Optional[str] = Field(None, description="Optional vertical assignment (required for LEAD role)")


# Event Models

class EventType(str, Enum):
    """
    Enumeration of event types for classification.

    Helps users filter events based on their interests.
    """
    MEETING = "meeting"
    WORKSHOP = "workshop"
    SOCIAL = "social"
    COMPETITION = "competition"
    CONFERENCE = "conference"
    NETWORKING = "networking"
    OTHER = "other"


class EventStatus(str, Enum):
    """
    Enumeration of event lifecycle states.

    *   **DRAFT**: Only visible to organizers.
    *   **PUBLISHED**: Visible to the target audience.
    *   **CANCELLED**: Event called off.
    *   **COMPLETED**: Event finished (archived).
    """
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class EventVisibility(str, Enum):
    """
    Enumeration of event visibility levels.

    *   **PUBLIC**: Visible to anyone on the platform.
    *   **MEMBERS_ONLY**: Restricted to club members.
    *   **INVITE_ONLY**: Private, requires direct invitation.
    """
    PUBLIC = "public"
    MEMBERS_ONLY = "members_only"
    INVITE_ONLY = "invite_only"


class EventDocument(BaseModel):
    """
    MongoDB document model for a Club Event.

    Events are the core activity unit of clubs. They can be physical, virtual (WebRTC),
    or hybrid. Supports recurring schedules and rich metadata.

    **Key Fields:**
    *   **visibility**: Controls who can see and register for the event.
    *   **recurrence_rule**: RRULE string for repeating events (e.g., "FREQ=WEEKLY").
    *   **webrtc_room_id**: If present, enables the "Join Virtual Room" button.
    """
    event_id: str = Field(..., description="Unique event identifier")
    club_id: str = Field(..., description="Parent club ID")
    title: str = Field(..., min_length=3, max_length=200, description="Event title")
    description: Optional[str] = Field(None, max_length=2000, description="Event description")
    event_type: EventType = Field(..., description="Type of event")
    status: EventStatus = Field(default=EventStatus.DRAFT, description="Event status")
    visibility: EventVisibility = Field(default=EventVisibility.MEMBERS_ONLY, description="Event visibility")
    start_time: datetime = Field(..., description="Event start time")
    end_time: datetime = Field(..., description="Event end time")
    timezone: str = Field(default="UTC", description="Event timezone")
    location: Optional[str] = Field(None, max_length=500, description="Physical location")
    virtual_link: Optional[str] = Field(None, description="Virtual meeting link")
    max_attendees: Optional[int] = Field(None, gt=0, description="Maximum number of attendees")
    attendee_count: int = Field(default=0, description="Current attendee count")
    organizer_id: str = Field(..., description="Event organizer user ID")
    co_organizers: List[str] = Field(default_factory=list, description="Co-organizer user IDs")
    tags: List[str] = Field(default_factory=list, description="Event tags")
    image_url: Optional[str] = Field(None, description="Event image/banner URL")
    agenda: List[Dict[str, Any]] = Field(default_factory=list, description="Event agenda items")
    requirements: List[str] = Field(default_factory=list, description="Event requirements/prerequisites")
    is_recurring: bool = Field(default=False, description="Whether event is recurring")
    recurrence_rule: Optional[str] = Field(None, description="Recurrence rule (RRULE)")
    parent_event_id: Optional[str] = Field(None, description="Parent event ID for recurring events")
    webrtc_room_id: Optional[str] = Field(None, description="WebRTC room ID for virtual events")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Event-specific settings")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode='after')
    def validate_times(self):
        """Validate event timing."""
        if self.end_time <= self.start_time:
            raise ValueError('End time must be after start time')
        return self


class EventAttendeeDocument(BaseModel):
    """
    MongoDB document model for Event Attendance.

    Tracks a user's registration and participation in an event.

    **Key Fields:**
    *   **status**: 'registered', 'waitlisted', 'cancelled', 'attended'.
    *   **attended_at**: Timestamp when the user checked in.
    """
    attendee_id: str = Field(..., description="Unique attendee identifier")
    event_id: str = Field(..., description="Event ID")
    user_id: str = Field(..., description="Attendee user ID")
    status: str = Field(default="registered", description="Attendance status")
    registered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attended_at: Optional[datetime] = Field(None, description="When user marked as attended")
    notes: Optional[str] = Field(None, max_length=500, description="Attendee notes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Event Request/Response Models

class CreateEventRequest(BaseModel):
    """
    Request model for creating a new event.

    **Validation:**
    *   **end_time**: Must be strictly after `start_time`.
    *   **title**: 3-200 characters.
    """
    title: str = Field(..., min_length=3, max_length=200, description="Event title")
    description: Optional[str] = Field(None, max_length=2000, description="Detailed description")
    event_type: EventType = Field(..., description="Type of event")
    visibility: EventVisibility = Field(default=EventVisibility.MEMBERS_ONLY, description="Who can see this")
    start_time: datetime = Field(..., description="Start timestamp")
    end_time: datetime = Field(..., description="End timestamp")
    timezone: str = Field(default="UTC", description="Timezone identifier")
    location: Optional[str] = Field(None, max_length=500, description="Physical location")
    virtual_link: Optional[str] = Field(None, description="URL for virtual meeting")
    max_attendees: Optional[int] = Field(None, gt=0, description="Capacity limit")
    co_organizers: List[str] = Field(default_factory=list, description="IDs of co-hosts")
    tags: List[str] = Field(default_factory=list, description="Search tags")
    image_url: Optional[str] = Field(None, description="Banner image URL")
    agenda: List[Dict[str, Any]] = Field(default_factory=list, description="Schedule items")
    requirements: List[str] = Field(default_factory=list, description="Prerequisites")
    is_recurring: bool = Field(default=False, description="Is this a repeating event?")
    recurrence_rule: Optional[str] = Field(None, description="RRULE string")

    @model_validator(mode='after')
    def validate_times(self):
        """Validate event timing."""
        if self.end_time <= self.start_time:
            raise ValueError('End time must be after start time')
        return self


class EventResponse(BaseModel):
    """
    Response model for event details.

    Includes all metadata required to render the event page.
    """
    event_id: str
    club_id: str
    title: str
    description: Optional[str]
    event_type: EventType
    status: EventStatus
    visibility: EventVisibility
    start_time: datetime
    end_time: datetime
    timezone: str
    location: Optional[str]
    virtual_link: Optional[str]
    max_attendees: Optional[int]
    attendee_count: int
    organizer_id: str
    co_organizers: List[str]
    tags: List[str]
    image_url: Optional[str]
    agenda: List[Dict[str, Any]]
    requirements: List[str]
    is_recurring: bool
    recurrence_rule: Optional[str]
    parent_event_id: Optional[str]
    webrtc_room_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class UpdateEventRequest(BaseModel):
    """
    Request model for updating an existing event.

    All fields are optional; only provided fields will be updated.
    """
    title: Optional[str] = Field(None, min_length=3, max_length=200, description="Updated title")
    description: Optional[str] = Field(None, max_length=2000, description="Updated description")
    event_type: Optional[EventType] = Field(None, description="Updated type")
    visibility: Optional[EventVisibility] = Field(None, description="Updated visibility")
    start_time: Optional[datetime] = Field(None, description="Updated start time")
    end_time: Optional[datetime] = Field(None, description="Updated end time")
    timezone: Optional[str] = Field(None, description="Updated timezone")
    location: Optional[str] = Field(None, max_length=500, description="Updated location")
    virtual_link: Optional[str] = Field(None, description="Updated virtual link")
    max_attendees: Optional[int] = Field(None, gt=0, description="Updated capacity")
    co_organizers: Optional[List[str]] = Field(None, description="Updated co-organizers")
    tags: Optional[List[str]] = Field(None, description="Updated tags")
    image_url: Optional[str] = Field(None, description="Updated image URL")
    agenda: Optional[List[Dict[str, Any]]] = Field(None, description="Updated agenda")
    requirements: Optional[List[str]] = Field(None, description="Updated requirements")
    status: Optional[EventStatus] = Field(None, description="Updated status (e.g., CANCELLED)")


class EventAttendeeResponse(BaseModel):
    """
    Response model for event attendee details.
    """
    attendee_id: str
    event_id: str
    user_id: str
    status: str
    registered_at: datetime
    attended_at: Optional[datetime]
    notes: Optional[str]


class RegisterForEventRequest(BaseModel):
    """
    Request model for registering for an event.
    """
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes for organizer")


class EventSearchRequest(BaseModel):
    """
    Request model for searching events.

    Supports filtering by date range, type, and organizer.
    """
    query: Optional[str] = Field(None, description="Search query")
    event_type: Optional[EventType] = Field(None, description="Filter by event type")
    status: Optional[EventStatus] = Field(None, description="Filter by status")
    visibility: Optional[EventVisibility] = Field(None, description="Filter by visibility")
    start_date: Optional[datetime] = Field(None, description="Events starting after this date")
    end_date: Optional[datetime] = Field(None, description="Events ending before this date")
    club_id: Optional[str] = Field(None, description="Filter by club")
    organizer_id: Optional[str] = Field(None, description="Filter by organizer")
    tags: List[str] = Field(default_factory=list, description="Filter by tags")
    page: int = Field(default=1, gt=0, description="Page number")
    limit: int = Field(default=20, gt=0, le=100, description="Results per page")
