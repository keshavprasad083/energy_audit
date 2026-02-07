# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Multi-site fleet analysis for comparing data centers across a portfolio."""

from __future__ import annotations

from pydantic import BaseModel, Field

from energy_audit.data.models import AuditResult, Grade


# ---------------------------------------------------------------------------
# Fleet models
# ---------------------------------------------------------------------------

class FleetSiteResult(BaseModel):
    """Aggregated audit metrics for a single site within a fleet."""

    site_name: str = Field(..., description="Unique name identifying this site")
    location: str = Field(..., description="Physical location of the site")
    server_count: int = Field(..., ge=0, description="Total servers at this site")
    overall_score: float = Field(
        ..., ge=0, le=100, description="Overall audit score (0-100)"
    )
    overall_grade: Grade = Field(..., description="Overall letter grade")
    pue: float = Field(..., ge=0, description="Average Power Usage Effectiveness")
    total_power_kw: float = Field(
        ..., ge=0, description="Average total facility power draw in kW"
    )
    zombie_count: int = Field(..., ge=0, description="Number of zombie servers detected")
    carbon_tonnes_year: float = Field(
        ..., ge=0,
        description="Estimated annual carbon emissions in metric tonnes CO2",
    )


class FleetReport(BaseModel):
    """Fleet-wide report aggregating metrics across all sites."""

    sites: list[FleetSiteResult] = Field(
        default_factory=list, description="Per-site audit summaries"
    )
    total_servers: int = Field(..., ge=0, description="Total servers across all sites")
    avg_score: float = Field(
        ..., ge=0, le=100, description="Average audit score across all sites"
    )
    best_site: str = Field(..., description="Site name with the highest overall score")
    worst_site: str = Field(..., description="Site name with the lowest overall score")
    total_power_kw: float = Field(
        ..., ge=0, description="Total power draw across all sites in kW"
    )
    total_carbon_tonnes_year: float = Field(
        ..., ge=0,
        description="Total estimated annual carbon emissions across all sites in tonnes CO2",
    )


# ---------------------------------------------------------------------------
# Fleet report builder
# ---------------------------------------------------------------------------

def _compute_site_pue(result: AuditResult) -> float:
    """Compute average PUE from energy readings, falling back to 0.0."""
    readings = result.data_center.energy_readings
    valid = [r.pue for r in readings if r.pue > 0]
    if not valid:
        return 0.0
    return round(sum(valid) / len(valid), 4)


def _compute_site_total_power_kw(result: AuditResult) -> float:
    """Compute average total facility power in kW from energy readings."""
    readings = result.data_center.energy_readings
    if not readings:
        return 0.0
    return round(
        sum(r.total_facility_power_kw for r in readings) / len(readings), 2
    )


def _compute_zombie_count(result: AuditResult) -> int:
    """Count servers flagged as zombies."""
    return sum(1 for s in result.data_center.servers if s.is_zombie)


def _compute_carbon_tonnes_year(result: AuditResult) -> float:
    """Estimate annual CO2 emissions in metric tonnes.

    Uses the average total facility power (kW) and the grid carbon intensity
    (gCO2/kWh) from the data-center configuration.  The formula:

        carbon_tonnes/year = avg_power_kw * 8760 h/yr * intensity_gCO2/kWh / 1_000_000
    """
    avg_power_kw = _compute_site_total_power_kw(result)
    intensity = result.data_center.config.carbon_intensity_gco2_per_kwh
    annual_kwh = avg_power_kw * 8760  # kW * hours/year = kWh/year
    carbon_g = annual_kwh * intensity
    carbon_tonnes = carbon_g / 1_000_000
    return round(carbon_tonnes, 2)


def build_fleet_report(results: dict[str, AuditResult]) -> FleetReport:
    """Build a fleet-wide report from per-site audit results.

    Parameters
    ----------
    results:
        Mapping of site name to the corresponding :class:`AuditResult`.

    Returns
    -------
    FleetReport
        Aggregated fleet report with per-site summaries and fleet-wide totals.
    """
    if not results:
        return FleetReport(
            sites=[],
            total_servers=0,
            avg_score=0.0,
            best_site="N/A",
            worst_site="N/A",
            total_power_kw=0.0,
            total_carbon_tonnes_year=0.0,
        )

    site_results: list[FleetSiteResult] = []

    for site_name, audit in results.items():
        dc = audit.data_center
        site = FleetSiteResult(
            site_name=site_name,
            location=dc.config.location,
            server_count=len(dc.servers),
            overall_score=audit.overall_score,
            overall_grade=audit.overall_grade,
            pue=_compute_site_pue(audit),
            total_power_kw=_compute_site_total_power_kw(audit),
            zombie_count=_compute_zombie_count(audit),
            carbon_tonnes_year=_compute_carbon_tonnes_year(audit),
        )
        site_results.append(site)

    total_servers = sum(s.server_count for s in site_results)
    avg_score = round(sum(s.overall_score for s in site_results) / len(site_results), 2)
    total_power = round(sum(s.total_power_kw for s in site_results), 2)
    total_carbon = round(sum(s.carbon_tonnes_year for s in site_results), 2)

    best = max(site_results, key=lambda s: s.overall_score)
    worst = min(site_results, key=lambda s: s.overall_score)

    return FleetReport(
        sites=site_results,
        total_servers=total_servers,
        avg_score=avg_score,
        best_site=best.site_name,
        worst_site=worst.site_name,
        total_power_kw=total_power,
        total_carbon_tonnes_year=total_carbon,
    )
