"""
Success Response Interceptor Middleware
FastAPI equivalent of NestJS SuccessResponseInterceptor.
Wraps all successful responses in a standard format with success flag and optional count.
"""

from typing import Callable, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
import json


# Key for skipping the interceptor on specific routes
SKIP_INTERCEPTOR_KEY = "skip_interceptor"


class SuccessResponseInterceptor(BaseHTTPMiddleware):
    """
    Middleware that wraps all successful responses in a standard format:
    {
        "success": true,
        "count": <length> (if data is a list),
        "data": <original response>
    }
    
    Can be skipped on specific routes using the @skip_interceptor decorator.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Skip interceptor for FastAPI built-in documentation endpoints
        excluded_paths = ["/openapi.json", "/docs", "/redoc"]
        if request.url.path in excluded_paths:
            return response
        
        # Only intercept successful JSON responses (2xx status codes)
        if not (200 <= response.status_code < 300):
            return response
        
        # Check if the route has the skip interceptor flag
        if hasattr(request.state, SKIP_INTERCEPTOR_KEY):
            skip = getattr(request.state, SKIP_INTERCEPTOR_KEY, False)
            if skip:
                return response
        
        # Check the response content type
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response
        
        # Read the original response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        try:
            # Parse the original response
            original_data = json.loads(response_body.decode())
            
            # Create the wrapped response
            wrapped_response = {
                "success": True,
                "data": original_data,
            }
            
            # Add count if data is a list
            if isinstance(original_data, list):
                wrapped_response["count"] = len(original_data)
            
            # Copy headers but exclude Content-Length (will be recalculated by JSONResponse)
            headers = dict(response.headers)
            headers.pop("content-length", None)
            
            # Return the wrapped response
            return JSONResponse(
                content=wrapped_response,
                status_code=response.status_code,
                headers=headers,
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            # If we can't parse the response, return it as is
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
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

