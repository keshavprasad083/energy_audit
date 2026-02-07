# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Recommendation engine.

Orchestrates all analysis modules, calculates impact for each
potential recommendation, and produces a ranked list of actionable
:class:`~energy_audit.data.models.Recommendation` objects.
"""

from __future__ import annotations

from energy_audit.analysis.cooling_analyzer import analyze_cooling
from energy_audit.analysis.cost_projector import project_costs
from energy_audit.analysis.hardware_lifecycle import analyze_hardware_lifecycle
from energy_audit.analysis.overprovisioning import detect_overprovisioned
from energy_audit.analysis.renewable_advisor import analyze_renewable_opportunity
from energy_audit.analysis.workload_optimizer import analyze_workload_scheduling
from energy_audit.analysis.zombie_detector import detect_zombies
from energy_audit.data.models import BoxScore, DataCenter, Recommendation
from energy_audit.recommendations.impact_calculator import (
    calculate_cooling_impact,
    calculate_refresh_impact,
    calculate_renewable_impact,
    calculate_rightsizing_impact,
    calculate_scheduling_impact,
    calculate_zombie_impact,
)
from energy_audit.recommendations.templates import (
    CAPACITY_PLANNING,
    COOLING_UPGRADE,
    LEGACY_HARDWARE_REFRESH,
    OVERPROVISIONED_RIGHTSIZING,
    PUE_IMPROVEMENT,
    RENEWABLE_ENERGY,
    WORKLOAD_SCHEDULING,
    ZOMBIE_DECOMMISSION,
)

# Maximum number of recommendations to return.
_MAX_RECOMMENDATIONS = 15


class RecommendationEngine:
    """Generate ranked recommendations based on data-center analysis.

    Usage::

        engine = RecommendationEngine()
        recommendations = engine.generate(dc, box1, box2, box3)
    """

    def generate(
        self,
        dc: DataCenter,
        box1: BoxScore,
        box2: BoxScore,
        box3: BoxScore,
    ) -> list[Recommendation]:
        """Generate ranked recommendations based on analysis.

        Runs all analysis modules, calculates the financial and energy
        impact of each potential recommendation, sorts by monthly
        dollar savings (descending), assigns ranks, and returns the
        top recommendations as :class:`Recommendation` objects.

        Parameters
        ----------
        dc:
            The data-center snapshot to analyze.
        box1:
            Box 1 (Current Operations) score -- used for PUE insight.
        box2:
            Box 2 (Legacy & Waste) score -- used for zombie / legacy
            findings.
        box3:
            Box 3 (Future Readiness) score -- used for scheduling /
            renewable findings.

        Returns
        -------
        list[Recommendation]
            Ranked list of up to 15 recommendations sorted by
            ``monthly_savings_dollars`` descending.
        """
        config = dc.config
        candidates: list[dict] = []

        # ---------------------------------------------------------------
        # 1. Zombie decommissioning (Box 2)
        # ---------------------------------------------------------------
        zombie_data = detect_zombies(dc)
        if zombie_data:
            dollars, kwh = calculate_zombie_impact(zombie_data, config)
            total_waste_watts = sum(z["power_watts"] for z in zombie_data)
            description = ZOMBIE_DECOMMISSION.description_template.format(
                zombie_count=len(zombie_data),
                total_waste_kwh=sum(z["monthly_waste_kwh"] for z in zombie_data),
                monthly_savings=dollars,
                total_waste_watts=total_waste_watts,
            )
            candidates.append(
                {
                    "title": ZOMBIE_DECOMMISSION.title,
                    "description": description,
                    "box_number": ZOMBIE_DECOMMISSION.box_number,
                    "effort": ZOMBIE_DECOMMISSION.effort,
                    "impact": ZOMBIE_DECOMMISSION.impact,
                    "monthly_savings_dollars": dollars,
                    "monthly_energy_savings_kwh": kwh,
                }
            )

        # ---------------------------------------------------------------
        # 2. Over-provisioned rightsizing (Box 2)
        # ---------------------------------------------------------------
        overprov_data = detect_overprovisioned(dc)
        if overprov_data:
            dollars, kwh = calculate_rightsizing_impact(overprov_data, config)
            total_savings_watts = sum(s["potential_savings_watts"] for s in overprov_data)
            description = OVERPROVISIONED_RIGHTSIZING.description_template.format(
                overprovisioned_count=len(overprov_data),
                potential_savings_watts=total_savings_watts,
                monthly_savings=dollars,
            )
            candidates.append(
                {
                    "title": OVERPROVISIONED_RIGHTSIZING.title,
                    "description": description,
                    "box_number": OVERPROVISIONED_RIGHTSIZING.box_number,
                    "effort": OVERPROVISIONED_RIGHTSIZING.effort,
                    "impact": OVERPROVISIONED_RIGHTSIZING.impact,
                    "monthly_savings_dollars": dollars,
                    "monthly_energy_savings_kwh": kwh,
                }
            )

        # ---------------------------------------------------------------
        # 3. Legacy hardware refresh (Box 2)
        # ---------------------------------------------------------------
        lifecycle_data = analyze_hardware_lifecycle(dc)
        if lifecycle_data["refresh_candidates"] > 0:
            dollars, kwh = calculate_refresh_impact(lifecycle_data, config)
            description = LEGACY_HARDWARE_REFRESH.description_template.format(
                refresh_candidates=lifecycle_data["refresh_candidates"],
                past_warranty_count=lifecycle_data["past_warranty_count"],
                past_warranty_pct=lifecycle_data["past_warranty_pct"],
                estimated_savings_kwh=lifecycle_data["estimated_refresh_savings_kwh"],
                monthly_savings=dollars,
            )
            candidates.append(
                {
                    "title": LEGACY_HARDWARE_REFRESH.title,
                    "description": description,
                    "box_number": LEGACY_HARDWARE_REFRESH.box_number,
                    "effort": LEGACY_HARDWARE_REFRESH.effort,
                    "impact": LEGACY_HARDWARE_REFRESH.impact,
                    "monthly_savings_dollars": dollars,
                    "monthly_energy_savings_kwh": kwh,
                }
            )

        # ---------------------------------------------------------------
        # 4. Cooling upgrade (Box 1)
        # ---------------------------------------------------------------
        cooling_data = analyze_cooling(dc)
        if cooling_data["underperforming_systems"] or cooling_data["overloaded_systems"]:
            dollars, kwh = calculate_cooling_impact(cooling_data, config)
            description = COOLING_UPGRADE.description_template.format(
                underperforming_count=len(cooling_data["underperforming_systems"]),
                overloaded_count=len(cooling_data["overloaded_systems"]),
                improvement_kwh=cooling_data["improvement_potential_kwh"],
                monthly_savings=dollars,
                avg_cop=cooling_data["avg_cop"],
            )
            candidates.append(
                {
                    "title": COOLING_UPGRADE.title,
                    "description": description,
                    "box_number": COOLING_UPGRADE.box_number,
                    "effort": COOLING_UPGRADE.effort,
                    "impact": COOLING_UPGRADE.impact,
                    "monthly_savings_dollars": dollars,
                    "monthly_energy_savings_kwh": kwh,
                }
            )

        # ---------------------------------------------------------------
        # 5. Workload scheduling (Box 3)
        # ---------------------------------------------------------------
        scheduling_data = analyze_workload_scheduling(dc)
        if scheduling_data["schedulable_count"] > 0:
            dollars, kwh = calculate_scheduling_impact(scheduling_data)
            description = WORKLOAD_SCHEDULING.description_template.format(
                schedulable_count=scheduling_data["schedulable_count"],
                total_workloads=scheduling_data["total_workloads"],
                schedulable_pct=scheduling_data["schedulable_pct"],
                schedulable_power_kw=scheduling_data["schedulable_power_kw"],
                monthly_savings=dollars,
            )
            candidates.append(
                {
                    "title": WORKLOAD_SCHEDULING.title,
                    "description": description,
                    "box_number": WORKLOAD_SCHEDULING.box_number,
                    "effort": WORKLOAD_SCHEDULING.effort,
                    "impact": WORKLOAD_SCHEDULING.impact,
                    "monthly_savings_dollars": dollars,
                    "monthly_energy_savings_kwh": kwh,
                }
            )

        # ---------------------------------------------------------------
        # 6. Renewable energy (Box 3)
        # ---------------------------------------------------------------
        renewable_data = analyze_renewable_opportunity(dc)
        if renewable_data["renewable_opportunity_score"] > 20:
            dollars, kwh = calculate_renewable_impact(renewable_data)
            ppa_note = (
                "A Power Purchase Agreement is available, enabling cost-effective transition. "
                if renewable_data["ppa_available"]
                else ""
            )
            description = RENEWABLE_ENERGY.description_template.format(
                current_renewable_pct=renewable_data["current_renewable_pct"],
                carbon_reduction=renewable_data["potential_carbon_reduction_tons_monthly"],
                ppa_note=ppa_note,
                cost_impact=renewable_data["estimated_cost_impact_monthly"],
            )
            candidates.append(
                {
                    "title": RENEWABLE_ENERGY.title,
                    "description": description,
                    "box_number": RENEWABLE_ENERGY.box_number,
                    "effort": RENEWABLE_ENERGY.effort,
                    "impact": RENEWABLE_ENERGY.impact,
                    "monthly_savings_dollars": dollars,
                    "monthly_energy_savings_kwh": kwh,
                }
            )

        # ---------------------------------------------------------------
        # 7. PUE improvement (Box 1)
        # ---------------------------------------------------------------
        avg_pue = dc.avg_pue
        target_pue = config.pue_target
        if avg_pue > target_pue:
            pue_gap = avg_pue - target_pue
            # Savings from PUE improvement:
            # Current IT power * (current_PUE - target_PUE) gives
            # the overhead kW that would be eliminated.
            it_power_kw = 0.0
            if dc.energy_readings:
                it_power_kw = dc.energy_readings[-1].it_equipment_power_kw
            savings_kw = it_power_kw * pue_gap
            savings_kwh = savings_kw * 24 * 30
            savings_dollars = savings_kwh * config.energy_cost_per_kwh

            description = PUE_IMPROVEMENT.description_template.format(
                current_pue=avg_pue,
                target_pue=target_pue,
                pue_gap=pue_gap,
                savings_kwh=savings_kwh,
                monthly_savings=savings_dollars,
            )
            candidates.append(
                {
                    "title": PUE_IMPROVEMENT.title,
                    "description": description,
                    "box_number": PUE_IMPROVEMENT.box_number,
                    "effort": PUE_IMPROVEMENT.effort,
                    "impact": PUE_IMPROVEMENT.impact,
                    "monthly_savings_dollars": round(savings_dollars, 2),
                    "monthly_energy_savings_kwh": round(savings_kwh, 2),
                }
            )

        # ---------------------------------------------------------------
        # 8. Capacity planning (Box 3)
        # ---------------------------------------------------------------
        cost_data = project_costs(dc)
        if cost_data["growth_rate_pct"] > 1.0:
            # If costs are growing more than 1 %/month, recommend planning.
            # Estimated savings: moderating growth by 50 % saves half
            # the difference between projected and straight-line costs.
            projected = cost_data["projected_12mo_cost"]
            straight = cost_data["annual_projected"]
            potential_annual_savings = (projected - straight) * 0.5
            monthly_savings = potential_annual_savings / 12
            monthly_kwh = monthly_savings / config.energy_cost_per_kwh if config.energy_cost_per_kwh > 0 else 0.0

            description = CAPACITY_PLANNING.description_template.format(
                growth_rate=cost_data["growth_rate_pct"],
                projected_12mo=projected,
                annual_current=straight,
                monthly_savings=monthly_savings,
            )
            candidates.append(
                {
                    "title": CAPACITY_PLANNING.title,
                    "description": description,
                    "box_number": CAPACITY_PLANNING.box_number,
                    "effort": CAPACITY_PLANNING.effort,
                    "impact": CAPACITY_PLANNING.impact,
                    "monthly_savings_dollars": round(max(monthly_savings, 0.0), 2),
                    "monthly_energy_savings_kwh": round(max(monthly_kwh, 0.0), 2),
                }
            )

        # ---------------------------------------------------------------
        # Sort by monthly savings descending and assign ranks
        # ---------------------------------------------------------------
        candidates.sort(key=lambda c: c["monthly_savings_dollars"], reverse=True)

        recommendations: list[Recommendation] = []
        for rank, candidate in enumerate(candidates[:_MAX_RECOMMENDATIONS], start=1):
            recommendations.append(
                Recommendation(
                    rank=rank,
                    box_number=candidate["box_number"],
                    title=candidate["title"],
                    description=candidate["description"],
                    monthly_savings_dollars=candidate["monthly_savings_dollars"],
                    monthly_energy_savings_kwh=candidate["monthly_energy_savings_kwh"],
                    effort=candidate["effort"],
                    impact=candidate["impact"],
                )
            )

        return recommendations
