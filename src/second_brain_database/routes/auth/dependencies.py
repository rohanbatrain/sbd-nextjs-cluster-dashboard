"""
# Authentication Dependencies

This module provides **FastAPI dependency injection functions** for authentication and security enforcement.
These reusable dependencies are used across the API to handle authentication, context management,
and security lockdowns, ensuring that security policies are applied consistently to all protected endpoints.

## Domain Overview

The dependency system implements a layered security model:

- **Layer 1: Authentication** - Verify JWT token and retrieve user
- **Layer 2: Context Injection** - Set tenant and workspace contexts for multi-tenancy
- **Layer 3: Security Lockdowns** - Enforce IP and User-Agent restrictions (Trusted Devices)

## Key Dependencies

### 1. `get_current_user_dep`
The foundational authentication dependency that:
- Validates JWT access tokens
- Fetches the user document from MongoDB
- Extracts tenant information from the token payload
- Sets the global tenant context for the request
- Enriches the user object with workspace memberships

**Usage:**
```python
@router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user_dep)):
    return {"username": current_user["username"]}
```

### 2. `enforce_ip_lockdown`
Enforces the "Trusted IP Lockdown" security feature:
- Checks if the user has enabled IP restrictions
- Verifies the request IP against the user's trusted IP list
- Blocks untrusted IPs with a 403 error
- Logs security events and sends email notifications

**Behavior:**
- **Lockdown Disabled**: Passes through without checking
- **Lockdown Enabled & IP Trusted**: Passes through
- **Lockdown Enabled & IP Untrusted**: Blocks request, logs event, sends email

### 3. `enforce_user_agent_lockdown`
Enforces the "Trusted User-Agent Lockdown" security feature:
- Restricts access to specific browsers/devices (identified by User-Agent string)
- Similar behavior to IP lockdown but for device fingerprinting

### 4. `enforce_all_lockdowns`
The comprehensive security dependency that chains all checks:
- Authentication (`get_current_user_dep`)
- IP restrictions (`enforce_ip_lockdown`)
- Device restrictions (`enforce_user_agent_lockdown`)

**Recommended Usage:**
```python
@router.post("/sensitive-action")
async def sensitive_action(current_user: dict = Depends(enforce_all_lockdowns)):
    # User is authenticated AND passed all security checks
    pass
```

## Multi-Tenancy Context

The `get_current_user_dep` dependency automatically sets up the tenant context for each request:

1. **Token Payload**: Extracts `primary_tenant_id` and `tenant_memberships` from JWT
2. **Global Context**: Sets the tenant context using `set_tenant_context()`
3. **User Enrichment**: Adds tenant and workspace data to the user object

This ensures that all database queries are automatically scoped to the correct tenant.

## Security Event Logging

All security violations are logged with comprehensive details:
- Event type (`ip_lockdown_violation`, `user_agent_lockdown_violation`)
- User ID and IP address
- Attempted vs. trusted values
- Endpoint and timestamp
- User-Agent and other request metadata

Logs are written to the `logs` collection for security auditing and threat detection.

## Email Notifications

When a lockdown violation occurs, the system:
1. Logs the security event
2. Sends an HTML email to the user with:
   - Details of the blocked attempt
   - List of currently trusted IPs/User-Agents
   - Action buttons to allow the access or add to trusted list

This provides transparency and allows users to quickly resolve legitimate access issues.

## Module Attributes

Attributes:
    oauth2_scheme (OAuth2PasswordBearer): FastAPI OAuth2 token extractor
"""

from typing import Any, Dict

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.managers.workspace_manager import workspace_manager
from second_brain_database.routes.auth.services.auth.password import send_blocked_ip_notification
from second_brain_database.utils.logging_utils import log_security_event

logger = get_logger(prefix="[Security Dependencies]")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user_dep(token: str = Depends(oauth2_scheme)):
    """
    Retrieve and enrich the current authenticated user context.

    This dependency performs several critical functions:
    1.  **Authentication**: Validates the JWT token and fetches the user from the database.
    2.  **Multi-tenancy**: Extracts tenant information (`primary_tenant_id`, `tenant_memberships`)
        from the token and sets the global tenant context for the request.
    3.  **Workspace Context**: Fetches the user's workspace memberships and adds them to the user object.

    **Context Injection:**
    The returned user object is enriched with:
    *   `current_tenant_id`: The active tenant for this request.
    *   `workspaces`: A list of workspaces the user has access to.

    Args:
        token (str): The JWT access token (injected by FastAPI).

    Returns:
        dict: The enriched user document.

    Raises:
        HTTPException(401): If the token is invalid or the user does not exist.
    """
    from second_brain_database.routes.auth.services.auth.login import get_current_user
    from second_brain_database.middleware.tenant_context import set_tenant_context, get_current_tenant_id
    from jose import jwt
    from second_brain_database.config import settings

    # 1. Get the core user object
    user = await get_current_user(token)

    if user:
        # 2. Extract tenant information from JWT token
        try:
            secret_key = getattr(settings, "SECRET_KEY", None)
            if hasattr(secret_key, "get_secret_value"):
                secret_key = secret_key.get_secret_value()
            
            payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
            primary_tenant_id = payload.get("primary_tenant_id", settings.DEFAULT_TENANT_ID)
            tenant_memberships = payload.get("tenant_memberships", [])
            
            # Add tenant information to user object
            user["primary_tenant_id"] = primary_tenant_id
            user["tenant_memberships"] = tenant_memberships
            user["current_tenant_id"] = get_current_tenant_id() or primary_tenant_id
            
            # Set tenant context if not already set (e.g., by middleware)
            if not get_current_tenant_id():
                set_tenant_context(primary_tenant_id)
                logger.debug(f"Set tenant context to primary tenant: {primary_tenant_id}")
            
        except Exception as e:
            logger.warning(f"Failed to extract tenant info from JWT for user {user.get('_id')}: {e}")
            # Fallback to default tenant
            user["primary_tenant_id"] = settings.DEFAULT_TENANT_ID
            user["tenant_memberships"] = []
            user["current_tenant_id"] = settings.DEFAULT_TENANT_ID
            set_tenant_context(settings.DEFAULT_TENANT_ID)
        
        # 3. Augment the user object with their workspace data (tenant-scoped)
        try:
            user_id = str(user["_id"])
            user_workspaces = await workspace_manager.get_workspaces_for_user(user_id)
            user["workspaces"] = user_workspaces
            logger.debug(f"User {user_id} is a member of {len(user_workspaces)} workspaces.")
        except Exception as e:
            logger.error(f"Failed to retrieve workspaces for user {user.get('_id')}: {e}")
            # Decide if this should be a hard fail or not. For now, we'll allow login
            # but the user won't have workspace context.
            user["workspaces"] = []


    return user


async def enforce_ip_lockdown(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user_dep)
) -> Dict[str, Any]:
    """
    Enforce Trusted IP Lockdown policy.

    This dependency checks if the user has enabled "Trusted IP Lockdown". If enabled,
    it verifies that the request's source IP address is in the user's list of trusted IPs.

    **Behavior:**
    *   **Lockdown Disabled**: Passes through without checking (returns user).
    *   **Lockdown Enabled & IP Trusted**: Passes through.
    *   **Lockdown Enabled & IP Untrusted**:
        1.  Blocks the request (raises 403).
        2.  Logs a security event (`ip_lockdown_violation`).
        3.  Sends an email notification to the user about the blocked attempt.

    Args:
        request (Request): The HTTP request object.
        current_user (Dict): The authenticated user.

    Returns:
        Dict: The user object (if check passes).

    Raises:
        HTTPException(403): If the IP is not trusted.
    """
    try:
        # Check IP lockdown using the security manager
        await security_manager.check_ip_lockdown(request, current_user)

        # Log successful IP lockdown check
        request_ip = security_manager.get_client_ip(request)
        logger.debug("IP lockdown check passed for user %s from IP %s", current_user.get("username"), request_ip)

        return current_user

    except HTTPException as e:
        # IP lockdown blocked the request - log and send notification
        request_ip = security_manager.get_client_ip(request)
        user_id = current_user.get("username", current_user.get("_id", "unknown"))
        trusted_ips = current_user.get("trusted_ips", [])
        endpoint = f"{request.method} {request.url.path}"

        # Log comprehensive security event
        log_security_event(
            event_type="ip_lockdown_violation",
            user_id=user_id,
            ip_address=request_ip,
            success=False,
            details={
                "attempted_ip": request_ip,
                "trusted_ips": trusted_ips,
                "endpoint": endpoint,
                "method": request.method,
                "path": request.url.path,
                "user_agent": request.headers.get("user-agent", ""),
                "timestamp": request.headers.get("date", ""),
                "lockdown_enabled": current_user.get("trusted_ip_lockdown", False),
                "trusted_ip_count": len(trusted_ips),
            },
        )

        logger.warning(
            "IP lockdown violation: blocked request from IP %s for user %s on endpoint %s (trusted IPs: %s)",
            request_ip,
            user_id,
            endpoint,
            trusted_ips,
        )

        # Send email notification about blocked access attempt
        try:
            user_email = current_user.get("email")
            if user_email:
                await send_blocked_ip_notification(
                    email=user_email, attempted_ip=request_ip, trusted_ips=trusted_ips, endpoint=endpoint
                )
                logger.info("Sent blocked IP notification email to %s", user_email)
            else:
                logger.warning("Cannot send blocked IP notification: no email for user %s", user_id)
        except Exception as email_error:
            logger.error("Failed to send blocked IP notification email: %s", email_error, exc_info=True)

        # Re-raise the original HTTPException
        raise


async def enforce_user_agent_lockdown(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user_dep)
) -> Dict[str, Any]:
    """
    Enforce Trusted User-Agent Lockdown policy.

    Similar to IP lockdown, this dependency restricts access to specific browsers or devices
    (identified by User-Agent string) if the user has enabled this feature.

    **Behavior:**
    *   **Lockdown Disabled**: Passes through.
    *   **Lockdown Enabled & UA Trusted**: Passes through.
    *   **Lockdown Enabled & UA Untrusted**:
        1.  Blocks the request (raises 403).
        2.  Logs a security event (`user_agent_lockdown_violation`).
        3.  Sends an email notification.

    Args:
        request (Request): The HTTP request object.
        current_user (Dict): The authenticated user.

    Returns:
        Dict: The user object (if check passes).

    Raises:
        HTTPException(403): If the User-Agent is not trusted.
    """
    try:
        # Check User Agent lockdown using the security manager
        await security_manager.check_user_agent_lockdown(request, current_user)

        # Log successful User Agent lockdown check
        request_user_agent = security_manager.get_client_user_agent(request)
        logger.debug(
            "User Agent lockdown check passed for user %s with User Agent %s",
            current_user.get("username"),
            request_user_agent,
        )

        return current_user

    except HTTPException as e:
        # User Agent lockdown blocked the request - log and send notification
        request_ip = security_manager.get_client_ip(request)
        request_user_agent = security_manager.get_client_user_agent(request)
        user_id = current_user.get("username", current_user.get("_id", "unknown"))
        trusted_user_agents = current_user.get("trusted_user_agents", [])
        endpoint = f"{request.method} {request.url.path}"

        # Log comprehensive security event
        log_security_event(
            event_type="user_agent_lockdown_violation",
            user_id=user_id,
            ip_address=request_ip,
            success=False,
            details={
                "attempted_user_agent": request_user_agent,
                "trusted_user_agents": trusted_user_agents,
                "endpoint": endpoint,
                "method": request.method,
                "path": request.url.path,
                "timestamp": request.headers.get("date", ""),
                "lockdown_enabled": current_user.get("trusted_user_agent_lockdown", False),
                "trusted_user_agent_count": len(trusted_user_agents),
            },
        )

        logger.warning(
            "User Agent lockdown violation: blocked request with User Agent %s for user %s on endpoint %s (trusted User Agents: %s)",
            request_user_agent,
            user_id,
            endpoint,
            trusted_user_agents,
        )

        # Send email notification about blocked access attempt
        try:
            from second_brain_database.routes.auth.services.auth.password import send_blocked_user_agent_notification

            user_email = current_user.get("email")
            if user_email:
                await send_blocked_user_agent_notification(
                    email=user_email,
                    attempted_user_agent=request_user_agent,
                    trusted_user_agents=trusted_user_agents,
                    endpoint=endpoint,
                )
                logger.info("Sent blocked User Agent notification email to %s", user_email)
            else:
                logger.warning("Cannot send blocked User Agent notification: no email for user %s", user_id)
        except Exception as email_error:
            logger.error("Failed to send blocked User Agent notification email: %s", email_error, exc_info=True)

        # Re-raise the original HTTPException
        raise


async def enforce_all_lockdowns(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user_dep)
) -> Dict[str, Any]:
    """
    Comprehensive security dependency enforcing all lockdown policies.

    This is the primary dependency used by protected endpoints. It chains together:
    1.  `get_current_user_dep`: Authentication & Context.
    2.  `enforce_ip_lockdown`: IP restrictions.
    3.  `enforce_user_agent_lockdown`: Device restrictions.

    Using this dependency ensures that all enabled security layers are active for the endpoint.

    Args:
        request (Request): The HTTP request object.
        current_user (Dict): The authenticated user.

    Returns:
        Dict: The user object (if all checks pass).

    Raises:
        HTTPException: If any security check fails.
    """
    user_id = current_user.get("username", current_user.get("_id", "unknown"))
    endpoint = f"{request.method} {request.url.path}"

    logger.debug("Starting combined lockdown checks for user %s on endpoint %s", user_id, endpoint)

    try:
        # First check IP lockdown - this will handle its own logging and notifications
        user = await enforce_ip_lockdown(request, current_user)

        # Then check User Agent lockdown - this will handle its own logging and notifications
        user = await enforce_user_agent_lockdown(request, user)

        logger.debug("All lockdown checks passed for user %s on endpoint %s", user_id, endpoint)
        return user

    except HTTPException as e:
        # Individual lockdown functions handle their own logging and notifications
        # We just need to log that the combined check failed and re-raise
        logger.info("Combined lockdown check failed for user %s on endpoint %s: %s", user_id, endpoint, e.detail)
        raise
