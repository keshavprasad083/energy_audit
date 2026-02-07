# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Impact calculation functions for each recommendation type.

Every function returns a ``(monthly_savings_dollars, monthly_energy_savings_kwh)``
tuple so the recommendation engine can rank by financial impact.
"""

from __future__ import annotations

from energy_audit.data.models import DataCenterConfig


# ---------------------------------------------------------------------------
# Zombie decommissioning
# ---------------------------------------------------------------------------

def calculate_zombie_impact(
    zombie_data: list[dict],
    dc_config: DataCenterConfig,
) -> tuple[float, float]:
    """Return (monthly_savings_dollars, monthly_energy_savings_kwh).

    Savings come directly from decommissioning zombie servers:
    the total monthly waste already calculated in the zombie detector.
    """
    total_kwh = sum(z["monthly_waste_kwh"] for z in zombie_data)
    total_dollars = sum(z["monthly_waste_dollars"] for z in zombie_data)
    return (round(total_dollars, 2), round(total_kwh, 2))


# ---------------------------------------------------------------------------
# Rightsizing over-provisioned servers
# ---------------------------------------------------------------------------

def calculate_rightsizing_impact(
    overprov_data: list[dict],
    dc_config: DataCenterConfig,
) -> tuple[float, float]:
    """Estimate savings from rightsizing overprovisioned servers.

    The potential savings in watts are converted to monthly kWh and
    then to dollars using the facility energy cost.
    """
    total_savings_watts = sum(s["potential_savings_watts"] for s in overprov_data)
    monthly_kwh = total_savings_watts * 24 * 30 / 1000
    monthly_dollars = monthly_kwh * dc_config.energy_cost_per_kwh
    return (round(monthly_dollars, 2), round(monthly_kwh, 2))


# ---------------------------------------------------------------------------
# Workload scheduling
# ---------------------------------------------------------------------------

def calculate_scheduling_impact(scheduling_data: dict) -> tuple[float, float]:
    """Estimate savings from workload scheduling optimization.

    The savings estimate is pre-computed by the workload optimizer.
    Energy savings are derived from the dollar savings and the assumed
    15 % off-peak discount.
    """
    monthly_dollars = scheduling_data.get("estimated_monthly_savings_dollars", 0.0)
    # Reverse-engineer kWh from the dollar savings.
    # The workload optimizer computes: savings = kwh * cost * 0.15
    # We only have the final dollar amount; approximate kWh saved as
    # a fraction of schedulable energy.
    schedulable_kwh = scheduling_data.get("schedulable_power_kw", 0.0) * 24 * 30
    monthly_kwh = schedulable_kwh * 0.15  # 15 % of schedulable energy
    return (round(monthly_dollars, 2), round(monthly_kwh, 2))


# ---------------------------------------------------------------------------
# Hardware refresh
# ---------------------------------------------------------------------------

def calculate_refresh_impact(
    lifecycle_data: dict,
    dc_config: DataCenterConfig,
) -> tuple[float, float]:
    """Estimate savings from hardware refresh.

    The lifecycle analyzer provides ``estimated_refresh_savings_kwh``
    based on a 30 % efficiency improvement for refresh candidates.
    """
    monthly_kwh = lifecycle_data.get("estimated_refresh_savings_kwh", 0.0)
    monthly_dollars = monthly_kwh * dc_config.energy_cost_per_kwh
    return (round(monthly_dollars, 2), round(monthly_kwh, 2))


# ---------------------------------------------------------------------------
# Cooling improvements
# ---------------------------------------------------------------------------

def calculate_cooling_impact(
    cooling_data: dict,
    dc_config: DataCenterConfig,
) -> tuple[float, float]:
    """Estimate savings from cooling improvements.

    Uses the ``improvement_potential_kwh`` value calculated by the
    cooling analyzer, which represents the energy savings if all
    underperforming systems were upgraded to benchmark COP.
    """
    monthly_kwh = cooling_data.get("improvement_potential_kwh", 0.0)
    monthly_dollars = monthly_kwh * dc_config.energy_cost_per_kwh
    return (round(monthly_dollars, 2), round(monthly_kwh, 2))


# ---------------------------------------------------------------------------
# Renewable energy
# ---------------------------------------------------------------------------

def calculate_renewable_impact(renewable_data: dict) -> tuple[float, float]:
    """Estimate impact of renewable energy adoption.

    For renewable energy, the "savings" represent cost impact (which may
    be positive or negative) and the "energy savings" represent the
    carbon reduction translated to an equivalent kWh metric.

    A negative cost impact (savings via PPA) is treated as a positive
    savings value.  A positive cost impact (premium) is treated as zero
    savings for ranking purposes -- the recommendation is still valuable
    for its environmental impact.
    """
    cost_impact = renewable_data.get("estimated_cost_impact_monthly", 0.0)

    # If the cost impact is negative (i.e. PPA savings), treat as savings.
    if cost_impact < 0:
        monthly_dollars = abs(cost_impact)
    else:
        monthly_dollars = 0.0

    # Use carbon reduction as a proxy for "energy equivalent" savings.
    # 1 ton CO2 ~ 2,000 kWh at typical grid intensity.
    carbon_tons = renewable_data.get("potential_carbon_reduction_tons_monthly", 0.0)
    equivalent_kwh = carbon_tons * 2000

    return (round(monthly_dollars, 2), round(equivalent_kwh, 2))
