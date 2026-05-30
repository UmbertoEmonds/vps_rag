from prometheus_client import Counter, Histogram, REGISTRY

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    labelnames=["endpoint", "method", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Duration of HTTP requests",
    labelnames=["endpoint"],
    buckets= [0.01, 0.05, 0.1, 0.25, 1.0, 2.0, 5.0, 10.0, 30.0]
)

ERROR_COUNT = Counter(
    "http_errors_total",
    "Total number of HTTP errors",
    labelnames=["endpoint"],
)
