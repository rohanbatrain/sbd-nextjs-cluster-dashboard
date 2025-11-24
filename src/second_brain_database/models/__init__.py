"""
# Data Models Package

This package contains the **Pydantic models** and **database schemas** that define the core data structures
of the Second Brain Database. These models serve as the single source of truth for data validation,
serialization, and type safety across the application.

## Package Architecture

The models are organized by domain:

- **`family_models`**: Family groups, members, relationships, and virtual economy (SBD tokens).
- **`blog_models`**: Content management system, posts, comments, and SEO metadata.
- **`ipam_models`**: IP address management, regions, hosts, and subnet hierarchies.
- **`club_models`**: University clubs, events, memberships, and WebRTC signaling.
- **`memex_models`**: Spaced repetition system (Anki-like) cards and decks.
- **`cluster_models`**: Distributed system state, node health, and replication status.
- **`migration_models`**: Data transfer jobs, progress tracking, and validation.
- **`tenant_models`**: Multi-tenancy configuration and isolation rules.

## Design Patterns

### 1. Request/Response Separation
Most domains follow a pattern of separating API contracts from database schemas:
- `*Request`: Input validation models (e.g., `CreateFamilyRequest`)
- `*Response`: Output serialization models (e.g., `FamilyResponse`)
- `*DB`: Internal database representations (often implicit or separate classes)

### 2. Validation
Models use Pydantic V2 for robust validation:
- **Field Validators**: Enforce constraints (e.g., email format, positive numbers)
- **Model Validators**: Cross-field validation (e.g., start_date < end_date)
- **Config**: Strict typing and extra forbidding to prevent pollution

### 3. Common Fields
All database models inherit common fields for consistency:
- `id`: Unique identifier (UUID or ObjectId)
- `created_at`: Timestamp of creation
- `updated_at`: Timestamp of last modification
- `tenant_id`: (Where applicable) Owner tenant identifier

## Usage Example

```python
from second_brain_database.models.family_models import CreateFamilyRequest

# Validate incoming data
try:
    payload = CreateFamilyRequest(
        name="The Smiths",
        admin_email="john@example.com"
    )
    print(payload.name)
except ValidationError as e:
    print(f"Invalid data: {e}")
```
"""

from .family_models import *

__all__ = [
    # Family models
    "CreateFamilyRequest",
    "InviteMemberRequest",
    "RespondToInvitationRequest",
    "UpdateRelationshipRequest",
    "UpdateSpendingPermissionsRequest",
    "FreezeAccountRequest",
    "CreateTokenRequestRequest",
    "ReviewTokenRequestRequest",
    "AdminActionRequest",
    "FamilyResponse",
    "FamilyMemberResponse",
    "InvitationResponse",
    "SBDAccountResponse",
    "TokenRequestResponse",
    "NotificationResponse",
    "FamilyLimitsResponse",
    "RelationshipResponse",
    "FamilyStatsResponse",
]
