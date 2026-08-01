import os
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class ProductionSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.limit = max(10, int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "60")))
        self.maximum_body = max(64_000, int(os.getenv("MAX_REQUEST_BYTES", "1000000")))
        self.requests = defaultdict(deque)
        self.lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        if int(request.headers.get("content-length", "0") or 0) > self.maximum_body:
            return JSONResponse({"error": "הבקשה גדולה מדי"}, status_code=413)
        if request.method != "GET" and request.url.path.startswith("/api/") and not self.allowed(client_key(request)):
            return JSONResponse({"error": "יותר מדי בקשות. נסה שוב בעוד דקה"}, status_code=429)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self'; img-src 'self' data:; connect-src 'self'"
        return response

    def allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            values = self.requests[key]
            while values and values[0] <= now - 60:
                values.popleft()
            if len(values) >= self.limit:
                return False
            values.append(now)
            return True


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else "unknown"
