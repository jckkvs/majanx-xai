# server/middleware/security.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time
from collections import defaultdict

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 120, window: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self.client_reqs = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # WebSocket は除外
        if request.scope.get("type") == "websocket":
            return await call_next(request)
            
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        reqs = self.client_reqs[client_ip]
        reqs[:] = [t for t in reqs if now - t < self.window]
        if len(reqs) >= self.max_requests:
            raise HTTPException(429, "レートリミット超過。1分後にお試しください。")
        reqs.append(now)
        return await call_next(request)

def setup_security(app: FastAPI):
    # CORSMiddleware は main.py で一括管理するためここでは削除
    app.add_middleware(RateLimitMiddleware)
    
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
