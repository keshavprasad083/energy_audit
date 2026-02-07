"""Zombie server detection and waste calculation.

Identifies servers that are powered on but performing no useful work,
calculating the associated energy waste and cost impact.
"""

from __future__ import annotations

from energy_audit.data.models import DataCenter, Server


def _is_zombie(server: Server) -> bool:
    """Determine whether a server qualifies as a zombie.

    A server is a zombie if:
    - Its ``is_zombie`` flag is already set, **or**
    - Its CPU utilization is below 5 % and it is not explicitly marked
      as needed (i.e. not overprovisioned -- overprovisioned servers are
      at least *intended* to run workloads, they just have too many
      resources allocated).
    """
    if server.is_zombie:
        return True
    return server.cpu_utilization < 0.05 and not server.is_overprovisioned


def detect_zombies(dc: DataCenter) -> list[dict]:
    """Return a list of zombie server details with waste calculations.

    Each entry in the returned list is a dictionary with the keys:

    - ``server_name`` -- human-readable server name
    - ``server_type`` -- hardware classification string
    - ``age_months`` -- server age in months
    - ``power_watts`` -- current measured power draw in watts
    - ``monthly_waste_kwh`` -- estimated monthly energy waste in kWh
    - ``monthly_waste_dollars`` -- estimated monthly cost waste in USD

    The monthly waste is computed as::

        monthly_power_waste_kwh = current_power_watts * 24 * 30 / 1000
        monthly_cost_waste = monthly_power_waste_kwh * dc.config.energy_cost_per_kwh
    """
    cost_per_kwh = dc.config.energy_cost_per_kwh
    zombies: list[dict] = []

    for server in dc.servers:
        if not _is_zombie(server):
            continue

        monthly_waste_kwh = server.current_power_watts * 24 * 30 / 1000
        monthly_waste_dollars = monthly_waste_kwh * cost_per_kwh

        zombies.append(
            {
                "server_name": server.name,
                "server_type": server.server_type.value,
                "age_months": server.age_months,
                "power_watts": server.current_power_watts,
                "monthly_waste_kwh": round(monthly_waste_kwh, 2),
                "monthly_waste_dollars": round(monthly_waste_dollars, 2),
            }
        )

    return zombies
