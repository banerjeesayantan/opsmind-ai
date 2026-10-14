"""Prometheus metric source adapter for OpsMind AI telemetry evidence collection."""

from datetime import datetime, UTC
from typing import Optional
import httpx
import structlog

from app.core.config import settings
from app.telemetry.interfaces import MetricSource
from app.telemetry.schemas import MetricPoint, TimeWindow

logger = structlog.get_logger()


class PrometheusMetricSource(MetricSource):
    """Adapter for retrieving time-series metrics from a live Prometheus instance.

    Queries the standard Prometheus HTTP API (/api/v1/query_range) for metric
    values within the incident's TimeWindow. If Prometheus is unreachable or returns
    an error, logs a warning and returns an empty list, allowing the investigation
    pipeline to proceed without crashing.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        query_template: Optional[str] = None,
        timeout: float = 5.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        """Initialize the Prometheus metric source.

        Args:
            base_url: Base URL of the Prometheus server (e.g. http://localhost:9090).
            query_template: PromQL query template supporting {service} formatting.
            timeout: HTTP request timeout in seconds.
            client: Optional httpx.AsyncClient for connection reuse or testing.
        """
        self.base_url = (base_url or getattr(settings, "PROMETHEUS_URL", "http://localhost:9090")).rstrip("/")
        self.query_template = query_template or 'rate(http_requests_total{{service="{service}"}}[1m])'
        self.timeout = timeout
        self._client = client

    async def fetch(self, service: str, time_window: TimeWindow) -> list[MetricPoint]:
        """Fetch metric points from Prometheus for the given service and time window.

        Args:
            service: Name of the service to query metrics for.
            time_window: The time range to filter metrics to.

        Returns:
            list[MetricPoint]: Parsed metric points, or empty list on failure.
        """
        query = self.query_template.format(service=service)
        url = f"{self.base_url}/api/v1/query_range"

        start_ts = time_window.start.timestamp()
        end_ts = time_window.end.timestamp()
        duration_seconds = max(1.0, end_ts - start_ts)
        # Determine step: roughly 15-30 data points across the window
        step = max(1, int(duration_seconds / 20))

        params = {
            "query": query,
            "start": str(start_ts),
            "end": str(end_ts),
            "step": f"{step}s",
        }

        try:
            if self._client is not None:
                resp = await self._client.get(url, params=params, timeout=self.timeout)
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, params=params, timeout=self.timeout)

            if resp.status_code != 200:
                logger.warning(
                    "prometheus_query_failed",
                    service=service,
                    status_code=resp.status_code,
                    response=resp.text[:200],
                )
                return []

            data = resp.json()
            if data.get("status") != "success":
                logger.warning("prometheus_non_success_status", service=service, data=data)
                return []

            results = data.get("data", {}).get("result", [])
            metric_points: list[MetricPoint] = []

            for item in results:
                metric_labels = item.get("metric", {})
                metric_name = metric_labels.get("__name__", "prometheus_metric")
                values = item.get("values", [])

                for val_entry in values:
                    if len(val_entry) >= 2:
                        ts, val_str = val_entry[0], val_entry[1]
                        try:
                            val_float = float(val_str)
                            dt = datetime.fromtimestamp(float(ts), tz=UTC)
                            metric_points.append(
                                MetricPoint(
                                    timestamp=dt,
                                    service=service,
                                    metric_name=metric_name,
                                    value=val_float,
                                    labels=metric_labels,
                                )
                            )
                        except (ValueError, TypeError):
                            continue

            return metric_points

        except Exception as exc:
            logger.warning(
                "prometheus_connection_error",
                service=service,
                url=url,
                error=str(exc),
            )
            return []
