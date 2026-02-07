"""Cost projection analysis.

Projects future energy costs based on current spending and consumption
trends observed over the readings window.
"""

from __future__ import annotations

from energy_audit.data.models import DataCenter


def project_costs(dc: DataCenter) -> dict:
    """Project future costs based on current trends.

    The data center snapshot contains up to 720 hourly energy readings
    (30 days).  The ``total_cost`` computed field on :class:`DataCenter`
    represents the total cost for that 30-day window.

    This function computes:

    - ``current_monthly`` -- total cost for the 30-day readings window
    - ``annual_projected`` -- simple annualised cost (monthly * 12)
    - ``growth_rate_pct`` -- percentage growth of facility power between
      the first 7 days and the last 7 days of readings
    - ``projected_12mo_cost`` -- 12-month cost projection incorporating
      the observed growth rate (compounded monthly)
    - ``cost_per_server_monthly`` -- average monthly cost per server

    Growth rate is estimated by comparing the average facility power in
    the first 168 readings (7 days) to the last 168 readings.  If the
    readings window is shorter than 14 days the growth rate defaults to
    zero.
    """
    current_monthly = dc.total_cost
    annual_projected = current_monthly * 12

    # Determine growth rate from energy readings trend.
    growth_rate_pct = 0.0
    readings = dc.energy_readings

    week_hours = 7 * 24  # 168 hourly readings

    if len(readings) >= 2 * week_hours:
        first_week = readings[:week_hours]
        last_week = readings[-week_hours:]

        avg_first = sum(r.total_facility_power_kw for r in first_week) / len(first_week)
        avg_last = sum(r.total_facility_power_kw for r in last_week) / len(last_week)

        if avg_first > 0:
            # Growth over the ~23-day gap between the midpoints of the
            # two windows.  Normalise to a monthly rate.
            raw_growth = (avg_last - avg_first) / avg_first
            # The gap between the midpoints of the first and last week
            # is roughly (len(readings) - week_hours) hours.
            gap_hours = len(readings) - week_hours
            gap_months = gap_hours / (24 * 30) if gap_hours > 0 else 1.0
            growth_rate_pct = (raw_growth / gap_months) * 100 if gap_months > 0 else 0.0

    # Project 12 months with monthly compounding.
    monthly_growth_rate = growth_rate_pct / 100  # as fraction
    if monthly_growth_rate != 0.0:
        projected_12mo_cost = 0.0
        for month in range(12):
            projected_12mo_cost += current_monthly * ((1 + monthly_growth_rate) ** month)
    else:
        projected_12mo_cost = annual_projected

    # Cost per server.
    total_servers = dc.total_servers
    cost_per_server = current_monthly / total_servers if total_servers > 0 else 0.0

    return {
        "current_monthly": round(current_monthly, 2),
        "annual_projected": round(annual_projected, 2),
        "growth_rate_pct": round(growth_rate_pct, 2),
        "projected_12mo_cost": round(projected_12mo_cost, 2),
        "cost_per_server_monthly": round(cost_per_server, 2),
    }
