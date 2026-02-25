from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "fastapi_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "fastapi_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
)
SSE_CLIENTS_CONNECTED = Gauge("fastapi_sse_clients_connected", "Connected SSE clients")
FLEET_MESSAGES_TOTAL = Counter("fleet_messages_processed_total", "Total messages processed")
FLEET_PROCESSING_ERRORS_TOTAL = Counter("fleet_processing_errors_total", "Total processing errors")
FLEET_EVENT_AGE_SECONDS = Gauge("fleet_event_age_seconds", "Age of latest processed event in seconds")


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
