"""Workload scheduling optimization analysis.

Evaluates the potential for shifting schedulable workloads to off-peak
hours to reduce energy costs.
"""

from __future__ import annotations

from energy_audit.data.models import DataCenter

# Assumed cost reduction when shifting workloads to off-peak hours.
_OFF_PEAK_SAVINGS_FRACTION = 0.15


def analyze_workload_scheduling(dc: DataCenter) -> dict:
    """Analyze workload scheduling optimization potential.

    Returns a dictionary with the following keys:

    - ``total_workloads`` -- total number of workloads
    - ``schedulable_count`` -- number of workloads marked as schedulable
    - ``schedulable_pct`` -- schedulable workloads as a percentage of total
    - ``schedulable_power_kw`` -- aggregate power draw of schedulable workloads in kW
    - ``estimated_monthly_savings_dollars`` -- estimated monthly cost savings
      from shifting schedulable workloads to off-peak hours

    Savings are estimated by assuming a 15 % cost reduction on the
    energy consumed by schedulable workloads when shifted to off-peak
    periods::

        monthly_energy_kwh = schedulable_power_kw * 24 * 30
        savings = monthly_energy_kwh * energy_cost_per_kwh * 0.15
    """
    workloads = dc.workloads
    total_workloads = len(workloads)

    if total_workloads == 0:
        return {
            "total_workloads": 0,
            "schedulable_count": 0,
            "schedulable_pct": 0.0,
            "schedulable_power_kw": 0.0,
            "estimated_monthly_savings_dollars": 0.0,
        }

    schedulable = [w for w in workloads if w.is_schedulable]
    schedulable_count = len(schedulable)
    schedulable_pct = (schedulable_count / total_workloads) * 100
    schedulable_power_kw = sum(w.power_consumption_kw for w in schedulable)

    monthly_energy_kwh = schedulable_power_kw * 24 * 30
    estimated_savings = (
        monthly_energy_kwh * dc.config.energy_cost_per_kwh * _OFF_PEAK_SAVINGS_FRACTION
    )

    return {
        "total_workloads": total_workloads,
        "schedulable_count": schedulable_count,
        "schedulable_pct": round(schedulable_pct, 2),
        "schedulable_power_kw": round(schedulable_power_kw, 2),
        "estimated_monthly_savings_dollars": round(estimated_savings, 2),
    }
