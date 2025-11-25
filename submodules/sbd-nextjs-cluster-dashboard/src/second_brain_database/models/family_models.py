"""
# Family Management Models

This module defines the **core data structures** for the Family Hub system, including family groups,
member relationships, virtual economy (SBD tokens), and notification systems. It uses Pydantic
models for robust validation of all API requests and database documents.

## Domain Model Overview

The family domain is built around the following key entities:

- **Family**: The central group unit containing members, settings, and a shared SBD account.
- **Member**: A user's membership within a family, including roles (admin/member) and permissions.
- **Relationship**: Bidirectional links between members (e.g., Parent ↔ Child, Sibling ↔ Sibling).
- **SBD Account**: A virtual bank account for the family with transaction history and spending limits.
- **Token Request**: A workflow for members to request tokens from admins.
- **Purchase Request**: A workflow for members to request real-world purchases using SBD tokens.

## Validation Rules

### 1. Relationships
- **Bidirectional Consistency**: Relationships must be reciprocal (e.g., if A is parent of B, B must be child of A).
- **Type Validation**: Only specific relationship types are allowed (defined in `RELATIONSHIP_TYPES`).

### 2. Financials
- **Non-Negative Values**: Token amounts and costs must be positive decimals (up to 2 decimal places).
- **Spending Limits**: Can be set to specific amounts or -1 for unlimited.

### 3. Identifiers
- **Family Names**: Must be at least 2 characters and cannot start with reserved prefixes.
- **User IDs**: Must be valid system identifiers.

## Usage Examples

### Creating a Family Request

```python
try:
    request = CreateFamilyRequest(
        name="The Robinsons",
        admin_email="admin@robinson.family"
    )
    # Validates name length and format
except ValidationError as e:
    print(f"Invalid family name: {e}")
```

### Managing Permissions

```python
# Grant unlimited spending to a parent
perms = UpdateSpendingPermissionsRequest(
    user_id="user_123",
    can_spend=True,
    spending_limit=-1
)
```

## Module Attributes

Attributes:
    RELATIONSHIP_TYPES (Dict[str, str]): Mapping of relationship types to their reciprocals.
        Used for validating and creating bidirectional links.
    NOTIFICATION_TYPES (List[str]): Allowed types for family notifications.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from second_brain_database.utils.decimal_helpers import validate_sbd_amount

# Constants for validation
RELATIONSHIP_TYPES = {
    "parent": "child",
    "child": "parent",
    "sibling": "sibling",
    "spouse": "spouse",
    "grandparent": "grandchild",
    "grandchild": "grandparent",
    "uncle": "nephew",
    "aunt": "niece",
    "nephew": "uncle",
    "niece": "aunt",
    "cousin": "cousin",
}

NOTIFICATION_TYPES = [
    "sbd_spend",
    "sbd_deposit",
    "large_transaction",
    "spending_limit_reached",
    "account_frozen",
    "account_unfrozen",
    "admin_promoted",
    "admin_demoted",
    "member_added",
    "member_removed",
    "token_request_created",
    "token_request_approved",
    "token_request_denied",
    "permissions_updated",
    "purchase_request_created",
    "purchase_request_approved",
    "purchase_request_denied",
]


# Request Models
class CreateFamilyRequest(BaseModel):
    """
    Request model for creating a new family group.

    Families are the core unit of organization. This request initializes a new family
    with the requester as the first admin.

    **Validation:**
    *   **name**: Optional. If provided, must be 2-100 chars and cannot use reserved prefixes
        like 'admin_' or 'system_'.
    """

    name: Optional[str] = Field(None, max_length=100, description="Optional custom family name")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if len(v) < 2:
                raise ValueError("Family name must be at least 2 characters long")
            # Prevent reserved prefixes
            if v.lower().startswith(("family_", "team_", "admin_", "system_")):
                raise ValueError("Family name cannot start with reserved prefixes")
        return v


class InviteMemberRequest(BaseModel):
    """
    Request model for inviting a new member to the family.

    **Validation:**
    *   **identifier**: Can be an email or username. Must not be empty.
    *   **relationship_type**: Must be a valid type from `RELATIONSHIP_TYPES` (e.g., 'parent', 'child').
        This defines the relationship *from the inviter to the invitee*.
    """

    identifier: str = Field(..., description="Email address or username of the user to invite")
    identifier_type: Literal["email", "username"] = Field("email", description="Type of identifier provided")
    relationship_type: str = Field(..., description="Relationship type from inviter's perspective")

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError("Identifier cannot be empty")
        return v

    @field_validator("relationship_type")
    @classmethod
    def validate_relationship_type(cls, v):
        v = v.lower().strip()
        if v not in RELATIONSHIP_TYPES:
            valid_types = ", ".join(RELATIONSHIP_TYPES.keys())
            raise ValueError(f"Invalid relationship type. Valid types: {valid_types}")
        return v


class RespondToInvitationRequest(BaseModel):
    """
    Request model for accepting or declining a family invitation.

    **Actions:**
    *   **accept**: Joins the family and establishes the defined relationship.
    *   **decline**: Marks the invitation as declined; user does not join.
    """

    action: Literal["accept", "decline"] = Field(..., description="Action to take on the invitation")


class UpdateRelationshipRequest(BaseModel):
    """
    Request model for modifying the relationship between two family members.

    Relationships are strictly bidirectional. Both directions must be provided and
    must be reciprocals of each other (e.g., Parent <-> Child).

    **Validation:**
    *   Types must exist in `RELATIONSHIP_TYPES`.
    """

    relationship_type_a_to_b: str = Field(..., description="Relationship type from user A to user B")
    relationship_type_b_to_a: str = Field(..., description="Relationship type from user B to user A")

    @field_validator("relationship_type_a_to_b", "relationship_type_b_to_a")
    @classmethod
    def validate_relationship_types(cls, v):
        v = v.lower().strip()
        if v not in RELATIONSHIP_TYPES:
            valid_types = ", ".join(RELATIONSHIP_TYPES.keys())
            raise ValueError(f"Invalid relationship type. Valid types: {valid_types}")
        return v


class UpdateSpendingPermissionsRequest(BaseModel):
    """
    Request model for configuring a member's SBD token spending rights.

    **Controls:**
    *   **can_spend**: Boolean toggle to enable/disable spending entirely.
    *   **spending_limit**: Maximum tokens spendable per period (implementation dependent).
        Set to `-1` for unlimited spending.
    """

    user_id: str = Field(..., description="ID of the user to update permissions for")
    spending_limit: Decimal = Field(..., ge=-1, description="Spending limit in SBD tokens (-1 for unlimited)")
    can_spend: bool = Field(..., description="Whether the user can spend from family account")

    @field_validator("spending_limit")
    @classmethod
    def validate_spending_limit(cls, v):
        if v < -1:
            raise ValueError("Spending limit must be -1 (unlimited) or a positive number")
        return v


class FreezeAccountRequest(BaseModel):
    """
    Request model for emergency freezing of the family SBD account.

    Freezing prevents all spending transactions. Used by admins in case of
    suspicious activity or parental control enforcement.

    **Validation:**
    *   **reason**: Required when action is 'freeze'.
    """

    action: Literal["freeze", "unfreeze"] = Field(..., description="Action to take on the account")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for freezing the account")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v, info):
        if info.data.get("action") == "freeze" and not v:
            raise ValueError("Reason is required when freezing an account")
        return v.strip() if v else None


class CreateTokenRequestRequest(BaseModel):
    """
    Request model for a member to ask for SBD tokens.

    Members can request tokens from the family admin for chores, rewards, or allowances.

    **Validation:**
    *   **amount**: Must be positive.
    *   **reason**: Required, min 5 chars.
    """

    amount: Decimal = Field(..., gt=0, description="Amount of tokens requested (up to 2 decimal places)")
    reason: str = Field(..., max_length=500, description="Reason for the token request")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Reason cannot be empty")
        if len(v) < 5:
            raise ValueError("Reason must be at least 5 characters long")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount is positive and has at most 2 decimal places."""
        validated = validate_sbd_amount(v)
        if validated <= 0:
            raise ValueError("Transaction amount must be positive")
        return validated


class ReviewTokenRequestRequest(BaseModel):
    """
    Request model for an admin to approve or deny a token request.

    **Actions:**
    *   **approve**: Transfers tokens from family account to requester.
    *   **deny**: Rejects the request.
    """

    action: Literal["approve", "deny"] = Field(..., description="Action to take on the request")
    comments: Optional[str] = Field(None, max_length=1000, description="Admin comments on the decision")

    @field_validator("comments")
    @classmethod
    def validate_comments(cls, v):
        return v.strip() if v else None


class AdminActionRequest(BaseModel):
    """
    Request model for promoting or demoting a family admin.

    **Actions:**
    *   **promote**: Grants full admin privileges.
    *   **demote**: Revokes admin privileges (cannot demote the last admin).
    """

    action: Literal["promote", "demote"] = Field(..., description="Action to take")


class BackupAdminRequest(BaseModel):
    """
    Request model for managing backup admins in the succession plan.

    Backup admins are notified if the primary admin account becomes inactive.
    """

    action: Literal["designate", "remove"] = Field(..., description="Action to take on backup admin")


class AdminActionsLogRequest(BaseModel):
    """
    Request model for retrieving the audit log of admin actions.

    Supports pagination via `limit` and `offset`.
    """

    limit: int = Field(50, ge=1, le=100, description="Maximum number of records to return")
    offset: int = Field(0, ge=0, description="Number of records to skip")


class UpdateNotificationPreferencesRequest(BaseModel):
    """
    Request model for customizing family notification settings.

    Allows users to toggle specific channels (Email, Push, SMS) and event types.
    """

    email_notifications: bool = Field(True, description="Enable email notifications")
    push_notifications: bool = Field(True, description="Enable push notifications")
    sms_notifications: bool = Field(False, description="Enable SMS notifications")
    notify_on_spend: bool = Field(True, description="Notify on family spending")
    notify_on_deposit: bool = Field(True, description="Notify on family deposits")
    large_transaction_threshold: int = Field(1000, ge=0, description="Threshold for large transaction alerts")


class MarkNotificationsReadRequest(BaseModel):
    """
    Request model for bulk-marking notifications as read.
    """

    notification_ids: List[str] = Field(..., description="List of notification IDs to mark as read")

    @field_validator("notification_ids")
    @classmethod
    def validate_notification_ids(cls, v):
        if not v:
            raise ValueError("At least one notification ID must be provided")
        return v


# --- Models for Purchase Requests ---
class PurchaseRequestUserInfo(BaseModel):
    """Snapshot of user info for purchase requests."""

    user_id: str
    username: str


class PurchaseRequestItemInfo(BaseModel):
    """Details of the item requested for purchase."""

    item_id: str
    name: str
    item_type: str
    image_url: Optional[str] = None


class PurchaseRequestResponse(BaseModel):
    """
    Response model for a purchase request.

    Purchase requests allow members to ask admins to buy real-world items using SBD tokens.
    """

    request_id: str
    family_id: str
    requester: PurchaseRequestUserInfo
    item: PurchaseRequestItemInfo
    cost: int
    status: Literal["PENDING", "APPROVED", "DENIED"]
    created_at: datetime
    reviewed_by: Optional[PurchaseRequestUserInfo] = None
    reviewed_at: Optional[datetime] = None


class DenyPurchaseRequest(BaseModel):
    """
    Request model for denying a purchase request.

    Requires a reason to explain the denial to the requester.
    """

    reason: Optional[str] = Field(None, max_length=500, description="Optional reason for denial")


# --- End of Purchase Request Models ---


# Response Models
class MemberPermissionsResponse(BaseModel):
    """
    Response model for a member's spending permissions.

    **Fields:**
    *   **spending_limit**: -1 indicates unlimited spending.
    *   **can_spend**: Master toggle for spending ability.
    """

    role: str
    spending_limit: Decimal
    can_spend: bool
    updated_by: str
    updated_at: datetime


class SBDAccountResponse(BaseModel):
    """
    Response model for the family's shared SBD token account.

    **Privacy:**
    *   **member_permissions**: Only visible to admins.
    *   **recent_transactions**: Limited to last 5-10 entries for summary views.
    """

    account_username: str
    balance: Decimal
    is_frozen: bool
    frozen_by: Optional[str] = None
    frozen_at: Optional[datetime] = None
    member_permissions: Dict[str, MemberPermissionsResponse]
    notification_settings: Dict[str, Any]
    recent_transactions: List[Dict[str, Any]] = []


class FamilySettingsResponse(BaseModel):
    """
    Response model for family configuration settings.

    **Fields:**
    *   **visibility**: 'public' (searchable) or 'private' (invite-only).
    *   **auto_approval_threshold**: Token requests below this amount are auto-approved.
    """

    allow_member_invites: bool
    visibility: str
    auto_approval_threshold: Decimal
    request_expiry_hours: int


class SuccessionPlanResponse(BaseModel):
    """
    Response model for the family's admin succession plan.

    Ensures continuity if the primary admin loses access.
    """

    backup_admins: List[str]
    recovery_contacts: List[str]


class FamilyResponse(BaseModel):
    """
    Response model for full family details.

    The central object returned when viewing a family dashboard.

    **Context:**
    *   **user_role**: The requesting user's role in this family (e.g., 'admin', 'member').
    *   **is_admin**: Shortcut boolean for frontend logic.
    """

    family_id: str
    name: str
    admin_user_ids: List[str]
    member_count: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
    is_admin: bool
    user_role: str
    sbd_account: SBDAccountResponse
    settings: FamilySettingsResponse
    succession_plan: SuccessionPlanResponse
    usage_stats: Dict[str, Any] = {}


class RelationshipResponse(BaseModel):
    """
    Response model for a single family relationship.

    Represents a directed link (e.g., "User A is parent of User B").
    """

    relationship_id: str
    related_user_id: str
    related_username: str
    relationship_type: str
    created_at: datetime
    activated_at: Optional[datetime] = None


class FamilyMemberResponse(BaseModel):
    """
    Response model for a family member's profile.

    Includes their role, permissions, and relationships to other members.
    """

    user_id: str
    username: str
    email: str
    role: str
    joined_at: datetime
    spending_permissions: MemberPermissionsResponse
    relationships: List[RelationshipResponse] = []
    is_active: bool = True


class InvitationResponse(BaseModel):
    """
    Response model for a pending or processed invitation.
    """

    invitation_id: str
    family_id: str
    family_name: str
    inviter_user_id: str
    inviter_username: str
    invitee_email: str
    invitee_username: str
    relationship_type: str
    status: str
    expires_at: datetime
    created_at: datetime
    responded_at: Optional[datetime] = None
    email_sent: bool
    email_sent_at: Optional[datetime] = None


class TokenRequestResponse(BaseModel):
    """
    Response model for a token request.

    Shows the status of a request (pending, approved, denied) and any admin feedback.
    """

    request_id: str
    family_id: str
    requester_user_id: str
    requester_username: str
    amount: Decimal
    reason: str
    status: str
    reviewed_by: Optional[str] = None
    admin_comments: Optional[str] = None
    auto_approved: bool
    created_at: datetime
    expires_at: datetime
    reviewed_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    """
    Response model for a user notification.

    **Fields:**
    *   **data**: Arbitrary JSON payload with context (e.g., transaction ID, user ID).
    *   **is_read**: Boolean flag for UI styling.
    """

    notification_id: str
    family_id: str
    type: str
    title: str
    message: str
    data: Dict[str, Any] = {}
    status: str
    created_at: datetime
    sent_at: Optional[datetime] = None
    is_read: bool
    read_at: Optional[datetime] = None


class FamilyUsageResponse(BaseModel):
    """
    Response model for family resource usage.

    Tracks member counts against plan limits.
    """

    family_id: str
    family_name: str
    member_count: int
    max_members: int
    role: str
    created_at: datetime


class FamilyLimitsResponse(BaseModel):
    """
    Response model for system-wide family limits.

    Used to enforce subscription tiers (e.g., max families per user).
    """

    max_families_allowed: int
    max_members_per_family: int
    current_families: int
    families_usage: List[FamilyUsageResponse]
    can_create_family: bool
    upgrade_required: bool
    upgrade_message: Optional[str] = None


class AdminActionResponse(BaseModel):
    """
    Response model for the result of an admin promotion/demotion.
    """

    family_id: str
    target_user_id: str
    target_username: str
    action: str
    new_role: str
    performed_by: str
    performed_by_username: str
    performed_at: datetime
    message: str
    transaction_safe: bool = True


class BackupAdminResponse(BaseModel):
    """
    Response model for backup admin updates.
    """

    family_id: str
    backup_user_id: str
    backup_username: str
    action: str
    role: str
    performed_by: str
    performed_by_username: str
    performed_at: datetime
    message: str
    transaction_safe: bool = True


class AdminActionLogEntry(BaseModel):
    """
    Model representing a single audit log entry for admin actions.

    **Fields:**
    *   **details**: JSON blob with action-specific metadata (e.g., old_role, new_role).
    """

    action_id: str
    family_id: str
    admin_user_id: str
    admin_username: str
    target_user_id: str
    target_username: str
    action_type: str
    details: Dict[str, Any]
    created_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AdminActionsLogResponse(BaseModel):
    """
    Response model for a paginated list of admin audit logs.
    """

    family_id: str
    actions: List[AdminActionLogEntry]
    pagination: Dict[str, Any]


class FamilyStatsResponse(BaseModel):
    """
    Response model for global family system statistics.

    Used by system admins to monitor platform usage.
    """

    total_families: int
    total_members: int
    total_relationships: int
    total_invitations_sent: int
    total_invitations_accepted: int
    total_token_requests: int
    total_sbd_transactions: int
    average_family_size: float
    most_common_relationships: List[Dict[str, Any]]


class DatabaseMigrationResponse(BaseModel):
    """
    Response model for database migration job status.
    """

    migration_id: str
    operation: str
    status: str
    collections_affected: List[str]
    records_processed: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rollback_available: bool


class BackupResponse(BaseModel):
    """
    Response model for database backup job status.
    """

    backup_id: str
    backup_type: str
    collections: List[str]
    file_path: str
    file_size: int
    created_at: datetime
    expires_at: Optional[datetime] = None
    status: str
    checksum: str


# Database Schema Models (for internal use)
class FamilyDocument(BaseModel):
    """
    MongoDB document model for the `families` collection.

    Stores the core family configuration, including the embedded SBD account
    and settings.
    """

    family_id: str
    name: str
    admin_user_ids: List[str]
    created_at: datetime
    updated_at: datetime
    member_count: int
    is_active: bool
    sbd_account: Dict[str, Any]
    settings: Dict[str, Any]
    succession_plan: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "family_id": "fam_abc123def456",
                "name": "Smith Family",
                "admin_user_ids": ["user_123", "user_456"],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "member_count": 3,
                "is_active": True,
                "sbd_account": {
                    "account_username": "family_smith",
                    "is_frozen": False,
                    "frozen_by": None,
                    "frozen_at": None,
                    "spending_permissions": {},
                    "notification_settings": {
                        "notify_on_spend": True,
                        "notify_on_deposit": True,
                        "large_transaction_threshold": 1000,
                        "notify_admins_only": False,
                    },
                },
                "settings": {
                    "allow_member_invites": True,
                    "visibility": "private",
                    "auto_approval_threshold": 100,
                    "request_expiry_hours": 168,
                },
                "succession_plan": {"backup_admins": [], "recovery_contacts": []},
            }
        }


class FamilyRelationshipDocument(BaseModel):
    """
    MongoDB document model for the `family_relationships` collection.

    Represents a directed edge in the family graph.
    """

    relationship_id: str
    family_id: str
    user_a_id: str
    user_b_id: str
    relationship_type_a_to_b: str
    relationship_type_b_to_a: str
    status: str
    created_by: str
    created_at: datetime
    activated_at: Optional[datetime] = None
    updated_at: datetime

    @field_validator("relationship_type_a_to_b", "relationship_type_b_to_a")
    @classmethod
    def validate_relationship_types(cls, v):
        if v not in RELATIONSHIP_TYPES:
            raise ValueError(f"Invalid relationship type: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["active", "pending", "declined"]
        if v not in valid_statuses:
            raise ValueError(f"Invalid status: {v}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "relationship_id": "rel_abc123def456",
                "family_id": "fam_abc123def456",
                "user_a_id": "user_123",
                "user_b_id": "user_456",
                "relationship_type_a_to_b": "parent",
                "relationship_type_b_to_a": "child",
                "status": "active",
                "created_by": "user_123",
                "created_at": "2024-01-01T00:00:00Z",
                "activated_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        }


class FamilyInvitationDocument(BaseModel):
    """
    MongoDB document model for the `family_invitations` collection.
    """

    invitation_id: str
    family_id: str
    inviter_user_id: str
    invitee_email: EmailStr
    invitee_user_id: str
    relationship_type: str
    invitation_token: str
    status: str
    expires_at: datetime
    created_at: datetime
    responded_at: Optional[datetime] = None
    email_sent: bool
    email_sent_at: Optional[datetime] = None

    @field_validator("relationship_type")
    @classmethod
    def validate_relationship_type(cls, v):
        if v not in RELATIONSHIP_TYPES:
            raise ValueError(f"Invalid relationship type: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["pending", "accepted", "declined", "expired"]
        if v not in valid_statuses:
            raise ValueError(f"Invalid status: {v}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "invitation_id": "inv_abc123def456",
                "family_id": "fam_abc123def456",
                "inviter_user_id": "user_123",
                "invitee_email": "john@example.com",
                "invitee_user_id": "user_456",
                "relationship_type": "child",
                "invitation_token": "secure_token_abc123",
                "status": "pending",
                "expires_at": "2024-01-08T00:00:00Z",
                "created_at": "2024-01-01T00:00:00Z",
                "responded_at": None,
                "email_sent": True,
                "email_sent_at": "2024-01-01T00:00:00Z",
            }
        }


class FamilyNotificationDocument(BaseModel):
    """
    MongoDB document model for the `family_notifications` collection.
    """

    notification_id: str
    family_id: str
    recipient_user_ids: List[str]
    type: str
    title: str
    message: str
    data: Dict[str, Any] = {}
    status: str
    created_at: datetime
    sent_at: Optional[datetime] = None
    read_by: Dict[str, datetime] = {}

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in NOTIFICATION_TYPES:
            raise ValueError(f"Invalid notification type: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["pending", "sent", "read", "archived"]
        if v not in valid_statuses:
            raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("recipient_user_ids")
    @classmethod
    def validate_recipients(cls, v):
        if not v:
            raise ValueError("At least one recipient is required")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "notification_id": "notif_abc123def456",
                "family_id": "fam_abc123def456",
                "recipient_user_ids": ["user_123", "user_456"],
                "type": "sbd_spend",
                "title": "Family Token Spending",
                "message": "John spent 50 tokens from the family account",
                "data": {"transaction_id": "txn_123", "amount": 50, "from_user": "user_456", "to_user": "user_789"},
                "status": "sent",
                "created_at": "2024-01-01T00:00:00Z",
                "sent_at": "2024-01-01T00:00:00Z",
                "read_by": {},
            }
        }


class FamilyTokenRequestDocument(BaseModel):
    """
    MongoDB document model for the `family_token_requests` collection.
    """

    request_id: str
    family_id: str
    requester_user_id: str
    amount: Decimal
    reason: str
    status: str
    reviewed_by: Optional[str] = None
    admin_comments: Optional[str] = None
    auto_approved: bool = False
    created_at: datetime
    expires_at: datetime
    reviewed_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount is positive and has at most 2 decimal places."""
        validated = validate_sbd_amount(v)
        if validated <= 0:
            raise ValueError("Amount must be positive")
        return validated

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["pending", "approved", "denied", "expired", "auto_approved"]
        if v not in valid_statuses:
            raise ValueError(f"Invalid status: {v}")
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        if not v or len(v.strip()) < 5:
            raise ValueError("Reason must be at least 5 characters long")
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "req_abc123def456",
                "family_id": "fam_abc123def456",
                "requester_user_id": "user_456",
                "amount": 100,
                "reason": "Need tokens for school supplies",
                "status": "pending",
                "reviewed_by": None,
                "admin_comments": None,
                "auto_approved": False,
                "created_at": "2024-01-01T00:00:00Z",
                "expires_at": "2024-01-08T00:00:00Z",
                "reviewed_at": None,
                "processed_at": None,
            }
        }


class PurchaseRequestDocument(BaseModel):
    """Database document model for family_purchase_requests collection."""

    request_id: str
    family_id: str
    requester_info: "PurchaseRequestUserInfo"
    item_info: "PurchaseRequestItemInfo"
    cost: int
    status: str = "PENDING"
    created_at: datetime
    reviewed_by_info: Optional["PurchaseRequestUserInfo"] = None
    reviewed_at: Optional[datetime] = None
    denial_reason: Optional[str] = None
    transaction_id: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid_statuses = ["PENDING", "APPROVED", "DENIED"]
        if v not in valid_statuses:
            raise ValueError(f"Invalid status: {v}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "pr_abc123def456",
                "family_id": "fam_abc123def456",
                "requester_info": {"user_id": "user_456", "username": "someuser"},
                "item_info": {
                    "item_id": "item_123",
                    "name": "Gold Sword",
                    "item_type": "weapon",
                    "image_url": "/items/gold_sword.png",
                },
                "cost": 100,
                "status": "PENDING",
                "created_at": "2024-01-01T00:00:00Z",
                "reviewed_by_info": None,
                "reviewed_at": None,
                "denial_reason": None,
                "transaction_id": None,
            }
        }


# Error Response Models
class FamilyErrorResponse(BaseModel):
    """Error response model for family operations."""

    error: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "FAMILY_LIMIT_EXCEEDED",
                    "message": "You have reached the maximum number of families allowed",
                    "details": {"current_families": 1, "max_families": 1},
                    "upgrade_info": {"required_plan": "premium", "upgrade_url": "/upgrade"},
                    "suggested_actions": ["Upgrade to premium plan", "Delete an existing family"],
                }
            }
        }


class ValidationErrorResponse(BaseModel):
    """Validation error response model."""

    detail: List[Dict[str, Any]]

    class Config:
        json_schema_extra = {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "relationship_type"],
                        "msg": "Invalid relationship type. Valid types: parent, child, sibling, spouse, grandparent, grandchild, uncle, aunt, nephew, niece, cousin",
                        "type": "value_error",
                    }
                ]
            }
        }
