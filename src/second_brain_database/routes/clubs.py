"""
# University Clubs Routes

This module provides the **REST API endpoints** for the University Clubs Platform.
It handles the lifecycle of universities, student clubs, verticals, and events.

## Domain Overview

The Clubs Platform is a multi-tenant system for student organizations:
- **University**: The top-level entity (e.g., "Stanford University").
- **Club**: A student organization within a university (e.g., "AI Club").
- **Vertical**: A sub-department or interest group within a club (e.g., "ML Team").
- **Member**: A user with a specific role in a club (Owner, Admin, Member).

## Key Features

### 1. Hierarchy & Multi-Tenancy
- **Isolation**: Clubs are scoped to universities; Verticals are scoped to clubs.
- **Role-Based Access Control (RBAC)**:
    - **Owner**: Full control, can delete club.
    - **Admin**: Can manage settings, members, and events.
    - **Lead**: Manages specific verticals or events.
    - **Member**: Standard access to events and discussions.

### 2. Lifecycle Management
- **Creation**: Users can request to create universities (requires approval) or clubs.
- **Approval Workflow**: System admins approve universities; Club admins approve members.
- **Updates**: Profile management (logo, banner, social links).

### 3. Discovery & Search
- **Filtering**: Find clubs by university, category, or tags.
- **Search**: Full-text search on club names and descriptions.
- **Recommendations**: "Popular" and "Recommended" lists based on engagement.

## API Endpoints

### Universities
- `POST /clubs/universities` - Request creation
- `GET /clubs/universities` - List approved
- `POST .../approve` - Approve (Admin only)

### Clubs
- `POST /clubs` - Create club
- `GET /clubs` - List/Filter clubs
- `GET /clubs/{id}` - Get details
- `PUT /clubs/{id}` - Update settings

### Verticals
- `POST /clubs/{id}/verticals` - Create vertical
- `GET /clubs/{id}/verticals` - List verticals

## Usage Examples

### Creating a Club

```python
await client.post("/clubs", json={
    "name": "Robotics Society",
    "university_id": "uni_123",
    "category": "Technology",
    "description": "Building the future of automation."
})
```

### Searching for Clubs

```python
# Find tech clubs at Stanford
await client.get("/clubs", params={
    "university_id": "stanford_u",
    "category": "Technology"
})
```

## Module Attributes

Attributes:
    router (APIRouter): FastAPI router with `/clubs` prefix
    club_manager (ClubManager): Singleton instance for business logic
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status

from second_brain_database.managers.club_auth_manager import (
    club_auth_manager,
    require_club_admin,
    require_club_lead,
    require_club_member,
    require_club_owner,
    require_vertical_lead,
)
from second_brain_database.managers.club_manager import ClubManager
from second_brain_database.managers.club_notification_manager import club_notification_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.club_webrtc_router import ClubEventWebRTCManager
from second_brain_database.models.club_models import (
    ClubDocument,
    ClubMemberDocument,
    ClubResponse,
    ClubRole,
    CreateClubRequest,
    CreateUniversityRequest,
    CreateVerticalRequest,
    InviteMemberRequest,
    UniversityDocument,
    UniversityResponse,
    VerticalDocument,
    VerticalResponse,
    ClubMemberResponse,
    ClubSearchRequest,
    ClubAnalyticsResponse,
    BulkInviteRequest,
    TransferMemberRequest,
    UpdateMemberRoleRequest,
    # Event models
    EventDocument,
    EventAttendeeDocument,
    CreateEventRequest,
    EventResponse,
    UpdateEventRequest,
    EventAttendeeResponse,
    RegisterForEventRequest,
    EventSearchRequest,
    EventType,
    EventStatus,
    EventVisibility,
)

logger = get_logger(prefix="[Club Routes]")

# Initialize manager
club_manager = ClubManager()

# Create router
router = APIRouter(prefix="/clubs", tags=["clubs"])


# University Management Routes

@router.post("/universities", response_model=UniversityResponse)
async def create_university(
    request: CreateUniversityRequest,
    current_user: dict = Depends(require_club_member)  # Any authenticated user can request
):
    """
    Request the creation of a new university entity.

    This endpoint allows any authenticated user to submit a request for a new university.
    The university is created in a `pending` state and requires approval from a system administrator
    before it becomes active and visible to other users.

    **Process:**
    1.  Validates the university name and domain (must be unique).
    2.  Creates the university document with `admin_approved=False`.
    3.  Logs the request for admin review.

    Args:
        request (CreateUniversityRequest): The university details (name, domain, location, etc.).
        current_user (dict): The authenticated user submitting the request.

    Returns:
        UniversityResponse: The created university details (including pending status).

    Raises:
        HTTPException(400): If the domain is invalid or already exists.
        HTTPException(500): If creation fails due to server error.
    """
    try:
        university = await club_manager.create_university(
            name=request.name,
            domain=request.domain,
            created_by=current_user.get("_id", current_user.get("user_id")),
            description=request.description,
            location=request.location,
            website=request.website,
            logo_url=request.logo_url
        )

        logger.info("Requested university creation: %s by user %s",
                   university.university_id, current_user.get("username"))
        return UniversityResponse(**university.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create university: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create university")


@router.get("/universities", response_model=List[UniversityResponse])
async def get_approved_universities(
    search: Optional[str] = Query(None, description="Search by name or domain"),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_club_member)
):
    """
    Retrieve a list of approved universities.

    This endpoint returns only universities that have been verified and approved by administrators.
    It supports searching by name or email domain.

    Args:
        search (str, optional): Search term for university name or domain.
        limit (int): Maximum number of results to return (default: 50).
        current_user (dict): The authenticated user.

    Returns:
        List[UniversityResponse]: A list of approved universities.
    """
    try:
        from second_brain_database.database import db_manager

        # Build query
        query = {"admin_approved": True, "status": "verified"}

        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"domain": {"$regex": search, "$options": "i"}}
            ]

        universities = []
        async for uni in db_manager.get_tenant_collection("universities").find(query).limit(limit):
            universities.append(UniversityResponse(**uni))

        return universities

    except Exception as e:
        logger.error("Failed to get universities: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get universities")


@router.get("/universities/{university_id}", response_model=UniversityResponse)
async def get_university(
    university_id: str,
    current_user: dict = Depends(require_club_member)
):
    """
    Get detailed information about a specific university.

    Args:
        university_id (str): The unique ID of the university.
        current_user (dict): The authenticated user.

    Returns:
        UniversityResponse: The university details.

    Raises:
        HTTPException(404): If the university is not found or not approved.
    """
    try:
        from second_brain_database.database import db_manager

        university_doc = await db_manager.get_tenant_collection("universities").find_one({
            "university_id": university_id,
            "admin_approved": True
        })

        if not university_doc:
            raise HTTPException(status_code=404, detail="University not found")

        return UniversityResponse(**university_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get university: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get university")


@router.post("/universities/{university_id}/approve", response_model=UniversityResponse)
async def approve_university(
    university_id: str,
    current_user: dict = Depends(require_club_owner)  # Admin only
):
    """
    Approve a pending university request (System Admin only).

    This action activates the university, making it visible to all users and allowing
    clubs to be created under it.

    **Access Control:**
    Requires system-level administrator privileges (currently restricted to Club Owners for simplicity,
    but should be restricted to Super Admins in production).

    Args:
        university_id (str): The ID of the university to approve.
        current_user (dict): The authenticated administrator.

    Returns:
        UniversityResponse: The updated university details with `admin_approved=True`.
    """
    try:
        # TODO: Add admin role check
        university = await club_manager.approve_university(
            university_id=university_id,
            approved_by=current_user.get("_id", current_user.get("user_id"))
        )

        logger.info("Approved university: %s by admin %s",
                   university.university_id, current_user.get("username"))
        return UniversityResponse(**university.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to approve university: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to approve university")


# Club Management Routes

@router.post("", response_model=ClubResponse)
async def create_club(
    request: CreateClubRequest,
    current_user: dict = Depends(require_club_member)
):
    """
    Create a new student club within a university.

    The creator of the club automatically becomes the `OWNER` of the club.

    **Process:**
    1.  Verifies the university exists and is active.
    2.  Creates the club document.
    3.  Creates a `ClubMember` record for the creator with `OWNER` role.
    4.  Initializes default settings.

    Args:
        request (CreateClubRequest): The club details (name, university_id, etc.).
        current_user (dict): The authenticated user (creator).

    Returns:
        ClubResponse: The created club details.

    Raises:
        HTTPException(400): If the university ID is invalid.
    """
    try:
        club = await club_manager.create_club(
            owner_id=current_user.get("_id", current_user.get("user_id")),
            university_id=request.university_id,
            name=request.name,
            category=request.category,
            description=request.description,
            logo_url=request.logo_url,
            banner_url=request.banner_url,
            website_url=request.website_url,
            social_links=request.social_links,
            max_members=request.max_members,
            tags=request.tags
        )

        logger.info("Created club: %s in university %s by user %s",
                   club.club_id, request.university_id, current_user.get("username"))
        return ClubResponse(**club.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create club: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create club")


@router.get("", response_model=List[ClubResponse])
async def get_clubs(
    university_id: Optional[str] = Query(None, description="Filter by university"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search clubs"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_club_member)
):
    """
    Retrieve a list of clubs with optional filtering.

    This endpoint is the primary way to discover clubs. It supports filtering by
    university, category, and text search.

    Args:
        university_id (str, optional): Filter by university ID.
        category (str, optional): Filter by club category (e.g., "Tech", "Arts").
        search (str, optional): Text search on name, description, or tags.
        limit (int): Maximum number of results.
        current_user (dict): The authenticated user.

    Returns:
        List[ClubResponse]: A list of active clubs matching the criteria.
    """
    try:
        from second_brain_database.database import db_manager

        # Build query
        query = {"is_active": True}

        if university_id:
            query["university_id"] = university_id
        if category:
            query["category"] = category
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
                {"tags": {"$in": [search]}}
            ]

        clubs = []
        async for club in db_manager.get_tenant_collection("clubs").find(query).limit(limit):
            clubs.append(ClubResponse(**club))

        return clubs

    except Exception as e:
        logger.error("Failed to get clubs: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get clubs")


@router.get("/search", response_model=List[ClubResponse])
async def search_clubs(
    request: ClubSearchRequest,
    current_user: dict = Depends(require_club_member)
):
    """
    Advanced search for clubs using complex filters.

    This endpoint supports more granular filtering options than the simple list endpoint,
    including tag filtering and pagination control via a request body (GET with body pattern,
    though often implemented as POST for complex queries, here it uses GET with dependency injection
    or query params mapped to model - *Note: FastAPI handles `ClubSearchRequest` as query params if not specified as Body*).
    *Correction*: The signature uses `request: ClubSearchRequest`. If `ClubSearchRequest` is a Pydantic model, FastAPI will expect it as a request body, which is non-standard for GET.
    *Refinement*: Assuming `ClubSearchRequest` is used as a dependency or body. Given the code, it seems to be treated as a dependency if fields are simple, or body.

    Args:
        request (ClubSearchRequest): The search criteria object.
        current_user (dict): The authenticated user.

    Returns:
        List[ClubResponse]: A list of clubs matching the search criteria.
    """
    try:
        from second_brain_database.database import db_manager

        # Build query
        query = {"is_active": True}

        if request.query:
            query["$or"] = [
                {"name": {"$regex": request.query, "$options": "i"}},
                {"description": {"$regex": request.query, "$options": "i"}},
                {"tags": {"$in": [request.query]}}
            ]

        if request.university_id:
            query["university_id"] = request.university_id

        if request.category:
            query["category"] = request.category

        if request.tags:
            query["tags"] = {"$in": request.tags}

        # Pagination
        skip = (request.page - 1) * request.limit

        clubs = []
        async for club in db_manager.get_tenant_collection("clubs").find(query).skip(skip).limit(request.limit):
            clubs.append(ClubResponse(**club))

        return clubs

    except Exception as e:
        logger.error("Failed to search clubs: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search clubs")


@router.get("/popular", response_model=List[ClubResponse])
async def get_popular_clubs(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(require_club_member)
):
    """Get popular clubs by member count."""
    try:
        from second_brain_database.database import db_manager

        clubs = []
        async for club in db_manager.get_tenant_collection("clubs").find({"is_active": True}).sort("member_count", -1).limit(limit):
            clubs.append(ClubResponse(**club))

        return clubs

    except Exception as e:
        logger.error("Failed to get popular clubs: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get popular clubs")


@router.get("/recommended", response_model=List[ClubResponse])
async def get_recommended_clubs(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(require_club_member)
):
    """Get recommended clubs (placeholder for ML-based recommendations)."""
    try:
        # For now, return popular clubs from different categories
        from second_brain_database.database import db_manager

        clubs = []
        async for club in db_manager.get_tenant_collection("clubs").aggregate([
            {"$match": {"is_active": True}},
            {"$sort": {"member_count": -1}},
            {"$limit": limit}
        ]):
            clubs.append(ClubResponse(**club))

        return clubs

    except Exception as e:
        logger.error("Failed to get recommended clubs: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get recommended clubs")


@router.get("/{club_id}", response_model=ClubResponse)
async def get_club(
    club_id: str,
    current_user: dict = Depends(require_club_member)
):
    """
    Get detailed information about a specific club.

    **Access Control:**
    Requires the user to be a member of the club (any role) to view full details.
    *Note: Public info might be available via `get_clubs`, but this endpoint enforces membership.*

    Args:
        club_id (str): The unique ID of the club.
        current_user (dict): The authenticated user.

    Returns:
        ClubResponse: The club details.

    Raises:
        HTTPException(403): If the user is not a member of the club.
        HTTPException(404): If the club is not found.
    """
    try:
        # Check access
        membership = await club_manager.check_club_access(
            current_user.get("_id", current_user.get("user_id")),
            club_id,
            ClubRole.MEMBER
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied")

        from second_brain_database.database import db_manager

        club_doc = await db_manager.get_tenant_collection("clubs").find_one({
            "club_id": club_id,
            "is_active": True
        })

        if not club_doc:
            raise HTTPException(status_code=404, detail="Club not found")

        return ClubResponse(**club_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get club: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get club")


@router.put("/{club_id}", response_model=ClubResponse)
async def update_club(
    club_id: str,
    request: CreateClubRequest,  # Reuse for updates
    current_user: dict = Depends(require_club_admin)
):
    """
    Update club settings and profile.

    This endpoint allows club administrators and owners to modify the club's
    details, such as description, social links, and branding.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role within the club.

    Args:
        club_id (str): The ID of the club to update.
        request (CreateClubRequest): The new club details.
        current_user (dict): The authenticated user (admin/owner).

    Returns:
        ClubResponse: The updated club details.

    Raises:
        HTTPException(403): If the user does not have admin privileges for this club.
    """
    try:
        # Check if user has admin access to this club
        if current_user.get("club_id") != club_id:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        from second_brain_database.database import db_manager

        # Update club
        update_data = request.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now()

        result = await db_manager.get_tenant_collection("clubs").update_one(
            {"club_id": club_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Club not found")

        # Get updated club
        club_doc = await db_manager.get_tenant_collection("clubs").find_one({"club_id": club_id})
        club = ClubResponse(**club_doc)

        # Clear cache
        await club_manager._clear_club_cache(club_id)

        logger.info("Updated club: %s", club_id)
        return club

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update club: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update club")


@router.delete("/{club_id}")
async def deactivate_club(
    club_id: str,
    current_user: dict = Depends(require_club_owner)
):
    """
    Deactivate (soft-delete) a club.

    This action marks the club as inactive, hiding it from search results and
    preventing new memberships. It does not permanently delete data.

    **Access Control:**
    Requires `OWNER` role.

    Args:
        club_id (str): The ID of the club to deactivate.
        current_user (dict): The authenticated user (owner).

    Returns:
        dict: Success message.

    Raises:
        HTTPException(403): If the user is not the owner of the club.
    """
    try:
        # Check if user is owner
        if current_user.get("club_id") != club_id:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        from second_brain_database.database import db_manager

        # Deactivate club
        result = await db_manager.get_tenant_collection("clubs").update_one(
            {"club_id": club_id},
            {"$set": {"is_active": False, "updated_at": datetime.now()}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Club not found")

        # Clear cache
        await club_manager._clear_club_cache(club_id)

        logger.info("Deactivated club: %s", club_id)
        return {"message": "Club deactivated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to deactivate club: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to deactivate club")


# Vertical Management Routes

@router.post("/{club_id}/verticals", response_model=VerticalResponse)
async def create_vertical(
    club_id: str,
    request: CreateVerticalRequest,
    current_user: dict = Depends(require_club_admin)
):
    """
    Create a new vertical (sub-department) within a club.

    Verticals allow clubs to organize members and activities into specific areas of interest
    (e.g., "AI/ML", "Web Dev", "Marketing").

    **Access Control:**
    Requires `ADMIN` or `OWNER` role within the club.

    Args:
        club_id (str): The ID of the club.
        request (CreateVerticalRequest): The vertical details (name, description, lead_id).
        current_user (dict): The authenticated user (admin).

    Returns:
        VerticalResponse: The created vertical details.

    Raises:
        HTTPException(403): If the user does not have admin privileges.
    """
    try:
        # Check club access
        if current_user.get("club_id") != club_id:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        vertical = await club_manager.create_vertical(
            club_id=club_id,
            name=request.name,
            description=request.description,
            lead_id=request.lead_id,
            max_members=request.max_members,
            color=request.color,
            icon=request.icon
        )

        logger.info("Created vertical: %s in club %s", vertical.vertical_id, club_id)
        return VerticalResponse(**vertical.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create vertical: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create vertical")


@router.get("/{club_id}/verticals", response_model=List[VerticalResponse])
async def get_club_verticals(
    club_id: str,
    current_user: dict = Depends(require_club_member)
):
    """
    Retrieve all active verticals for a club.

    Args:
        club_id (str): The ID of the club.
        current_user (dict): The authenticated user.

    Returns:
        List[VerticalResponse]: A list of active verticals.
    """
    try:
        # Check club access
        if current_user.get("club_id") != club_id:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        from second_brain_database.database import db_manager

        verticals = []
        async for vert in db_manager.get_tenant_collection("club_verticals").find({
            "club_id": club_id,
            "is_active": True
        }):
            verticals.append(VerticalResponse(**vert))

        return verticals

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get club verticals: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get verticals")


@router.get("/verticals/{vertical_id}", response_model=VerticalResponse)
async def get_vertical(
    vertical_id: str,
    current_user: dict = Depends(require_club_member)
):
    """
    Get detailed information about a specific vertical.

    **Access Control:**
    Requires membership in the parent club.

    Args:
        vertical_id (str): The unique ID of the vertical.
        current_user (dict): The authenticated user.

    Returns:
        VerticalResponse: The vertical details.

    Raises:
        HTTPException(404): If the vertical is not found.
    """
    try:
        from second_brain_database.database import db_manager

        vertical_doc = await db_manager.get_tenant_collection("club_verticals").find_one({
            "vertical_id": vertical_id,
            "is_active": True
        })

        if not vertical_doc:
            raise HTTPException(status_code=404, detail="Vertical not found")

        # Check club access
        membership = await club_manager.check_club_access(
            current_user.get("_id", current_user.get("user_id")),
            vertical_doc["club_id"],
            ClubRole.MEMBER
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied")

        return VerticalResponse(**vertical_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get vertical: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get vertical")


@router.put("/verticals/{vertical_id}", response_model=VerticalResponse)
async def update_vertical(
    vertical_id: str,
    request: CreateVerticalRequest,
    current_user: dict = Depends(require_club_admin)
):
    """
    Update vertical details.

    Allows updating the name, description, color, and icon of a vertical.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role in the parent club.

    Args:
        vertical_id (str): The ID of the vertical to update.
        request (CreateVerticalRequest): The new details.
        current_user (dict): The authenticated user (admin).

    Returns:
        VerticalResponse: The updated vertical.
    """
    try:
        from second_brain_database.database import db_manager

        # Get vertical to check club access
        vertical_doc = await db_manager.get_tenant_collection("club_verticals").find_one({
            "vertical_id": vertical_id,
            "is_active": True
        })

        if not vertical_doc:
            raise HTTPException(status_code=404, detail="Vertical not found")

        # Check club access
        if current_user.get("club_id") != vertical_doc["club_id"]:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        # Update vertical
        update_data = request.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now()

        result = await db_manager.get_tenant_collection("club_verticals").update_one(
            {"vertical_id": vertical_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Vertical not found")

        # Get updated vertical
        updated_doc = await db_manager.get_tenant_collection("club_verticals").find_one({"vertical_id": vertical_id})
        vertical = VerticalResponse(**updated_doc)

        logger.info("Updated vertical: %s", vertical_id)
        return vertical

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update vertical: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update vertical")


@router.put("/verticals/{vertical_id}/lead")
async def assign_vertical_lead(
    vertical_id: str,
    lead_id: str = Query(..., description="New lead user ID"),
    current_user: dict = Depends(require_club_admin)
):
    """
    Assign or change the lead of a vertical.

    The new lead must already be a member of the club.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role in the parent club.

    Args:
        vertical_id (str): The ID of the vertical.
        lead_id (str): The user ID of the new lead.
        current_user (dict): The authenticated user (admin).

    Returns:
        dict: Success message.

    Raises:
        HTTPException(400): If the proposed lead is not a club member.
    """
    try:
        from second_brain_database.database import db_manager

        # Get vertical
        vertical_doc = await db_manager.get_tenant_collection("club_verticals").find_one({
            "vertical_id": vertical_id,
            "is_active": True
        })

        if not vertical_doc:
            raise HTTPException(status_code=404, detail="Vertical not found")

        # Check club access
        if current_user.get("club_id") != vertical_doc["club_id"]:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        # Verify lead is club member
        member = await db_manager.get_tenant_collection("club_members").find_one({
            "club_id": vertical_doc["club_id"],
            "user_id": lead_id,
            "is_active": True
        })

        if not member:
            raise HTTPException(status_code=400, detail="Lead must be an active club member")

        # Update vertical lead
        result = await db_manager.get_tenant_collection("club_verticals").update_one(
            {"vertical_id": vertical_id},
            {"$set": {"lead_id": lead_id, "updated_at": datetime.now()}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Vertical not found")

        logger.info("Assigned lead %s to vertical %s", lead_id, vertical_id)
        return {"message": "Vertical lead assigned successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to assign vertical lead: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to assign vertical lead")


@router.delete("/verticals/{vertical_id}")
async def remove_vertical(
    vertical_id: str,
    current_user: dict = Depends(require_club_admin)
):
    """
    Deactivate (soft-delete) a vertical.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role in the parent club.

    Args:
        vertical_id (str): The ID of the vertical to remove.
        current_user (dict): The authenticated user (admin).

    Returns:
        dict: Success message.
    """
    try:
        from second_brain_database.database import db_manager

        # Get vertical
        vertical_doc = await db_manager.get_tenant_collection("club_verticals").find_one({
            "vertical_id": vertical_id,
            "is_active": True
        })

        if not vertical_doc:
            raise HTTPException(status_code=404, detail="Vertical not found")

        # Check club access
        if current_user.get("club_id") != vertical_doc["club_id"]:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        # Deactivate vertical
        result = await db_manager.get_tenant_collection("club_verticals").update_one(
            {"vertical_id": vertical_id},
            {"$set": {"is_active": False, "updated_at": datetime.now()}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Vertical not found")

        # Update club vertical count
        await db_manager.get_tenant_collection("clubs").update_one(
            {"club_id": vertical_doc["club_id"]},
            {"$inc": {"vertical_count": -1}}
        )

        logger.info("Removed vertical: %s", vertical_id)
        return {"message": "Vertical removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to remove vertical: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove vertical")


# Member Management Routes

@router.post("/{club_id}/members/invite", response_model=ClubMemberResponse)
async def invite_member(
    club_id: str,
    request: InviteMemberRequest,
    current_user: dict = Depends(require_club_lead)
):
    """
    Invite a user to join the club.

    This endpoint creates a pending membership record for the invited user.
    The user must accept the invitation to become an active member.

    **Access Control:**
    Requires `LEAD`, `ADMIN`, or `OWNER` role. Leads can only invite to their vertical.

    Args:
        club_id (str): The ID of the club.
        request (InviteMemberRequest): The invitation details (user_id, role, vertical_id).
        current_user (dict): The authenticated user (inviter).

    Returns:
        ClubMemberResponse: The pending membership details.

    Raises:
        HTTPException(400): If the user is already a member or invited.
    """
    try:
        # Check club access
        if current_user.get("club_id") != club_id:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        member = await club_manager.invite_member(
            club_id=club_id,
            user_id=request.user_id,
            role=request.role,
            invited_by=current_user.get("_id", current_user.get("user_id")),
            vertical_id=request.vertical_id,
            message=request.message
        )

        logger.info("Invited user %s to club %s with role %s",
                   request.user_id, club_id, request.role.value)
        return ClubMemberResponse(**member.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to invite member: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to invite member")


@router.post("/{club_id}/members/bulk-invite", response_model=List[ClubMemberResponse])
async def bulk_invite_members(
    club_id: str,
    request: BulkInviteRequest,
    current_user: dict = Depends(require_club_admin)
):
    """
    Bulk invite multiple users to the club.

    Efficiently processes a list of invitations. Errors for individual users (e.g., already a member)
    are logged but do not stop the entire batch.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role.

    Args:
        club_id (str): The ID of the club.
        request (BulkInviteRequest): A list of invitation requests.
        current_user (dict): The authenticated user (admin).

    Returns:
        List[ClubMemberResponse]: A list of successfully created invitations.
    """
    try:
        # Check club access
        if current_user.get("club_id") != club_id:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        members = []
        for invite in request.invites:
            try:
                member = await club_manager.invite_member(
                    club_id=club_id,
                    user_id=invite.user_id,
                    role=invite.role,
                    invited_by=current_user.get("_id", current_user.get("user_id")),
                    vertical_id=invite.vertical_id,
                    message=invite.message
                )
                members.append(ClubMemberResponse(**member.model_dump()))
            except Exception as e:
                logger.warning("Failed to invite user %s: %s", invite.user_id, e)
                continue

        logger.info("Bulk invited %d members to club %s", len(members), club_id)
        return members

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to bulk invite members: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to bulk invite members")


@router.post("/members/{member_id}/accept", response_model=ClubMemberResponse)
async def accept_invitation(
    member_id: str,
    current_user: dict = Depends(require_club_member)
):
    """
    Accept a pending club invitation.

    This action activates the user's membership in the club.

    Args:
        member_id (str): The ID of the membership record (from the invitation).
        current_user (dict): The authenticated user (must match the invited user).

    Returns:
        ClubMemberResponse: The active membership details.

    Raises:
        HTTPException(400): If the invitation is invalid or not for this user.
    """
    try:
        member = await club_manager.accept_invitation(
            member_id=member_id,
            user_id=current_user.get("_id", current_user.get("user_id"))
        )

        logger.info("Accepted invitation: %s for user %s",
                   member_id, current_user.get("username"))
        return ClubMemberResponse(**member.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to accept invitation: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to accept invitation")


@router.put("/members/{member_id}/role", response_model=ClubMemberResponse)
async def update_member_role(
    member_id: str,
    request: UpdateMemberRoleRequest,
    current_user: dict = Depends(require_club_admin)
):
    """
    Promote or demote a club member.

    Allows changing a member's role (e.g., Member -> Lead) and vertical assignment.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role.

    Args:
        member_id (str): The ID of the member to update.
        request (UpdateMemberRoleRequest): The new role and vertical.
        current_user (dict): The authenticated user (admin).

    Returns:
        ClubMemberResponse: The updated member details.
    """
    try:
        from second_brain_database.database import db_manager

        # Get member to check club access
        member_doc = await db_manager.get_tenant_collection("club_members").find_one({
            "member_id": member_id,
            "is_active": True
        })

        if not member_doc:
            raise HTTPException(status_code=404, detail="Member not found")

        # Check club access
        if current_user.get("club_id") != member_doc["club_id"]:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        # Update role
        update_data = {
            "role": request.role,
            "vertical_id": request.vertical_id,
            "updated_at": datetime.now()
        }

        result = await db_manager.get_tenant_collection("club_members").update_one(
            {"member_id": member_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Member not found")

        # Get updated member
        updated_doc = await db_manager.get_tenant_collection("club_members").find_one({"member_id": member_id})
        member = ClubMemberResponse(**updated_doc)

        logger.info("Updated role for member %s to %s", member_id, request.role.value)
        return member

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update member role: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update member role")


@router.put("/members/{member_id}/transfer", response_model=ClubMemberResponse)
async def transfer_member(
    member_id: str,
    request: TransferMemberRequest,
    current_user: dict = Depends(require_club_admin)
):
    """
    Transfer a member to a different vertical.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role.

    Args:
        member_id (str): The ID of the member.
        request (TransferMemberRequest): The new vertical ID.
        current_user (dict): The authenticated user (admin).

    Returns:
        ClubMemberResponse: The updated member details.
    """
    try:
        from second_brain_database.database import db_manager

        # Get member
        member_doc = await db_manager.get_tenant_collection("club_members").find_one({
            "member_id": member_id,
            "is_active": True
        })

        if not member_doc:
            raise HTTPException(status_code=404, detail="Member not found")

        # Check club access
        if current_user.get("club_id") != member_doc["club_id"]:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        # If assigning to vertical, verify it exists
        if request.vertical_id:
            vertical = await db_manager.get_tenant_collection("club_verticals").find_one({
                "vertical_id": request.vertical_id,
                "club_id": member_doc["club_id"],
                "is_active": True
            })
            if not vertical:
                raise HTTPException(status_code=400, detail="Vertical not found")

        # Update vertical assignment
        update_data = {
            "vertical_id": request.vertical_id,
            "updated_at": datetime.now()
        }

        result = await db_manager.get_tenant_collection("club_members").update_one(
            {"member_id": member_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Member not found")

        # Get updated member
        updated_doc = await db_manager.get_tenant_collection("club_members").find_one({"member_id": member_id})
        member = ClubMemberResponse(**updated_doc)

        logger.info("Transferred member %s to vertical %s", member_id, request.vertical_id)
        return member

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to transfer member: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to transfer member")


@router.put("/members/{member_id}/alumni", response_model=ClubMemberResponse)
async def mark_member_alumni(
    member_id: str,
    current_user: dict = Depends(require_club_admin)
):
    """
    Mark a member as an alumni.

    Alumni retain read-only access to the club but are not considered active members.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role.

    Args:
        member_id (str): The ID of the member.
        current_user (dict): The authenticated user (admin).

    Returns:
        ClubMemberResponse: The updated member details.
    """
    try:
        from second_brain_database.database import db_manager

        # Get member
        member_doc = await db_manager.get_tenant_collection("club_members").find_one({
            "member_id": member_id,
            "is_active": True
        })

        if not member_doc:
            raise HTTPException(status_code=404, detail="Member not found")

        # Check club access
        if current_user.get("club_id") != member_doc["club_id"]:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        # Mark as alumni
        update_data = {
            "is_alumni": True,
            "updated_at": datetime.now()
        }

        result = await db_manager.get_tenant_collection("club_members").update_one(
            {"member_id": member_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Member not found")

        # Get updated member
        updated_doc = await db_manager.get_tenant_collection("club_members").find_one({"member_id": member_id})
        member = ClubMemberResponse(**updated_doc)

        logger.info("Marked member %s as alumni", member_id)
        return member

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to mark member as alumni: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to mark member as alumni")


@router.delete("/members/{member_id}")
async def remove_member(
    member_id: str,
    current_user: dict = Depends(require_club_admin)
):
    """
    Remove (kick) a member from the club.

    This action deactivates the membership. The user will lose access to club resources.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role. Cannot remove the Owner.

    Args:
        member_id (str): The ID of the member to remove.
        current_user (dict): The authenticated user (admin).

    Returns:
        dict: Success message.

    Raises:
        HTTPException(400): If attempting to remove the club owner.
    """
    try:
        from second_brain_database.database import db_manager

        # Get member
        member_doc = await db_manager.get_tenant_collection("club_members").find_one({
            "member_id": member_id,
            "is_active": True
        })

        if not member_doc:
            raise HTTPException(status_code=404, detail="Member not found")

        # Check club access
        if current_user.get("club_id") != member_doc["club_id"]:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        # Cannot remove owner
        if member_doc["role"] == "owner":
            raise HTTPException(status_code=400, detail="Cannot remove club owner")

        # Deactivate membership
        result = await db_manager.get_tenant_collection("club_members").update_one(
            {"member_id": member_id},
            {"$set": {"is_active": False, "updated_at": datetime.now()}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Member not found")

        # Update club member count
        await db_manager.get_tenant_collection("clubs").update_one(
            {"club_id": member_doc["club_id"]},
            {"$inc": {"member_count": -1}}
        )

        # Update university member count
        club = await db_manager.get_tenant_collection("clubs").find_one({"club_id": member_doc["club_id"]})
        await db_manager.get_tenant_collection("universities").update_one(
            {"university_id": club["university_id"]},
            {"$inc": {"total_members": -1}}
        )

        # Update vertical member count if assigned
        if member_doc.get("vertical_id"):
            await db_manager.get_tenant_collection("club_verticals").update_one(
                {"vertical_id": member_doc["vertical_id"]},
                {"$inc": {"member_count": -1}}
            )

        logger.info("Removed member: %s from club %s", member_id, member_doc["club_id"])
        return {"message": "Member removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to remove member: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to remove member")


@router.get("/me/clubs", response_model=List[ClubResponse])
async def get_my_clubs(
    current_user: dict = Depends(require_club_member)
):
    """
    Retrieve all clubs the current user has joined.

    Args:
        current_user (dict): The authenticated user.

    Returns:
        List[ClubResponse]: A list of clubs where the user is a member.
    """
    try:
        clubs = await club_manager.get_user_clubs(
            current_user.get("_id", current_user.get("user_id"))
        )

        return [ClubResponse(**club.model_dump()) for club in clubs]

    except Exception as e:
        logger.error("Failed to get user clubs: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get user clubs")


@router.get("/{club_id}/members", response_model=List[ClubMemberResponse])
async def get_club_members(
    club_id: str,
    include_alumni: bool = Query(False, description="Include alumni members"),
    current_user: dict = Depends(require_club_member)
):
    """
    Retrieve the member directory for a club.

    **Access Control:**
    Requires membership in the club.

    Args:
        club_id (str): The ID of the club.
        include_alumni (bool): Whether to include alumni in the list.
        current_user (dict): The authenticated user.

    Returns:
        List[ClubMemberResponse]: A list of club members.
    """
    try:
        # Check club access
        if current_user.get("club_id") != club_id:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        from second_brain_database.database import db_manager

        # Build query
        query = {"club_id": club_id}
        if not include_alumni:
            query["is_alumni"] = False

        members = []
        async for member in db_manager.get_tenant_collection("club_members").find(query):
            members.append(ClubMemberResponse(**member))

        return members

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get club members: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get club members")


@router.get("/{club_id}/members/activity", response_model=ClubAnalyticsResponse)
async def get_club_member_activity(
    club_id: str,
    current_user: dict = Depends(require_club_admin)
):
    """
    Get member activity analytics (Admin only).

    Provides insights into member growth, vertical participation, and engagement scores.

    **Access Control:**
    Requires `ADMIN` or `OWNER` role.

    Args:
        club_id (str): The ID of the club.
        current_user (dict): The authenticated user (admin).

    Returns:
        ClubAnalyticsResponse: Analytics data.
    """
    try:
        # Check club access
        if current_user.get("club_id") != club_id:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        # Placeholder for analytics - implement later
        analytics = ClubAnalyticsResponse(
            club_id=club_id,
            member_growth=[],
            vertical_participation={},
            activity_metrics={},
            engagement_score=0.0
        )

        return analytics

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get club member activity: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get member activity")


# Authentication Routes for Clubs

@router.post("/auth/clubs/{club_id}/login")
async def login_to_club(
    club_id: str,
    current_user: dict = Depends(require_club_member)
):
    """
    Authenticate into a specific club context.

    Issues a club-scoped JWT token containing the user's role and vertical assignment
    within that specific club. This token is used for subsequent club-specific operations.

    Args:
        club_id (str): The ID of the club.
        current_user (dict): The authenticated user.

    Returns:
        dict: Access token and role information.
    """
    try:
        # Check if user has access to this club
        membership = await club_manager.check_club_access(
            current_user.get("_id", current_user.get("user_id")),
            club_id,
            ClubRole.MEMBER
        )

        if not membership:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        # Create club token
        token = await club_auth_manager.create_club_token(
            user_id=current_user.get("_id", current_user.get("user_id")),
            username=current_user.get("username"),
            club_id=club_id,
            role=membership.role,
            vertical_id=membership.vertical_id
        )

        logger.info("User %s logged into club %s with role %s",
                   current_user.get("username"), club_id, membership.role.value)

        return {
            "access_token": token,
            "token_type": "bearer",
            "club_id": club_id,
            "role": membership.role.value,
            "vertical_id": membership.vertical_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to login to club: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to login to club")


# Event Management Routes

@router.post("/{club_id}/events", response_model=EventResponse)
async def create_club_event(
    club_id: str,
    request: CreateEventRequest,
    current_user: dict = Depends(require_club_lead)
):
    """
    Create a new club event.

    Supports creating physical, virtual, or hybrid events.
    Automatically sets up a WebRTC room for virtual events if requested.
    Sends email announcements to club members.

    **Features:**
    *   **WebRTC Integration**: Creates a video room for virtual events.
    *   **Notifications**: Emails all club members about the new event.
    *   **Scheduling**: Validates start and end times.

    **Access Control:**
    Requires `LEAD`, `ADMIN`, or `OWNER` role.

    Args:
        club_id (str): The ID of the club.
        request (CreateEventRequest): The event details.
        current_user (dict): The authenticated user (organizer).

    Returns:
        EventResponse: The created event details.
    """
    try:
        # Check club access
        if current_user.get("club_id") != club_id:
            raise HTTPException(status_code=403, detail="Access denied to this club")

        from second_brain_database.database import db_manager

        # Generate event ID
        event_id = str(uuid4())

        # Create WebRTC room for virtual events
        webrtc_room_id = None
        if request.virtual_link or request.event_type in [EventType.MEETING, EventType.WORKSHOP]:
            # Create WebRTC room for the event
            webrtc_room_id = await ClubEventWebRTCManager.create_event_room(
                club_id=club_id,
                event_id=event_id,
                event_title=request.title,
                organizer_id=current_user.get("_id", current_user.get("user_id"))
            )

        # Create event document
        event_doc = EventDocument(
            event_id=event_id,
            club_id=club_id,
            title=request.title,
            description=request.description,
            event_type=request.event_type,
            status=EventStatus.PUBLISHED,  # Auto-publish for now
            visibility=request.visibility,
            start_time=request.start_time,
            end_time=request.end_time,
            timezone=request.timezone,
            location=request.location,
            virtual_link=request.virtual_link,
            max_attendees=request.max_attendees,
            organizer_id=current_user.get("_id", current_user.get("user_id")),
            co_organizers=request.co_organizers or [],
            tags=request.tags or [],
            image_url=request.image_url,
            agenda=request.agenda or [],
            requirements=request.requirements or [],
            is_recurring=request.is_recurring,
            recurrence_rule=request.recurrence_rule,
            webrtc_room_id=webrtc_room_id
        )

        # Save to database
        await db_manager.get_tenant_collection("club_events").insert_one(event_doc.model_dump())

        # Send event announcement notification
        try:
            await club_notification_manager.send_event_announcement_email(
                club_id=club_id,
                event_title=request.title,
                event_description=request.description,
                event_start_time=request.start_time,
                event_end_time=request.end_time,
                event_location=request.location,
                event_virtual_link=request.virtual_link,
                organizer_name=current_user.get("username", "Club Organizer")
            )
        except Exception as e:
            logger.warning("Failed to send event announcement notification: %s", e)
            # Don't fail the event creation if notification fails

        logger.info("Created event: %s in club %s with WebRTC room %s",
                   event_id, club_id, webrtc_room_id)
        return EventResponse(**event_doc.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create club event: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create event")


@router.get("/{club_id}/events", response_model=List[EventResponse])
async def get_club_events(
    club_id: str,
    status: Optional[EventStatus] = Query(None, description="Filter by event status"),
    event_type: Optional[EventType] = Query(None, description="Filter by event type"),
    upcoming_only: bool = Query(True, description="Show only upcoming events"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_club_member)
):
    """
    Retrieve a list of events for a club.

    Args:
        club_id (str): The ID of the club.
        status (EventStatus, optional): Filter by status (e.g., PUBLISHED, CANCELLED).
        event_type (EventType, optional): Filter by type (e.g., WORKSHOP, MEETING).
        upcoming_only (bool): If True, returns only future events.
        limit (int): Maximum number of results.
        current_user (dict): The authenticated user.

    Returns:
        List[EventResponse]: A list of events.
    """
    try:
        # Check club access
        membership = await club_manager.check_club_access(
            current_user.get("_id", current_user.get("user_id")),
            club_id,
            ClubRole.MEMBER
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied")

        from second_brain_database.database import db_manager

        # Build query
        query = {"club_id": club_id}

        if status:
            query["status"] = status

        if event_type:
            query["event_type"] = event_type

        if upcoming_only:
            query["start_time"] = {"$gte": datetime.now()}

        # Get events
        events = []
        async for event_doc in db_manager.get_tenant_collection("club_events").find(query).sort("start_time", 1).limit(limit):
            events.append(EventResponse(**event_doc))

        return events

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get club events: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get events")


@router.get("/events/search", response_model=List[EventResponse])
async def search_events(
    request: EventSearchRequest,
    current_user: dict = Depends(require_club_member)
):
    """
    Search for events across all clubs the user is a member of.

    Supports complex filtering by date range, type, tags, and organizer.

    Args:
        request (EventSearchRequest): The search criteria.
        current_user (dict): The authenticated user.

    Returns:
        List[EventResponse]: A list of matching events.
    """
    try:
        from second_brain_database.database import db_manager

        # Build query
        query = {}

        if request.query:
            query["$or"] = [
                {"title": {"$regex": request.query, "$options": "i"}},
                {"description": {"$regex": request.query, "$options": "i"}},
                {"tags": {"$in": [request.query]}}
            ]

        if request.club_id:
            query["club_id"] = request.club_id

        if request.event_type:
            query["event_type"] = request.event_type

        if request.status:
            query["status"] = request.status

        if request.visibility:
            query["visibility"] = request.visibility

        if request.organizer_id:
            query["organizer_id"] = request.organizer_id

        if request.tags:
            query["tags"] = {"$in": request.tags}

        # Date filters
        if request.start_date or request.end_date:
            date_filter = {}
            if request.start_date:
                date_filter["$gte"] = request.start_date
            if request.end_date:
                date_filter["$lte"] = request.end_date
            query["start_time"] = date_filter

        # Pagination
        skip = (request.page - 1) * request.limit

        events = []
        async for event_doc in db_manager.get_tenant_collection("club_events").find(query).sort("start_time", 1).skip(skip).limit(request.limit):
            # Check access to each event's club
            membership = await club_manager.check_club_access(
                current_user.get("_id", current_user.get("user_id")),
                event_doc["club_id"],
                ClubRole.MEMBER
            )
            if membership:
                events.append(EventResponse(**event_doc))

        return events

    except Exception as e:
        logger.error("Failed to search events: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search events")


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: str,
    current_user: dict = Depends(require_club_member)
):
    """Get a specific event by ID."""
    try:
        from second_brain_database.database import db_manager

        event_doc = await db_manager.get_tenant_collection("club_events").find_one({"event_id": event_id})

        if not event_doc:
            raise HTTPException(status_code=404, detail="Event not found")

        # Check club access
        membership = await club_manager.check_club_access(
            current_user.get("_id", current_user.get("user_id")),
            event_doc["club_id"],
            ClubRole.MEMBER
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied")

        return EventResponse(**event_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get event: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get event")


@router.put("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: str,
    request: UpdateEventRequest,
    current_user: dict = Depends(require_club_lead)
):
    """Update an event (organizer or co-organizer only)."""
    try:
        from second_brain_database.database import db_manager

        # Get event
        event_doc = await db_manager.get_tenant_collection("club_events").find_one({"event_id": event_id})

        if not event_doc:
            raise HTTPException(status_code=404, detail="Event not found")

        # Check if user can edit this event
        user_id = current_user.get("_id", current_user.get("user_id"))
        if user_id != event_doc["organizer_id"] and user_id not in event_doc.get("co_organizers", []):
            # Check club admin access as fallback
            membership = await club_manager.check_club_access(
                user_id,
                event_doc["club_id"],
                ClubRole.ADMIN
            )
            if not membership:
                raise HTTPException(status_code=403, detail="Access denied")

        # Update event
        update_data = request.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now()

        result = await db_manager.get_tenant_collection("club_events").update_one(
            {"event_id": event_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Event not found")

        # Get updated event
        updated_doc = await db_manager.get_tenant_collection("club_events").find_one({"event_id": event_id})
        event = EventResponse(**updated_doc)

        logger.info("Updated event: %s", event_id)
        return event

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update event: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update event")


@router.delete("/events/{event_id}")
async def delete_event(
    event_id: str,
    current_user: dict = Depends(require_club_lead)
):
    """Delete an event (organizer or admin only)."""
    try:
        from second_brain_database.database import db_manager

        # Get event
        event_doc = await db_manager.get_tenant_collection("club_events").find_one({"event_id": event_id})

        if not event_doc:
            raise HTTPException(status_code=404, detail="Event not found")

        # Check if user can delete this event
        user_id = current_user.get("_id", current_user.get("user_id"))
        if user_id != event_doc["organizer_id"]:
            # Check club admin access
            membership = await club_manager.check_club_access(
                user_id,
                event_doc["club_id"],
                ClubRole.ADMIN
            )
            if not membership:
                raise HTTPException(status_code=403, detail="Access denied")

        # Delete WebRTC room if exists
        if event_doc.get("webrtc_room_id"):
            try:
                await ClubEventWebRTCManager.delete_event_room(event_doc["webrtc_room_id"])
            except Exception as e:
                logger.warning("Failed to delete WebRTC room %s: %s", event_doc["webrtc_room_id"], e)

        # Delete event
        await db_manager.get_tenant_collection("club_events").delete_one({"event_id": event_id})

        # Delete all attendee records
        await db_manager.get_tenant_collection("event_attendees").delete_many({"event_id": event_id})

        logger.info("Deleted event: %s", event_id)
        return {"message": "Event deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete event: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete event")


@router.post("/events/{event_id}/register", response_model=EventAttendeeResponse)
async def register_for_event(
    event_id: str,
    request: RegisterForEventRequest = None,
    current_user: dict = Depends(require_club_member)
):
    """Register for an event."""
    try:
        from second_brain_database.database import db_manager

        # Get event
        event_doc = await db_manager.get_tenant_collection("club_events").find_one({"event_id": event_id})

        if not event_doc:
            raise HTTPException(status_code=404, detail="Event not found")

        # Check club access
        membership = await club_manager.check_club_access(
            current_user.get("_id", current_user.get("user_id")),
            event_doc["club_id"],
            ClubRole.MEMBER
        )
        if not membership:
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if event is full
        if event_doc.get("max_attendees") and event_doc["attendee_count"] >= event_doc["max_attendees"]:
            raise HTTPException(status_code=400, detail="Event is full")

        # Check if already registered
        existing = await db_manager.get_tenant_collection("event_attendees").find_one({
            "event_id": event_id,
            "user_id": current_user.get("_id", current_user.get("user_id"))
        })

        if existing:
            raise HTTPException(status_code=400, detail="Already registered for this event")

        # Create attendee record
        attendee_id = str(uuid4())
        attendee_doc = EventAttendeeDocument(
            attendee_id=attendee_id,
            event_id=event_id,
            user_id=current_user.get("_id", current_user.get("user_id")),
            notes=request.notes if request else None
        )

        await db_manager.get_tenant_collection("event_attendees").insert_one(attendee_doc.model_dump())

        # Update event attendee count
        await db_manager.get_tenant_collection("club_events").update_one(
            {"event_id": event_id},
            {"$inc": {"attendee_count": 1}}
        )

        logger.info("User %s registered for event %s", current_user.get("username"), event_id)
        return EventAttendeeResponse(**attendee_doc.model_dump())

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to register for event: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to register for event")


@router.delete("/events/{event_id}/register")
async def unregister_from_event(
    event_id: str,
    current_user: dict = Depends(require_club_member)
):
    """Unregister from an event."""
    try:
        from second_brain_database.database import db_manager

        # Get event
        event_doc = await db_manager.get_tenant_collection("club_events").find_one({"event_id": event_id})

        if not event_doc:
            raise HTTPException(status_code=404, detail="Event not found")

        user_id = current_user.get("_id", current_user.get("user_id"))

        # Delete attendee record
        result = await db_manager.get_tenant_collection("event_attendees").delete_one({
            "event_id": event_id,
            "user_id": user_id
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Not registered for this event")

        # Update event attendee count
        await db_manager.get_tenant_collection("club_events").update_one(
            {"event_id": event_id},
            {"$inc": {"attendee_count": -1}}
        )

        logger.info("User %s unregistered from event %s", current_user.get("username"), event_id)
        return {"message": "Successfully unregistered from event"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to unregister from event: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to unregister from event")


@router.get("/events/{event_id}/attendees", response_model=List[EventAttendeeResponse])
async def get_event_attendees(
    event_id: str,
    current_user: dict = Depends(require_club_lead)
):
    """Get attendees for an event (organizer/co-organizer/admin only)."""
    try:
        from second_brain_database.database import db_manager

        # Get event
        event_doc = await db_manager.get_tenant_collection("club_events").find_one({"event_id": event_id})

        if not event_doc:
            raise HTTPException(status_code=404, detail="Event not found")

        # Check if user can view attendees
        user_id = current_user.get("_id", current_user.get("user_id"))
        if user_id != event_doc["organizer_id"] and user_id not in event_doc.get("co_organizers", []):
            # Check club admin access
            membership = await club_manager.check_club_access(
                user_id,
                event_doc["club_id"],
                ClubRole.ADMIN
            )
            if not membership:
                raise HTTPException(status_code=403, detail="Access denied")

        # Get attendees
        attendees = []
        async for attendee_doc in db_manager.get_tenant_collection("event_attendees").find({"event_id": event_id}):
            attendees.append(EventAttendeeResponse(**attendee_doc))

        return attendees

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get event attendees: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get event attendees")


@router.put("/events/{event_id}/attendees/{attendee_id}/attended")
async def mark_attendee_attended(
    event_id: str,
    attendee_id: str,
    current_user: dict = Depends(require_club_lead)
):
    """Mark an attendee as having attended the event."""
    try:
        from second_brain_database.database import db_manager

        # Get event
        event_doc = await db_manager.get_tenant_collection("club_events").find_one({"event_id": event_id})

        if not event_doc:
            raise HTTPException(status_code=404, detail="Event not found")

        # Check if user can mark attendance
        user_id = current_user.get("_id", current_user.get("user_id"))
        if user_id != event_doc["organizer_id"] and user_id not in event_doc.get("co_organizers", []):
            # Check club admin access
            membership = await club_manager.check_club_access(
                user_id,
                event_doc["club_id"],
                ClubRole.ADMIN
            )
            if not membership:
                raise HTTPException(status_code=403, detail="Access denied")

        # Mark as attended
        result = await db_manager.get_tenant_collection("event_attendees").update_one(
            {"attendee_id": attendee_id, "event_id": event_id},
            {"$set": {"attended_at": datetime.now(), "status": "attended"}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Attendee not found")

        logger.info("Marked attendee %s as attended for event %s", attendee_id, event_id)
        return {"message": "Attendee marked as attended"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to mark attendee as attended: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to mark attendee as attended")


@router.post("/events/{event_id}/reminders")
async def send_event_reminders(
    event_id: str,
    current_user: dict = Depends(require_club_lead)
):
    """Send reminder notifications for an event."""
    try:
        from second_brain_database.database import db_manager

        # Get event
        event_doc = await db_manager.get_tenant_collection("club_events").find_one({"event_id": event_id})

        if not event_doc:
            raise HTTPException(status_code=404, detail="Event not found")

        # Check if user can send reminders
        user_id = current_user.get("_id", current_user.get("user_id"))
        if user_id != event_doc["organizer_id"] and user_id not in event_doc.get("co_organizers", []):
            # Check club admin access
            membership = await club_manager.check_club_access(
                user_id,
                event_doc["club_id"],
                ClubRole.ADMIN
            )
            if not membership:
                raise HTTPException(status_code=403, detail="Access denied")

        # Get all registered attendees
        attendees = []
        async for attendee_doc in db_manager.get_tenant_collection("event_attendees").find({"event_id": event_id}):
            attendees.append(attendee_doc)

        # Send reminders
        reminder_count = 0
        for attendee in attendees:
            try:
                await club_notification_manager.send_event_reminder_email(
                    recipient_email=attendee["user_id"],  # This should be email, but we have user_id
                    event_title=event_doc["title"],
                    event_start_time=event_doc["start_time"],
                    event_location=event_doc.get("location"),
                    event_virtual_link=event_doc.get("virtual_link"),
                    club_name="Club Event"  # TODO: Get actual club name
                )
                reminder_count += 1
            except Exception as e:
                logger.warning("Failed to send reminder to attendee %s: %s", attendee["attendee_id"], e)

        logger.info("Sent %d reminders for event %s", reminder_count, event_id)
        return {"message": f"Sent {reminder_count} reminder notifications"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to send event reminders: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send reminders")


# ============================================================================
# DIRECT MEMBERSHIP ENDPOINTS
# ============================================================================

@router.post("/{club_id}/join")
async def join_club(
    club_id: str,
    message: Optional[str] = Body(None, description="Optional message to club admins"),
    current_user: dict = Depends(require_club_member),
):
    """
    Request to join a club directly.
    
    - **Public clubs**: Automatically approved and user becomes a member
    - **Private clubs**: Creates pending membership request requiring admin approval
    
    **Returns:**
    - Membership status (approved or pending)
    - Member ID if approved
    """
    user_id = str(current_user["_id"])
    username = current_user["username"]
    
    try:
        # Get club details
        club = await club_manager.get_club(club_id)
        if not club:
            raise HTTPException(status_code=404, detail="Club not found")
            
        # Check if already a member
        existing_membership = await club_manager.get_member_by_user_id(club_id, user_id)
        if existing_membership:
            if existing_membership.get("status") == "active":
                raise HTTPException(status_code=400, detail="Already a member of this club")
            elif existing_membership.get("status") == "pending":
                raise HTTPException(status_code=400, detail="Membership request already pending")
                
        # Determine if club is public or private
        is_public = club.get("is_public", True)
        
        if is_public:
            # Auto-approve for public clubs
            member_id = f"mem_{datetime.now().timestamp()}_{user_id[:8]}"
            
            member_doc = {
                "member_id": member_id,
                "club_id": club_id,
                "user_id": user_id,
                "username": username,
                "role": ClubRole.MEMBER.value,
                "status": "active",
                "joined_at": datetime.now(),
                "invited_by": None,
                "invitation_message": None,
            }
            
            await db_manager.get_tenant_collection("club_members").insert_one(member_doc)
            
            # Increment member count
            await db_manager.get_tenant_collection("clubs").update_one(
                {"club_id": club_id},
                {"$inc": {"member_count": 1}}
            )
            
            logger.info("User %s joined public club %s", username, club_id)
            
            return {
                "status": "approved",
                "member_id": member_id,
                "club_id": club_id,
                "message": "Successfully joined the club"
            }
        else:
            # Create pending request for private clubs
            member_id = f"mem_{datetime.now().timestamp()}_{user_id[:8]}"
            
            member_doc = {
                "member_id": member_id,
                "club_id": club_id,
                "user_id": user_id,
                "username": username,
                "role": ClubRole.MEMBER.value,
                "status": "pending",
                "requested_at": datetime.now(),
                "request_message": message,
                "invited_by": None,
                "invitation_message": None,
            }
            
            await db_manager.get_tenant_collection("club_members").insert_one(member_doc)
            
            # Notify club admins
            try:
                admins = await club_manager.get_club_members(
                    club_id,
                    role_filter=ClubRole.ADMIN
                )
                
                for admin in admins:
                    await club_notification_manager.send_join_request_notification(
                        admin_email=admin.get("user_id"),  # Should be email
                        requester_name=username,
                        club_name=club.get("name"),
                        request_message=message
                    )
            except Exception as e:
                logger.warning("Failed to notify admins of join request: %s", e)
                
            logger.info("User %s requested to join private club %s", username, club_id)
            
            return {
                "status": "pending",
                "member_id": member_id,
                "club_id": club_id,
                "message": "Join request submitted. Awaiting admin approval."
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to join club: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to join club")


@router.post("/{club_id}/leave")
async def leave_club(
    club_id: str,
    current_user: dict = Depends(require_club_member),
):
    """
    Leave a club.
    
    **Restrictions:**
    - Club owners cannot leave their own club
    - Must transfer ownership first before leaving
    
    **Returns:**
    - Success message
    """
    user_id = str(current_user["_id"])
    username = current_user["username"]
    
    try:
        # Get club details
        club = await club_manager.get_club(club_id)
        if not club:
            raise HTTPException(status_code=404, detail="Club not found")
            
        # Check if user is a member
        membership = await club_manager.get_member_by_user_id(club_id, user_id)
        if not membership:
            raise HTTPException(status_code=400, detail="Not a member of this club")
            
        # Prevent owner from leaving
        if membership.get("role") == ClubRole.OWNER.value:
            raise HTTPException(
                status_code=400,
                detail="Club owners cannot leave. Transfer ownership first."
            )
            
        # Remove membership
        await db_manager.get_tenant_collection("club_members").delete_one({
            "club_id": club_id,
            "user_id": user_id
        })
        
        # Decrement member count (only if was active member)
        if membership.get("status") == "active":
            await db_manager.get_tenant_collection("clubs").update_one(
                {"club_id": club_id},
                {"$inc": {"member_count": -1}}
            )
            
        logger.info("User %s left club %s", username, club_id)
        
        return {
            "status": "success",
            "club_id": club_id,
            "message": "Successfully left the club"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to leave club: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to leave club")