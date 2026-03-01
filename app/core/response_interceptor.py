"""
Success Response Interceptor Middleware
FastAPI equivalent of NestJS SuccessResponseInterceptor.
Wraps all successful responses in a standard format with success flag.
"""

from typing import Callable
from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware


# Key for skipping the interceptor on specific routes
SKIP_INTERCEPTOR_KEY = "skip_interceptor"


class SuccessResponseInterceptor(BaseHTTPMiddleware):
    """
    Middleware that wraps all successful JSON responses in:
    {"success": true, "data": <original response>}

    Uses byte-level wrapping — no JSON parsing or re-serialization.
    Can be skipped on specific routes using the @skip_interceptor decorator.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Skip interceptor for FastAPI built-in documentation endpoints
        if request.url.path in ("/openapi.json", "/docs", "/redoc"):
            return response

        # Only intercept successful JSON responses (2xx status codes)
        if not (200 <= response.status_code < 300):
            return response

        # Check if the route has the skip interceptor flag
        if getattr(request.state, SKIP_INTERCEPTOR_KEY, False):
            return response

        # Check the response content type
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Collect body efficiently — O(n) with join vs O(n²) with +=
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        body = b"".join(chunks)

        # Wrap at byte level — NO json.loads, NO json.dumps
        wrapped = b'{"success":true,"data":' + body + b"}"

        # Copy headers, drop content-length (now stale after wrapping)
        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() != "content-length"
        }

        return Response(
            content=wrapped,
            status_code=response.status_code,
            headers=headers,
            media_type="application/json",
        )


def skip_interceptor(func: Callable) -> Callable:
    """
    Decorator to skip the success response interceptor on specific routes.
    
    Usage:
        @router.get("/custom")
        @skip_interceptor
        async def custom_endpoint():
            return {"custom": "response"}
    """
    # Mark the function with the skip interceptor flag
    setattr(func, SKIP_INTERCEPTOR_KEY, True)
    return func


class CustomAPIRoute(APIRoute):
    """
    Custom API Route that checks for the skip_interceptor decorator
    and sets it in the request state.
    """

    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            # Check if the endpoint function has the skip interceptor flag
            if hasattr(self.endpoint, SKIP_INTERCEPTOR_KEY):
                skip = getattr(self.endpoint, SKIP_INTERCEPTOR_KEY, False)
                setattr(request.state, SKIP_INTERCEPTOR_KEY, skip)
            
            return await original_route_handler(request)

        return custom_route_handler

