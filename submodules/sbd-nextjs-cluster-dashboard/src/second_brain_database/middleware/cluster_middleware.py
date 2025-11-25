"""
Cluster middleware for distributed SBD architecture.

This middleware intercepts incoming requests and routes them to the appropriate
node in the cluster based on operation type and load balancing configuration.
"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.services.request_router import request_router

logger = get_logger()


class ClusterMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling distributed request routing.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Dispatch request to appropriate node or handle locally.
        """
        # Skip if cluster mode disabled
        if not settings.CLUSTER_ENABLED:
            return await call_next(request)

        # Skip cluster internal routes to avoid loops
        if request.url.path.startswith("/cluster/"):
            return await call_next(request)

        # Skip health checks and metrics
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Check for forwarded request to avoid loops
        if request.headers.get("X-Forwarded-From"):
            # Verify cluster token if configured
            if settings.CLUSTER_AUTH_TOKEN:
                token = request.headers.get("X-Cluster-Token")
                expected = settings.CLUSTER_AUTH_TOKEN.get_secret_value()
                if token != expected:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Invalid cluster token"},
                    )
            return await call_next(request)

        try:
            # Attempt to route request
            forwarded_response = await request_router.route_request(request)
            
            if forwarded_response:
                return forwarded_response

            # If not forwarded, handle locally
            return await call_next(request)

        except Exception as e:
            logger.error(f"Cluster middleware error: {e}", exc_info=True)
            return JSONResponse(
                status_code=503,
                content={"detail": "Cluster routing failed"},
            )
