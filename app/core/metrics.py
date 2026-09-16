"""Prometheus metrics configuration for the application.
 
This module sets up and configures Prometheus metrics for monitoring the application.
"""
 
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response
 
# Request metrics
http_requests_total = Counter("http_requests_total", "Total number of HTTP requests", ["method", "endpoint", "status"])
 
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds", ["method", "endpoint"]
)
 
# Database metrics
db_connections = Gauge("db_connections", "Number of active database connections")
 
llm_inference_duration_seconds = Histogram(
    "llm_inference_duration_seconds",
    "Time spent processing LLM inference",
    ["model"],
    buckets=[0.1, 0.3, 0.5, 1.0, 2.0, 5.0]
)
 
 
llm_stream_duration_seconds = Histogram(
    "llm_stream_duration_seconds",
    "Time spent processing LLM stream inference",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)
 
# --- Incident investigation/response observability (Phase 6) ---------------
# These cover the parts of the OpsMind pipeline that aren't plain HTTP
# requests: investigation runs, risk/approval decisions, action
# executions, and verification outcomes. Recorded from
# app.services.persistence.IncidentPersistenceService, the single
# choke-point every state transition already passes through, rather than
# scattered across API routes or graph nodes.
 
investigations_completed_total = Counter(
    "opsmind_investigations_completed_total",
    "Completed incident investigations, by whether a diagnosis was reached",
    ["outcome"],  # "diagnosed" | "unresolved"
)
 
diagnosis_confidence = Histogram(
    "opsmind_diagnosis_confidence",
    "Confidence score of reached diagnoses",
    buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0],
)
 
remediations_by_risk_total = Counter(
    "opsmind_remediations_by_risk_total",
    "Recommended remediations, by action type and classified risk level",
    ["action_type", "risk_level"],
)
 
approvals_total = Counter(
    "opsmind_approvals_total",
    "Approval requests, by resulting status",
    ["status"],  # "not_required" | "pending" | "approved" | "rejected"
)
 
action_executions_total = Counter(
    "opsmind_action_executions_total",
    "Remediation action execution attempts, by action type and outcome status",
    ["action_type", "status"],
)
 
verifications_total = Counter(
    "opsmind_verifications_total",
    "Post-action verification checks, by recovery verdict",
    ["recovered"],  # "true" | "false" | "unknown"
)
 
incident_time_to_resolution_seconds = Histogram(
    "opsmind_incident_time_to_resolution_seconds",
    "Wall-clock time from incident creation to RESOLVED/UNRESOLVED",
    buckets=[30, 60, 300, 600, 1800, 3600, 14400, 86400],
)
 
 
async def metrics(request: Request) -> Response:
    """ASGI route handler for GET /metrics - the Prometheus scrape target.
 
    A minimal, dependency-free replacement for starlette_prometheus.metrics
    (which is itself just this same generate_latest() call against the
    default registry) - swapped in alongside dropping
    starlette_prometheus.PrometheusMiddleware below.
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
 
 
def setup_metrics(app):
    """Register the Prometheus /metrics scrape endpoint.
 
    Per-request instrumentation (http_requests_total,
    http_request_duration_seconds) is already handled by
    app.core.middleware.MetricsMiddleware - registered separately in
    app.main - which labels by the plain request path and never inspects
    router internals, so it was never affected by the
    starlette_prometheus.PrometheusMiddleware bug this function used to
    also register here. That registration is removed rather than
    replaced, to avoid double-counting every request through two
    middlewares recording the same metrics.
 
    Args:
        app: FastAPI application instance
    """
    app.add_route("/metrics", metrics)