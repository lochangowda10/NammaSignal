"""
NammaSignal Security Enhancements
Rate limiting, security headers, request timeout, and circuit breaker patterns
"""
import time
import asyncio
from typing import Callable, Dict, Any
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger("nammasignal.security")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS (only over HTTPS in production)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Basic CSP - can be enhanced based on frontend needs
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using sliding window"""

    def __init__(
        self,
        app: ASGIApp,
        calls_per_minute: int = 60,
        burst_limit: int = 10
    ):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.burst_limit = burst_limit
        self.requests: Dict[str, list] = defaultdict(list)
        self.cleanup_interval = 60  # seconds
        self.last_cleanup = time.time()

    async def dispatch(self, request: Request, call_next):
        # Clean up old entries periodically
        now = time.time()
        if now - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(now)
            self.last_cleanup = now

        # Get client identifier (IP address, or user ID if authenticated)
        client_id = request.client.host if request.client else "unknown"

        # Check if user is authenticated for higher limits
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # In a real implementation, you'd decode the token here to get user ID
            client_id = f"authenticated_{client_id}"

        # Check rate limit
        if self._is_rate_limited(client_id, now):
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": "60"}
            )

        # Record this request
        self.requests[client_id].append(now)

        response: Response = await call_next(request)
        return response

    def _is_rate_limited(self, client_id: str, now: float) -> bool:
        """Check if client has exceeded rate limit"""
        requests = self.requests[client_id]

        # Remove requests older than 1 minute
        cutoff = now - 60
        while requests and requests[0] < cutoff:
            requests.pop(0)

        # Check if at or over limit
        return len(requests) >= self.calls_per_minute

    def _cleanup_old_entries(self, now: float):
        """Clean up old entries to prevent memory leak"""
        cutoff = now - 300  # Keep 5 minutes of history
        for client_id in list(self.requests.keys()):
            requests = self.requests[client_id]
            # Remove old requests
            while requests and requests[0] < cutoff:
                requests.pop(0)
            # Remove empty entries
            if not requests:
                del self.requests[client_id]


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Request timeout middleware"""

    def __init__(self, app: ASGIApp, timeout_seconds: float = 30.0):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next):
        try:
            # Apply timeout to request processing
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout for {request.method} {request.url.path}")
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="Request timeout. Please try again."
            )


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """Simple circuit breaker pattern for external dependencies"""

    def __init__(self, app: ASGIApp, failure_threshold: int = 5, timeout_seconds: int = 60):
        super().__init__(app)
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count: Dict[str, int] = defaultdict(int)
        self.last_failure_time: Dict[str, float] = defaultdict(float)
        self.state: Dict[str, str] = defaultdict(lambda: "CLOSED")  # CLOSED, OPEN, HALF_OPEN

    async def dispatch(self, request: Request, call_next):
        # Determine which service this request is targeting (simple path-based)
        service = self._get_service_from_path(request.url.path)

        # Check circuit breaker state
        if not self._allow_request(service):
            logger.warning(f"Circuit breaker OPEN for service: {service}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service {service} temporarily unavailable. Please try again later."
            )

        try:
            response: Response = await call_next(request)
            # Success - reset failure count
            self._on_success(service)
            return response
        except Exception as exc:
            # Failure - increment failure count
            self._on_failure(service)
            raise exc

    def _get_service_from_path(self, path: str) -> str:
        """Map URL path to service name"""
        if path.startswith("/api/v1/observations"):
            return "observations"
        elif path.startswith("/api/v1/hazards"):
            return "hazards"
        elif path.startswith("/api/v1/simulation"):
            return "simulation"
        elif path.startswith("/api/v1/audit"):
            return "audit"
        else:
            return "general"

    def _allow_request(self, service: str) -> bool:
        """Check if request is allowed based on circuit breaker state"""
        state = self.state[service]

        if state == "CLOSED":
            return True
        elif state == "OPEN":
            # Check if timeout has passed to try HALF_OPEN
            if time.time() - self.last_failure_time[service] > self.timeout_seconds:
                self.state[service] = "HALF_OPEN"
                return True
            return False
        elif state == "HALF_OPEN":
            return True

        return False

    def _on_success(self, service: str):
        """Handle successful request"""
        self.failure_count[service] = 0
        self.state[service] = "CLOSED"

    def _on_failure(self, service: str):
        """Handle failed request"""
        self.failure_count[service] += 1
        self.last_failure_time[service] = time.time()

        if self.failure_count[service] >= self.failure_threshold:
            self.state[service] = "OPEN"
            logger.warning(f"Circuit breaker OPEN for service: {service} after {self.failure_count[service]} failures")


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Audit logging for security events"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Extract request info
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Process request
        try:
            response: Response = await call_next(request)
            status_code = response.status_code

            # Log authentication/authorization events
            if path.startswith("/api/v1/auth/") or "authorization" in path.lower():
                self._log_security_event(
                    event_type="AUTH_ATTEMPT",
                    method=method,
                    path=path,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    status_code=status_code,
                    processing_time=time.time() - start_time
                )

            # Log potential security events
            if status_code in [401, 403, 429]:
                self._log_security_event(
                    event_type="SECURITY_EVENT",
                    method=method,
                    path=path,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    status_code=status_code,
                    processing_time=time.time() - start_time
                )

            return response
        except Exception as exc:
            # Log exceptions
            self._log_security_event(
                event_type="EXCEPTION",
                method=method,
                path=path,
                client_ip=client_ip,
                user_agent=user_agent,
                status_code=500,
                processing_time=time.time() - start_time,
                error=str(exc)
            )
            raise exc

    def _log_security_event(
        self,
        event_type: str,
        method: str,
        path: str,
        client_ip: str,
        user_agent: str,
        status_code: int,
        processing_time: float,
        error: str = None
    ):
        """Log security event"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "method": method,
            "path": path,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "status_code": status_code,
            "processing_time_ms": round(processing_time * 1000, 2)
        }

        if error:
            log_data["error"] = error

        if status_code >= 400:
            logger.warning(f"Security event: {log_data}")
        else:
            logger.info(f"Security event: {log_data}")


def apply_security_middleware(app):
    """Apply all security middleware to the FastAPI app"""
    # Order matters - first added is outermost (executes first)
    app.add_middleware(AuditLoggingMiddleware)
    app.add_middleware(CircuitBreakerMiddleware, failure_threshold=5, timeout_seconds=60)
    app.add_middleware(TimeoutMiddleware, timeout_seconds=30.0)
    app.add_middleware(RateLimitMiddleware, calls_per_minute=60, burst_limit=10)
    app.add_middleware(SecurityHeadersMiddleware)

    return app