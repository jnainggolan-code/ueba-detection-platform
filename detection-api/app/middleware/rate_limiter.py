"""
Rate Limiting Middleware for FastAPI/Starlette.

This module provides a sliding window rate limiter middleware based on client source IP.
It uses an in-memory dictionary to track requests and includes a periodic background
cleanup task to prevent memory leaks.
"""

import asyncio
import logging
import math
import os
import time
from typing import Dict, List, Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces a sliding window rate limit per source IP address.

    Attributes:
        max_requests (int): Maximum requests allowed within the window.
        window_seconds (int): Width of the sliding window in seconds.
        ip_windows (Dict[str, List[float]]): In-memory store of request timestamps per IP.
        lock (asyncio.Lock): Lock to ensure async safety for in-memory store operations.
        cleanup_task (Optional[asyncio.Task]): Background task for periodic cleanup.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_requests: Optional[int] = None,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)

        if max_requests is None:
            env_val = os.getenv("RATE_LIMIT_PER_MINUTE")
            if env_val is not None:
                try:
                    max_requests = int(env_val)
                    logger.info(
                        "Configured RateLimitMiddleware with max_requests=%d (from RATE_LIMIT_PER_MINUTE)",
                        max_requests,
                    )
                except ValueError:
                    logger.warning(
                        "Invalid RATE_LIMIT_PER_MINUTE env var value: '%s'. Falling back to default 100.",
                        env_val,
                    )
                    max_requests = 100
            else:
                max_requests = 100
                logger.info(
                    "Configured RateLimitMiddleware with default max_requests=100",
                )
        else:
            logger.info(
                "Configured RateLimitMiddleware with constructor max_requests=%d",
                max_requests,
            )

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.ip_windows: Dict[str, List[float]] = {}
        self.lock = asyncio.Lock()
        self.cleanup_task: Optional[asyncio.Task] = None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Intercept incoming requests to check rate limit."""
        # Initialize cleanup task on the first request
        if self.cleanup_task is None:
            async with self.lock:
                if self.cleanup_task is None:
                    self.cleanup_task = asyncio.create_task(
                        self._periodic_cleanup(),
                        name="rate-limiter-cleanup",
                    )
                    logger.debug("Started rate limiter periodic cleanup task")

        client_ip = self._get_client_ip(request)
        now = time.monotonic()

        async with self.lock:
            timestamps = self.ip_windows.get(client_ip, [])
            valid_timestamps = [
                t for t in timestamps if now - t < self.window_seconds
            ]

            if len(valid_timestamps) >= self.max_requests:
                earliest_ts = valid_timestamps[0]
                retry_after = max(
                    1, math.ceil(earliest_ts + self.window_seconds - now)
                )
                logger.warning(
                    "Rate limit exceeded for IP: %s. Requests: %d/%d in %ds. Blocked for %ds.",
                    client_ip,
                    len(valid_timestamps),
                    self.max_requests,
                    self.window_seconds,
                    retry_after,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many requests",
                        "retry_after": retry_after,
                    },
                    headers={"Retry-After": str(retry_after)},
                )

            valid_timestamps.append(now)
            self.ip_windows[client_ip] = valid_timestamps

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract the client IP from the request."""
        client_ip: Optional[str] = None
        if request.client and request.client.host:
            client_ip = request.client.host
        else:
            x_forwarded_for = request.headers.get("x-forwarded-for")
            if x_forwarded_for:
                client_ip = x_forwarded_for.split(",")[0].strip()
        return client_ip or "127.0.0.1"

    async def _periodic_cleanup(self) -> None:
        """Periodically clean up expired entries from the IP store."""
        while True:
            try:
                await asyncio.sleep(60)
                now = time.monotonic()
                async with self.lock:
                    expired_ips = []
                    for ip, timestamps in list(self.ip_windows.items()):
                        valid_timestamps = [
                            t for t in timestamps if now - t < self.window_seconds
                        ]
                        if not valid_timestamps:
                            expired_ips.append(ip)
                        else:
                            self.ip_windows[ip] = valid_timestamps
                    for ip in expired_ips:
                        self.ip_windows.pop(ip, None)
                logger.debug(
                    "Completed rate limiter cleanup. Removed %d inactive IPs.",
                    len(expired_ips),
                )
            except asyncio.CancelledError:
                logger.debug("Rate limiter cleanup task cancelled")
                break
            except Exception as e:
                logger.error(
                    "Error in rate limiter cleanup task: %s",
                    str(e),
                    exc_info=True,
                )
