# core/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import time

REQ_TOTAL = Counter("http_requests_total", "Total HTTP Requests", ["method", "endpoint", "status"])
REQ_LATENCY = Histogram("http_request_duration_seconds", "HTTP Request Latency")
WS_CONNECTIONS = Gauge("websocket_active_connections", "Active WebSocket Connections")
AI_INFERENCE_TIME = Histogram("ai_inference_duration_seconds", "AI Inference Time")

class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/metrics":
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
        
        if scope["type"] == "http":
            start = time.time()
            async def wrapped_send(message):
                if message["type"] == "http.response.start":
                    status = str(message.get("status", 500))
                    REQ_TOTAL.labels(method=scope["method"], endpoint=scope["path"], status=status).inc()
                    REQ_LATENCY.observe(time.time() - start)
                await send(message)
            await self.app(scope, receive, send=wrapped_send)
        else:
            await self.app(scope, receive, send)
