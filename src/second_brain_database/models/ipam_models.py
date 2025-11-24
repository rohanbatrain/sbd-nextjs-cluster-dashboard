"""
# IP Address Management (IPAM) Models

This module defines the **core data structures** for the IPAM system, managing the hierarchical
allocation of IP addresses across continents, countries, regions, and hosts. It enforces strict
validation rules for IP formats, hostname conventions, and quota limits.

## Domain Model Overview

The IPAM system uses a geographic hierarchy for IP allocation:

1.  **Continent**: Top-level grouping (e.g., North America).
2.  **Country**: Second-level grouping (e.g., USA). Mapped to specific X-octet ranges.
3.  **Region**: User-defined logical grouping (e.g., "US-East-Prod"). Assigned a unique Y-octet.
4.  **Host**: Individual device (e.g., "web-server-01"). Assigned a unique Z-octet (1-254).

## Key Features

### 1. Hierarchical Addressing
- **Structure**: `10.X.Y.Z` (Private Class A network).
- **X-Octet**: Country code (mapped via `ContinentCountryMapping`).
- **Y-Octet**: Region ID (unique per user/country).
- **Z-Octet**: Host ID (unique per region).

### 2. Validation Rules
- **Hostnames**: RFC 1123 compliant (alphanumeric, hyphens, dots).
- **Tags**: Key-value pairs for flexible resource organization.
- **Quotas**: Limits on the number of regions and hosts per user.

### 3. Audit & History
- **Audit Trails**: Full history of changes for every resource (`AuditHistoryEntry`).
- **Snapshots**: State capture at the time of modification.

## Usage Examples

### Creating a Region

```python
region = RegionCreateRequest(
    country="USA",
    region_name="production-cluster",
    description="Main production environment",
    tags={"env": "prod", "team": "backend"}
)
```

### Allocating a Host

```python
host = HostCreateRequest(
    region_id="region_123",
    hostname="api-gateway-01",
    device_type="Container",
    os_type="Linux"
)
```

## Module Attributes

Attributes:
    VALID_STATUSES (List[str]): Lifecycle states for resources (Active, Reserved, Retired).
    VALID_DEVICE_TYPES (List[str]): Categorization for hosts (VM, Container, Physical, etc.).
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Constants for validation
VALID_STATUSES = ["Active", "Reserved", "Retired"]
VALID_DEVICE_TYPES = ["VM", "Container", "Physical", "Network", "Storage", "Other"]
TAG_KEY_PATTERN = r"^[a-zA-Z0-9_-]+$"


# Request Models - Region Management
class RegionCreateRequest(BaseModel):
    """
    Request model for creating a new region allocation.

    A region represents a logical grouping of hosts within a specific country.
    It is assigned a unique Y-octet (0-255) within the country's X-octet range.

    **Validation:**
    *   **country**: Must be a valid country name (case-insensitive).
    *   **region_name**: 2-100 chars, alphanumeric + hyphens/dots. No special chars.
    """

    country: str = Field(..., min_length=2, max_length=100, description="Country name for region allocation")
    region_name: str = Field(..., min_length=2, max_length=100, description="User-defined region name")
    description: Optional[str] = Field(None, max_length=500, description="Optional region description")
    owner: Optional[str] = Field(None, max_length=100, description="Team or owner identifier")
    tags: Optional[Dict[str, str]] = Field(None, description="Key-value tags for organization")

    @field_validator("country")
    @classmethod
    def validate_country(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Country name cannot be empty")
        return v

    @field_validator("region_name")
    @classmethod
    def validate_region_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Region name cannot be empty")
        if len(v) < 2:
            raise ValueError("Region name must be at least 2 characters long")
        # Prevent special characters that could cause issues
        if any(char in v for char in ["<", ">", "&", '"', "'"]):
            raise ValueError("Region name contains invalid characters")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        return v.strip() if v else None

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, v):
        return v.strip() if v else None


class RegionUpdateRequest(BaseModel):
    """
    Request model for updating an existing region.

    Allows modification of metadata (name, description, owner, tags) and status.
    Changing the `region_name` does NOT change the underlying IP allocation.

    **Fields:**
    *   **status**: Can be set to 'Active', 'Reserved', or 'Retired'.
    """

    region_name: Optional[str] = Field(None, min_length=2, max_length=100, description="Updated region name")
    description: Optional[str] = Field(None, max_length=500, description="Updated description")
    owner: Optional[str] = Field(None, max_length=100, description="Updated owner")
    status: Optional[Literal["Active", "Reserved", "Retired"]] = Field(None, description="Updated status")
    tags: Optional[Dict[str, str]] = Field(None, description="Updated tags")

    @field_validator("region_name")
    @classmethod
    def validate_region_name(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Region name cannot be empty")
            if len(v) < 2:
                raise ValueError("Region name must be at least 2 characters long")
            if any(char in v for char in ["<", ">", "&", '"', "'"]):
                raise ValueError("Region name contains invalid characters")
        return v

    @field_validator("description", "owner")
    @classmethod
    def validate_optional_strings(cls, v):
        return v.strip() if v else None


# Request Models - Host Management
class HostCreateRequest(BaseModel):
    """
    Request model for creating a new host allocation.

    A host represents a single IP address (Z-octet) within a region.

    **Validation:**
    *   **hostname**: RFC 1123 compliant (alphanumeric, hyphens, dots). Max 253 chars.
    *   **device_type**: Must be one of `VALID_DEVICE_TYPES`.
    """

    region_id: str = Field(..., description="Region ID where host will be allocated")
    hostname: str = Field(..., min_length=1, max_length=253, description="Hostname for the device")
    device_type: Optional[Literal["VM", "Container", "Physical", "Network", "Storage", "Other"]] = Field(
        None, description="Type of device"
    )
    os_type: Optional[str] = Field(None, max_length=100, description="Operating system type")
    application: Optional[str] = Field(None, max_length=200, description="Application running on host")
    cost_center: Optional[str] = Field(None, max_length=100, description="Cost center for billing")
    owner: Optional[str] = Field(None, max_length=100, description="Team or owner identifier")
    purpose: Optional[str] = Field(None, max_length=500, description="Purpose or description")
    tags: Optional[Dict[str, str]] = Field(None, description="Key-value tags for organization")
    notes: Optional[str] = Field(None, max_length=2000, description="Additional notes")

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError("Hostname cannot be empty")
        # Basic hostname validation (RFC 1123)
        if not all(c.isalnum() or c in ["-", "."] for c in v):
            raise ValueError("Hostname can only contain alphanumeric characters, hyphens, and dots")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Hostname cannot start or end with a hyphen")
        return v

    @field_validator("os_type", "application", "cost_center", "owner", "purpose", "notes")
    @classmethod
    def validate_optional_strings(cls, v):
        return v.strip() if v else None


class HostUpdateRequest(BaseModel):
    """
    Request model for updating an existing host.

    Allows modification of metadata and status.
    Changing the `hostname` updates the record but does not change the IP.

    **Fields:**
    *   **status**: Lifecycle state ('Active', 'Reserved', 'Released').
    """

    hostname: Optional[str] = Field(None, min_length=1, max_length=253, description="Updated hostname")
    device_type: Optional[Literal["VM", "Container", "Physical", "Network", "Storage", "Other"]] = Field(
        None, description="Updated device type"
    )
    os_type: Optional[str] = Field(None, max_length=100, description="Updated OS type")
    application: Optional[str] = Field(None, max_length=200, description="Updated application")
    cost_center: Optional[str] = Field(None, max_length=100, description="Updated cost center")
    owner: Optional[str] = Field(None, max_length=100, description="Updated owner")
    purpose: Optional[str] = Field(None, max_length=500, description="Updated purpose")
    status: Optional[Literal["Active", "Reserved", "Released"]] = Field(None, description="Updated status")
    tags: Optional[Dict[str, str]] = Field(None, description="Updated tags")
    notes: Optional[str] = Field(None, max_length=2000, description="Updated notes")

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, v):
        if v is not None:
            v = v.strip().lower()
            if not v:
                raise ValueError("Hostname cannot be empty")
            if not all(c.isalnum() or c in ["-", "."] for c in v):
                raise ValueError("Hostname can only contain alphanumeric characters, hyphens, and dots")
            if v.startswith("-") or v.endswith("-"):
                raise ValueError("Hostname cannot start or end with a hyphen")
        return v

    @field_validator("os_type", "application", "cost_center", "owner", "purpose", "notes")
    @classmethod
    def validate_optional_strings(cls, v):
        return v.strip() if v else None


class BatchHostCreateRequest(BaseModel):
    """
    Request model for batch host allocation.

    Allocates multiple sequential IP addresses in a single region.

    **Validation:**
    *   **count**: 1-100 hosts per request.
    *   **hostname_prefix**: Used to generate hostnames (e.g., 'web-' -> 'web-1', 'web-2').
    """

    region_id: str = Field(..., description="Region ID where hosts will be allocated")
    count: int = Field(..., ge=1, le=100, description="Number of hosts to allocate (max 100)")
    hostname_prefix: str = Field(..., min_length=1, max_length=240, description="Prefix for generated hostnames")
    device_type: Optional[Literal["VM", "Container", "Physical", "Network", "Storage", "Other"]] = Field(
        None, description="Device type for all hosts"
    )
    owner: Optional[str] = Field(None, max_length=100, description="Owner for all hosts")
    tags: Optional[Dict[str, str]] = Field(None, description="Tags for all hosts")

    @field_validator("hostname_prefix")
    @classmethod
    def validate_hostname_prefix(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError("Hostname prefix cannot be empty")
        if not all(c.isalnum() or c in ["-"] for c in v):
            raise ValueError("Hostname prefix can only contain alphanumeric characters and hyphens")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Hostname prefix cannot start or end with a hyphen")
        return v


# Request Models - Comments
class CommentCreateRequest(BaseModel):
    """
    Request model for adding a comment to a resource.

    Comments provide an audit trail for human decisions and context.
    """

    comment_text: str = Field(..., min_length=1, max_length=2000, description="Comment text")

    @field_validator("comment_text")
    @classmethod
    def validate_comment_text(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Comment text cannot be empty")
        return v


# Request Models - Retirement and Release
class RetireAllocationRequest(BaseModel):
    """
    Request model for retiring an allocation.

    Retiring a resource marks it as permanently inactive but preserves its history.

    **Fields:**
    *   **cascade**: If True (for regions), recursively retires all contained hosts.
    """

    reason: str = Field(..., min_length=5, max_length=500, description="Reason for retirement")
    cascade: bool = Field(False, description="For regions: also retire all child hosts")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Reason cannot be empty")
        if len(v) < 5:
            raise ValueError("Reason must be at least 5 characters long")
        return v


class BulkReleaseRequest(BaseModel):
    """
    Request model for bulk host release.

    Releasing a host returns its IP address to the available pool.

    **Validation:**
    *   **host_ids**: List of 1-100 unique host IDs.
    """

    host_ids: List[str] = Field(..., min_items=1, max_items=100, description="List of host IDs to release")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for release")

    @field_validator("host_ids")
    @classmethod
    def validate_host_ids(cls, v):
        if not v:
            raise ValueError("At least one host ID must be provided")
        if len(v) > 100:
            raise ValueError("Cannot release more than 100 hosts at once")
        # Remove duplicates
        return list(set(v))

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Reason cannot be empty")
        if len(v) < 5:
            raise ValueError("Reason must be at least 5 characters long")
        return v


# Request Models - Reservation
class ReservationCreateRequest(BaseModel):
    """
    Request model for creating a manual reservation.

    Reservations hold specific IP addresses or ranges, preventing automatic allocation.

    **Fields:**
    *   **x_octet**: Country code.
    *   **y_octet**: Region ID.
    *   **z_octet**: Host ID (optional for region reservations).
    """

    resource_type: Literal["region", "host"] = Field(..., description="Type of resource to reserve")
    x_octet: int = Field(..., ge=0, le=255, description="X octet value")
    y_octet: int = Field(..., ge=0, le=255, description="Y octet value")
    z_octet: Optional[int] = Field(None, ge=1, le=254, description="Z octet value (for host reservations)")
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for reservation")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Reason cannot be empty")
        if len(v) < 5:
            raise ValueError("Reason must be at least 5 characters long")
        return v


# Request Models - Search and Filtering
class SearchRequest(BaseModel):
    """
    Request model for searching allocations.

    Supports complex filtering across multiple dimensions.

    **Filters:**
    *   **cidr**: Supports standard CIDR notation (e.g., '10.1.0.0/16').
    *   **tags**: Matches resources containing ALL specified tags (AND logic).
    """

    ip_address: Optional[str] = Field(None, description="IP address for exact or partial match")
    cidr: Optional[str] = Field(None, description="CIDR range for matching")
    hostname: Optional[str] = Field(None, description="Hostname for partial match (case-insensitive)")
    region_name: Optional[str] = Field(None, description="Region name for partial match")
    continent: Optional[str] = Field(None, description="Filter by continent")
    country: Optional[str] = Field(None, description="Filter by country")
    status: Optional[Literal["Active", "Reserved", "Retired", "Released"]] = Field(None, description="Filter by status")
    owner: Optional[str] = Field(None, description="Filter by owner")
    tags: Optional[Dict[str, str]] = Field(None, description="Filter by tags (AND logic)")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date (after)")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date (before)")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=100, description="Results per page (max 100)")


# Request Models - Import/Export
class ExportRequest(BaseModel):
    """
    Request model for exporting allocations.

    **Formats:**
    *   **json**: Full structural fidelity.
    *   **csv**: Flattened list suitable for spreadsheets.
    """

    format: Literal["csv", "json"] = Field("json", description="Export format")
    resource_type: Optional[Literal["regions", "hosts", "all"]] = Field("all", description="Resources to export")
    include_hierarchy: bool = Field(True, description="Include hierarchical structure")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters to apply")


class ImportRequest(BaseModel):
    """
    Request model for importing allocations.

    **Modes:**
    *   **preview**: Validates data and returns a summary of changes without applying them.
    *   **manual**: Applies changes but requires explicit confirmation for conflicts.
    *   **auto**: Automatically resolves conflicts where possible.
    """

    mode: Literal["auto", "manual", "preview"] = Field("preview", description="Import mode")
    force: bool = Field(False, description="Skip existing allocations without error")


# Response Models - Country and Mapping
class CountryResponse(BaseModel):
    """
    Response model for country-level IPAM data.

    Maps a physical country to its assigned X-octet range in the 10.X.Y.Z schema.

    **Fields:**
    *   **x_start** / **x_end**: The inclusive range of X-octets assigned to this country.
    *   **utilization_percent**: Percentage of available regions (Y-octets) currently allocated.
    """

    continent: str
    country: str
    x_start: int
    x_end: int
    total_blocks: int
    allocated_regions: int
    remaining_capacity: int
    utilization_percent: float
    is_reserved: bool


class ContinentCountryMapping(BaseModel):
    """
    Response model for the global IPAM hierarchy.

    Groups countries by continent for navigation and visualization.
    """

    continent: str
    countries: List[CountryResponse]


# Response Models - Utilization Statistics
class UtilizationStats(BaseModel):
    """
    Response model for generic resource utilization statistics.

    Used for dashboards showing capacity planning metrics.
    """

    total_capacity: int
    allocated: int
    available: int
    utilization_percent: float
    breakdown: Optional[Dict[str, Any]] = None


class RegionUtilizationResponse(BaseModel):
    """
    Response model for region-specific utilization.

    Shows how many hosts (Z-octets) are used within a specific region.
    """

    region_id: str
    cidr: str
    region_name: str
    total_hosts: int = 254
    allocated_hosts: int
    available_hosts: int
    utilization_percent: float


class CountryUtilizationResponse(BaseModel):
    """
    Response model for country-specific utilization.

    Shows how many regions (Y-octets) are used within a country's X-octet blocks.
    """

    country: str
    continent: str
    x_range: str
    total_capacity: int
    allocated_regions: int
    utilization_percent: float
    x_value_breakdown: List[Dict[str, Any]]


# Response Models - Region
class CommentResponse(BaseModel):
    """
    Response model for a single comment on a resource.
    """

    text: str
    author_id: str
    timestamp: datetime


class RegionResponse(BaseModel):
    """
    Response model for a full region allocation.

    **Fields:**
    *   **cidr**: The CIDR block for this region (e.g., '10.1.5.0/24').
    *   **x_octet**: The country code part of the IP.
    *   **y_octet**: The region ID part of the IP.
    """

    region_id: str
    user_id: str
    country: str
    continent: str
    x_octet: int
    y_octet: int
    cidr: str
    region_name: str
    description: Optional[str] = None
    # Backwards-compatible: `owner` kept for older clients. New clients
    # should use `owner_name` for the human-friendly owner string and
    # `owner_id` for the internal identifier.
    owner: Optional[str] = None
    owner_name: Optional[str] = None
    owner_id: Optional[str] = None
    status: str
    tags: Dict[str, str] = {}
    comments: List[CommentResponse] = []
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


# Response Models - Host
class HostResponse(BaseModel):
    """
    Response model for a full host allocation.

    **Fields:**
    *   **ip_address**: The full IPv4 address (e.g., '10.1.5.12').
    *   **z_octet**: The host ID part of the IP (1-254).
    """

    host_id: str
    user_id: str
    region_id: str
    x_octet: int
    y_octet: int
    z_octet: int
    ip_address: str
    hostname: str
    device_type: Optional[str] = None
    os_type: Optional[str] = None
    application: Optional[str] = None
    cost_center: Optional[str] = None
    # Backwards-compatible owner field plus explicit owner_name and owner_id
    owner: Optional[str] = None
    owner_name: Optional[str] = None
    owner_id: Optional[str] = None
    purpose: Optional[str] = None
    status: str
    tags: Dict[str, str] = {}
    notes: Optional[str] = None
    comments: List[CommentResponse] = []
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str


# Response Models - Batch Operations
class BatchHostCreateResult(BaseModel):
    """
    Response model for batch host creation.

    Summarizes the outcome of a bulk allocation request.

    **Fields:**
    *   **hosts**: List of successfully allocated host objects.
    *   **errors**: List of failures (e.g., if a specific IP was already taken).
    """

    total_requested: int
    successful: int
    failed: int
    hosts: List[HostResponse]
    errors: List[Dict[str, Any]] = []


class BulkReleaseResult(BaseModel):
    """
    Response model for bulk host release.

    **Fields:**
    *   **results**: Detailed status for each requested host ID.
    """

    total_requested: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]


# Response Models - IP Interpretation
class HostHierarchyInfo(BaseModel):
    """
    Simplified host info for hierarchy visualization.
    """

    host_id: str
    hostname: str
    z_octet: int
    status: str
    device_type: Optional[str] = None


class RegionHierarchyInfo(BaseModel):
    """
    Simplified region info for hierarchy visualization.
    """

    region_id: str
    region_name: str
    cidr: str
    y_octet: int
    status: str


class CountryHierarchyInfo(BaseModel):
    """
    Simplified country info for hierarchy visualization.
    """

    name: str
    x_range: str
    x_octet: int


class IPHierarchyResponse(BaseModel):
    """
    Response model for IP address interpretation.

    Given an IP, returns its place in the hierarchy (Country -> Region -> Host).
    """

    ip_address: str
    hierarchy: Dict[str, Any]


# Response Models - Validation
class ValidationResult(BaseModel):
    """
    Response model for generic validation checks.
    """

    valid: bool
    errors: List[str] = []
    warnings: List[str] = []


class ImportValidationResult(BaseModel):
    """
    Response model for import preview/validation.

    **Fields:**
    *   **valid_rows**: Count of records that can be imported safely.
    *   **invalid_rows**: Count of records with errors.
    """

    valid: bool
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []


# Response Models - Search and Pagination
class PaginationMetadata(BaseModel):
    """
    Standard pagination metadata.
    """

    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class SearchResponse(BaseModel):
    """
    Response model for search results.

    Wraps a list of results (regions or hosts) with pagination and filter context.
    """

    results: List[Dict[str, Any]]
    pagination: PaginationMetadata
    filters_applied: Dict[str, Any]


# Response Models - Audit and History
class AuditChangeEntry(BaseModel):
    """
    Model for a field-level change in the audit history.

    Captures the before and after state of a specific field.
    """

    field: str
    old_value: Any
    new_value: Any


class AuditHistoryEntry(BaseModel):
    """
    Response model for a single audit history entry.

    Represents an event in the lifecycle of a resource.

    **Fields:**
    *   **snapshot**: Full state of the resource at the time of this event.
    *   **changes**: List of specific field modifications.
    """

    audit_id: str
    user_id: str
    action_type: str
    resource_type: str
    resource_id: str
    ip_address: Optional[str] = None
    cidr: Optional[str] = None
    snapshot: Dict[str, Any]
    changes: List[AuditChangeEntry] = []
    reason: Optional[str] = None
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class AuditHistoryResponse(BaseModel):
    """
    Response model for a paginated audit history query.
    """

    entries: List[AuditHistoryEntry]
    pagination: PaginationMetadata


# Response Models - Quota Management
class QuotaResponse(BaseModel):
    """
    Response model for user quota information.

    Tracks usage against limits for regions and hosts.
    """

    user_id: str
    region_quota: int
    host_quota: int
    region_count: int
    host_count: int
    region_usage_percent: float
    host_usage_percent: float
    last_updated: datetime


# Response Models - Statistics and Analytics
class AllocationVelocityResponse(BaseModel):
    """
    Response model for allocation velocity metrics.

    Measures the rate of new allocations over time to predict capacity needs.
    """

    time_range: str
    allocations_per_day: float
    allocations_per_week: float
    allocations_per_month: float
    trend: str  # "increasing", "decreasing", "stable"


class TopUtilizedResource(BaseModel):
    """
    Response model for identifying high-usage resources.
    """

    resource_type: str
    resource_id: str
    resource_name: str
    utilization_percent: float
    allocated: int
    total_capacity: int


class ContinentStatisticsResponse(BaseModel):
    """
    Response model for aggregated continent statistics.
    """

    continent: str
    total_countries: int
    total_capacity: int
    allocated_regions: int
    utilization_percent: float
    countries: List[CountryUtilizationResponse]


# Response Models - Preview
class NextAvailablePreview(BaseModel):
    """
    Response model for previewing the next available allocation.

    Used by UI to suggest the next free IP/Region before creation.
    """

    available: bool
    next_allocation: Optional[str] = None
    message: str


# Response Models - Export Job
class ExportJobResponse(BaseModel):
    """
    Response model for asynchronous export job status.
    """

    job_id: str
    status: str
    format: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None


# Error Response Models
class IPAMErrorResponse(BaseModel):
    """
    Standard error response model for IPAM operations.
    """

    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


class CapacityExhaustedError(BaseModel):
    """
    Specific error for when a range (Country or Region) is full.
    """

    error: str = "capacity_exhausted"
    message: str
    details: Dict[str, Any]


class QuotaExceededError(BaseModel):
    """
    Specific error for when a user exceeds their allocation quota.
    """

    error: str = "quota_exceeded"
    message: str
    quota_type: str
    current_usage: int
    quota_limit: int
