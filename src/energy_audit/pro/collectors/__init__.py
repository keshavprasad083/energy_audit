# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Data collectors for ingesting real infrastructure data."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from energy_audit.pro.collectors.base import DataCollector

COLLECTOR_REGISTRY: dict[str, type[DataCollector]] = {}


def register_collector(name: str, cls: type[DataCollector]) -> None:
    """Register a collector class by name."""
    COLLECTOR_REGISTRY[name] = cls


def get_collector(name: str) -> type[DataCollector]:
    """Look up a registered collector by name."""
    # Lazy-import known collectors to populate the registry
    if not COLLECTOR_REGISTRY:
        _load_builtin_collectors()

    if name not in COLLECTOR_REGISTRY:
        available = ", ".join(sorted(COLLECTOR_REGISTRY.keys()))
        raise KeyError(f"Unknown collector '{name}'. Available: {available}")
    return COLLECTOR_REGISTRY[name]


def _load_builtin_collectors() -> None:
    """Import built-in collectors so they self-register."""
    try:
        from energy_audit.pro.collectors import file_import  # noqa: F401
    except ImportError:
        pass
    try:
        from energy_audit.pro.collectors import snmp  # noqa: F401
    except ImportError:
        pass
    try:
        from energy_audit.pro.collectors import ipmi  # noqa: F401
    except ImportError:
        pass
    try:
        from energy_audit.pro.collectors import redfish  # noqa: F401
    except ImportError:
        pass
    try:
        from energy_audit.pro.collectors.cloud import load_all as _load_cloud
        _load_cloud()
    except ImportError:
        pass
