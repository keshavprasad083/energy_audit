# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Core Pydantic v2 data models for the energy audit tool.

This module defines the complete data contract used by all other modules
including analysis, scoring, recommendations, reporting, and CLI layers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ServerType(str, Enum):
    """Classification of server hardware by primary workload capability."""

    cpu = "cpu"
    gpu_training = "gpu_training"
    gpu_inference = "gpu_inference"
    storage = "storage"


class CoolingType(str, Enum):
    """Data-center cooling methodology."""

    air = "air"
    liquid = "liquid"
    hybrid = "hybrid"


class WorkloadType(str, Enum):
    """High-level workload classification."""

    ai_training = "ai_training"
    ai_inference = "ai_inference"
    general_compute = "general_compute"
    database = "database"
    storage = "storage"
    web_serving = "web_serving"


class EnergySource(str, Enum):
    """Primary energy source feeding the facility."""

    grid = "grid"
    solar = "solar"
    wind = "wind"
    nuclear = "nuclear"
    natural_gas = "natural_gas"
    mixed = "mixed"


class Grade(str, Enum):
    """Letter grade used across all scoring sub-metrics and roll-ups."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"

    @property
    def color(self) -> str:
        """Terminal / report color associated with this grade."""
        if self in (Grade.A, Grade.B):
            return "green"
        if self is Grade.C:
            return "yellow"
        return "red"


# ---------------------------------------------------------------------------
# Infrastructure models
# ---------------------------------------------------------------------------

class Server(BaseModel):
    """A single physical or virtual server inside the data center."""

    model_config = {"frozen": False, "populate_by_name": True}

    id: str = Field(..., description="Unique server identifier")
    name: str = Field(..., description="Human-readable server name")
    server_type: ServerType = Field(..., description="Hardware classification")
    rack_id: str = Field(default="", description="Rack this server is installed in")

    # Power
    tdp_watts: float = Field(
        ..., gt=0, description="Thermal design power in watts"
    )
    current_power_watts: float = Field(
        ..., ge=0, description="Real-time measured power draw in watts"
    )

    # Utilization (0.0 - 1.0 fractions)
    cpu_utilization: float = Field(
        ..., ge=0, le=1.0, description="CPU utilization fraction (0.0-1.0)"
    )
    gpu_utilization: float = Field(
        default=0.0, ge=0, le=1.0,
        description="GPU utilization fraction (0.0-1.0); 0.0 for CPU-only servers",
    )
    memory_utilization: float = Field(
        default=0.0, ge=0, le=1.0,
        description="Memory utilization fraction (0.0-1.0)",
    )

    # Memory (absolute values for reporting)
    memory_allocated_gb: float = Field(
        default=0.0, ge=0, description="Memory currently allocated in GB"
    )
    memory_total_gb: float = Field(
        default=0.0, ge=0, description="Total installed memory in GB"
    )

    # Lifecycle
    age_months: int = Field(
        ..., ge=0, description="Server age in months since deployment"
    )
    warranty_months: int = Field(
        ..., ge=0, description="Original warranty length in months"
    )

    # Flags
    is_zombie: bool = Field(
        default=False,
        description="True if the server is powered on but doing no useful work",
    )
    is_overprovisioned: bool = Field(
        default=False,
        description="True if allocated resources far exceed actual demand",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def power_efficiency_ratio(self) -> float:
        """Ratio of current power to TDP; lower means more headroom."""
        if self.tdp_watts == 0:
            return 0.0
        return round(self.current_power_watts / self.tdp_watts, 4)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cpu_utilization_pct(self) -> float:
        """CPU utilization as percentage (0-100)."""
        return round(self.cpu_utilization * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gpu_utilization_pct(self) -> float:
        """GPU utilization as percentage (0-100)."""
        return round(self.gpu_utilization * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_past_warranty(self) -> bool:
        """Whether the server has exceeded its warranty period."""
        return self.age_months > self.warranty_months


class Rack(BaseModel):
    """A physical rack housing one or more servers."""

    model_config = {"frozen": False, "populate_by_name": True}

    id: str = Field(..., description="Unique rack identifier")
    name: str = Field(..., description="Human-readable rack name")
    location: str = Field(
        default="", description="Physical location within the facility (row/aisle)"
    )

    max_power_kw: float = Field(
        ..., gt=0, description="Maximum rated power capacity in kW"
    )
    current_power_kw: float = Field(
        ..., ge=0, description="Current aggregate power draw in kW"
    )

    cooling_type: CoolingType = Field(
        default=CoolingType.air, description="Cooling methodology serving this rack"
    )
    server_ids: list[str] = Field(
        default_factory=list,
        description="IDs of servers installed in this rack",
    )

    # Thermal
    inlet_temp_celsius: float = Field(
        default=22.0, description="Cold-aisle inlet temperature in Celsius"
    )
    outlet_temp_celsius: float = Field(
        default=35.0, description="Hot-aisle outlet temperature in Celsius"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def power_utilization_pct(self) -> float:
        """Percentage of rack power capacity currently in use."""
        if self.max_power_kw == 0:
            return 0.0
        return round((self.current_power_kw / self.max_power_kw) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def delta_temp_celsius(self) -> float:
        """Temperature differential across the rack."""
        return round(self.outlet_temp_celsius - self.inlet_temp_celsius, 2)


class Workload(BaseModel):
    """A logical workload that may span one or more servers."""

    model_config = {"frozen": False, "populate_by_name": True}

    id: str = Field(..., description="Unique workload identifier")
    name: str = Field(..., description="Human-readable workload name")
    workload_type: WorkloadType = Field(
        ..., description="High-level workload classification"
    )
    server_ids: list[str] = Field(
        default_factory=list,
        description="IDs of servers running this workload",
    )
    power_consumption_kw: float = Field(
        ..., ge=0, description="Aggregate power consumption in kW"
    )
    is_schedulable: bool = Field(
        default=False,
        description="Whether this workload can be shifted to off-peak hours",
    )
    priority: int = Field(
        default=3, ge=1, le=5,
        description="Business priority (1 = highest, 5 = lowest)",
    )


class EnergyReading(BaseModel):
    """A single point-in-time energy measurement for the facility."""

    model_config = {"frozen": False, "populate_by_name": True}

    timestamp: datetime = Field(
        ..., description="UTC timestamp of the reading"
    )
    total_facility_power_kw: float = Field(
        ..., ge=0, description="Total facility power in kW"
    )
    it_equipment_power_kw: float = Field(
        ..., ge=0, description="IT equipment power in kW"
    )
    cooling_power_kw: float = Field(
        ..., ge=0, description="Cooling infrastructure power in kW"
    )
    lighting_power_kw: float = Field(
        ..., ge=0, description="Lighting and ancillary power in kW"
    )
    ups_loss_kw: float = Field(
        ..., ge=0, description="Uninterruptible power supply conversion loss in kW"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pue(self) -> float:
        """Power Usage Effectiveness (total facility / IT equipment).

        A perfect PUE is 1.0; typical data centers range from 1.2 to 2.0+.
        Returns 0.0 when IT equipment power is zero to avoid division errors.
        """
        if self.it_equipment_power_kw == 0:
            return 0.0
        return round(
            self.total_facility_power_kw / self.it_equipment_power_kw, 4
        )


class CoolingSystem(BaseModel):
    """A cooling unit or system serving part or all of the facility."""

    model_config = {"frozen": False, "populate_by_name": True}

    id: str = Field(default="", description="Unique cooling system identifier")
    name: str = Field(default="", description="Human-readable name")
    cooling_type: CoolingType = Field(
        ..., description="Cooling methodology"
    )
    cop: float = Field(
        ..., gt=0,
        description="Coefficient of Performance (higher is more efficient)",
    )
    capacity_kw: float = Field(
        ..., gt=0, description="Maximum cooling capacity in kW"
    )
    current_load_kw: float = Field(
        ..., ge=0, description="Current cooling load in kW"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def load_pct(self) -> float:
        """Current cooling load as a percentage of capacity."""
        if self.capacity_kw == 0:
            return 0.0
        return round((self.current_load_kw / self.capacity_kw) * 100, 2)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class DataCenterConfig(BaseModel):
    """Static configuration and metadata for a data-center facility."""

    model_config = {"frozen": False, "populate_by_name": True}

    name: str = Field(..., description="Facility name")
    location: str = Field(
        ..., description="Physical address or campus identifier"
    )
    region: str = Field(
        ..., description="Geographic region (e.g. us-east-1, eu-west-1)"
    )

    total_power_capacity_mw: float = Field(
        ..., gt=0, description="Total contracted power capacity in MW"
    )
    energy_cost_per_kwh: float = Field(
        ..., gt=0, description="Blended energy cost in $/kWh"
    )
    carbon_intensity_gco2_per_kwh: float = Field(
        ..., ge=0,
        description="Grid carbon intensity in gCO2/kWh",
    )
    renewable_percentage: float = Field(
        ..., ge=0, le=1.0,
        description="Fraction of energy from renewable sources (0.0-1.0)",
    )
    ppa_available: bool = Field(
        default=False,
        description="Whether a Power Purchase Agreement is in place",
    )
    energy_source: str = Field(
        ..., description="Primary energy source description"
    )
    pue_target: float = Field(
        default=1.4, gt=1.0,
        description="Target PUE for this facility"
    )
    cooling_type: str = Field(
        default="air",
        description="Primary cooling strategy: air, liquid, or hybrid"
    )


# ---------------------------------------------------------------------------
# Main container
# ---------------------------------------------------------------------------

class DataCenter(BaseModel):
    """Top-level container representing a full data-center snapshot.

    This is the primary input object consumed by the analysis, scoring,
    and recommendation engines.  It carries 30 days (720 hours) of
    energy readings alongside the current infrastructure inventory.
    """

    model_config = {"frozen": False, "populate_by_name": True}

    config: DataCenterConfig = Field(
        ..., description="Facility configuration and metadata"
    )
    servers: list[Server] = Field(
        default_factory=list, description="All servers in the facility"
    )
    racks: list[Rack] = Field(
        default_factory=list, description="All racks in the facility"
    )
    workloads: list[Workload] = Field(
        default_factory=list, description="All active workloads"
    )
    energy_readings: list[EnergyReading] = Field(
        default_factory=list,
        description="Hourly energy readings (up to 720 hours / 30 days)",
    )
    cooling_systems: list[CoolingSystem] = Field(
        default_factory=list, description="All cooling systems in the facility"
    )

    # -- Aggregate computed properties -----------------------------------------

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_servers(self) -> int:
        """Total number of servers in the facility."""
        return len(self.servers)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gpu_server_count(self) -> int:
        """Number of GPU-class servers (training + inference)."""
        gpu_types = {ServerType.gpu_training, ServerType.gpu_inference}
        return sum(1 for s in self.servers if s.server_type in gpu_types)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_cpu_utilization(self) -> float:
        """Mean CPU utilization across all servers (0.0-1.0)."""
        if not self.servers:
            return 0.0
        return round(
            sum(s.cpu_utilization for s in self.servers) / len(self.servers), 4
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_gpu_utilization(self) -> float:
        """Mean GPU utilization across servers that have GPUs (0.0-1.0).

        Returns 0.0 when there are no GPU servers.
        """
        gpu_servers = [
            s for s in self.servers if s.gpu_utilization > 0
        ]
        if not gpu_servers:
            return 0.0
        return round(
            sum(s.gpu_utilization for s in gpu_servers) / len(gpu_servers), 4
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def zombie_count(self) -> int:
        """Number of servers flagged as zombies."""
        return sum(1 for s in self.servers if s.is_zombie)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def overprovisioned_count(self) -> int:
        """Number of servers flagged as overprovisioned."""
        return sum(1 for s in self.servers if s.is_overprovisioned)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_pue(self) -> float:
        """Average Power Usage Effectiveness across all readings.

        Returns 0.0 when there are no energy readings.
        """
        valid = [r for r in self.energy_readings if r.pue > 0]
        if not valid:
            return 0.0
        return round(sum(r.pue for r in valid) / len(valid), 4)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_energy_kwh(self) -> float:
        """Total energy consumed over the readings window in kWh.

        Each reading represents one hour, so power in kW equals energy
        in kWh for that hour.
        """
        return round(
            sum(r.total_facility_power_kw for r in self.energy_readings), 2
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_cost(self) -> float:
        """Total energy cost in dollars over the readings window."""
        return round(
            self.total_energy_kwh * self.config.energy_cost_per_kwh, 2
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def avg_server_age_months(self) -> float:
        """Mean server age in months."""
        if not self.servers:
            return 0.0
        return round(
            sum(s.age_months for s in self.servers) / len(self.servers), 2
        )


# ---------------------------------------------------------------------------
# Scoring result models
# ---------------------------------------------------------------------------

class SubMetricScore(BaseModel):
    """A single scored sub-metric within a box score."""

    model_config = {"frozen": False, "populate_by_name": True}

    name: str = Field(..., description="Sub-metric display name")
    value: float = Field(
        ..., description="Raw measured value before normalization"
    )
    score: float = Field(
        ..., ge=0, le=100,
        description="Normalized score on a 0-100 scale",
    )
    weight: float = Field(
        ..., ge=0, le=1,
        description="Weight of this sub-metric in the box roll-up (0-1)",
    )
    grade: Grade = Field(..., description="Letter grade for this sub-metric")
    description: str = Field(
        ..., description="Human-readable explanation of what was measured"
    )


class BoxScore(BaseModel):
    """Aggregated score for one of the three strategy boxes.

    Box 1: Current Operations
    Box 2: Legacy & Waste
    Box 3: Future Readiness
    """

    model_config = {"frozen": False, "populate_by_name": True}

    box_number: int = Field(
        ..., ge=1, le=3, description="Box identifier (1, 2, or 3)"
    )
    box_name: str = Field(
        ..., description="Human-readable name for this scoring box"
    )
    overall_score: float = Field(
        ..., ge=0, le=100,
        description="Weighted roll-up score for the box (0-100)",
    )
    grade: Grade = Field(..., description="Letter grade for this box")
    sub_metrics: list[SubMetricScore] = Field(
        default_factory=list,
        description="Individual sub-metric scores within this box",
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Key findings and observations for this box",
    )


class Recommendation(BaseModel):
    """A single actionable recommendation produced by the audit."""

    model_config = {"frozen": False, "populate_by_name": True}

    rank: int = Field(
        ..., ge=1,
        description="Priority rank (1 = most impactful)",
    )
    box_number: int = Field(
        ..., ge=1, le=3,
        description="Which scoring box this recommendation relates to",
    )
    title: str = Field(
        ..., description="Short actionable title"
    )
    description: str = Field(
        ..., description="Detailed explanation and rationale"
    )
    monthly_savings_dollars: float = Field(
        ..., ge=0,
        description="Estimated monthly cost savings in USD",
    )
    monthly_energy_savings_kwh: float = Field(
        ..., ge=0,
        description="Estimated monthly energy savings in kWh",
    )
    effort: str = Field(
        ..., pattern=r"^(low|medium|high)$",
        description="Implementation effort level: low, medium, or high",
    )
    impact: str = Field(
        ..., pattern=r"^(low|medium|high)$",
        description="Expected impact level: low, medium, or high",
    )


class AuditResult(BaseModel):
    """Complete output of an energy audit run.

    This is the top-level result object consumed by the reporting and
    CLI layers to produce terminal output, PDF reports, and JSON exports.
    """

    model_config = {"frozen": False, "populate_by_name": True}

    data_center: DataCenter = Field(
        ..., description="The data-center snapshot that was audited"
    )

    # Three scoring boxes
    box1: BoxScore = Field(
        ..., description="Box 1: Current Operations"
    )
    box2: BoxScore = Field(
        ..., description="Box 2: Legacy & Waste"
    )
    box3: BoxScore = Field(
        ..., description="Box 3: Future Readiness"
    )

    overall_score: float = Field(
        ..., ge=0, le=100,
        description="Weighted overall audit score (0-100)",
    )
    overall_grade: Grade = Field(
        ..., description="Overall letter grade for the facility"
    )

    recommendations: list[Recommendation] = Field(
        default_factory=list,
        description="Prioritized list of actionable recommendations",
    )
    executive_summary: str = Field(
        ..., description="Executive summary suitable for leadership review"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the audit was generated",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_monthly_savings(self) -> float:
        """Sum of estimated monthly savings across all recommendations."""
        return round(
            sum(r.monthly_savings_dollars for r in self.recommendations), 2
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_monthly_energy_savings_kwh(self) -> float:
        """Sum of estimated monthly energy savings across all recommendations."""
        return round(
            sum(r.monthly_energy_savings_kwh for r in self.recommendations), 2
        )
