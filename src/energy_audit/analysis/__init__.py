# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Domain analyzers for data center energy assessment."""

from energy_audit.analysis.zombie_detector import detect_zombies
from energy_audit.analysis.overprovisioning import detect_overprovisioned
from energy_audit.analysis.cooling_analyzer import analyze_cooling
from energy_audit.analysis.workload_optimizer import analyze_workload_scheduling
from energy_audit.analysis.cost_projector import project_costs
from energy_audit.analysis.hardware_lifecycle import analyze_hardware_lifecycle
from energy_audit.analysis.renewable_advisor import analyze_renewable_opportunity

__all__ = [
    "analyze_cooling",
    "analyze_hardware_lifecycle",
    "analyze_renewable_opportunity",
    "analyze_workload_scheduling",
    "detect_overprovisioned",
    "detect_zombies",
    "project_costs",
]
