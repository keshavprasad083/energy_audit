# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Pro configuration model and YAML loader."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Credential handling
# ---------------------------------------------------------------------------

class CredentialRef(BaseModel):
    """Reference to credentials — supports env vars, file paths, or inline."""

    env_var: str | None = Field(default=None, description="Environment variable name")
    file_path: str | None = Field(default=None, description="Path to credentials file")
    value: str | None = Field(default=None, description="Inline value (dev only)")

    def resolve(self) -> str:
        """Resolve the credential to a plain string."""
        if self.env_var:
            val = os.environ.get(self.env_var)
            if val:
                return val
        if self.file_path:
            path = Path(self.file_path).expanduser()
            if path.exists():
                return path.read_text().strip()
        if self.value:
            return self.value
        raise ValueError(
            "Could not resolve credential: none of env_var, file_path, or value produced a result"
        )


# ---------------------------------------------------------------------------
# Source configuration
# ---------------------------------------------------------------------------

class CollectorSourceConfig(BaseModel):
    """Configuration for a single data collector source."""

    type: str = Field(
        ..., description="Collector type: snmp, ipmi, redfish, aws, azure, gcp, csv, json"
    )
    enabled: bool = Field(default=True)
    endpoints: list[str] = Field(
        default_factory=list, description="Hostnames, IPs, or file paths"
    )
    credentials: CredentialRef | None = Field(default=None)
    options: dict[str, Any] = Field(
        default_factory=dict, description="Collector-specific options"
    )
    timeout_seconds: int = Field(default=30, ge=1)
    retry_count: int = Field(default=2, ge=0)


# ---------------------------------------------------------------------------
# Facility metadata
# ---------------------------------------------------------------------------

class FacilityConfig(BaseModel):
    """Facility metadata that cannot be auto-discovered."""

    name: str
    location: str = Field(default="Unknown")
    region: str = Field(default="unknown")
    total_power_capacity_mw: float = Field(default=1.0, gt=0)
    energy_cost_per_kwh: float = Field(default=0.10, gt=0)
    carbon_intensity_gco2_per_kwh: float = Field(default=400.0, ge=0)
    renewable_percentage: float = Field(default=0.0, ge=0, le=1.0)
    ppa_available: bool = Field(default=False)
    energy_source: str = Field(default="grid")
    pue_target: float = Field(default=1.4, gt=1.0)
    cooling_type: str = Field(default="air")


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

class ProConfig(BaseModel):
    """Top-level pro configuration loaded from YAML."""

    facility: FacilityConfig
    sources: list[CollectorSourceConfig] = Field(min_length=1)
    collection_window_hours: int = Field(default=720, ge=1)
    parallel_collection: bool = Field(default=True)
    output_dir: str | None = Field(default=None)


def load_config(path: str | Path) -> ProConfig:
    """Load a ProConfig from a YAML file."""
    from energy_audit.pro import check_dependency
    check_dependency("yaml", "pip install -e '.[pro]'")

    import yaml

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return ProConfig.model_validate(raw)
