# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Recommendation template definitions.

Each template carries a static title, a description template string
with ``{placeholder}`` fields, and metadata used for sorting and
display (box_number, effort, impact).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationTemplate:
    """Immutable template for a single recommendation type."""

    title: str
    description_template: str
    box_number: int
    effort: str  # "low", "medium", "high"
    impact: str  # "low", "medium", "high"


ZOMBIE_DECOMMISSION = RecommendationTemplate(
    title="Decommission Zombie Servers",
    description_template=(
        "Identified {zombie_count} zombie servers consuming "
        "{total_waste_kwh:.0f} kWh/month with no productive workload. "
        "Decommissioning these servers would save an estimated "
        "${monthly_savings:,.2f}/month and reduce facility power by "
        "{total_waste_watts:.0f} W."
    ),
    box_number=2,
    effort="low",
    impact="high",
)

OVERPROVISIONED_RIGHTSIZING = RecommendationTemplate(
    title="Rightsize Over-Provisioned Servers",
    description_template=(
        "Found {overprovisioned_count} over-provisioned servers where "
        "allocated resources significantly exceed demand. Rightsizing "
        "these servers could reduce power consumption by "
        "{potential_savings_watts:.0f} W, saving approximately "
        "${monthly_savings:,.2f}/month."
    ),
    box_number=2,
    effort="medium",
    impact="medium",
)

LEGACY_HARDWARE_REFRESH = RecommendationTemplate(
    title="Refresh Legacy Hardware",
    description_template=(
        "{refresh_candidates} servers are candidates for hardware refresh "
        "(age > 48 months or past warranty). {past_warranty_count} servers "
        "({past_warranty_pct:.1f}%) have exceeded their warranty. "
        "Modern replacements are ~30% more efficient, potentially saving "
        "{estimated_savings_kwh:,.0f} kWh/month (${monthly_savings:,.2f}/month)."
    ),
    box_number=2,
    effort="high",
    impact="high",
)

COOLING_UPGRADE = RecommendationTemplate(
    title="Upgrade Underperforming Cooling Systems",
    description_template=(
        "{underperforming_count} cooling systems are operating below "
        "industry benchmark COP. {overloaded_count} systems are running "
        "above 85% capacity. Upgrading to benchmark efficiency could save "
        "{improvement_kwh:,.0f} kWh/month (${monthly_savings:,.2f}/month). "
        "Current average COP: {avg_cop:.2f}."
    ),
    box_number=1,
    effort="high",
    impact="high",
)

WORKLOAD_SCHEDULING = RecommendationTemplate(
    title="Optimize Workload Scheduling",
    description_template=(
        "{schedulable_count} of {total_workloads} workloads "
        "({schedulable_pct:.1f}%) are schedulable and could be shifted to "
        "off-peak hours. These workloads consume {schedulable_power_kw:.1f} kW. "
        "Off-peak scheduling could save approximately "
        "${monthly_savings:,.2f}/month."
    ),
    box_number=3,
    effort="low",
    impact="medium",
)

RENEWABLE_ENERGY = RecommendationTemplate(
    title="Increase Renewable Energy Adoption",
    description_template=(
        "Current renewable energy stands at {current_renewable_pct:.1f}%. "
        "Moving to 100% renewable could reduce carbon emissions by "
        "{carbon_reduction:.2f} tons CO2/month. "
        "{ppa_note}"
        "Estimated monthly cost impact: ${cost_impact:,.2f}."
    ),
    box_number=3,
    effort="medium",
    impact="high",
)

PUE_IMPROVEMENT = RecommendationTemplate(
    title="Improve Power Usage Effectiveness (PUE)",
    description_template=(
        "Current average PUE is {current_pue:.2f} against a target of "
        "{target_pue:.2f}. Reducing PUE by {pue_gap:.2f} points would "
        "save approximately {savings_kwh:,.0f} kWh/month "
        "(${monthly_savings:,.2f}/month). Focus on cooling efficiency, "
        "UPS optimization, and lighting upgrades."
    ),
    box_number=1,
    effort="medium",
    impact="high",
)

CAPACITY_PLANNING = RecommendationTemplate(
    title="Implement Proactive Capacity Planning",
    description_template=(
        "Energy consumption is growing at {growth_rate:.1f}%/month. "
        "Projected 12-month cost is ${projected_12mo:,.2f} "
        "(vs ${annual_current:,.2f} at current rate). "
        "Proactive capacity planning and workload consolidation could "
        "moderate growth and save approximately ${monthly_savings:,.2f}/month."
    ),
    box_number=3,
    effort="medium",
    impact="medium",
)
