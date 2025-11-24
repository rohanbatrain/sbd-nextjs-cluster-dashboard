"""
# Workspace & Team Models

This module defines the data structures for **collaborative workspaces**, enabling teams to share
resources, manage permissions, and operate a shared SBD wallet. It supports granular role-based
access control and configurable settings for team governance.

## Domain Model Overview

A workspace acts as a container for team collaboration, featuring:

- **Members**: Users with specific roles (Admin, Editor, Viewer).
- **Settings**: Configuration for invites, default roles, and visibility.
- **Shared Wallet**: A virtual SBD account for team expenses and budget management.

## Key Features

### 1. Collaboration
- **Roles**:
    - `admin`: Full control over workspace and members.
    - `editor`: Can create and modify content.
    - `viewer`: Read-only access.
- **Invites**: Configurable policy for who can invite new members.

### 2. Financial Management
- **Shared SBD Account**: Centralized wallet for the workspace.
- **Spending Controls**: Limits and permissions for member transactions.
- **Notifications**: Alerts for large transactions or deposits.

## Usage Examples

### Creating a Workspace

```python
workspace = WorkspaceDocument(
    workspace_id="ws_123",
    name="Engineering Team",
    owner_id="user_admin",
    members=[
        WorkspaceMember(user_id="user_admin", role="admin"),
        WorkspaceMember(user_id="user_dev", role="editor")
    ]
)
```

### Configuring Wallet Settings

```python
settings = WorkspaceSBDAccount(
    account_username="eng_wallet",
    notification_settings={
        "notify_on_spend": True,
        "large_transaction_threshold": 5000
    }
)
```

## Module Attributes

Attributes:
    None: This module relies on Pydantic models and does not define global constants.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class WorkspaceMember(BaseModel):
    """Defines a user's membership and role within a workspace.

    Attributes:
        user_id (str): The ID of the user.
        role (Literal): The role of the user within the workspace (admin, editor, viewer).
        joined_at (datetime): Timestamp of when the member joined.
    """

    user_id: str = Field(..., description="The ID of the user.")
    # Full-featured roles for granular permissions
    role: Literal["admin", "editor", "viewer"] = Field(
        "viewer", description="The role of the user within the workspace."
    )
    joined_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of when the member joined.")


class WorkspaceSettings(BaseModel):
    """Defines settings for a workspace.

    Attributes:
        allow_member_invites (bool): Determines if non-admin members can invite others (as viewers).
        default_new_member_role (Literal): The default role assigned to newly invited members.
    """

    allow_member_invites: bool = Field(
        True, description="Determines if non-admin members can invite others (as viewers)."
    )
    default_new_member_role: Literal["editor", "viewer"] = Field(
        "viewer", description="The default role assigned to newly invited members."
    )


class WorkspaceSBDAccount(BaseModel):
    """SBD account configuration for workspace shared token management.

    Attributes:
        account_username (str): Virtual account username for the workspace.
        is_frozen (bool): Whether the account is currently frozen.
        frozen_by (Optional[str]): Username of admin who froze the account.
        frozen_at (Optional[datetime]): When the account was frozen.
        spending_permissions (Dict): Spending permissions for all workspace members.
        notification_settings (Dict): Notification settings for SBD transactions.
    """

    account_username: str = Field(default="", description="Virtual account username for the workspace")
    is_frozen: bool = Field(default=False, description="Whether the account is currently frozen")
    frozen_by: Optional[str] = Field(None, description="Username of admin who froze the account")
    frozen_at: Optional[datetime] = Field(None, description="When the account was frozen")
    spending_permissions: Dict[str, Any] = Field(
        default_factory=dict, description="Spending permissions for all workspace members"
    )
    notification_settings: Dict[str, Any] = Field(
        default_factory=lambda: {
            "notify_on_spend": True,
            "notify_on_deposit": True,
            "large_transaction_threshold": 1000,
            "notify_admins_only": False,
        },
        description="Notification settings for SBD transactions",
    )


class WorkspaceDocument(BaseModel):
    """Database document model for the workspaces collection.

    Attributes:
        workspace_id (str): Unique identifier for the workspace.
        name (str): The name of the workspace.
        description (Optional[str]): A brief description of the workspace.
        owner_id (str): The user ID of the workspace owner, who has ultimate control.
        members (List[WorkspaceMember]): List of members in the workspace.
        settings (WorkspaceSettings): Settings for the workspace.
        created_at (datetime): Creation timestamp.
        updated_at (datetime): Last update timestamp.
        sbd_account (WorkspaceSBDAccount): SBD account configuration for shared token management.
    """

    workspace_id: str = Field(..., description="Unique identifier for the workspace.")
    name: str = Field(..., max_length=100, description="The name of the workspace.")
    description: Optional[str] = Field(None, max_length=500, description="A brief description of the workspace.")
    owner_id: str = Field(..., description="The user ID of the workspace owner, who has ultimate control.")
    members: List[WorkspaceMember] = Field(..., description="List of members in the workspace.")
    settings: WorkspaceSettings = Field(default_factory=WorkspaceSettings, description="Settings for the workspace.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # SBD account information for team wallet functionality
    sbd_account: WorkspaceSBDAccount = Field(
        default_factory=WorkspaceSBDAccount, description="SBD account configuration for shared token management"
    )
