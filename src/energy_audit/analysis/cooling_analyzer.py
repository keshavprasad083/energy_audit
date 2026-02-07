# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Cooling infrastructure efficiency analysis.

Evaluates the performance of cooling systems against industry benchmarks
and identifies opportunities for improvement.
"""

from __future__ import annotations

from energy_audit.data.models import DataCenter

# Industry benchmark COP values by cooling type.
_COP_BENCHMARKS: dict[str, float] = {
    "air": 3.5,
    "liquid": 6.0,
    "hybrid": 4.5,
}

# A cooling system is considered overloaded when its load exceeds this
# fraction of its rated capacity.
_OVERLOAD_THRESHOLD = 0.85


def analyze_cooling(dc: DataCenter) -> dict:
    """Analyze cooling efficiency across all cooling systems.

    Returns a dictionary with the following keys:

    - ``avg_cop`` -- average Coefficient of Performance across systems
    - ``cooling_systems_count`` -- total number of cooling systems
    - ``overloaded_systems`` -- list of system names exceeding 85 % capacity
    - ``underperforming_systems`` -- list of system names with COP below
      the type-specific benchmark
    - ``total_cooling_power_kw`` -- aggregate cooling power draw in kW
    - ``cooling_as_pct_of_total`` -- cooling power as a percentage of
      total facility power
    - ``improvement_potential_kwh`` -- estimated monthly kWh savings if
      all underperforming systems improved to their benchmark COP
    """
    systems = dc.cooling_systems

    if not systems:
        return {
            "avg_cop": 0.0,
            "cooling_systems_count": 0,
            "overloaded_systems": [],
            "underperforming_systems": [],
            "total_cooling_power_kw": 0.0,
            "cooling_as_pct_of_total": 0.0,
            "improvement_potential_kwh": 0.0,
        }

    total_cop = 0.0
    total_cooling_power_kw = 0.0
    overloaded: list[str] = []
    underperforming: list[str] = []
    improvement_potential_kw = 0.0

    for cs in systems:
        total_cop += cs.cop
        total_cooling_power_kw += cs.current_load_kw

        # Overloaded check: load_pct is a percentage (0-100 scale)
        if cs.load_pct > _OVERLOAD_THRESHOLD * 100:
            overloaded.append(cs.name or cs.id)

        # Benchmark lookup -- fall back to the air benchmark
        benchmark_cop = _COP_BENCHMARKS.get(cs.cooling_type.value, _COP_BENCHMARKS["air"])

        if cs.cop < benchmark_cop:
            underperforming.append(cs.name or cs.id)

            # Improvement potential: the current system uses more power
            # to remove the same amount of heat than a system at benchmark COP.
            # Power_saved = current_load * (1 - current_cop / benchmark_cop)
            if benchmark_cop > 0:
                saved_kw = cs.current_load_kw * (1 - cs.cop / benchmark_cop)
                improvement_potential_kw += max(saved_kw, 0.0)

    avg_cop = total_cop / len(systems)

    # Compute cooling as a percentage of total facility power.
    # Use the most recent energy reading if available.
    total_facility_power_kw = 0.0
    if dc.energy_readings:
        total_facility_power_kw = dc.energy_readings[-1].total_facility_power_kw

    if total_facility_power_kw > 0:
        cooling_pct = (total_cooling_power_kw / total_facility_power_kw) * 100
    else:
        cooling_pct = 0.0

    # Monthly improvement potential (kW -> kWh over 30 days * 24 hours)
    improvement_potential_kwh = improvement_potential_kw * 24 * 30

    return {
        "avg_cop": round(avg_cop, 2),
        "cooling_systems_count": len(systems),
        "overloaded_systems": overloaded,
        "underperforming_systems": underperforming,
        "total_cooling_power_kw": round(total_cooling_power_kw, 2),
        "cooling_as_pct_of_total": round(cooling_pct, 2),
        "improvement_potential_kwh": round(improvement_potential_kwh, 2),
    }
