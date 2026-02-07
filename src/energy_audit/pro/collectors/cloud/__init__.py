# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Cloud provider collectors for AWS, Azure, and GCP.

Submodules are imported lazily so that missing cloud SDKs do not
prevent the rest of the application from loading.  Each submodule
self-registers its collector with the central registry on import.

Available collectors (after import):
    - ``aws``  — :class:`~energy_audit.pro.collectors.cloud.aws.AWSCollector`
    - ``azure`` — :class:`~energy_audit.pro.collectors.cloud.azure.AzureCollector`
    - ``gcp``  — :class:`~energy_audit.pro.collectors.cloud.gcp.GCPCollector`
"""

from __future__ import annotations

import importlib
from typing import Any

_SUBMODULES = {
    "power_models": "energy_audit.pro.collectors.cloud.power_models",
    "aws": "energy_audit.pro.collectors.cloud.aws",
    "azure": "energy_audit.pro.collectors.cloud.azure",
    "gcp": "energy_audit.pro.collectors.cloud.gcp",
}


def __getattr__(name: str) -> Any:
    """Lazily import submodules on first attribute access."""
    if name in _SUBMODULES:
        return importlib.import_module(_SUBMODULES[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return list(_SUBMODULES.keys()) + ["load_all"]


def load_all() -> None:
    """Force-import every cloud collector so they self-register."""
    for modpath in _SUBMODULES.values():
        try:
            importlib.import_module(modpath)
        except ImportError:
            pass
