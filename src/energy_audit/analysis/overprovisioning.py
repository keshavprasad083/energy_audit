"""Over-provisioned server detection and rightsizing analysis.

Identifies servers where allocated resources significantly exceed actual
demand, and estimates the power savings achievable through rightsizing.
"""

from __future__ import annotations

from energy_audit.data.models import DataCenter, Server


def _is_overprovisioned(server: Server) -> bool:
    """Determine whether a server qualifies as overprovisioned.

    A server is overprovisioned if:
    - Its ``is_overprovisioned`` flag is already set, **or**
    - Its memory utilization exceeds 70 % while CPU utilization is
      below 20 %, indicating the workload could run on a smaller
      machine (memory-bound but CPU-idle).
    """
    if server.is_overprovisioned:
        return True
    return server.memory_utilization > 0.7 and server.cpu_utilization < 0.2


def detect_overprovisioned(dc: DataCenter) -> list[dict]:
    """Return a list of overprovisioned server details.

    Each entry in the returned list is a dictionary with the keys:

    - ``server_name`` -- human-readable server name
    - ``cpu_util`` -- CPU utilization fraction (0.0-1.0)
    - ``memory_util`` -- memory utilization fraction (0.0-1.0)
    - ``gpu_util`` -- GPU utilization fraction (0.0-1.0)
    - ``current_power`` -- current measured power draw in watts
    - ``potential_savings_watts`` -- estimated watts saved by rightsizing

    The potential savings are computed as::

        potential_savings = current_power_watts - (tdp_watts * 0.3)

    The 0.3 factor represents the approximate power draw of a
    right-sized replacement running the same workload.  When the
    calculated savings would be negative (server already efficient),
    savings are clamped to zero.
    """
    results: list[dict] = []

    for server in dc.servers:
        if not _is_overprovisioned(server):
            continue

        potential_savings = server.current_power_watts - (server.tdp_watts * 0.3)
        potential_savings = max(potential_savings, 0.0)

        results.append(
            {
                "server_name": server.name,
                "cpu_util": server.cpu_utilization,
                "memory_util": server.memory_utilization,
                "gpu_util": server.gpu_utilization,
                "current_power": server.current_power_watts,
                "potential_savings_watts": round(potential_savings, 2),
            }
        )

    return results
