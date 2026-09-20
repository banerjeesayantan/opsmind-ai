"""Config validation for the Grafana/Prometheus observability stack.

These are deliberately not integration tests against real Grafana/Prometheus
containers (that would need Docker, which this project's CI doesn't run) -
they validate the actual config files that ship in the repo: that they're
well-formed, wire together correctly, and - the check most likely to
silently rot - that every metric name a dashboard panel queries still
exists as a real metric in app.core.metrics. A metric getting renamed or
removed without updating the dashboard would otherwise only be discovered
by a human looking at a blank panel in Grafana.

Run with: pytest tests/test_grafana_config.py -v
"""

import json
import re
from pathlib import Path

import yaml

import app.core.metrics as metrics_module

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_PATH = REPO_ROOT / "grafana" / "dashboards" / "json" / "opsmind_overview.json"
DASHBOARDS_PROVIDER_PATH = REPO_ROOT / "grafana" / "dashboards" / "dashboards.yml"
DATASOURCE_PATH = REPO_ROOT / "grafana" / "datasources" / "datasources.yml"
PROMETHEUS_CONFIG_PATH = REPO_ROOT / "prometheus" / "prometheus.yml"
DOCKER_COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"

# prometheus_client strips the reserved "_total" suffix off Counter._name
# internally (it's re-appended only at scrape/exposition time), so
# reconstruct the actual exposed name the same way, or "http_requests_total"
# in a dashboard query would never match "http_requests" in the registry.
_DEFINED_METRIC_NAMES = set()
for _obj in vars(metrics_module).values():
    if not (hasattr(_obj, "_name") and hasattr(_obj, "_type")):
        continue
    _name = _obj._name
    if _obj._type == "counter" and not _name.endswith("_total"):
        _name += "_total"
    _DEFINED_METRIC_NAMES.add(_name)


def _load_dashboard() -> dict:
    return json.loads(DASHBOARD_PATH.read_text())


def _panel_exprs(dashboard: dict):
    for panel in dashboard["dashboard"]["panels"]:
        for target in panel["targets"]:
            yield panel["title"], target["expr"]


# A Histogram named "foo_seconds" registers as "foo_seconds_bucket" /
# "_sum" / "_count" in Prometheus; a query against the bucket/sum/count
# suffix is valid PromQL and should still resolve back to the base metric
# name defined in app.core.metrics.
_HISTOGRAM_SUFFIXES = ("_bucket", "_sum", "_count")


def _base_metric_name(name: str) -> str:
    for suffix in _HISTOGRAM_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


# --- Dashboard JSON structure ---------------------------------------------


def test_dashboard_json_is_well_formed():
    dashboard = _load_dashboard()
    assert dashboard["dashboard"]["uid"] == "opsmind-overview"
    assert dashboard["dashboard"]["title"]
    panels = dashboard["dashboard"]["panels"]
    assert len(panels) > 0
    for panel in panels:
        assert panel["title"]
        assert panel["datasource"] == "Prometheus"
        assert len(panel["targets"]) > 0
        for target in panel["targets"]:
            assert target["expr"]


def test_dashboard_covers_the_required_metric_categories():
    """The task asked for incident/HTTP/remediation/action/verification
    coverage specifically - this pins that down rather than trusting a
    panel count alone."""
    dashboard = _load_dashboard()
    all_exprs = " ".join(expr for _, expr in _panel_exprs(dashboard))

    assert "http_request" in all_exprs, "missing HTTP-level metrics"
    assert "opsmind_investigations_completed_total" in all_exprs, "missing incident/investigation metrics"
    assert "opsmind_remediations_by_risk_total" in all_exprs, "missing remediation metrics"
    assert "opsmind_action_executions_total" in all_exprs, "missing action-execution metrics"
    assert "opsmind_verifications_total" in all_exprs, "missing verification metrics"
    assert "opsmind_approvals_total" in all_exprs, "missing approval metrics"


def test_every_dashboard_metric_reference_exists_in_app_core_metrics():
    """Regression guard against silent dashboard rot: every metric name a
    panel queries must actually be defined in app.core.metrics. Catches
    the case where a metric is renamed/removed in code but the dashboard
    JSON isn't updated to match - which would otherwise only surface as a
    blank panel discovered by a human.
    """
    dashboard = _load_dashboard()
    identifier_pattern = re.compile(r"\b([a-z][a-z0-9_]*)\b")
    grouping_clause_pattern = re.compile(r"\b(?:by|without|on|group_left|group_right)\s*\([^)]*\)")

    # PromQL keywords/functions that look like identifiers but aren't metric names.
    not_functions = {
        "sum", "rate", "histogram_quantile", "avg", "count",
        "min", "max", "quantile",
    }

    referenced = set()
    for _, expr in _panel_exprs(dashboard):
        # Label lists in by(...)/without(...) clauses contain label names
        # (endpoint, status, risk_level, ...), not metric names - strip
        # them out before scanning, or they'd be mistaken for metrics.
        expr_without_grouping_clauses = grouping_clause_pattern.sub("", expr)
        for match in identifier_pattern.findall(expr_without_grouping_clauses):
            if match not in not_functions:
                referenced.add(_base_metric_name(match))

    unknown = referenced - _DEFINED_METRIC_NAMES
    assert not unknown, f"Dashboard references metrics not defined in app.core.metrics: {sorted(unknown)}"


# --- Grafana/Prometheus provisioning config --------------------------------


def test_dashboards_provider_config_points_at_the_dashboard_directory():
    config = yaml.safe_load(DASHBOARDS_PROVIDER_PATH.read_text())
    provider = config["providers"][0]
    assert provider["type"] == "file"
    assert provider["options"]["path"].endswith("/dashboards/json")


def test_datasource_config_defines_a_default_prometheus_datasource():
    config = yaml.safe_load(DATASOURCE_PATH.read_text())
    datasource = config["datasources"][0]
    assert datasource["name"] == "Prometheus"
    assert datasource["type"] == "prometheus"
    assert datasource["isDefault"] is True
    assert datasource["url"]


def test_prometheus_scrape_config_targets_the_app_metrics_endpoint():
    config = yaml.safe_load(PROMETHEUS_CONFIG_PATH.read_text())
    jobs = {job["job_name"]: job for job in config["scrape_configs"]}
    assert "fastapi" in jobs
    assert jobs["fastapi"]["metrics_path"] == "/metrics"
    targets = jobs["fastapi"]["static_configs"][0]["targets"]
    assert any("app" in t for t in targets), "expected the scrape target to reference the 'app' compose service"


def test_docker_compose_wires_grafana_prometheus_and_provisioning_together():
    """Config-level check that `docker-compose up` alone (no manual setup)
    would produce a working Grafana with the Prometheus datasource and
    OpsMind dashboard already provisioned - not a live Docker run (this
    environment doesn't have Docker available), but every piece of the
    wiring docker-compose depends on is verified to actually exist and be
    consistent.
    """
    compose = yaml.safe_load(DOCKER_COMPOSE_PATH.read_text())
    services = compose["services"]

    assert "prometheus" in services
    assert "grafana" in services

    grafana = services["grafana"]
    assert "prometheus" in grafana.get("depends_on", []), "grafana should wait for prometheus to be up"

    mounted_paths = " ".join(grafana.get("volumes", []))
    assert "./grafana/dashboards" in mounted_paths
    assert "./grafana/datasources" in mounted_paths

    # Every local (non-named-volume) path grafana/prometheus mount must
    # actually exist in the repo, or provisioning silently does nothing.
    for service_name in ("grafana", "prometheus"):
        for volume in services[service_name].get("volumes", []):
            local_path = volume.split(":")[0]
            if local_path.startswith("./"):
                assert (REPO_ROOT / local_path[2:]).exists(), f"{service_name} mounts missing path: {local_path}"
