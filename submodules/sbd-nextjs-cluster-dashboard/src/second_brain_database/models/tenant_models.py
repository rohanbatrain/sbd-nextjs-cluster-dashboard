"""
# Multi-Tenancy Models

This module defines the **core data structures** for the multi-tenant architecture,
enabling logical isolation of data and resources for different organizations (tenants)
within a single deployment.

## Domain Model Overview

The multi-tenancy system is built around:

- **Tenant**: An isolated workspace with its own users, data, and settings.
- **Membership**: The association between a user and a tenant, defining their role.
- **Plan**: The subscription tier (Free, Pro, Enterprise) determining feature access.

## Key Features

### 1. Data Isolation
- **Logical Separation**: All resources are scoped to a `tenant_id`.
- **Context Awareness**: API requests must specify the active tenant context.

### 2. Role-Based Access Control (RBAC)
- **Owner**: Full control, including billing and deletion.
- **Admin**: Can manage users and settings.
- **Member**: Standard access to features.
- **Viewer**: Read-only access.

### 3. Resource Limits
- **Quotas**: Limits on users, storage, and API usage based on the subscription plan.
- **Feature Flags**: Toggle specific capabilities per tenant.

## Usage Examples

### Creating a New Tenant

```python
tenant = CreateTenantRequest(
    name="Acme Corp",
    slug="acme-corp",
    plan="pro",
    description="Main workspace for Acme Corp"
)
```

### Inviting a User

```python
invite = InviteUserToTenantRequest(
    user_id="user_456",
    role="member"
)
```

## Module Attributes

Attributes:
    TENANT_PLANS (List[str]): Available subscription tiers.
    TENANT_ROLES (List[str]): User roles within a tenant.
    TENANT_STATUSES (List[str]): Lifecycle states for a tenant.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Constants for validation
TENANT_PLANS = ["free", "pro", "enterprise"]
TENANT_STATUSES = ["active", "suspended", "trial", "cancelled"]
TENANT_ROLES = ["owner", "admin", "member", "viewer"]
MEMBERSHIP_STATUSES = ["active", "invited", "suspended"]


# Request Models
class CreateTenantRequest(BaseModel):
    """Request model for creating a new tenant (organization).

    Attributes:
        name (str): Display name of the tenant. Must be 2-100 characters.
        slug (Optional[str]): URL-friendly unique identifier. Auto-generated if not provided.
        plan (Literal["free", "pro", "enterprise"]): Initial subscription tier. Defaults to "free".
        description (Optional[str]): Brief description of the tenant's purpose.
    """
    name: str = Field(..., min_length=2, max_length=100, description="Tenant name")
    slug: Optional[str] = Field(None, min_length=2, max_length=50, description="URL-friendly identifier")
    plan: Literal["free", "pro", "enterprise"] = Field("free", description="Subscription plan")
    description: Optional[str] = Field(None, max_length=500, description="Tenant description")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        """Validate that the slug contains only URL-safe characters."""
        if v is not None:
            v = v.strip().lower()
            if not v.replace("-", "").replace("_", "").isalnum():
                raise ValueError("Slug must contain only alphanumeric characters, dashes, and underscores")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate that the tenant name is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Tenant name cannot be empty")
        return v


class UpdateTenantRequest(BaseModel):
    """Request model for updating existing tenant details.

    Attributes:
        name (Optional[str]): New display name.
        description (Optional[str]): New description.
        plan (Optional[Literal]): New subscription plan (requires billing authorization).
        status (Optional[Literal]): New lifecycle status (e.g., suspend/activate).
    """
    name: Optional[str] = Field(None, min_length=2, max_length=100, description="New tenant name")
    description: Optional[str] = Field(None, max_length=500, description="New description")
    plan: Optional[Literal["free", "pro", "enterprise"]] = Field(None, description="New subscription plan")
    status: Optional[Literal["active", "suspended", "trial", "cancelled"]] = Field(None, description="New status")


class InviteUserToTenantRequest(BaseModel):
    """Request model for inviting a user to join a tenant.

    Attributes:
        user_id (str): The unique identifier of the user to invite.
        role (Literal["admin", "member", "viewer"]): The role to assign to the user.
    """
    user_id: str = Field(..., description="ID of the user to invite")
    role: Literal["admin", "member", "viewer"] = Field("member", description="Role to assign")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        """Ensure users cannot be invited as 'owner' directly."""
        if v == "owner":
            raise ValueError("Cannot invite users as owner. Transfer ownership instead.")
        return v


class UpdateMembershipRequest(BaseModel):
    """Request model for modifying a member's role or permissions.

    Attributes:
        role (Optional[Literal]): New role to assign.
        permissions (Optional[Dict[str, bool]]): Granular permission overrides.
    """
    role: Optional[Literal["admin", "member", "viewer"]] = Field(None, description="New role")
    permissions: Optional[Dict[str, bool]] = Field(None, description="Permission overrides")


class SwitchTenantRequest(BaseModel):
    """Request model for switching the user's active context to another tenant.

    Attributes:
        tenant_id (str): The ID of the target tenant.
    """
    tenant_id: str = Field(..., description="ID of the tenant to switch to")


# Response Models
class TenantSettingsResponse(BaseModel):
    """Response model for tenant configuration and limits.

    Attributes:
        max_users (int): Maximum number of allowed members.
        max_storage_gb (int): Storage quota in Gigabytes.
        features_enabled (List[str]): List of active feature flags.
        custom_domain (Optional[str]): Configured custom domain, if any.
    """
    max_users: int = Field(..., description="Maximum allowed users")
    max_storage_gb: int = Field(..., description="Storage quota in GB")
    features_enabled: List[str] = Field(..., description="Enabled features")
    custom_domain: Optional[str] = Field(None, description="Custom domain name")


class TenantBillingResponse(BaseModel):
    """Response model for tenant billing status.

    Attributes:
        subscription_id (Optional[str]): External payment provider subscription ID.
        current_period_start (Optional[datetime]): Start of the current billing cycle.
        current_period_end (Optional[datetime]): End of the current billing cycle.
    """
    subscription_id: Optional[str] = Field(None, description="Stripe/Provider subscription ID")
    current_period_start: Optional[datetime] = Field(None, description="Billing period start")
    current_period_end: Optional[datetime] = Field(None, description="Billing period end")


class TenantResponse(BaseModel):
    """Standard response model for tenant information.

    Attributes:
        tenant_id (str): Unique identifier.
        name (str): Display name.
        slug (str): URL-friendly identifier.
        plan (str): Current subscription plan.
        status (str): Current lifecycle status.
        description (Optional[str]): Description text.
        owner_user_id (str): ID of the tenant owner.
        settings (TenantSettingsResponse): Configuration settings.
        billing (TenantBillingResponse): Billing details.
        member_count (int): Current number of members.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """
    tenant_id: str = Field(..., description="Unique tenant ID")
    name: str = Field(..., description="Tenant name")
    slug: str = Field(..., description="URL slug")
    plan: str = Field(..., description="Subscription plan")
    status: str = Field(..., description="Tenant status")
    description: Optional[str] = Field(None, description="Description")
    owner_user_id: str = Field(..., description="Owner user ID")
    settings: TenantSettingsResponse = Field(..., description="Tenant settings")
    billing: TenantBillingResponse = Field(..., description="Billing info")
    member_count: int = Field(0, description="Count of members")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class TenantMembershipPermissionsResponse(BaseModel):
    """Response model detailing a member's computed permissions.

    Attributes:
        can_invite_users (bool): Whether the user can invite others.
        can_manage_billing (bool): Whether the user can access billing.
        can_access_audit_logs (bool): Whether the user can view logs.
    """
    can_invite_users: bool = Field(..., description="Permission to invite users")
    can_manage_billing: bool = Field(..., description="Permission to manage billing")
    can_access_audit_logs: bool = Field(..., description="Permission to view audit logs")


class TenantMembershipResponse(BaseModel):
    """Response model for a user's membership in a tenant.

    Attributes:
        membership_id (str): Unique membership ID.
        tenant_id (str): ID of the tenant.
        tenant_name (str): Name of the tenant.
        user_id (str): ID of the user.
        role (str): Assigned role.
        status (str): Membership status (active/invited).
        permissions (TenantMembershipPermissionsResponse): Effective permissions.
        invited_by (Optional[str]): User ID of the inviter.
        invited_at (Optional[datetime]): When the invitation was sent.
        joined_at (Optional[datetime]): When the user accepted/joined.
    """
    membership_id: str = Field(..., description="Membership ID")
    tenant_id: str = Field(..., description="Tenant ID")
    tenant_name: str = Field(..., description="Tenant name")
    user_id: str = Field(..., description="User ID")
    role: str = Field(..., description="Assigned role")
    status: str = Field(..., description="Membership status")
    permissions: TenantMembershipPermissionsResponse = Field(..., description="Effective permissions")
    invited_by: Optional[str] = Field(None, description="Invited by user ID")
    invited_at: Optional[datetime] = Field(None, description="Invitation time")
    joined_at: Optional[datetime] = Field(None, description="Join time")


class TenantMemberResponse(BaseModel):
    """Response model for listing members within a tenant context.

    Attributes:
        user_id (str): User ID.
        username (str): User's display name.
        email (str): User's email address.
        role (str): Role in this tenant.
        status (str): Membership status.
        joined_at (Optional[datetime]): When they joined.
    """
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    role: str = Field(..., description="Role")
    status: str = Field(..., description="Status")
    joined_at: Optional[datetime] = Field(None, description="Join time")


class TenantListResponse(BaseModel):
    """Response model for listing tenants a user belongs to.

    Attributes:
        tenants (List[TenantResponse]): List of tenants.
        total_count (int): Total number of tenants found.
    """
    tenants: List[TenantResponse] = Field(..., description="List of tenants")
    total_count: int = Field(..., description="Total count")


class TenantMembersListResponse(BaseModel):
    """Response model for listing members of a specific tenant.

    Attributes:
        members (List[TenantMemberResponse]): List of members.
        total_count (int): Total number of members found.
    """
    members: List[TenantMemberResponse] = Field(..., description="List of members")
    total_count: int = Field(..., description="Total count")


class TenantLimitsResponse(BaseModel):
    """Response model for checking tenant resource usage against limits.

    Attributes:
        plan (str): Current plan.
        max_users (int): User limit.
        max_storage_gb (int): Storage limit.
        current_users (int): Current user count.
        current_storage_gb (float): Current storage usage.
        features_enabled (List[str]): Enabled features.
        can_upgrade (bool): Whether upgrade is available.
        upgrade_required_for (List[str]): Features requiring upgrade.
    """
    plan: str = Field(..., description="Current plan")
    max_users: int = Field(..., description="Max users limit")
    max_storage_gb: int = Field(..., description="Max storage limit")
    current_users: int = Field(..., description="Current user count")
    current_storage_gb: float = Field(..., description="Current storage usage")
    features_enabled: List[str] = Field(..., description="Enabled features")
    can_upgrade: bool = Field(..., description="Upgrade available")
    upgrade_required_for: List[str] = Field(default_factory=list, description="Features needing upgrade")


# Database Schema Models
class TenantDocument(BaseModel):
    """Database document model for the 'tenants' collection.

    Attributes:
        tenant_id (str): Unique identifier.
        name (str): Tenant name.
        slug (str): URL slug.
        plan (str): Subscription plan.
        status (str): Lifecycle status.
        description (Optional[str]): Description.
        owner_user_id (str): Owner ID.
        settings (Dict[str, Any]): Settings dictionary.
        billing (Dict[str, Any]): Billing dictionary.
        member_count (int): Cached member count.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
    """
    tenant_id: str = Field(..., description="Unique tenant ID")
    name: str = Field(..., description="Tenant name")
    slug: str = Field(..., description="URL slug")
    plan: str = Field(..., description="Subscription plan")
    status: str = Field(..., description="Tenant status")
    description: Optional[str] = Field(None, description="Description")
    owner_user_id: str = Field(..., description="Owner user ID")
    settings: Dict[str, Any] = Field(..., description="Settings object")
    billing: Dict[str, Any] = Field(..., description="Billing object")
    member_count: int = Field(0, description="Member count")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")

    @field_validator("plan")
    @classmethod
    def validate_plan(cls, v):
        """Validate plan against allowed values."""
        if v not in TENANT_PLANS:
            raise ValueError(f"Invalid plan: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        """Validate status against allowed values."""
        if v not in TENANT_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v


class TenantMembershipDocument(BaseModel):
    """Database document model for the 'tenant_memberships' collection.

    Attributes:
        membership_id (str): Unique ID.
        tenant_id (str): Tenant ID.
        user_id (str): User ID.
        role (str): Role.
        status (str): Status.
        permissions (Dict[str, bool]): Permission overrides.
        invited_by (Optional[str]): Inviter ID.
        invited_at (Optional[datetime]): Invitation time.
        joined_at (Optional[datetime]): Join time.
        created_at (datetime): Creation time.
        updated_at (datetime): Update time.
    """
    membership_id: str = Field(..., description="Membership ID")
    tenant_id: str = Field(..., description="Tenant ID")
    user_id: str = Field(..., description="User ID")
    role: str = Field(..., description="Role")
    status: str = Field(..., description="Status")
    permissions: Dict[str, bool] = Field(..., description="Permissions")
    invited_by: Optional[str] = Field(None, description="Invited by")
    invited_at: Optional[datetime] = Field(None, description="Invitation time")
    joined_at: Optional[datetime] = Field(None, description="Join time")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Update time")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        """Validate role against allowed values."""
        if v not in TENANT_ROLES:
            raise ValueError(f"Invalid role: {v}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        """Validate status against allowed values."""
        if v not in MEMBERSHIP_STATUSES:
            raise ValueError(f"Invalid status: {v}")
        return v
