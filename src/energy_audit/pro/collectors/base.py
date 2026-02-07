# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Abstract collector protocol and raw data models.

Every collector must produce a :class:`CollectorResult` containing
:class:`RawServerData` and :class:`RawEnergyReading` instances.
The mapper then converts these into the core ``DataCenter`` model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Raw data models (collected from real sources)
# ---------------------------------------------------------------------------

class RawServerData(BaseModel):
    """Raw server data from any collector. All fields optional — the mapper
    merges data from multiple collectors and fills gaps with defaults."""

    hostname: str = Field(..., description="Server hostname or identifier")
    ip_address: str | None = None
    server_type_hint: str | None = Field(
        default=None, description="Hint: cpu, gpu_training, gpu_inference, storage"
    )

    # Power
    power_watts: float | None = None
    tdp_watts: float | None = None

    # Utilization (0.0-1.0)
    cpu_utilization: float | None = None
    gpu_utilization: float | None = None
    memory_utilization: float | None = None
    memory_total_gb: float | None = None
    memory_used_gb: float | None = None

    # Thermal
    inlet_temp_celsius: float | None = None
    outlet_temp_celsius: float | None = None

    # Asset
    model: str | None = None
    serial: str | None = None
    firmware_version: str | None = None
    age_months: int | None = None
    warranty_months: int | None = None

    # Rack
    rack_id: str | None = None

    # Free-form metadata
    tags: dict[str, str] = Field(default_factory=dict)


class RawEnergyReading(BaseModel):
    """A single timestamped energy data point."""

    timestamp: datetime
    total_power_kw: float | None = None
    it_power_kw: float | None = None
    cooling_power_kw: float | None = None
    lighting_power_kw: float | None = None
    ups_loss_kw: float | None = None


class RawCoolingData(BaseModel):
    """Raw cooling system data."""

    name: str = ""
    cooling_type: str = "air"
    cop: float | None = None
    capacity_kw: float | None = None
    current_load_kw: float | None = None


class CollectorResult(BaseModel):
    """Aggregated output from a single collector run."""

    source_type: str = Field(..., description="Collector type that produced this")
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now()
    )
    servers: list[RawServerData] = Field(default_factory=list)
    energy_readings: list[RawEnergyReading] = Field(default_factory=list)
    cooling_data: list[RawCoolingData] = Field(default_factory=list)
    rack_data: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Collector protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class DataCollector(Protocol):
    """Protocol that all collectors must satisfy."""

    def collect(self) -> CollectorResult:
        """Run data collection and return raw data."""
        ...

    def discover(self) -> list[str]:
        """Discover available endpoints/resources. Returns descriptions."""
        ...

    def test_connection(self) -> bool:
        """Test that the collector can reach its target."""
        ...
