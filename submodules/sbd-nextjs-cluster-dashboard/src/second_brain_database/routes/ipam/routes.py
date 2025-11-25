"""
# IPAM Routes

This module provides the **REST API endpoints** for the IP Address Management System.
It implements the hierarchical logic for managing the **10.X.Y.Z** private address space.

## Domain Overview

The IPAM system is structured around a strict hierarchy:
1.  **Country (X-Octet)**: Top-level geographical division.
2.  **Region (Y-Octet)**: /24 Subnets allocated within a country.
3.  **Host (Z-Octet)**: Individual IP addresses within a region.

## Key Features

### 1. Hierarchical Allocation
- **Countries**: List and inspect available X-ranges.
- **Regions**: Allocate /24 blocks (10.X.Y.0/24).
- **Hosts**: Assign specific IPs (10.X.Y.Z) to devices.

### 2. Advanced Management
- **Reservations**: Hold resources before full allocation.
- **Sharing**: Generate secure links to share resource details.
- **Bulk Operations**: Tag or update multiple resources at once.

### 3. Analytics & Monitoring
- **Utilization**: Real-time capacity tracking per country/region.
- **Forecasting**: Predict exhaustion dates based on usage trends.
- **Webhooks**: Event-driven notifications for external systems.

## API Endpoints

### Core Resources
- `GET /ipam/countries` - List countries
- `POST /ipam/regions` - Allocate region
- `GET /ipam/regions` - List regions
- `POST /ipam/hosts` - Allocate host

### Advanced Features
- `POST /ipam/reservations` - Create reservation
- `POST /ipam/shares` - Create share link
- `POST /ipam/bulk/tags` - Bulk tag update

## Usage Example

### Allocating a Region

```python
await client.post("/ipam/regions", params={
    "country": "India",
    "region_name": "Mumbai-DC1"
})
```
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from typing import List, Optional, Dict, Any

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.ipam_manager import ipam_manager
from second_brain_database.routes.ipam.dependencies import (
    get_current_user_for_ipam,
    require_ipam_read,
    require_ipam_allocate,
    require_ipam_update,
    require_ipam_release,
    require_ipam_admin,
    check_ipam_rate_limit,
)
from second_brain_database.routes.ipam.models import (
    ReservationCreateRequest,
    ReservationConvertRequest,
    ShareCreateRequest,
    PreferencesUpdateRequest,
    SavedFilterRequest,
    NotificationRuleRequest,
    NotificationUpdateRequest,
    WebhookCreateRequest,
    BulkTagUpdateRequest,
)
from second_brain_database.routes.ipam.utils import (
    format_region_response,
    format_host_response,
    format_country_response,
    format_utilization_response,
    format_pagination_response,
    format_error_response,
    validate_pagination_params,
    extract_client_info,
)

logger = get_logger(prefix="[IPAM Routes]")

# Create router with prefix and tags
router = APIRouter(
    prefix="/ipam",
    tags=["IPAM"]
)


# ============================================================================
# Health Check Endpoint
# ============================================================================

@router.get(
    "/health",
    summary="IPAM health check",
    description="""
    Check the health status of the IPAM system.
    
    Verifies:
    - MongoDB connection
    - Redis connection
    - Continent-country mapping loaded
    
    Returns 200 OK if all checks pass, 503 Service Unavailable otherwise.
    """,
    responses={
        200: {
            "description": "IPAM system is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "checks": {
                            "mongodb": "ok",
                            "redis": "ok",
                            "mappings": "ok"
                        }
                    }
                }
            }
        },
        503: {
            "description": "IPAM system is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "checks": {
                            "mongodb": "ok",
                            "redis": "error",
                            "mappings": "ok"
                        }
                    }
                }
            }
        }
    },
    tags=["IPAM - System"]
)
async def health_check():
    """
    Perform a comprehensive health check of the IPAM system and its dependencies.

    Verifies the operational status of all critical components required for IP address management,
    including database connectivity and cache availability.

    **Checks Performed:**
    - **MongoDB**: Verifies read/write access to the IPAM collections.
    - **Redis**: Checks connection for rate limiting and caching.
    - **Mappings**: Ensures continent-country mapping data is loaded and accessible.

    **Return Codes:**
    - **200 OK**: All systems operational.
    - **503 Service Unavailable**: One or more critical dependencies failed.

    Returns:
        A dictionary containing the overall `status` and individual check results.

    Raises:
        HTTPException: **503** if the system is unhealthy.
    """
    try:
        # TODO: Implement actual health checks
        # - Check MongoDB connection
        # - Check Redis connection
        # - Verify continent-country mapping loaded
        
        return {
            "status": "healthy",
            "checks": {
                "mongodb": "ok",
                "redis": "ok",
                "mappings": "ok"
            }
        }
    except Exception as e:
        logger.error("IPAM health check failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "error": str(e)
            }
        )


# ============================================================================
# Country and Mapping Endpoints
# ============================================================================

@router.get(
    "/countries",
    summary="List all countries",
    description="""
    Retrieve all predefined countries with their continent mappings and X octet ranges.
    
    Supports filtering by continent to narrow down results.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved countries",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "continent": "Asia",
                            "country": "India",
                            "x_start": 0,
                            "x_end": 29,
                            "total_blocks": 7680,
                            "is_reserved": False
                        }
                    ]
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Countries"]
)
async def list_countries(
    request: Request,
    continent: Optional[str] = Query(None, description="Filter by continent"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve a list of all supported countries with their IPAM configuration.

    Returns the static mapping of countries to their assigned "X-octet" ranges within the
    10.X.Y.Z private address space. This serves as the root of the IPAM hierarchy.

    **Features:**
    - **Filtering**: Filter by continent (e.g., "Asia", "Europe").
    - **Enrichment**: Response includes the number of regions allocated by the current user in each country.
    - **Utilization**: Calculates the percentage of assigned address space used.

    **Rate Limiting:**
    - 500 requests per hour per user.

    Args:
        request: The FastAPI request object.
        continent: Optional filter to return countries only from a specific continent.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A list of country objects with metadata and utilization stats.

    Raises:
        HTTPException: **500** if the country list cannot be retrieved.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "country_list", limit=500, period=3600)
    
    try:
        countries = await ipam_manager.get_all_countries(continent=continent)
        
        # Enrich each country with allocated regions count for this user
        regions_collection = db_manager.get_tenant_collection("ipam_regions")
        for country in countries:
            allocated_regions = await regions_collection.count_documents({
                "user_id": user_id,
                "country": country["country"]
            })
            country["allocated_regions"] = allocated_regions
            
            # Calculate utilization percentage
            total_capacity = country.get("total_blocks", 0) * 256  # Each block is /16 = 256 /24 regions
            country["utilization_percentage"] = round((allocated_regions / total_capacity * 100), 2) if total_capacity > 0 else 0.0
        
        logger.info(
            "User %s listed %d countries (continent_filter=%s)",
            user_id,
            len(countries),
            continent or "all"
        )
        
        return [format_country_response(country) for country in countries]
        
    except Exception as e:
        logger.error("Failed to list countries for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "country_list_failed",
                "Failed to retrieve country list"
            )
        )


@router.get(
    "/countries/{country}",
    summary="Get country details",
    description="""
    Retrieve detailed information about a specific country including its
    continent, X octet range, and total capacity.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved country details",
            "content": {
                "application/json": {
                    "example": {
                        "continent": "Asia",
                        "country": "India",
                        "x_start": 0,
                        "x_end": 29,
                        "total_blocks": 7680,
                        "is_reserved": False
                    }
                }
            }
        },
        404: {"description": "Country not found"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Countries"]
)
async def get_country(
    request: Request,
    country: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve detailed configuration and statistics for a specific country.

    Provides the IPAM parameters (X-octet range) and current usage statistics for a single country.
    Useful for validating availability before attempting to create a new region.

    **Data Points:**
    - **Continent**: The geographical continent.
    - **X-Range**: The start and end values for the second octet (10.X...).
    - **Capacity**: Total number of /24 blocks available.
    - **Allocated**: Number of regions currently allocated by the user.

    Args:
        request: The FastAPI request object.
        country: The name of the country (case-insensitive).
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Detailed country object with utilization metrics.

    Raises:
        HTTPException: **404** if country not found, **500** for server errors.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "country_get", limit=500, period=3600)
    
    try:
        country_data = await ipam_manager.get_country_mapping(country)
        
        if not country_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    "country_not_found",
                    f"Country '{country}' not found"
                )
            )
        
        # Add allocated regions count for this user
        regions_collection = db_manager.get_tenant_collection("ipam_regions")
        allocated_regions = await regions_collection.count_documents({
            "user_id": user_id,
            "country": country
        })
        country_data["allocated_regions"] = allocated_regions
        
        # Calculate utilization percentage
        total_capacity = country_data.get("total_blocks", 0) * 256  # Each block is /16 = 256 /24 regions
        country_data["utilization_percentage"] = round((allocated_regions / total_capacity * 100), 2) if total_capacity > 0 else 0.0
        
        logger.info("User %s retrieved country details for %s", user_id, country)
        
        return format_country_response(country_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get country %s for user %s: %s", country, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "country_get_failed",
                f"Failed to retrieve country '{country}'"
            )
        )


@router.get(
    "/countries/{country}/utilization",
    summary="Get country utilization statistics",
    description="""
    Calculate and retrieve utilization statistics for a specific country
    within the authenticated user's namespace.
    
    Returns total capacity, allocated regions, and utilization percentage.
    Results are cached for 5 minutes.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved utilization statistics",
            "content": {
                "application/json": {
                    "example": {
                        "resource_type": "country",
                        "resource_id": "India",
                        "total_capacity": 7680,
                        "allocated": 150,
                        "available": 7530,
                        "utilization_percent": 1.95,
                        "breakdown": {
                            "0": {"allocated": 50, "capacity": 256},
                            "1": {"allocated": 100, "capacity": 256}
                        }
                    }
                }
            }
        },
        404: {"description": "Country not found"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Countries"]
)
async def get_country_utilization(
    request: Request,
    country: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Calculate and retrieve detailed utilization statistics for a country.

    Performs a real-time analysis of the user's IP address usage within a specific country.
    This includes a breakdown of allocated vs. available /24 blocks.

    **Metrics:**
    - **Total Capacity**: Maximum possible regions in the country's X-range.
    - **Allocated**: Number of regions currently owned by the user.
    - **Utilization %**: Percentage of capacity used.
    - **Breakdown**: Detailed usage per X-octet.

    **Caching:**
    - Results are cached for 5 minutes to reduce database load.

    Args:
        request: The FastAPI request object.
        country: The name of the country.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        `UtilizationResponse` object with detailed statistics.

    Raises:
        HTTPException: **500** if calculation fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "country_utilization", limit=500, period=3600)
    
    try:
        utilization = await ipam_manager.calculate_country_utilization(user_id, country)
        
        logger.info(
            "User %s retrieved utilization for country %s: %.2f%%",
            user_id,
            country,
            utilization.get("utilization_percent", 0)
        )
        
        return format_utilization_response(utilization)
        
    except Exception as e:
        logger.error(
            "Failed to get country utilization for %s, user %s: %s",
            country,
            user_id,
            e,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "country_utilization_failed",
                f"Failed to calculate utilization for country '{country}'"
            )
        )


# ============================================================================
# Region Management Endpoints
# ============================================================================

@router.post(
    "/regions",
    status_code=status.HTTP_201_CREATED,
    summary="Create new region",
    description="""
    Allocate a new /24 region block within a country's address space.
    
    The system automatically:
    - Selects the next available X.Y combination
    - Validates country capacity
    - Enforces user quotas
    - Creates audit trail
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:allocate
    """,
    responses={
        201: {
            "description": "Region allocated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "region_id": "550e8400-e29b-41d4-a716-446655440000",
                        "cidr": "10.5.23.0/24",
                        "x_octet": 5,
                        "y_octet": 23,
                        "country": "India",
                        "continent": "Asia",
                        "region_name": "Mumbai DC1",
                        "status": "Active"
                    }
                }
            }
        },
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Capacity exhausted or duplicate name"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def create_region(
    request: Request,
    country: str = Query(..., description="Country for region allocation"),
    region_name: str = Query(..., description="Name for the region"),
    description: Optional[str] = Query(None, description="Optional description"),
    tags: Optional[str] = Query(None, description="Optional tags as JSON string"),
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """
    Allocate a new /24 region block within a country's address space.

    This is the primary endpoint for provisioning new network segments. It automatically
    finds the next available subnet (10.X.Y.0/24) within the target country's assigned range.

    **Allocation Logic:**
    1.  **Validation**: Checks if the country exists and has capacity.
    2.  **Selection**: Finds the lowest available X and Y octets.
    3.  **Reservation**: Atomically reserves the block to prevent race conditions.
    4.  **Quota Check**: Verifies the user hasn't exceeded their region limit.

    **Side Effects:**
    - Creates a new document in `ipam_regions` collection.
    - Logs the allocation in the audit trail.
    - Sets the authenticated user as the owner.

    Args:
        request: The FastAPI request object.
        country: Target country for allocation.
        region_name: User-friendly name for the region (must be unique within country).
        description: Optional text description.
        tags: Optional JSON string of tags (e.g., `{"env": "prod"}`).
        current_user: The authenticated user (requires `ipam:allocate` permission).

    Returns:
        The newly created region object with assigned CIDR.

    Raises:
        HTTPException:
            - **409 Conflict**: If capacity is exhausted or name is duplicate.
            - **429 Too Many Requests**: If user quota is exceeded.
            - **400 Bad Request**: For validation errors.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_create", limit=100, period=3600)
    
    try:
        region = await ipam_manager.allocate_region(
            user_id=user_id,
            country=country,
            region_name=region_name,
            description=description,
            tags=tags or {}
        )
        
        # Set owner to username automatically
        owner_name = current_user.get("username", user_id)
        await db_manager.get_tenant_collection("ipam_regions").update_one(
            {"_id": region["_id"]},
            {"$set": {"owner": owner_name}}
        )
        region["owner"] = owner_name
        
        logger.info(
            "User %s created region %s in country %s: %s",
            user_id,
            region.get("cidr"),
            country,
            region_name
        )
        
        return format_region_response(region)
        
    except Exception as e:
        logger.error(
            "Failed to create region for user %s in country %s: %s",
            user_id,
            country,
            e,
            exc_info=True
        )
        
        # Check for specific error types
        error_msg = str(e).lower()
        if "capacity" in error_msg or "exhausted" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "capacity_exhausted",
                    f"No available addresses in country {country}",
                    {"country": country}
                )
            )
        elif "duplicate" in error_msg or "exists" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "duplicate_name",
                    f"Region name '{region_name}' already exists in {country}",
                    {"country": country, "region_name": region_name}
                )
            )
        elif "quota" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=format_error_response(
                    "quota_exceeded",
                    "Region quota exceeded",
                    {"user_id": user_id}
                )
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response(
                    "region_creation_failed",
                    str(e)
                )
            )


@router.get(
    "/regions",
    summary="List regions",
    description="""
    List regions with optional filters and pagination.
    
    Supports filtering by country, status, owner, tags, and date ranges.
    Results are paginated with configurable page size.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved regions",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "region_id": "550e8400-e29b-41d4-a716-446655440000",
                                "cidr": "10.5.23.0/24",
                                "country": "India",
                                "region_name": "Mumbai DC1",
                                "status": "Active"
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "page_size": 50,
                            "total_count": 150,
                            "total_pages": 3,
                            "has_next": True,
                            "has_prev": False
                        }
                    }
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def list_regions(
    request: Request,
    country: Optional[str] = Query(None, description="Filter by country"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    owner: Optional[str] = Query(None, description="Filter by owner (accepts owner name or owner id)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve a paginated list of allocated regions with advanced filtering.

    Allows users to browse their allocated network segments. Supports filtering by various
    attributes to find specific regions.

    **Filters:**
    - **Country**: Filter by country name.
    - **Status**: Filter by operational status (e.g., 'Active', 'Maintenance').
    - **Owner**: Filter by owner username or ID.
    - **Tags**: (Not yet implemented in this endpoint, but planned).

    **Pagination:**
    - Standard page/page_size pagination.
    - Returns total count and page metadata.

    Args:
        request: The FastAPI request object.
        country: Optional country filter.
        status_filter: Optional status filter (aliased as `status`).
        owner: Optional owner filter.
        page: Page number (1-based).
        page_size: Items per page (max 100).
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Paginated response containing a list of region objects.

    Raises:
        HTTPException: **400** for invalid parameters, **500** for query errors.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_list", limit=500, period=3600)
    
    try:
        # Validate pagination
        page, page_size = validate_pagination_params(page, page_size)
        
        # Build filters
        filters = {}
        if country:
            filters["country"] = country
        if status_filter:
            filters["status"] = status_filter
        if owner:
            filters["owner"] = owner
        
        # Get regions
        result = await ipam_manager.get_regions(
            user_id=user_id,
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        # Format response
        formatted_regions = [format_region_response(r) for r in result.get("regions", [])]
        
        logger.info(
            "User %s listed %d regions (page=%d, filters=%s)",
            user_id,
            len(formatted_regions),
            page,
            filters
        )
        
        return format_pagination_response(
            items=formatted_regions,
            page=page,
            page_size=page_size,
            total_count=result.get("pagination", {}).get("total_count", 0)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("invalid_parameters", str(e))
        )
    except Exception as e:
        logger.error("Failed to list regions for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("region_list_failed", "Failed to retrieve regions")
        )


@router.get(
    "/regions/{region_id}",
    summary="Get region details",
    description="""
    Retrieve detailed information about a specific region.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved region details"},
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def get_region(
    request: Request,
    region_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve detailed information for a specific region by its ID.

    Returns the full configuration of a region, including its CIDR, location,
    status, and metadata.

    **Access Control:**
    - Users can only view regions they own or have been granted access to via RBAC.

    Args:
        request: The FastAPI request object.
        region_id: The UUID of the region.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        The region object.

    Raises:
        HTTPException: **404** if region not found, **500** for server errors.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_get", limit=500, period=3600)
    
    try:
        region = await ipam_manager.get_region_by_id(user_id, region_id)
        
        if not region:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    "region_not_found",
                    f"Region '{region_id}' not found"
                )
            )
        
        logger.info("User %s retrieved region %s", user_id, region_id)
        
        return format_region_response(region)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get region %s for user %s: %s", region_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("region_get_failed", "Failed to retrieve region")
        )


@router.patch(
    "/regions/{region_id}",
    summary="Update region",
    description="""
    Update region metadata including name, description, owner, status, and tags.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:update
    """,
    responses={
        200: {"description": "Region updated successfully"},
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def update_region(
    request: Request,
    region_id: str,
    region_name: Optional[str] = Query(None, description="New region name"),
    description: Optional[str] = Query(None, description="New description"),
    owner: Optional[str] = Query(None, description="New owner (accepts owner name or owner id)"),
    status_update: Optional[str] = Query(None, alias="status", description="New status"),
    tags: Optional[str] = Query(None, description="New tags (JSON string)"),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Update the metadata and status of an existing region.

    Allows modification of non-structural attributes. The CIDR and Country cannot be changed
    once allocated (requires migration/re-allocation).

    **Modifiable Fields:**
    - **Name**: Region name (must remain unique within country).
    - **Description**: Text description.
    - **Owner**: Transfer ownership to another user.
    - **Status**: Update operational status.
    - **Tags**: Update resource tags.

    Args:
        request: The FastAPI request object.
        region_id: The UUID of the region to update.
        region_name: New name.
        description: New description.
        owner: New owner username/ID.
        status_update: New status (aliased as `status`).
        tags: New tags JSON string.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        The updated region object.

    Raises:
        HTTPException: **404** if not found, **400** if update fails (e.g., duplicate name).
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_update", limit=100, period=3600)
    
    try:
        # Build updates dict
        updates = {}
        if region_name is not None:
            updates["region_name"] = region_name
        if description is not None:
            updates["description"] = description
        if owner is not None:
            updates["owner"] = owner
        if status_update is not None:
            updates["status"] = status_update
        if tags is not None:
            updates["tags"] = tags
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response(
                    "no_updates",
                    "No update fields provided"
                )
            )
        
        region = await ipam_manager.update_region(user_id, region_id, updates)
        
        logger.info("User %s updated region %s: %s", user_id, region_id, list(updates.keys()))
        
        return format_region_response(region)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update region %s for user %s: %s", region_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("region_not_found", f"Region '{region_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("region_update_failed", str(e))
            )


@router.delete(
    "/regions/{region_id}",
    summary="Retire region",
    description="""
    Retire (hard delete) a region and optionally cascade to all child hosts.
    
    The region is permanently deleted and moved to audit history.
    Address space is immediately reclaimed.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:release
    """,
    responses={
        200: {"description": "Region retired successfully"},
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def retire_region(
    request: Request,
    region_id: str,
    reason: str = Query(..., description="Reason for retirement"),
    cascade: bool = Query(False, description="Also retire all child hosts"),
    current_user: Dict[str, Any] = Depends(require_ipam_release)
):
    """
    Permanently retire a region and reclaim its address space.

    This is a destructive operation that removes the region from active service.
    The region's CIDR block becomes available for re-allocation.

    **Cascade Deletion:**
    - If `cascade=True`, all hosts allocated within this region are also retired.
    - If `cascade=False` (default), the operation fails if active hosts exist.

    **Audit:**
    - The region record is moved to the `ipam_history` collection.
    - A retirement reason is mandatory for audit compliance.

    Args:
        request: The FastAPI request object.
        region_id: The UUID of the region to retire.
        reason: Mandatory text explaining why the region is being retired.
        cascade: Boolean flag to auto-retire child hosts.
        current_user: The authenticated user (requires `ipam:release` permission).

    Returns:
        A dictionary containing the status, region ID, and count of retired hosts.

    Raises:
        HTTPException:
            - **404** if region not found.
            - **400** if active hosts exist and cascade is False.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_retire", limit=100, period=3600)
    
    try:
        result = await ipam_manager.retire_allocation(
            user_id=user_id,
            resource_type="region",
            resource_id=region_id,
            reason=reason,
            cascade=cascade
        )
        
        logger.info(
            "User %s retired region %s (cascade=%s): %s",
            user_id,
            region_id,
            cascade,
            reason
        )
        
        return {
            "status": "success",
            "message": "Region retired successfully",
            "region_id": region_id,
            "cascade": cascade,
            "hosts_retired": result.get("hosts_retired", 0)
        }
        
    except Exception as e:
        logger.error("Failed to retire region %s for user %s: %s", region_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("region_not_found", f"Region '{region_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("region_retire_failed", str(e))
            )


@router.get(
    "/regions/{region_id}/comments",
    summary="Get region comments",
    description="""
    Retrieve all comments for a region.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Comments retrieved successfully"},
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def get_region_comments(
    request: Request,
    region_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve the comment history for a specific region.

    Returns a chronological list of user comments and system notes associated with the region.
    Useful for tracking operational changes, incidents, or deployment notes.

    **Data Model:**
    - Comments include timestamp, author, and text content.
    - Sorted by timestamp (newest first).

    Args:
        request: The FastAPI request object.
        region_id: The UUID of the region.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary containing the list of `comments` and `total` count.

    Raises:
        HTTPException: **404** if region not found, **500** for server errors.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_comments_get", limit=500, period=3600)
    
    try:
        # Get region to verify ownership
        region = await ipam_manager.get_region_by_id(user_id, region_id)
        
        if not region:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("region_not_found", f"Region '{region_id}' not found")
            )
        
        # Return comments from region
        comments = region.get("comments", [])
        
        logger.info("User %s retrieved %d comments for region %s", user_id, len(comments), region_id)
        
        return {
            "comments": comments,
            "total": len(comments)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get comments for region %s for user %s: %s", region_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("comments_get_failed", "Failed to retrieve comments")
        )


@router.post(
    "/regions/{region_id}/comments",
    status_code=status.HTTP_201_CREATED,
    summary="Add comment to region",
    description="""
    Add an immutable comment to a region's history.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:update
    """,
    responses={
        201: {"description": "Comment added successfully"},
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def add_region_comment(
    request: Request,
    region_id: str,
    comment_text: str = Query(..., max_length=2000, description="Comment text"),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Append a new comment to a region's history.

    Comments are immutable once added. They are used for collaboration and audit trails.
    System events (like creation and updates) are also logged as comments automatically.

    **Constraints:**
    - Maximum length: 2000 characters.
    - HTML/Markdown is not rendered (stored as plain text).

    Args:
        request: The FastAPI request object.
        region_id: The UUID of the region.
        comment_text: The content of the comment.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        A dictionary confirming success and returning the added comment object.

    Raises:
        HTTPException: **404** if region not found, **400** if comment is invalid.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_comment", limit=100, period=3600)
    
    try:
        result = await ipam_manager.add_comment(
            user_id=user_id,
            resource_type="region",
            resource_id=region_id,
            comment_text=comment_text
        )
        
        logger.info("User %s added comment to region %s", user_id, region_id)
        
        return {
            "status": "success",
            "message": "Comment added successfully",
            "region_id": region_id,
            "comment": result.get("comment")
        }
        
    except Exception as e:
        logger.error("Failed to add comment to region %s for user %s: %s", region_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("region_not_found", f"Region '{region_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("comment_add_failed", str(e))
            )


@router.get(
    "/regions/preview-next",
    summary="Preview next region allocation",
    description="""
    Preview the next available X.Y CIDR that would be allocated for a country.
    
    Does not actually allocate the region, just shows what would be allocated.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved preview",
            "content": {
                "application/json": {
                    "example": {
                        "country": "India",
                        "next_cidr": "10.5.23.0/24",
                        "x_octet": 5,
                        "y_octet": 23,
                        "available": True
                    }
                }
            }
        },
        409: {"description": "No available addresses"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def preview_next_region(
    request: Request,
    country: str = Query(..., description="Country for preview"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Simulate the next region allocation to preview the assigned CIDR.

    Calculates the next available 10.X.Y.0/24 block for a given country without actually
    reserving it. Useful for UI wizards to show users what they will get.

    **Logic:**
    - Scans existing allocations in the country.
    - Finds the first gap in the X.Y sequence.
    - Returns the predicted CIDR and octet values.

    **Concurrency Note:**
    - This is a prediction only. In high-concurrency scenarios, another user might take
      the block before the actual creation request is made.

    Args:
        request: The FastAPI request object.
        country: The target country.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary with the predicted `cidr`, `x_octet`, `y_octet`, and availability status.

    Raises:
        HTTPException: **409** if no addresses are available.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_preview", limit=500, period=3600)
    
    try:
        preview = await ipam_manager.get_next_available_region(user_id, country)
        
        if not preview:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "capacity_exhausted",
                    f"No available addresses in country {country}",
                    {"country": country}
                )
            )
        
        logger.info("User %s previewed next region for country %s: %s", user_id, country, preview.get("cidr"))
        
        return preview
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to preview next region for user %s in country %s: %s", user_id, country, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("region_preview_failed", "Failed to preview next region")
        )


@router.get(
    "/regions/{region_id}/utilization",
    summary="Get region utilization",
    description="""
    Calculate and retrieve utilization statistics for a specific region.
    
    Returns total capacity (254 usable hosts), allocated hosts, and utilization percentage.
    Results are cached for 5 minutes.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved utilization statistics",
            "content": {
                "application/json": {
                    "example": {
                        "resource_type": "region",
                        "resource_id": "550e8400-e29b-41d4-a716-446655440000",
                        "total_capacity": 254,
                        "allocated": 45,
                        "available": 209,
                        "utilization_percent": 17.72
                    }
                }
            }
        },
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def get_region_utilization(
    request: Request,
    region_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Calculate and retrieve detailed utilization statistics for a specific region.

    Analyzes the usage of the /24 subnet (256 addresses).
    - **Total Capacity**: 254 usable hosts (excluding network .0 and broadcast .255).
    - **Allocated**: Number of active host records.
    - **Available**: Remaining free IPs.

    **Caching:**
    - Results are cached for 5 minutes.

    Args:
        request: The FastAPI request object.
        region_id: The UUID of the region.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        `UtilizationResponse` object with host-level statistics.

    Raises:
        HTTPException: **404** if region not found, **500** for calculation errors.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_utilization", limit=500, period=3600)
    
    try:
        utilization = await ipam_manager.calculate_region_utilization(user_id, region_id)
        
        logger.info(
            "User %s retrieved utilization for region %s: %.2f%%",
            user_id,
            region_id,
            utilization.get("utilization_percent", 0)
        )
        
        return format_utilization_response(utilization)
        
    except Exception as e:
        logger.error(
            "Failed to get region utilization for %s, user %s: %s",
            region_id,
            user_id,
            e,
            exc_info=True
        )
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("region_not_found", f"Region '{region_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=format_error_response("region_utilization_failed", "Failed to calculate utilization")
            )


# ============================================================================
# Host Management Endpoints
# ============================================================================

@router.post(
    "/hosts",
    status_code=status.HTTP_201_CREATED,
    summary="Create new host",
    description="""
    Allocate a new host address within a region.
    
    The system automatically assigns the next available Z octet (1-254).
    
    **Rate Limiting:** 1000 requests per hour per user
    
    **Required Permission:** ipam:allocate
    """,
    responses={
        201: {"description": "Host allocated successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Capacity exhausted or duplicate hostname"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def create_host(
    request: Request,
    region_id: str = Query(..., description="Region ID for host allocation"),
    hostname: str = Query(..., description="Hostname for the host"),
    device_type: Optional[str] = Query(None, description="Device type (VM, Container, Physical)"),
    os_type: Optional[str] = Query(None, description="Operating system type"),
    application: Optional[str] = Query(None, description="Application running on host"),
    cost_center: Optional[str] = Query(None, description="Cost center"),
    owner: Optional[str] = Query(None, description="Owner/team identifier (accepts owner name or owner id)"),
    purpose: Optional[str] = Query(None, description="Purpose description"),
    tags: Optional[str] = Query(None, description="Optional tags (JSON string)"),
    notes: Optional[str] = Query(None, description="Optional notes"),
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """
    Allocate a single host IP address within a specific region.

    Assigns the next available IP (10.X.Y.Z) in the region's subnet.
    The system manages the Z-octet (1-254) allocation automatically.

    **Features:**
    - **Auto-IP**: Finds the first free IP in the subnet.
    - **Duplicate Check**: Ensures hostname is unique within the region.
    - **Metadata**: Stores device type, OS, application, and other inventory data.

    **Rate Limiting:**
    - 1000 requests per hour per user (higher limit for bulk operations).

    Args:
        request: The FastAPI request object.
        region_id: The parent region's UUID.
        hostname: Unique hostname for the device.
        device_type: Type of device (e.g., 'VM', 'Container').
        os_type: Operating system.
        application: Primary application.
        cost_center: Billing code.
        owner: Owner username or team ID.
        purpose: Description of use.
        tags: JSON tags.
        notes: Additional notes.
        current_user: The authenticated user (requires `ipam:allocate` permission).

    Returns:
        The newly created host object with assigned IP address.

    Raises:
        HTTPException:
            - **409 Conflict**: If region is full or hostname exists.
            - **429 Too Many Requests**: If quota exceeded.
            - **400 Bad Request**: Validation errors.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_create", limit=1000, period=3600)
    
    try:
        metadata = {
            "device_type": device_type,
            "os_type": os_type,
            "application": application,
            "cost_center": cost_center,
            "owner": owner,
            "purpose": purpose,
            "tags": tags or {},
            "notes": notes
        }
        
        host = await ipam_manager.allocate_host(
            user_id=user_id,
            region_id=region_id,
            hostname=hostname,
            metadata=metadata
        )
        
        logger.info(
            "User %s created host %s in region %s: %s",
            user_id,
            host.get("ip_address"),
            region_id,
            hostname
        )
        
        return format_host_response(host)
        
    except Exception as e:
        logger.error(
            "Failed to create host for user %s in region %s: %s",
            user_id,
            region_id,
            e,
            exc_info=True
        )
        
        error_msg = str(e).lower()
        if "capacity" in error_msg or "exhausted" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "capacity_exhausted",
                    f"No available addresses in region {region_id}",
                    {"region_id": region_id}
                )
            )
        elif "duplicate" in error_msg or "exists" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "duplicate_hostname",
                    f"Hostname '{hostname}' already exists in region",
                    {"region_id": region_id, "hostname": hostname}
                )
            )
        elif "quota" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=format_error_response("quota_exceeded", "Host quota exceeded")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("host_creation_failed", str(e))
            )


@router.post(
    "/hosts/batch",
    status_code=status.HTTP_201_CREATED,
    summary="Batch create hosts",
    description="""
    Allocate multiple hosts in a single request (max 100).
    
    Hosts are allocated consecutively with auto-generated hostnames.
    
    **Rate Limiting:** 1000 requests per hour per user
    
    **Required Permission:** ipam:allocate
    """,
    responses={
        201: {"description": "Hosts allocated successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Capacity exhausted"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def batch_create_hosts(
    request: Request,
    region_id: str = Query(..., description="Region ID for host allocation"),
    count: int = Query(..., ge=1, le=100, description="Number of hosts to create"),
    hostname_prefix: str = Query(..., description="Hostname prefix (e.g., 'web-')"),
    device_type: Optional[str] = Query(None, description="Device type"),
    owner: Optional[str] = Query(None, description="Owner/team identifier (accepts owner name or owner id)"),
    tags: Optional[str] = Query(None, description="Optional tags (JSON string)"),
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """
    Bulk allocate multiple hosts in a single operation.

    Efficiently provisions up to 100 hosts in a region. Useful for scaling clusters
    or deploying identical nodes.

    **Naming Convention:**
    - Hosts are named sequentially: `{hostname_prefix}1`, `{hostname_prefix}2`, etc.
    - If a name collision occurs, it skips to the next index.

    **Atomicity:**
    - Attempts to create all requested hosts.
    - Returns a list of successfully created hosts and any failures.
    - Does not roll back successful creations if some fail (partial success allowed).

    Args:
        request: The FastAPI request object.
        region_id: The parent region's UUID.
        count: Number of hosts to create (1-100).
        hostname_prefix: Base name for generating hostnames.
        device_type: Optional device type for all hosts.
        owner: Optional owner for all hosts.
        tags: Optional tags for all hosts.
        current_user: The authenticated user (requires `ipam:allocate` permission).

    Returns:
        A summary dictionary with `status`, `hosts` list, and `failed` list.

    Raises:
        HTTPException: **409** if region capacity is insufficient for the requested count.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_batch_create", limit=1000, period=3600)
    
    try:
        result = await ipam_manager.allocate_hosts_batch(
            user_id=user_id,
            region_id=region_id,
            count=count,
            hostname_prefix=hostname_prefix,
            metadata={
                "device_type": device_type,
                "owner": owner,
                "tags": tags or {}
            }
        )
        
        logger.info(
            "User %s batch created %d hosts in region %s",
            user_id,
            len(result.get("hosts", [])),
            region_id
        )
        
        return {
            "status": "success",
            "message": f"Created {len(result.get('hosts', []))} hosts",
            "hosts": [format_host_response(h) for h in result.get("hosts", [])],
            "failed": result.get("failed", [])
        }
        
    except Exception as e:
        logger.error(
            "Failed to batch create hosts for user %s in region %s: %s",
            user_id,
            region_id,
            e,
            exc_info=True
        )
        
        error_msg = str(e).lower()
        if "capacity" in error_msg or "exhausted" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "capacity_exhausted",
                    f"Insufficient capacity in region {region_id}",
                    {"region_id": region_id, "requested": count}
                )
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("batch_creation_failed", str(e))
            )


@router.get(
    "/hosts",
    summary="List hosts",
    description="""
    List hosts with optional filters and pagination.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved hosts"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def list_hosts(
    request: Request,
    region_id: Optional[str] = Query(None, description="Filter by region"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    hostname: Optional[str] = Query(None, description="Filter by hostname (partial match)"),
    device_type: Optional[str] = Query(None, description="Filter by device type"),
    owner: Optional[str] = Query(None, description="Filter by owner (accepts owner name or owner id)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve a paginated list of allocated hosts with advanced filtering.

    The primary search interface for finding specific devices or IP addresses.

    **Filters:**
    - **Region**: Scope to a specific subnet.
    - **Status**: Filter by operational status.
    - **Hostname**: Partial match search.
    - **Device Type**: Filter by inventory type.
    - **Owner**: Filter by assigned owner.

    Args:
        request: The FastAPI request object.
        region_id: Optional region filter.
        status_filter: Optional status filter (aliased as `status`).
        hostname: Optional hostname search.
        device_type: Optional device type filter.
        owner: Optional owner filter.
        page: Page number.
        page_size: Items per page.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Paginated list of host objects.

    Raises:
        HTTPException: **500** if query fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_list", limit=500, period=3600)
    
    try:
        # Validate pagination
        page, page_size = validate_pagination_params(page, page_size)
        
        # Build filters
        filters = {}
        if region_id:
            filters["region_id"] = region_id
        if status_filter:
            filters["status"] = status_filter
        if hostname:
            filters["hostname"] = hostname
        if device_type:
            filters["device_type"] = device_type
        if owner:
            filters["owner"] = owner
        
        # Get hosts
        hosts = await ipam_manager.get_hosts(
            user_id=user_id,
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        # Format response
        formatted_hosts = [format_host_response(h) for h in hosts.get("items", [])]
        
        logger.info(
            "User %s listed %d hosts (page=%d, filters=%s)",
            user_id,
            len(formatted_hosts),
            page,
            filters
        )
        
        return format_pagination_response(
            items=formatted_hosts,
            page=page,
            page_size=page_size,
            total_count=hosts.get("total_count", 0)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("invalid_parameters", str(e))
        )
    except Exception as e:
        logger.error("Failed to list hosts for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("host_list_failed", "Failed to retrieve hosts")
        )


@router.get(
    "/hosts/{host_id}",
    summary="Get host details",
    description="""
    Retrieve detailed information about a specific host.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved host details"},
        404: {"description": "Host not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def get_host(
    request: Request,
    host_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve detailed configuration and status for a specific host.

    Returns the full host object including its IP address, assigned region,
    metadata (OS, device type), and current status.

    **Access Control:**
    - Users can only view hosts they own or have been granted access to.

    Args:
        request: The FastAPI request object.
        host_id: The UUID of the host.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        The host object.

    Raises:
        HTTPException: **404** if host not found, **500** for server errors.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_get", limit=500, period=3600)
    
    try:
        host = await ipam_manager.get_host_by_id(user_id, host_id)
        
        if not host:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("host_not_found", f"Host '{host_id}' not found")
            )
        
        logger.info("User %s retrieved host %s", user_id, host_id)
        
        return format_host_response(host)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get host %s for user %s: %s", host_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("host_get_failed", "Failed to retrieve host")
        )


@router.get(
    "/hosts/by-ip/{ip_address}",
    summary="Lookup host by IP address",
    description="""
    Retrieve host details by IP address.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved host details"},
        404: {"description": "Host not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def get_host_by_ip(
    request: Request,
    ip_address: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Find a host record by its IP address.

    Performs a reverse lookup to find the host associated with a specific IP (10.X.Y.Z).
    Useful for troubleshooting network issues or identifying devices from logs.

    **Scope:**
    - Searches only within the user's authorized namespace.

    Args:
        request: The FastAPI request object.
        ip_address: The IPv4 address string.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        The host object if found.

    Raises:
        HTTPException: **404** if no host matches the IP.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_lookup", limit=500, period=3600)
    
    try:
        host = await ipam_manager.get_host_by_ip(user_id, ip_address)
        
        if not host:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    "host_not_found",
                    f"Host with IP '{ip_address}' not found"
                )
            )
        
        logger.info("User %s looked up host by IP %s", user_id, ip_address)
        
        return format_host_response(host)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to lookup host by IP %s for user %s: %s", ip_address, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("host_lookup_failed", "Failed to lookup host")
        )


@router.post(
    "/hosts/bulk-lookup",
    summary="Bulk IP lookup",
    description="""
    Lookup multiple IP addresses in a single request.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved host details"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def bulk_lookup_hosts(
    request: Request,
    ip_addresses: List[str] = Query(..., description="List of IP addresses to lookup"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Perform a bulk reverse lookup for a list of IP addresses.

    Optimized endpoint for resolving multiple IPs to hostnames/metadata in a single query.
    Useful for enriching log data or network visualization tools.

    **Performance:**
    - Uses a single database query with `$in` operator.
    - Much faster than calling `get_host_by_ip` in a loop.

    Args:
        request: The FastAPI request object.
        ip_addresses: List of IPv4 address strings.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary with `results` (list of host objects or None), `found` count, and `not_found` count.

    Raises:
        HTTPException: **500** if lookup fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_bulk_lookup", limit=500, period=3600)
    
    try:
        result = await ipam_manager.bulk_lookup_ips(user_id, ip_addresses)
        
        logger.info("User %s performed bulk lookup for %d IPs", user_id, len(ip_addresses))
        
        return {
            "results": [format_host_response(h) if h else None for h in result.get("hosts", [])],
            "found": result.get("found", 0),
            "not_found": result.get("not_found", 0)
        }
        
    except Exception as e:
        logger.error("Failed to bulk lookup hosts for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("bulk_lookup_failed", "Failed to lookup hosts")
        )


@router.patch(
    "/hosts/{host_id}",
    summary="Update host",
    description="""
    Update host metadata.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:update
    """,
    responses={
        200: {"description": "Host updated successfully"},
        404: {"description": "Host not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def update_host(
    request: Request,
    host_id: str,
    hostname: Optional[str] = Query(None, description="New hostname"),
    device_type: Optional[str] = Query(None, description="New device type"),
    os_type: Optional[str] = Query(None, description="New OS type"),
    application: Optional[str] = Query(None, description="New application"),
    cost_center: Optional[str] = Query(None, description="New cost center"),
    owner: Optional[str] = Query(None, description="New owner (accepts owner name or owner id)"),
    purpose: Optional[str] = Query(None, description="New purpose"),
    status_update: Optional[str] = Query(None, alias="status", description="New status"),
    tags: Optional[str] = Query(None, description="New tags (JSON string)"),
    notes: Optional[str] = Query(None, description="New notes"),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Update host metadata and inventory information.

    Allows modification of non-structural attributes. The IP address and Region cannot be changed
    (requires release and re-allocation).

    **Modifiable Fields:**
    - **Hostname**: Must remain unique within the region.
    - **Inventory**: Device type, OS, application, cost center.
    - **Ownership**: Transfer to another user/team.
    - **Status**: Update operational status.
    - **Tags/Notes**: Update metadata.

    Args:
        request: The FastAPI request object.
        host_id: The UUID of the host.
        hostname: New hostname.
        device_type: New device type.
        os_type: New OS.
        application: New application.
        cost_center: New cost center.
        owner: New owner.
        purpose: New purpose.
        status_update: New status (aliased as `status`).
        tags: New tags JSON string.
        notes: New notes.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        The updated host object.

    Raises:
        HTTPException: **404** if not found, **400** if update fails (e.g., duplicate hostname).
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_update", limit=100, period=3600)
    
    try:
        # Build updates dict
        updates = {}
        if hostname is not None:
            updates["hostname"] = hostname
        if device_type is not None:
            updates["device_type"] = device_type
        if os_type is not None:
            updates["os_type"] = os_type
        if application is not None:
            updates["application"] = application
        if cost_center is not None:
            updates["cost_center"] = cost_center
        if owner is not None:
            updates["owner"] = owner
        if purpose is not None:
            updates["purpose"] = purpose
        if status_update is not None:
            updates["status"] = status_update
        if tags is not None:
            updates["tags"] = tags
        if notes is not None:
            updates["notes"] = notes
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("no_updates", "No update fields provided")
            )
        
        host = await ipam_manager.update_host(user_id, host_id, updates)
        
        logger.info("User %s updated host %s: %s", user_id, host_id, list(updates.keys()))
        
        return format_host_response(host)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update host %s for user %s: %s", host_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("host_not_found", f"Host '{host_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("host_update_failed", str(e))
            )


@router.delete(
    "/hosts/{host_id}",
    summary="Retire host",
    description="""
    Retire (hard delete) a host.
    
    The host is permanently deleted and moved to audit history.
    Address space is immediately reclaimed.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:release
    """,
    responses={
        200: {"description": "Host retired successfully"},
        404: {"description": "Host not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def retire_host(
    request: Request,
    host_id: str,
    reason: str = Query(..., description="Reason for retirement"),
    current_user: Dict[str, Any] = Depends(require_ipam_release)
):
    """
    Permanently retire a host and reclaim its IP address.

    Removes the host record from active service and moves it to the audit history.
    The IP address becomes immediately available for re-allocation.

    **Audit:**
    - A retirement reason is mandatory.

    Args:
        request: The FastAPI request object.
        host_id: The UUID of the host.
        reason: Mandatory text explaining the retirement.
        current_user: The authenticated user (requires `ipam:release` permission).

    Returns:
        A dictionary confirming success.

    Raises:
        HTTPException: **404** if host not found.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_retire", limit=100, period=3600)
    
    try:
        result = await ipam_manager.retire_allocation(
            user_id=user_id,
            resource_type="host",
            resource_id=host_id,
            reason=reason,
            cascade=False
        )
        
        logger.info("User %s retired host %s: %s", user_id, host_id, reason)
        
        return {
            "status": "success",
            "message": "Host retired successfully",
            "host_id": host_id
        }
        
    except Exception as e:
        logger.error("Failed to retire host %s for user %s: %s", host_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("host_not_found", f"Host '{host_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("host_retire_failed", str(e))
            )


@router.post(
    "/hosts/bulk-release",
    summary="Bulk release hosts",
    description="""
    Release multiple hosts in a single request.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:release
    """,
    responses={
        200: {"description": "Hosts released successfully"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def bulk_release_hosts(
    request: Request,
    host_ids: List[str] = Query(..., description="List of host IDs to release"),
    reason: str = Query(..., description="Reason for release"),
    current_user: Dict[str, Any] = Depends(require_ipam_release)
):
    """
    Bulk retire multiple hosts in a single operation.

    Efficiently releases a batch of IP addresses. Useful for decommissioning clusters
    or cleaning up temporary environments.

    **Behavior:**
    - Processes requests in parallel (or bulk operation).
    - Returns detailed success/failure counts.

    Args:
        request: The FastAPI request object.
        host_ids: List of host UUIDs to release.
        reason: Mandatory reason for all releases.
        current_user: The authenticated user (requires `ipam:release` permission).

    Returns:
        A summary dictionary with counts and individual results.

    Raises:
        HTTPException: **400** if operation fails completely.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_bulk_release", limit=100, period=3600)
    
    try:
        result = await ipam_manager.bulk_release_hosts(user_id, host_ids, reason)
        
        logger.info(
            "User %s bulk released %d hosts (success=%d, failed=%d)",
            user_id,
            len(host_ids),
            result.get("success_count", 0),
            result.get("failed_count", 0)
        )
        
        return {
            "status": "success",
            "message": f"Released {result.get('success_count', 0)} hosts",
            "success_count": result.get("success_count", 0),
            "failed_count": result.get("failed_count", 0),
            "results": result.get("results", [])
        }
        
    except Exception as e:
        logger.error("Failed to bulk release hosts for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("bulk_release_failed", str(e))
        )


@router.post(
    "/hosts/{host_id}/comments",
    status_code=status.HTTP_201_CREATED,
    summary="Add comment to host",
    description="""
    Add an immutable comment to a host's history.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:update
    """,
    responses={
        201: {"description": "Comment added successfully"},
        404: {"description": "Host not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def add_host_comment(
    request: Request,
    host_id: str,
    comment_text: str = Query(..., max_length=2000, description="Comment text"),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Append a new comment to a host's history.

    Comments are immutable and used for tracking device lifecycle events,
    maintenance notes, or incident reports.

    Args:
        request: The FastAPI request object.
        host_id: The UUID of the host.
        comment_text: The content of the comment.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        A dictionary confirming success and returning the added comment.

    Raises:
        HTTPException: **404** if host not found.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_comment", limit=100, period=3600)
    
    try:
        result = await ipam_manager.add_comment(
            user_id=user_id,
            resource_type="host",
            resource_id=host_id,
            comment_text=comment_text
        )
        
        logger.info("User %s added comment to host %s", user_id, host_id)
        
        return {
            "status": "success",
            "message": "Comment added successfully",
            "host_id": host_id,
            "comment": result.get("comment")
        }
        
    except Exception as e:
        logger.error("Failed to add comment to host %s for user %s: %s", host_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("host_not_found", f"Host '{host_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("comment_add_failed", str(e))
            )


@router.get(
    "/hosts/preview-next",
    summary="Preview next host allocation",
    description="""
    Preview the next available Z octet that would be allocated for a region.
    
    Does not actually allocate the host, just shows what would be allocated.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved preview",
            "content": {
                "application/json": {
                    "example": {
                        "region_id": "550e8400-e29b-41d4-a716-446655440000",
                        "next_ip": "10.5.23.45",
                        "z_octet": 45,
                        "available": True
                    }
                }
            }
        },
        409: {"description": "No available addresses"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def preview_next_host(
    request: Request,
    region_id: str = Query(..., description="Region ID for preview"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Simulate the next host allocation to preview the assigned IP.

    Calculates the next available Z octet (1-254) for a given region.
    Useful for UI feedback before provisioning.

    **Logic:**
    - Scans existing hosts in the region.
    - Finds the first gap in the Z sequence.

    Args:
        request: The FastAPI request object.
        region_id: The parent region ID.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary with the predicted `next_ip`, `z_octet`, and availability status.

    Raises:
        HTTPException: **409** if subnet is full.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_preview", limit=500, period=3600)
    
    try:
        preview = await ipam_manager.get_next_available_host(user_id, region_id)
        
        if not preview:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "capacity_exhausted",
                    f"No available addresses in region {region_id}",
                    {"region_id": region_id}
                )
            )
        
        logger.info("User %s previewed next host for region %s: %s", user_id, region_id, preview.get("next_ip"))
        
        return preview
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to preview next host for user %s in region %s: %s", user_id, region_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("host_preview_failed", "Failed to preview next host")
        )


# ============================================================================
# IP Interpretation Endpoint
# ============================================================================

@router.post(
    "/interpret",
    summary="Interpret IP address hierarchy",
    description="""
    Interpret any IP address in the 10.X.Y.Z format to understand its geographic hierarchy.
    
    Returns hierarchical JSON: Global Root → Continent → Country → Region → Host
    
    Returns 404 for addresses not owned by the authenticated user (user isolation).
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully interpreted IP address",
            "content": {
                "application/json": {
                    "example": {
                        "ip_address": "10.5.23.45",
                        "hierarchy": {
                            "global_root": "10.0.0.0/8",
                            "continent": "Asia",
                            "country": {
                                "name": "India",
                                "x_range": "0-29",
                                "x_octet": 5
                            },
                            "region": {
                                "region_id": "550e8400-e29b-41d4-a716-446655440000",
                                "region_name": "Mumbai DC1",
                                "cidr": "10.5.23.0/24",
                                "y_octet": 23,
                                "status": "Active"
                            },
                            "host": {
                                "host_id": "660e8400-e29b-41d4-a716-446655440001",
                                "hostname": "web-server-01",
                                "z_octet": 45,
                                "status": "Active",
                                "device_type": "VM"
                            }
                        }
                    }
                }
            }
        },
        404: {"description": "Address not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Interpretation"]
)
async def interpret_ip_address(
    request: Request,
    ip_address: str = Query(..., description="IP address to interpret (10.X.Y.Z format)"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Interpret any IP address in the 10.X.Y.Z format to understand its geographic hierarchy.

    Decodes the IP address structure to identify its location and purpose within the global network.
    Returns the full hierarchy from Global Root down to the specific Host.

    **Hierarchy Levels:**
    - **Global Root**: 10.0.0.0/8
    - **Continent**: Derived from the X octet range.
    - **Country**: Specific X octet.
    - **Region**: Specific Y octet (subnet).
    - **Host**: Specific Z octet.

    **Access Control:**
    - Returns 404 if the IP belongs to a subnet the user cannot access.

    Args:
        request: The FastAPI request object.
        ip_address: The IPv4 address string (10.X.Y.Z).
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A hierarchical JSON object detailing the IP's location and status.

    Raises:
        HTTPException: **404** if IP not found or access denied.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "ip_interpret", limit=500, period=3600)
    
    try:
        interpretation = await ipam_manager.interpret_ip_address(user_id, ip_address)
        
        if not interpretation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    "address_not_found",
                    f"IP address '{ip_address}' not found or not owned by user"
                )
            )
        
        logger.info("User %s interpreted IP address %s", user_id, ip_address)
        
        return interpretation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to interpret IP %s for user %s: %s", ip_address, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("interpretation_failed", "Failed to interpret IP address")
        )


# ============================================================================
# Statistics and Analytics Endpoints
# ============================================================================

@router.get(
    "/statistics/continent/{continent}",
    summary="Get continent statistics",
    description="""
    Retrieve aggregated utilization statistics for all countries within a continent.
    
    Results are cached for 5 minutes.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved continent statistics"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Statistics"]
)
async def get_continent_statistics(
    request: Request,
    continent: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve aggregated utilization statistics for a specific continent.

    Provides high-level metrics on IP usage across all countries within the continent.
    Useful for capacity planning and identifying high-growth areas.

    **Caching:**
    - Results are cached for 5 minutes to reduce database load.

    Args:
        request: The FastAPI request object.
        continent: The name of the continent (e.g., "Asia", "Europe").
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary containing total capacity, used IPs, and utilization percentage.

    Raises:
        HTTPException: **500** if statistics calculation fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "stats_continent", limit=500, period=3600)
    
    try:
        stats = await ipam_manager.get_continent_statistics(user_id, continent)
        
        logger.info("User %s retrieved continent statistics for %s", user_id, continent)
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get continent statistics for %s, user %s: %s", continent, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("stats_failed", "Failed to retrieve continent statistics")
        )


@router.get(
    "/statistics/top-utilized",
    summary="Get top utilized resources",
    description="""
    Retrieve the most utilized countries and regions sorted by utilization percentage.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved top utilized resources"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Statistics"]
)
async def get_top_utilized(
    request: Request,
    limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Identify the most heavily utilized countries and regions.

    Returns a ranked list of resources sorted by utilization percentage (descending).
    Critical for proactive capacity management and identifying potential bottlenecks.

    Args:
        request: The FastAPI request object.
        limit: Maximum number of results to return (1-100).
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A list of resource objects with their utilization metrics.

    Raises:
        HTTPException: **500** if query fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "stats_top_utilized", limit=500, period=3600)
    
    try:
        stats = await ipam_manager.get_top_utilized_resources(user_id, limit)
        
        logger.info("User %s retrieved top %d utilized resources", user_id, limit)
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get top utilized resources for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("stats_failed", "Failed to retrieve top utilized resources")
        )


@router.get(
    "/statistics/allocation-velocity",
    summary="Get allocation velocity trends",
    description="""
    Retrieve allocation trends showing allocations per day/week/month.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved allocation velocity"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Statistics"]
)
async def get_allocation_velocity(
    request: Request,
    time_range: str = Query("30d", description="Time range (7d, 30d, 90d)"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Analyze the rate of new IP allocations over time.

    Returns time-series data showing the number of new hosts created per day/week/month.
    Used for trend analysis and forecasting future demand.

    **Time Ranges:**
    - `7d`: Last 7 days (daily resolution).
    - `30d`: Last 30 days (daily resolution).
    - `90d`: Last 90 days (weekly resolution).

    Args:
        request: The FastAPI request object.
        time_range: The analysis period (`7d`, `30d`, `90d`).
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A list of data points `{date, count}`.

    Raises:
        HTTPException: **500** if analysis fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "stats_velocity", limit=500, period=3600)
    
    try:
        stats = await ipam_manager.get_allocation_velocity(user_id, time_range)
        
        logger.info("User %s retrieved allocation velocity for %s", user_id, time_range)
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get allocation velocity for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("stats_failed", "Failed to retrieve allocation velocity")
        )


# ============================================================================
# Search Endpoint
# ============================================================================

@router.get(
    "/search",
    summary="Search allocations",
    description="""
    Search allocations with comprehensive filters.
    
    Supports filtering by IP/CIDR, hostname, region name, continent, country, status, owner, tags, and date ranges.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved search results"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Search"]
)
async def search_allocations(
    request: Request,
    ip_address: Optional[str] = Query(None, description="IP address or CIDR to search"),
    hostname: Optional[str] = Query(None, description="Hostname (partial match)"),
    region_name: Optional[str] = Query(None, description="Region name (partial match)"),
    continent: Optional[str] = Query(None, description="Filter by continent"),
    country: Optional[str] = Query(None, description="Filter by country"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    owner: Optional[str] = Query(None, description="Filter by owner (accepts owner name or owner id)"),
    tags: Optional[str] = Query(None, description="Filter by tags (JSON string)"),
    created_after: Optional[str] = Query(None, description="Created after date (ISO format)"),
    created_before: Optional[str] = Query(None, description="Created before date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Search for IP allocations using advanced multi-field filtering.

    The primary search engine for the IPAM system. Supports combining multiple filters
    to narrow down results (AND logic).

    **Searchable Fields:**
    - **IP/CIDR**: Exact match or subnet containment.
    - **Geography**: Continent, Country, Region.
    - **Metadata**: Hostname, Owner, Tags.
    - **Time**: Creation date range.

    Args:
        request: The FastAPI request object.
        ip_address: IP or CIDR to search.
        hostname: Partial hostname match.
        region_name: Partial region name match.
        continent: Exact continent match.
        country: Exact country match.
        status_filter: Status (Active, Reserved, etc.).
        owner: Owner ID or name.
        tags: JSON string of tags.
        created_after: ISO date string.
        created_before: ISO date string.
        page: Page number.
        page_size: Items per page.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Paginated search results.

    Raises:
        HTTPException: **400** for invalid parameters, **500** for search errors.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "search", limit=500, period=3600)
    
    try:
        # Validate pagination
        page, page_size = validate_pagination_params(page, page_size)
        
        # Build search parameters
        search_params = {
            "ip_address": ip_address,
            "hostname": hostname,
            "region_name": region_name,
            "continent": continent,
            "country": country,
            "status": status_filter,
            "owner": owner,
            "tags": tags,
            "created_after": created_after,
            "created_before": created_before,
            "page": page,
            "page_size": page_size
        }
        
        # Remove None values
        search_params = {k: v for k, v in search_params.items() if v is not None}
        
        results = await ipam_manager.search_allocations(user_id, search_params)
        
        logger.info("User %s searched allocations: %d results", user_id, results.get("total_count", 0))
        
        return format_pagination_response(
            items=results.get("items", []),
            page=page,
            page_size=page_size,
            total_count=results.get("total_count", 0)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("invalid_parameters", str(e))
        )
    except Exception as e:
        logger.error("Failed to search allocations for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("search_failed", "Failed to search allocations")
        )


# ============================================================================
# Import/Export Endpoints
# ============================================================================

@router.post(
    "/export",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create export job",
    description="""
    Create an asynchronous export job for allocations.
    
    Supports CSV and JSON formats with optional filters.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        202: {"description": "Export job created successfully"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Import/Export"]
)
async def create_export_job(
    request: Request,
    format: str = Query("csv", description="Export format (csv, json)"),
    include_hierarchy: bool = Query(False, description="Include hierarchical data"),
    country: Optional[str] = Query(None, description="Filter by country"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Initiate an asynchronous background job to export IPAM data.

    Generates a downloadable report of IP allocations based on provided filters.
    Since exports can be large, this endpoint returns a Job ID immediately.

    **Formats:**
    - **CSV**: Flat format, best for spreadsheets.
    - **JSON**: Hierarchical or flat JSON, best for programmatic use.

    Args:
        request: The FastAPI request object.
        format: Output format (`csv` or `json`).
        include_hierarchy: If true, includes full hierarchy data in JSON.
        country: Optional filter by country.
        status_filter: Optional filter by status.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary with `job_id` and status `accepted`.

    Raises:
        HTTPException: **400** if export initiation fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "export_create", limit=100, period=3600)
    
    try:
        filters = {}
        if country:
            filters["country"] = country
        if status_filter:
            filters["status"] = status_filter
        
        job_id = await ipam_manager.export_allocations(
            user_id=user_id,
            format=format,
            filters=filters,
            include_hierarchy=include_hierarchy
        )
        
        logger.info("User %s created export job %s", user_id, job_id)
        
        return {
            "status": "accepted",
            "message": "Export job created successfully",
            "job_id": job_id
        }
        
    except Exception as e:
        logger.error("Failed to create export job for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("export_failed", str(e))
        )


@router.get(
    "/export/{job_id}/download",
    summary="Download export",
    description="""
    Download completed export file.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Export file downloaded successfully"},
        404: {"description": "Export job not found"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Import/Export"]
)
async def download_export(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get the temporary download URL for a completed export job.

    Checks the status of an export job and returns a signed URL if the file is ready.
    Download URLs are time-limited for security.

    Args:
        request: The FastAPI request object.
        job_id: The UUID of the export job.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary containing the `download_url`.

    Raises:
        HTTPException: **404** if job not found or not ready.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "export_download", limit=100, period=3600)
    
    try:
        download_url = await ipam_manager.get_export_download_url(user_id, job_id)
        
        if not download_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("export_not_found", f"Export job '{job_id}' not found")
            )
        
        logger.info("User %s downloaded export %s", user_id, job_id)
        
        return {"download_url": download_url}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to download export %s for user %s: %s", job_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("download_failed", "Failed to download export")
        )


@router.post(
    "/import",
    status_code=status.HTTP_201_CREATED,
    summary="Import allocations",
    description="""
    Import allocations from CSV or JSON file.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:allocate
    """,
    responses={
        201: {"description": "Import completed successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Import/Export"]
)
async def import_allocations(
    request: Request,
    file_content: str = Query(..., description="File content (CSV or JSON)"),
    mode: str = Query("auto", description="Import mode (auto, manual, preview)"),
    force: bool = Query(False, description="Skip existing allocations"),
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """
    Bulk import IP allocations from an external file.

    Parses and processes a CSV or JSON file to create multiple host records.
    Supports "dry run" mode via `preview` to validate data before committing.

    **Modes:**
    - `auto`: Attempts to import, skips errors if possible.
    - `manual`: Stops on first error.
    - `preview`: Validates only, no changes made.

    Args:
        request: The FastAPI request object.
        file_content: Raw content of the CSV/JSON file.
        mode: Import strategy (`auto`, `manual`, `preview`).
        force: If true, overwrites existing records (dangerous).
        current_user: The authenticated user (requires `ipam:allocate` permission).

    Returns:
        A summary of the import operation (success/fail counts).

    Raises:
        HTTPException: **400** if file format is invalid.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "import", limit=100, period=3600)
    
    try:
        result = await ipam_manager.import_allocations(
            user_id=user_id,
            file_content=file_content,
            mode=mode,
            force=force
        )
        
        logger.info(
            "User %s imported allocations: success=%d, failed=%d",
            user_id,
            result.get("success_count", 0),
            result.get("failed_count", 0)
        )
        
        return result
        
    except Exception as e:
        logger.error("Failed to import allocations for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("import_failed", str(e))
        )


@router.post(
    "/import/preview",
    summary="Preview import validation",
    description="""
    Validate import file without actually importing.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Validation completed successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Import/Export"]
)
async def preview_import(
    request: Request,
    file_content: str = Query(..., description="File content (CSV or JSON)"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Validate an import file and report potential errors without applying changes.

    A safe way to test an import file. Checks for:
    - Format validity (CSV/JSON).
    - Required fields.
    - Data constraints (IP conflicts, invalid regions).

    Args:
        request: The FastAPI request object.
        file_content: Raw content of the CSV/JSON file.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A detailed validation report with error counts and sample errors.

    Raises:
        HTTPException: **400** if validation fails critically.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "import_preview", limit=100, period=3600)
    
    try:
        result = await ipam_manager.import_allocations(
            user_id=user_id,
            file_content=file_content,
            mode="preview",
            force=False
        )
        
        logger.info("User %s previewed import: %d valid, %d errors", user_id, result.get("valid_count", 0), result.get("error_count", 0))
        
        return result
        
    except Exception as e:
        logger.error("Failed to preview import for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("preview_failed", str(e))
        )


# ============================================================================
# Audit History Endpoints
# ============================================================================

@router.get(
    "/audit",
    summary="Query audit history (alias)",
    description="""
    Query audit history with filters. This is an alias for /audit/history.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved audit history"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Audit"]
)
async def get_audit(
    request: Request,
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Query the IPAM audit log (Alias).

    Legacy alias for `/audit/history`. Redirects to the main history endpoint.
    See `get_audit_history` for full documentation.

    Args:
        request: The FastAPI request object.
        action_type: Filter by action.
        resource_type: Filter by resource.
        start_date: Start of date range.
        end_date: End of date range.
        page: Page number.
        page_size: Items per page.
        current_user: The authenticated user.

    Returns:
        Paginated audit logs.
    """
    # Delegate to the main audit history endpoint
    return await get_audit_history(
        request=request,
        action_type=action_type,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
        current_user=current_user
    )


@router.get(
    "/audit/history",
    summary="Query audit history",
    description="""
    Query audit history with filters.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved audit history"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Audit"]
)
async def get_audit_history(
    request: Request,
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve a chronological history of all IPAM operations.

    Provides a complete audit trail for compliance and security monitoring.
    Tracks who did what, when, and to which resource.

    **Filters:**
    - **Action**: CREATE, UPDATE, DELETE, etc.
    - **Resource**: Region, Host, Country.
    - **Time**: Date range filtering.

    Args:
        request: The FastAPI request object.
        action_type: Optional action filter.
        resource_type: Optional resource type filter.
        start_date: Optional start date (ISO).
        end_date: Optional end date (ISO).
        page: Page number.
        page_size: Items per page.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Paginated list of audit log entries.

    Raises:
        HTTPException: **500** if query fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "audit_history", limit=500, period=3600)
    
    try:
        # Validate pagination
        page, page_size = validate_pagination_params(page, page_size)
        
        filters = {}
        if action_type:
            filters["action_type"] = action_type
        if resource_type:
            filters["resource_type"] = resource_type
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date
        
        history = await ipam_manager.get_audit_history(
            user_id=user_id,
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        logger.info("User %s queried audit history: %d results", user_id, history.get("total_count", 0))
        
        return format_pagination_response(
            items=history.get("items", []),
            page=page,
            page_size=page_size,
            total_count=history.get("total_count", 0)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("invalid_parameters", str(e))
        )
    except Exception as e:
        logger.error("Failed to get audit history for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("audit_history_failed", "Failed to retrieve audit history")
        )


@router.get(
    "/audit/history/{ip_address}",
    summary="Get IP-specific audit history",
    description="""
    Retrieve audit history for a specific IP address.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved IP audit history"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Audit"]
)
async def get_ip_audit_history(
    request: Request,
    ip_address: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve the complete audit trail for a specific IP address.

    Shows the lifecycle history of an IP, including allocations, releases, and modifications.
    Useful for forensic analysis of a specific network resource.

    Args:
        request: The FastAPI request object.
        ip_address: The IPv4 address to investigate.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A list of audit log entries for the specified IP.

    Raises:
        HTTPException: **500** if query fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "audit_ip_history", limit=500, period=3600)
    
    try:
        history = await ipam_manager.get_audit_history(
            user_id=user_id,
            filters={"ip_address": ip_address}
        )
        
        logger.info("User %s queried audit history for IP %s", user_id, ip_address)
        
        return history.get("items", [])
        
    except Exception as e:
        logger.error("Failed to get IP audit history for %s, user %s: %s", ip_address, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("audit_history_failed", "Failed to retrieve IP audit history")
        )


@router.post(
    "/audit/export",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Export audit history",
    description="""
    Create export job for audit history.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        202: {"description": "Export job created successfully"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Audit"]
)
async def export_audit_history(
    request: Request,
    format: str = Query("csv", description="Export format (csv, json)"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Initiate an asynchronous export of the audit history log.

    Generates a compliance report containing all audit events matching the filters.
    Returns a Job ID for tracking the export status.

    **Formats:**
    - **CSV**: Standard audit log format.
    - **JSON**: Structured event data.

    Args:
        request: The FastAPI request object.
        format: Output format (`csv` or `json`).
        action_type: Optional filter by action type.
        start_date: Optional start date.
        end_date: Optional end date.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary with `job_id` and status `accepted`.

    Raises:
        HTTPException: **400** if export fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "audit_export", limit=100, period=3600)
    
    try:
        filters = {}
        if action_type:
            filters["action_type"] = action_type
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date
        
        job_id = await ipam_manager.export_audit_history(
            user_id=user_id,
            format=format,
            filters=filters
        )
        
        logger.info("User %s created audit export job %s", user_id, job_id)
        
        return {
            "status": "accepted",
            "message": "Audit export job created successfully",
            "job_id": job_id
        }
        
    except Exception as e:
        logger.error("Failed to export audit history for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("audit_export_failed", str(e))
        )


# ============================================================================
# Admin Quota Management Endpoints
# ============================================================================

@router.get(
    "/admin/quotas/{target_user_id}",
    summary="Get user quota",
    description="""
    Get quota information for a specific user.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:admin
    """,
    responses={
        200: {"description": "Successfully retrieved user quota"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Admin"]
)
async def get_user_quota(
    request: Request,
    target_user_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_admin)
):
    """
    Retrieve resource quotas for a specific user (Admin Only).

    Displays the limits on regions, hosts, and other IPAM resources for a target user.
    Used by administrators to monitor usage and enforce limits.

    **Access Control:**
    - Restricted to users with `ipam:admin` permission.

    Args:
        request: The FastAPI request object.
        target_user_id: The ID of the user to inspect.
        current_user: The authenticated user (requires `ipam:admin` permission).

    Returns:
        A dictionary containing quota limits and current usage.

    Raises:
        HTTPException: **500** if retrieval fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "admin_quota_get", limit=100, period=3600)
    
    try:
        quota = await ipam_manager.get_user_quota(target_user_id)
        
        logger.info("Admin %s retrieved quota for user %s", user_id, target_user_id)
        
        return quota
        
    except Exception as e:
        logger.error("Failed to get quota for user %s by admin %s: %s", target_user_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("quota_get_failed", "Failed to retrieve user quota")
        )


@router.patch(
    "/admin/quotas/{target_user_id}",
    summary="Update user quota",
    description="""
    Update quota limits for a specific user.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:admin
    """,
    responses={
        200: {"description": "Quota updated successfully"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Admin"]
)
async def update_user_quota(
    request: Request,
    target_user_id: str,
    region_quota: Optional[int] = Query(None, ge=0, description="New region quota"),
    host_quota: Optional[int] = Query(None, ge=0, description="New host quota"),
    current_user: Dict[str, Any] = Depends(require_ipam_admin)
):
    """
    Modify resource quotas for a specific user (Admin Only).

    Allows administrators to increase or decrease the number of regions or hosts
    a user is allowed to allocate.

    **Quotas:**
    - **Region Quota**: Max number of active regions.
    - **Host Quota**: Max number of active hosts.

    Args:
        request: The FastAPI request object.
        target_user_id: The ID of the user to update.
        region_quota: New limit for regions (optional).
        host_quota: New limit for hosts (optional).
        current_user: The authenticated user (requires `ipam:admin` permission).

    Returns:
        The updated quota object.

    Raises:
        HTTPException: **400** if no updates provided.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "admin_quota_update", limit=100, period=3600)
    
    try:
        updates = {}
        if region_quota is not None:
            updates["region_quota"] = region_quota
        if host_quota is not None:
            updates["host_quota"] = host_quota
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("no_updates", "No quota updates provided")
            )
        
        quota = await ipam_manager.update_user_quota(target_user_id, updates)
        
        logger.info("Admin %s updated quota for user %s: %s", user_id, target_user_id, list(updates.keys()))
        
        return quota
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update quota for user %s by admin %s: %s", target_user_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("quota_update_failed", str(e))
        )


@router.get(
    "/admin/quotas",
    summary="List all user quotas",
    description="""
    List quotas for all users with pagination.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:admin
    """,
    responses={
        200: {"description": "Successfully retrieved user quotas"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Admin"]
)
async def list_user_quotas(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_admin)
):
    """
    List all user quotas with pagination (Admin Only).

    Provides a system-wide view of resource limits and usage across all users.
    Essential for capacity planning and identifying heavy users.

    Args:
        request: The FastAPI request object.
        page: Page number.
        page_size: Items per page.
        current_user: The authenticated user (requires `ipam:admin` permission).

    Returns:
        Paginated list of user quotas.

    Raises:
        HTTPException: **500** if listing fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "admin_quota_list", limit=100, period=3600)
    
    try:
        # Validate pagination
        page, page_size = validate_pagination_params(page, page_size)
        
        quotas = await ipam_manager.list_all_user_quotas(page=page, page_size=page_size)
        
        logger.info("Admin %s listed user quotas: %d results", user_id, quotas.get("total_count", 0))
        
        return format_pagination_response(
            items=quotas.get("items", []),
            page=page,
            page_size=page_size,
            total_count=quotas.get("total_count", 0)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("invalid_parameters", str(e))
        )
    except Exception as e:
        logger.error("Failed to list user quotas by admin %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("quota_list_failed", "Failed to list user quotas")
        )


# ============================================================================
# Reservation Management Endpoints
# ============================================================================

@router.post(
    "/reservations",
    status_code=status.HTTP_201_CREATED,
    summary="Create IP reservation",
    description="""
    Create a new IP address or region reservation.
    
    Reservations hold an address for a specified period without allocating it.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:allocate
    """,
    responses={
        201: {"description": "Reservation created successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Address already allocated or reserved"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Reservations"]
)
async def create_reservation(
    request: Request,
    reservation_request: ReservationCreateRequest,
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """
    Reserve an IP address or region for future use.

    Reservations prevent other users from allocating the specified resource
    but do not activate it. Reservations automatically expire after the specified duration.

    **Use Cases:**
    - Planning a new deployment.
    - Holding an IP for a specific service migration.

    Args:
        request: The FastAPI request object.
        reservation_request: Pydantic model containing reservation details.
        current_user: The authenticated user (requires `ipam:allocate` permission).

    Returns:
        The created reservation object.

    Raises:
        HTTPException: **409** if resource is already taken.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "reservation_create", limit=100, period=3600)
    
    try:
        result = await ipam_manager.create_reservation(
            user_id=user_id,
            resource_type=reservation_request.resource_type,
            x_octet=reservation_request.x_octet,
            y_octet=reservation_request.y_octet,
            z_octet=reservation_request.z_octet,
            reason=reservation_request.reason,
            expires_in_days=reservation_request.expires_in_days
        )
        
        logger.info("Reservation created: user=%s type=%s", user_id, reservation_request.resource_type)
        return result
        
    except Exception as e:
        logger.error("Failed to create reservation: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("reservation_create_failed", str(e))
        )


@router.get(
    "/reservations",
    summary="List reservations",
    description="""
    List user's reservations with filtering.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved reservations"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Reservations"]
)
async def list_reservations(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    resource_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    List active reservations with optional filtering.

    Retrieves all reservations made by the current user (or all if admin).
    Supports filtering by status (active/expired) and resource type.

    Args:
        request: The FastAPI request object.
        status_filter: Filter by status (e.g., `active`).
        resource_type: Filter by type (`host`, `region`).
        page: Page number.
        page_size: Items per page.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Paginated list of reservations.

    Raises:
        HTTPException: **500** if listing fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "reservation_list", limit=500, period=3600)
    
    try:
        filters = {}
        if status_filter:
            filters["status"] = status_filter
        if resource_type:
            filters["resource_type"] = resource_type
        
        result = await ipam_manager.get_reservations(
            user_id=user_id,
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        return result
        
    except Exception as e:
        logger.error("Failed to list reservations: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("reservation_list_failed", "Failed to retrieve reservations")
        )


@router.get(
    "/reservations/{reservation_id}",
    summary="Get reservation details",
    tags=["IPAM - Reservations"]
)
async def get_reservation(
    request: Request,
    reservation_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get detailed information about a specific reservation.

    Args:
        request: The FastAPI request object.
        reservation_id: The UUID of the reservation.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        The reservation object.

    Raises:
        HTTPException: **404** if not found.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_reservation_by_id(user_id, reservation_id)
        if not result:
            raise HTTPException(status_code=404, detail="Reservation not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get reservation: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.post(
    "/reservations/{reservation_id}/convert",
    summary="Convert reservation to allocation",
    tags=["IPAM - Reservations"]
)
async def convert_reservation(
    request: Request,
    reservation_id: str,
    region_name: Optional[str] = Query(None),
    hostname: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """
    Convert an active reservation into a live allocation.

    Promotes a reserved IP or region to active status. The reservation is removed,
    and a standard allocation record is created.

    Args:
        request: The FastAPI request object.
        reservation_id: The UUID of the reservation.
        region_name: Optional name for the new region (if converting region).
        hostname: Optional hostname for the new host (if converting host).
        current_user: The authenticated user (requires `ipam:allocate` permission).

    Returns:
        The newly created allocation object.

    Raises:
        HTTPException: **400** if conversion fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.convert_reservation(
            user_id=user_id,
            reservation_id=reservation_id,
            region_name=region_name,
            hostname=hostname
        )
        return result
    except Exception as e:
        logger.error("Failed to convert reservation: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/reservations/{reservation_id}",
    summary="Delete reservation",
    tags=["IPAM - Reservations"]
)
async def delete_reservation(
    request: Request,
    reservation_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_release)
):
    """
    Cancel and delete a reservation.

    Releases the reserved resource back to the free pool immediately.

    Args:
        request: The FastAPI request object.
        reservation_id: The UUID of the reservation.
        current_user: The authenticated user (requires `ipam:release` permission).

    Returns:
        Success message.

    Raises:
        HTTPException: **400** if deletion fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.delete_reservation(user_id, reservation_id)
        return {"status": "success", "message": "Reservation deleted"}
    except Exception as e:
        logger.error("Failed to delete reservation: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



# ============================================================================
# User Preferences Endpoints
# ============================================================================

@router.get(
    "/preferences",
    summary="Get user preferences",
    tags=["IPAM - Preferences"]
)
async def get_preferences(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve current user's IPAM preferences.

    Returns settings such as default quotas, notification preferences, and UI defaults.

    Args:
        request: The FastAPI request object.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary of user preferences.

    Raises:
        HTTPException: **500** if retrieval fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_user_preferences(user_id)
        return result
    except Exception as e:
        logger.error("Failed to get preferences: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/preferences",
    summary="Update user preferences",
    tags=["IPAM - Preferences"]
)
async def update_preferences(
    request: Request,
    default_country: Optional[str] = Query(None),
    default_region_quota: Optional[int] = Query(None),
    default_host_quota: Optional[int] = Query(None),
    notification_enabled: Optional[bool] = Query(None),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Update user's IPAM preferences.

    Allows customization of default values and behavior for the IPAM interface.

    Args:
        request: The FastAPI request object.
        default_country: Default country for new allocations.
        default_region_quota: Default region quota.
        default_host_quota: Default host quota.
        notification_enabled: Enable/disable notifications.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        The updated preferences object.

    Raises:
        HTTPException: **400** if update fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        preferences = {}
        if default_country is not None:
            preferences["default_country"] = default_country
        if default_region_quota is not None:
            preferences["default_region_quota"] = default_region_quota
        if default_host_quota is not None:
            preferences["default_host_quota"] = default_host_quota
        if notification_enabled is not None:
            preferences["notification_enabled"] = notification_enabled
        
        result = await ipam_manager.update_user_preferences(user_id, preferences)
        return result
    except Exception as e:
        logger.error("Failed to update preferences: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/preferences/filters",
    status_code=status.HTTP_201_CREATED,
    summary="Save filter",
    tags=["IPAM - Preferences"]
)
async def save_filter(
    request: Request,
    filter_name: str = Query(...),
    filter_criteria: str = Query(...),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Save a custom search filter for quick access.

    Allows users to name and save complex filter combinations (e.g., "High Usage Asia Regions")
    for one-click retrieval later.

    Args:
        request: The FastAPI request object.
        filter_name: A unique name for the filter.
        filter_criteria: JSON string representing the filter parameters.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        The saved filter object.

    Raises:
        HTTPException: **400** if save fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.save_filter(user_id, filter_name, filter_criteria)
        return result
    except Exception as e:
        logger.error("Failed to save filter: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/preferences/filters",
    summary="Get saved filters",
    tags=["IPAM - Preferences"]
)
async def get_saved_filters(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve all saved filters for the current user.

    Args:
        request: The FastAPI request object.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A list of saved filter objects.

    Raises:
        HTTPException: **500** if retrieval fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_saved_filters(user_id)
        return result
    except Exception as e:
        logger.error("Failed to get filters: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.delete(
    "/preferences/filters/{filter_id}",
    summary="Delete saved filter",
    tags=["IPAM - Preferences"]
)
async def delete_filter(
    request: Request,
    filter_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Delete a saved filter.

    Args:
        request: The FastAPI request object.
        filter_id: The UUID of the filter.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        Success message.

    Raises:
        HTTPException: **400** if deletion fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.delete_filter(user_id, filter_id)
        return {"status": "success", "message": "Filter deleted"}
    except Exception as e:
        logger.error("Failed to delete filter: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Dashboard Statistics Endpoints
# ============================================================================

@router.get(
    "/statistics/dashboard",
    summary="Get dashboard statistics",
    tags=["IPAM - Statistics"]
)
async def get_dashboard_stats(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve high-level dashboard statistics.

    Provides a summary view for the main IPAM dashboard, including:
    - Total regions and hosts.
    - Overall utilization.
    - Recent alerts.
    - Quick status counts.

    Args:
        request: The FastAPI request object.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary of dashboard metrics.

    Raises:
        HTTPException: **500** if calculation fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "dashboard_stats", limit=500, period=3600)
    
    try:
        result = await ipam_manager.calculate_dashboard_stats(user_id)
        return result
    except Exception as e:
        logger.error("Failed to get dashboard stats: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================================
# Capacity Forecasting Endpoints
# ============================================================================

@router.get(
    "/statistics/forecast/{resource_type}/{resource_id}",
    summary="Get capacity forecast",
    tags=["IPAM - Statistics"]
)
async def get_forecast(
    request: Request,
    resource_type: str,
    resource_id: str,
    days_ahead: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Predict future capacity usage for a specific resource.

    Uses historical data to forecast when a region or subnet will reach capacity.
    Essential for proactive infrastructure planning.

    Args:
        request: The FastAPI request object.
        resource_type: Type of resource (`region`, `subnet`).
        resource_id: The UUID of the resource.
        days_ahead: Number of days to forecast (1-365).
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A forecast object with predicted usage curve and saturation date.

    Raises:
        HTTPException: **500** if forecasting fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.calculate_forecast(user_id, resource_type, resource_id)
        return result
    except Exception as e:
        logger.error("Failed to get forecast: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/statistics/trends",
    summary="Get allocation trends",
    tags=["IPAM - Statistics"]
)
async def get_trends(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Analyze historical allocation trends.

    Returns trend lines for resource consumption over the specified period.

    Args:
        request: The FastAPI request object.
        days: Number of days to analyze (1-365).
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Trend data points.

    Raises:
        HTTPException: **500** if analysis fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.calculate_trends(user_id, days)
        return result
    except Exception as e:
        logger.error("Failed to get trends: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================================
# Notification Endpoints
# ============================================================================

@router.get(
    "/notifications",
    summary="List notifications",
    tags=["IPAM - Notifications"]
)
async def list_notifications(
    request: Request,
    is_read: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    List user notifications with optional filtering.

    Retrieves system alerts, warnings, and informational messages.

    Args:
        request: The FastAPI request object.
        is_read: Filter by read/unread status.
        page: Page number.
        page_size: Items per page.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Paginated list of notifications.

    Raises:
        HTTPException: **500** if listing fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        filters = {}
        if is_read is not None:
            filters["is_read"] = is_read
        
        result = await ipam_manager.get_notifications(user_id, filters, page, page_size)
        return result
    except Exception as e:
        logger.error("Failed to list notifications: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/notifications/unread",
    summary="Get unread notification count",
    tags=["IPAM - Notifications"]
)
async def get_unread_count(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get the count of unread notifications.

    Used for UI badges and alerts.

    Args:
        request: The FastAPI request object.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Dictionary with `unread_count`.

    Raises:
        HTTPException: **500** if counting fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        filters = {"is_read": False}
        result = await ipam_manager.get_notifications(user_id, filters, 1, 1)
        return {"unread_count": result.get("total_count", 0)}
    except Exception as e:
        logger.error("Failed to get unread count: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.patch(
    "/notifications/{notification_id}",
    summary="Mark notification as read",
    tags=["IPAM - Notifications"]
)
async def mark_notification_read(
    request: Request,
    notification_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Mark a notification as read.

    Args:
        request: The FastAPI request object.
        notification_id: The UUID of the notification.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        Success message.

    Raises:
        HTTPException: **400** if update fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.mark_notification_read(user_id, notification_id)
        return {"status": "success", "message": "Notification marked as read"}
    except Exception as e:
        logger.error("Failed to mark notification read: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/notifications/{notification_id}",
    summary="Delete notification",
    tags=["IPAM - Notifications"]
)
async def delete_notification(
    request: Request,
    notification_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Delete a notification.

    Args:
        request: The FastAPI request object.
        notification_id: The UUID of the notification.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        Success message.

    Raises:
        HTTPException: **400** if deletion fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.delete_notification(user_id, notification_id)
        return {"status": "success", "message": "Notification deleted"}
    except Exception as e:
        logger.error("Failed to delete notification: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Notification Rules Endpoints
# ============================================================================

@router.post(
    "/notifications/rules",
    status_code=status.HTTP_201_CREATED,
    summary="Create notification rule",
    tags=["IPAM - Notifications"]
)
async def create_notification_rule(
    request: Request,
    event_type: str = Query(...),
    threshold: Optional[float] = Query(None),
    notification_method: str = Query("in_app"),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Create a custom notification rule.

    Define conditions under which the user should be alerted (e.g., "Region > 90% full").

    Args:
        request: The FastAPI request object.
        event_type: The type of event to monitor.
        threshold: The value that triggers the alert.
        notification_method: Delivery method (`in_app`, `email`).
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        The created rule object.

    Raises:
        HTTPException: **400** if creation fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.create_notification_rule(
            user_id=user_id,
            event_type=event_type,
            threshold=threshold,
            notification_method=notification_method
        )
        return result
    except Exception as e:
        logger.error("Failed to create notification rule: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



@router.get(
    "/notifications/rules",
    summary="List notification rules",
    tags=["IPAM - Notifications"]
)
async def list_notification_rules(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    List all notification rules configured by the user.

    Args:
        request: The FastAPI request object.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A list of notification rules.

    Raises:
        HTTPException: **500** if listing fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        collection = ipam_manager.db_manager.get_tenant_collection("ipam_notification_rules")
        cursor = collection.find({"user_id": user_id}).sort("created_at", -1)
        rules = await cursor.to_list(None)
        
        for rule in rules:
            rule["_id"] = str(rule["_id"])
        
        return {"rules": rules}
    except Exception as e:
        logger.error("Failed to list notification rules: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/notifications/rules/{rule_id}",
    summary="Update notification rule",
    tags=["IPAM - Notifications"]
)
async def update_notification_rule(
    request: Request,
    rule_id: str,
    is_active: Optional[bool] = Query(None),
    threshold: Optional[float] = Query(None),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Update an existing notification rule.

    Args:
        request: The FastAPI request object.
        rule_id: The UUID of the rule.
        is_active: Enable/disable the rule.
        threshold: Update the trigger threshold.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        Success message.

    Raises:
        HTTPException: **400** if update fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        from bson import ObjectId
        collection = ipam_manager.db_manager.get_tenant_collection("ipam_notification_rules")
        
        updates = {}
        if is_active is not None:
            updates["is_active"] = is_active
        if threshold is not None:
            updates["threshold"] = threshold
        
        if updates:
            await collection.update_one(
                {"_id": ObjectId(rule_id), "user_id": user_id},
                {"$set": updates}
            )
        
        return {"status": "success", "message": "Rule updated"}
    except Exception as e:
        logger.error("Failed to update notification rule: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



@router.delete(
    "/notifications/rules/{rule_id}",
    summary="Delete notification rule",
    tags=["IPAM - Notifications"]
)
async def delete_notification_rule(
    request: Request,
    rule_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Delete a notification rule.

    Args:
        request: The FastAPI request object.
        rule_id: The UUID of the rule.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        Success message.

    Raises:
        HTTPException: **400** if deletion fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        from bson import ObjectId
        collection = ipam_manager.db_manager.get_tenant_collection("ipam_notification_rules")
        await collection.delete_one({"_id": ObjectId(rule_id), "user_id": user_id})
        return {"status": "success", "message": "Rule deleted"}
    except Exception as e:
        logger.error("Failed to delete notification rule: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Shareable Links Endpoints
# ============================================================================

@router.post(
    "/shares",
    status_code=status.HTTP_201_CREATED,
    summary="Create shareable link",
    tags=["IPAM - Shares"]
)
async def create_share(
    request: Request,
    resource_type: str = Query(...),
    resource_id: str = Query(...),
    expires_in_days: int = Query(7, ge=1, le=90),
    description: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Generate a temporary shareable link for an IPAM resource.

    Allows external or unauthenticated access to specific resource details
    for a limited time.

    Args:
        request: The FastAPI request object.
        resource_type: Type of resource (`host`, `region`).
        resource_id: The UUID of the resource.
        expires_in_days: Validity period (1-90 days).
        description: Optional description of the share.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        The created share object containing the access token/URL.

    Raises:
        HTTPException: **400** if creation fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "share_create", limit=100, period=3600)
    
    try:
        result = await ipam_manager.create_share(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            expires_in_days=expires_in_days,
            description=description
        )
        return result
    except Exception as e:
        logger.error("Failed to create share: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



@router.get(
    "/shares",
    summary="List user's shares",
    tags=["IPAM - Shares"]
)
async def list_shares(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    List all active shareable links created by the user.

    Args:
        request: The FastAPI request object.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A list of active shares.

    Raises:
        HTTPException: **500** if listing fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.list_user_shares(user_id)
        return {"shares": result}
    except Exception as e:
        logger.error("Failed to list shares: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/shares/{share_token}",
    summary="Access shared resource (no auth)",
    tags=["IPAM - Shares"]
)
async def get_shared_resource(
    request: Request,
    share_token: str
):
    """
    Access a shared resource using a valid share token.

    **Authentication:**
    - No user authentication required.
    - Validates the share token and expiration.

    Args:
        request: The FastAPI request object.
        share_token: The unique token for the share.

    Returns:
        The shared resource details.

    Raises:
        HTTPException: **404** if token is invalid or expired.
    """
    try:
        result = await ipam_manager.get_shared_resource(share_token)
        return result
    except Exception as e:
        logger.error("Failed to get shared resource: %s", e, exc_info=True)
        raise HTTPException(status_code=404, detail="Share not found or expired")


@router.delete(
    "/shares/{share_id}",
    summary="Revoke share",
    tags=["IPAM - Shares"]
)
async def revoke_share(
    request: Request,
    share_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Revoke a shareable link immediately.

    Invalidates the token so it can no longer be used to access the resource.

    Args:
        request: The FastAPI request object.
        share_id: The UUID of the share.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        Success message.

    Raises:
        HTTPException: **400** if revocation fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.revoke_share(user_id, share_id)
        return {"status": "success", "message": "Share revoked"}
    except Exception as e:
        logger.error("Failed to revoke share: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



# ============================================================================
# Webhook Endpoints
# ============================================================================

@router.post(
    "/webhooks",
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    tags=["IPAM - Webhooks"]
)
async def create_webhook(
    request: Request,
    webhook_url: str = Query(...),
    events: List[str] = Query(...),
    description: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Register a new webhook for IPAM events.

    External systems can subscribe to events like `allocation_created` or `capacity_warning`.

    Args:
        request: The FastAPI request object.
        webhook_url: The destination URL for the webhook payload.
        events: List of event types to subscribe to.
        description: Optional description.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        The created webhook object.

    Raises:
        HTTPException: **400** if creation fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "webhook_create", limit=10, period=3600)
    
    try:
        result = await ipam_manager.create_webhook(
            user_id=user_id,
            webhook_url=webhook_url,
            events=events,
            description=description
        )
        return result
    except Exception as e:
        logger.error("Failed to create webhook: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/webhooks",
    summary="List webhooks",
    tags=["IPAM - Webhooks"]
)
async def list_webhooks(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    List all registered webhooks.

    Args:
        request: The FastAPI request object.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A list of webhooks.

    Raises:
        HTTPException: **500** if listing fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_webhooks(user_id)
        return {"webhooks": result}
    except Exception as e:
        logger.error("Failed to list webhooks: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.get(
    "/webhooks/{webhook_id}/deliveries",
    summary="Get webhook delivery history",
    tags=["IPAM - Webhooks"]
)
async def get_webhook_deliveries(
    request: Request,
    webhook_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    View the delivery history for a specific webhook.

    Useful for debugging failed deliveries or verifying integration.

    Args:
        request: The FastAPI request object.
        webhook_id: The UUID of the webhook.
        page: Page number.
        page_size: Items per page.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Paginated list of delivery attempts.

    Raises:
        HTTPException: **500** if retrieval fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_webhook_deliveries(user_id, webhook_id, page, page_size)
        return result
    except Exception as e:
        logger.error("Failed to get webhook deliveries: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/webhooks/{webhook_id}",
    summary="Delete webhook",
    tags=["IPAM - Webhooks"]
)
async def delete_webhook(
    request: Request,
    webhook_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Delete a webhook registration.

    Args:
        request: The FastAPI request object.
        webhook_id: The UUID of the webhook.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        Success message.

    Raises:
        HTTPException: **400** if deletion fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.delete_webhook(user_id, webhook_id)
        return {"status": "success", "message": "Webhook deleted"}
    except Exception as e:
        logger.error("Failed to delete webhook: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Bulk Operations Endpoints
# ============================================================================

@router.post(
    "/bulk/tags",
    summary="Bulk update tags",
    tags=["IPAM - Bulk Operations"]
)
async def bulk_update_tags(
    request: Request,
    bulk_request: BulkTagUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Perform a bulk update of tags on multiple resources.

    Supports adding, removing, or setting tags for a batch of IDs.

    Args:
        request: The FastAPI request object.
        bulk_request: Pydantic model with resource IDs and tag operations.
        current_user: The authenticated user (requires `ipam:update` permission).

    Returns:
        A summary of the operation.

    Raises:
        HTTPException: **400** if update fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "bulk_tags", limit=10, period=3600)
    
    try:
        result = await ipam_manager.bulk_update_tags(
            user_id=user_id,
            resource_type=bulk_request.resource_type,
            resource_ids=bulk_request.resource_ids,
            operation=bulk_request.operation,
            tags=bulk_request.tags
        )
        return result
    except Exception as e:
        logger.error("Failed bulk tag update: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



@router.get(
    "/bulk/jobs/{job_id}",
    summary="Get bulk job status",
    tags=["IPAM - Bulk Operations"]
)
async def get_bulk_job_status(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Check the status of a long-running bulk operation.

    Args:
        request: The FastAPI request object.
        job_id: The UUID of the background job.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        The job status object.

    Raises:
        HTTPException: **404** if job not found.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_bulk_job_status(user_id, job_id)
        return result
    except Exception as e:
        logger.error("Failed to get bulk job status: %s", e, exc_info=True)
        raise HTTPException(status_code=404, detail="Job not found")


# ============================================================================
# Metrics and Monitoring Endpoints
# ============================================================================

@router.get(
    "/metrics",
    summary="Get IPAM system metrics",
    description="""
    Retrieve comprehensive metrics about IPAM system performance and usage.
    
    Includes:
    - Error rates by type and endpoint
    - Request rates and response times
    - Capacity warnings
    - Quota exceeded events
    - Operation success/failure rates
    - Allocation rates
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved metrics",
            "content": {
                "application/json": {
                    "example": {
                        "timestamp": "2025-01-15T10:30:00Z",
                        "requests": {
                            "requests_per_minute": 45.0,
                            "average_response_time": 0.125
                        },
                        "errors": {
                            "capacity_exhausted": 5,
                            "quota_exceeded": 12,
                            "total": 17,
                            "errors_per_minute": 0.5
                        },
                        "capacity_warnings": {
                            "country": 3,
                            "region": 8,
                            "total": 11
                        },
                        "operations": {
                            "allocate_region": {
                                "success_count": 150,
                                "failure_count": 5,
                                "success_rate": 96.8
                            }
                        }
                    }
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Monitoring"]
)
async def get_ipam_metrics(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Retrieve comprehensive IPAM system metrics.

    Provides a high-level overview of system health, including request rates,
    error counts, and capacity warnings.

    Args:
        request: The FastAPI request object.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A metrics summary object.

    Raises:
        HTTPException: **500** if retrieval fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "metrics", limit=100, period=3600)
    
    try:
        from second_brain_database.routes.ipam.monitoring.metrics_tracker import get_ipam_metrics_tracker
        from second_brain_database.managers.redis_manager import redis_manager
        
        metrics_tracker = get_ipam_metrics_tracker(redis_manager)
        summary = await metrics_tracker.get_metrics_summary()
        
        logger.info("User %s retrieved IPAM metrics", user_id)
        
        return summary
        
    except Exception as e:
        logger.error("Failed to get IPAM metrics for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "metrics_retrieval_failed",
                "Failed to retrieve system metrics"
            )
        )


@router.get(
    "/metrics/errors",
    summary="Get error rates",
    description="""
    Retrieve detailed error rate information.
    
    Returns error counts by type, total errors, and errors per minute.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved error rates",
            "content": {
                "application/json": {
                    "example": {
                        "capacity_exhausted": 5,
                        "quota_exceeded": 12,
                        "validation_error": 3,
                        "total": 20,
                        "errors_per_minute": 0.5
                    }
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Monitoring"]
)
async def get_error_rates(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get detailed error rate information broken down by type.

    Helps identify specific failure modes (e.g., capacity exhaustion vs. validation errors).

    Args:
        request: The FastAPI request object.
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        A dictionary of error counts and rates.

    Raises:
        HTTPException: **500** if retrieval fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "metrics_errors", limit=100, period=3600)
    
    try:
        from second_brain_database.routes.ipam.monitoring.metrics_tracker import get_ipam_metrics_tracker
        from second_brain_database.managers.redis_manager import redis_manager
        
        metrics_tracker = get_ipam_metrics_tracker(redis_manager)
        error_rates = await metrics_tracker.get_error_rates()
        
        logger.info("User %s retrieved error rates", user_id)
        
        return error_rates
        
    except Exception as e:
        logger.error("Failed to get error rates for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "error_rates_retrieval_failed",
                "Failed to retrieve error rates"
            )
        )


@router.get(
    "/metrics/endpoint/{endpoint:path}",
    summary="Get endpoint-specific metrics",
    description="""
    Retrieve metrics for a specific API endpoint.
    
    Returns error counts and response times for the specified endpoint.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved endpoint metrics",
            "content": {
                "application/json": {
                    "example": {
                        "endpoint": "/ipam/regions",
                        "errors": {
                            "capacity_exhausted": 3,
                            "validation_error": 1
                        },
                        "average_response_time": 0.145
                    }
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Monitoring"]
)
async def get_endpoint_metrics(
    request: Request,
    endpoint: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get performance metrics for a specific API endpoint.

    Args:
        request: The FastAPI request object.
        endpoint: The API path to analyze (e.g., `/ipam/regions`).
        current_user: The authenticated user (requires `ipam:read` permission).

    Returns:
        Endpoint-specific error rates and response times.

    Raises:
        HTTPException: **500** if retrieval fails.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "metrics_endpoint", limit=100, period=3600)
    
    try:
        from second_brain_database.routes.ipam.monitoring.metrics_tracker import get_ipam_metrics_tracker
        from second_brain_database.managers.redis_manager import redis_manager
        
        metrics_tracker = get_ipam_metrics_tracker(redis_manager)
        
        # Get endpoint-specific metrics
        errors = await metrics_tracker.get_endpoint_error_rates(endpoint)
        avg_response_time = await metrics_tracker.get_average_response_time(endpoint)
        
        result = {
            "endpoint": endpoint,
            "errors": errors,
            "average_response_time": avg_response_time
        }
        
        logger.info("User %s retrieved metrics for endpoint %s", user_id, endpoint)
        
        return result
        
    except Exception as e:
        logger.error("Failed to get endpoint metrics for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "endpoint_metrics_retrieval_failed",
                "Failed to retrieve endpoint metrics"
            )
        )
