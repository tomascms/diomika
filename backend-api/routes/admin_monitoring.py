"""Monitoring API endpoints — health, metrics, and external service integration status."""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException

from core.auth import require_admin
from core.local_only import admin_must_be_local
from core.monitoring_hub import get_monitoring_hub, MonitoringProvider

logger = logging.getLogger("diomika-api")

router = APIRouter(
    prefix="/admin/monitoring",
    tags=["Admin Monitoring"],
    dependencies=[Depends(admin_must_be_local), Depends(require_admin)],
)


@router.get("/health")
def get_health():
    """Get overall system and external services health status."""
    hub = get_monitoring_hub()
    return hub.get_overall_health()


@router.get("/errors")
def get_error_summary(hours: int = 24):
    """Get aggregated error summary from Sentry and Axiom."""
    if hours < 1 or hours > 720:
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 720")
    hub = get_monitoring_hub()
    return hub.get_error_summary(hours=hours)


@router.get("/performance")
def get_performance(hours: int = 24):
    """Get performance metrics from Cloudflare and UptimeRobot."""
    if hours < 1 or hours > 720:
        raise HTTPException(status_code=400, detail="Hours must be between 1 and 720")
    hub = get_monitoring_hub()
    return hub.get_performance_metrics(hours=hours)


@router.get("/credentials/status")
def check_credentials_status():
    """Check which external services have credentials configured."""
    hub = get_monitoring_hub()
    return {
        "configured_services": hub.validate_all_credentials(),
        "message": "List of configured external monitoring services",
    }


@router.get("/cloudflare/analytics")
def get_cloudflare_analytics(period: str = "24h"):
    """Get Cloudflare edge analytics."""
    hub = get_monitoring_hub()
    if not hub.cloudflare.api_token:
        raise HTTPException(status_code=503, detail="Cloudflare not configured")
    return hub.cloudflare.get_analytics(period=period)


@router.get("/cloudflare/waf")
def get_cloudflare_waf(hours: int = 24):
    """Get Cloudflare WAF (firewall) events."""
    hub = get_monitoring_hub()
    if not hub.cloudflare.api_token:
        raise HTTPException(status_code=503, detail="Cloudflare not configured")
    return hub.cloudflare.get_waf_events(last_n_hours=hours)


@router.get("/sentry/issues")
def get_sentry_issues(status: str = "unresolved"):
    """Get Sentry issues."""
    hub = get_monitoring_hub()
    if not hub.sentry.auth_token:
        raise HTTPException(status_code=503, detail="Sentry not configured")
    if status not in ("unresolved", "resolved", "ignored"):
        raise HTTPException(status_code=400, detail="Invalid status filter")
    return hub.sentry.get_issues(status=status)


@router.post("/sentry/issues/{issue_id}/resolve")
def resolve_sentry_issue(issue_id: str):
    """Resolve a Sentry issue."""
    hub = get_monitoring_hub()
    if not hub.sentry.auth_token:
        raise HTTPException(status_code=503, detail="Sentry not configured")
    return hub.sentry.resolve_issue(issue_id)


@router.get("/axiom/errors")
def get_axiom_errors(hours: int = 24):
    """Get error metrics from Axiom."""
    hub = get_monitoring_hub()
    if not hub.axiom.api_token:
        raise HTTPException(status_code=503, detail="Axiom not configured")
    return hub.axiom.get_error_metrics(last_n_hours=hours)


@router.get("/axiom/logs")
def query_axiom_logs(q: str, limit: int = 100):
    """Execute APL query against Axiom logs."""
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter required")
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")
    hub = get_monitoring_hub()
    if not hub.axiom.api_token:
        raise HTTPException(status_code=503, detail="Axiom not configured")
    return hub.axiom.get_logs(query=q, limit=limit)


@router.get("/posthog/features/{feature_name}")
def get_posthog_feature(feature_name: str, days: int = 7):
    """Get PostHog feature usage analytics."""
    hub = get_monitoring_hub()
    if not hub.posthog.api_key:
        raise HTTPException(status_code=503, detail="PostHog not configured")
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
    return hub.posthog.get_feature_usage(feature_name=feature_name, days=days)


@router.get("/uptimerobot/monitors")
def get_uptimerobot_monitors():
    """List all UptimeRobot monitors."""
    hub = get_monitoring_hub()
    if not hub.uptimerobot.api_key:
        raise HTTPException(status_code=503, detail="UptimeRobot not configured")
    return hub.uptimerobot.get_monitors()


@router.get("/uptimerobot/uptime")
def get_uptimerobot_status(monitor_id: str = "all"):
    """Get uptime status from UptimeRobot."""
    hub = get_monitoring_hub()
    if not hub.uptimerobot.api_key:
        raise HTTPException(status_code=503, detail="UptimeRobot not configured")
    return hub.uptimerobot.get_uptime_status(monitor_id=monitor_id)


@router.get("/github/workflows")
def get_github_workflows(limit: int = 10):
    """Get recent GitHub workflow runs."""
    hub = get_monitoring_hub()
    if not hub.github.token:
        raise HTTPException(status_code=503, detail="GitHub not configured")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
    return hub.github.get_workflow_runs(limit=limit)


@router.get("/github/deployments")
def get_github_deployments():
    """Get latest GitHub deployment status."""
    hub = get_monitoring_hub()
    if not hub.github.token:
        raise HTTPException(status_code=503, detail="GitHub not configured")
    return hub.github.get_latest_deployment()
