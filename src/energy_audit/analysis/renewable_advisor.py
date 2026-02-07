# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Renewable energy opportunity analysis.

Evaluates the potential for increasing renewable energy adoption and
estimates the environmental and financial impact.
"""

from __future__ import annotations

from energy_audit.data.models import DataCenter

# Typical renewable energy premium per kWh for facilities currently
# below 50 % renewable.
_RENEWABLE_PREMIUM_PER_KWH = 0.03  # $0.03

# Typical PPA savings per kWh when a Power Purchase Agreement is available.
_PPA_SAVINGS_PER_KWH = 0.01  # $0.01


def analyze_renewable_opportunity(dc: DataCenter) -> dict:
    """Analyze renewable energy adoption opportunity.

    Returns a dictionary with the following keys:

    - ``current_renewable_pct`` -- current renewable fraction as a
      percentage (0-100)
    - ``ppa_available`` -- whether a Power Purchase Agreement is in place
    - ``current_carbon_intensity`` -- grid carbon intensity in gCO2/kWh
    - ``potential_carbon_reduction_tons_monthly`` -- estimated monthly
      CO2 reduction in metric tons if moved to 100 % renewable
    - ``renewable_opportunity_score`` -- score from 0 to 100 indicating
      how much room there is for improvement (higher = more opportunity)
    - ``estimated_cost_impact_monthly`` -- estimated monthly cost change
      from increasing renewable percentage; positive means added cost,
      negative means savings (e.g. through PPA)

    Carbon reduction is based on the facility's total monthly energy
    consumption and the proportion that is currently *non-renewable*::

        non_renewable_kwh = total_monthly_kwh * (1 - renewable_fraction)
        carbon_reduction_kg = non_renewable_kwh * carbon_intensity_gco2 / 1000
        carbon_reduction_tons = carbon_reduction_kg / 1000
    """
    config = dc.config

    current_renewable_pct = config.renewable_percentage * 100
    ppa_available = config.ppa_available
    carbon_intensity = config.carbon_intensity_gco2_per_kwh

    # Monthly energy consumption (total_energy_kwh covers the 30-day window).
    total_monthly_kwh = dc.total_energy_kwh

    # Fraction of energy that is currently non-renewable.
    non_renewable_fraction = 1.0 - config.renewable_percentage
    non_renewable_kwh = total_monthly_kwh * non_renewable_fraction

    # Carbon reduction if all non-renewable energy were replaced.
    carbon_reduction_kg = non_renewable_kwh * carbon_intensity / 1000
    carbon_reduction_tons = carbon_reduction_kg / 1000

    # Opportunity score: more room to grow -> higher score.
    # Scale: 0 at 100 % renewable, 100 at 0 % renewable.
    # Bonus points if PPA is available (easier to act on).
    base_score = non_renewable_fraction * 100
    if ppa_available:
        base_score = min(base_score + 10, 100.0)
    renewable_opportunity_score = round(base_score, 1)

    # Cost impact estimation.
    if ppa_available:
        # PPA typically offers savings on non-renewable portion.
        cost_impact = -(non_renewable_kwh * _PPA_SAVINGS_PER_KWH)
    elif config.renewable_percentage < 0.5:
        # Below 50 % renewable: switching has a premium.
        cost_impact = non_renewable_kwh * _RENEWABLE_PREMIUM_PER_KWH
    else:
        # Above 50 % renewable: economies of scale bring down the premium.
        cost_impact = non_renewable_kwh * (_RENEWABLE_PREMIUM_PER_KWH * 0.5)

    return {
        "current_renewable_pct": round(current_renewable_pct, 2),
        "ppa_available": ppa_available,
        "current_carbon_intensity": carbon_intensity,
        "potential_carbon_reduction_tons_monthly": round(carbon_reduction_tons, 2),
        "renewable_opportunity_score": renewable_opportunity_score,
        "estimated_cost_impact_monthly": round(cost_impact, 2),
    }
