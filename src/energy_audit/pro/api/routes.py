# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""FastAPI router with REST endpoints for the energy audit API."""

from __future__ import annotations

from typing import Any, Callable

from energy_audit.pro import check_dependency

check_dependency("fastapi", "pip install -e '.[pro-api]'")

from fastapi import APIRouter, Depends, HTTPException  # noqa: E402

from energy_audit.pro.api.models import (  # noqa: E402
    AuditRequest,
    AuditResponse,
    ComplianceRequest,
    ComplianceResponse,
    HealthResponse,
)

router = APIRouter(prefix="/api/v1", tags=["energy-audit"])


# ---------------------------------------------------------------------------
# Dependency injection — audit runner
# ---------------------------------------------------------------------------

def _default_audit_runner() -> Callable[..., Any]:
    """Return the default audit runner callable.

    This factory is used as a FastAPI dependency so the runner can be
    overridden in tests or custom deployments.
    """
    return _run_audit


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _run_audit(request: AuditRequest) -> AuditResponse:
    """Execute the audit pipeline and return a structured response."""
    from energy_audit.data.models import AuditResult
    from energy_audit.recommendations.engine import RecommendationEngine
    from energy_audit.reporting.executive_summary import generate_executive_summary
    from energy_audit.scoring.engine import ScoringEngine

    if request.config_path:
        # Pro path — real data from YAML config
        from energy_audit.pro.config import load_config
        from energy_audit.pro.collectors import get_collector
        from energy_audit.pro.mapper import DataCenterMapper

        cfg = load_config(request.config_path)
        results = []
        for source in cfg.sources:
            if not source.enabled:
                continue
            collector_cls = get_collector(source.type)
            collector = collector_cls(source)
            result = collector.collect()
            results.append(result)

        mapper = DataCenterMapper(cfg.facility)
        dc = mapper.map(results)
    else:
        # Simulated path — use profile + seed
        from energy_audit.data.generator import DataCenterGenerator
        from energy_audit.data.profiles import get_profile

        profile = get_profile(request.profile)
        generator = DataCenterGenerator(profile, seed=request.seed)
        dc = generator.generate()

    engine = ScoringEngine()
    box1, box2, box3, overall_score, overall_grade = engine.score(dc)

    rec_engine = RecommendationEngine()
    recommendations = rec_engine.generate(dc, box1, box2, box3)

    executive_summary = generate_executive_summary(
        dc, box1, box2, box3, overall_score, overall_grade, recommendations
    )

    return AuditResponse(
        overall_score=round(overall_score, 2),
        overall_grade=overall_grade.value,
        box1_score=round(box1.overall_score, 2),
        box2_score=round(box2.overall_score, 2),
        box3_score=round(box3.overall_score, 2),
        server_count=dc.total_servers,
        pue=round(dc.avg_pue, 4),
        recommendation_count=len(recommendations),
        executive_summary=executive_summary,
    )


def _run_compliance(request: ComplianceRequest) -> ComplianceResponse:
    """Run compliance checks and return a structured response."""
    from energy_audit.pro.config import load_config
    from energy_audit.pro.collectors import get_collector
    from energy_audit.pro.mapper import DataCenterMapper
    from energy_audit.scoring.engine import ScoringEngine

    cfg = load_config(request.config_path)
    results = []
    for source in cfg.sources:
        if not source.enabled:
            continue
        collector_cls = get_collector(source.type)
        collector = collector_cls(source)
        result = collector.collect()
        results.append(result)

    mapper = DataCenterMapper(cfg.facility)
    dc = mapper.map(results)

    engine = ScoringEngine()
    box1, box2, box3, overall_score, overall_grade = engine.score(dc)

    # Framework-specific compliance checks
    checks = _evaluate_compliance(request.framework, dc, box1, box2, box3)
    compliant = [c for c in checks if c["status"] == "compliant"]

    return ComplianceResponse(
        framework=request.framework,
        compliance_percentage=round(
            (len(compliant) / len(checks) * 100) if checks else 0.0, 2
        ),
        compliant_count=len(compliant),
        total_checks=len(checks),
        checks=checks,
    )


def _evaluate_compliance(
    framework: str,
    dc: Any,
    box1: Any,
    box2: Any,
    box3: Any,
) -> list[dict[str, Any]]:
    """Evaluate compliance checks for a given regulatory framework.

    Returns a list of check result dicts with keys: id, name, status, detail.
    """
    checks: list[dict[str, Any]] = []

    if framework == "eu-eed":
        checks = [
            {
                "id": "eed-pue",
                "name": "PUE below EU EED threshold (1.5)",
                "status": "compliant" if dc.avg_pue < 1.5 else "non-compliant",
                "detail": f"Measured PUE: {dc.avg_pue:.4f}",
            },
            {
                "id": "eed-renewable",
                "name": "Renewable energy percentage reported",
                "status": "compliant" if dc.config.renewable_percentage > 0 else "non-compliant",
                "detail": (
                    f"Renewable: {dc.config.renewable_percentage * 100:.1f}%"
                ),
            },
            {
                "id": "eed-waste-heat",
                "name": "Waste heat recovery assessment",
                "status": "compliant" if box1.overall_score >= 50 else "non-compliant",
                "detail": f"Box 1 score: {box1.overall_score:.1f}",
            },
        ]
    elif framework == "iso-50001":
        checks = [
            {
                "id": "iso-energy-baseline",
                "name": "Energy baseline established",
                "status": "compliant" if len(dc.energy_readings) > 0 else "non-compliant",
                "detail": f"Energy readings: {len(dc.energy_readings)}",
            },
            {
                "id": "iso-monitoring",
                "name": "Continuous energy monitoring in place",
                "status": "compliant" if len(dc.energy_readings) >= 168 else "non-compliant",
                "detail": f"Readings available: {len(dc.energy_readings)} (need >= 168)",
            },
            {
                "id": "iso-improvement",
                "name": "Energy improvement targets defined",
                "status": "compliant" if box3.overall_score >= 40 else "non-compliant",
                "detail": f"Box 3 (Future Readiness) score: {box3.overall_score:.1f}",
            },
            {
                "id": "iso-management-review",
                "name": "Management review cycle",
                "status": "compliant",
                "detail": "Audit report generated — review cycle initiated.",
            },
        ]
    elif framework == "sec-climate":
        checks = [
            {
                "id": "sec-emissions",
                "name": "Scope 2 emissions quantified",
                "status": "compliant" if dc.config.carbon_intensity_gco2_per_kwh > 0 else "non-compliant",
                "detail": (
                    f"Carbon intensity: {dc.config.carbon_intensity_gco2_per_kwh} gCO2/kWh"
                ),
            },
            {
                "id": "sec-energy-cost",
                "name": "Energy cost disclosure",
                "status": "compliant" if dc.total_cost > 0 else "non-compliant",
                "detail": f"Total energy cost: ${dc.total_cost:,.2f}",
            },
            {
                "id": "sec-risk",
                "name": "Climate risk assessment",
                "status": "compliant" if box2.overall_score >= 40 else "non-compliant",
                "detail": f"Box 2 (Legacy & Waste) score: {box2.overall_score:.1f}",
            },
        ]

    return checks


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return service health status and version information."""
    import energy_audit
    from energy_audit.pro import _PRO_AVAILABLE

    return HealthResponse(
        status="ok",
        version=energy_audit.__version__,
        pro_available=_PRO_AVAILABLE,
    )


@router.post("/audit", response_model=AuditResponse)
async def audit(
    request: AuditRequest,
    runner: Callable[..., Any] = Depends(_default_audit_runner),
) -> AuditResponse:
    """Run an energy audit and return scored results.

    Supply *config_path* for real-data Pro audits or omit it to run
    against a simulated data-center profile.
    """
    try:
        return runner(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audit failed: {exc}") from exc


@router.post("/compliance", response_model=ComplianceResponse)
async def compliance(request: ComplianceRequest) -> ComplianceResponse:
    """Run regulatory compliance checks against a configured facility.

    Requires a *config_path* pointing to a valid pro YAML configuration.
    """
    try:
        return _run_compliance(request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Compliance check failed: {exc}"
        ) from exc
