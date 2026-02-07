"""Data center profile presets for simulated data generation.

Each profile configures how the generator creates simulated data center
environments, from small startups to large hyperscale facilities.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DCProfile(BaseModel):
    """Data center profile defining the characteristics of a simulated facility."""

    name: str = Field(description="Short identifier for the profile")
    description: str = Field(description="Human-readable description of the profile")

    # Server configuration
    server_count: int = Field(description="Total number of servers in the facility")
    gpu_percentage: float = Field(
        description="Fraction of servers that are GPU-equipped (0.0-1.0)"
    )
    gpu_training_ratio: float = Field(
        description="Fraction of GPU servers dedicated to training vs inference (0.0-1.0)"
    )
    rack_count: int = Field(description="Total number of racks")

    # Power and cooling
    pue_target: float = Field(description="Target Power Usage Effectiveness ratio")
    cooling_type: str = Field(description="Cooling strategy: 'air', 'liquid', or 'hybrid'")

    # Energy economics
    energy_cost_per_kwh: float = Field(description="Energy cost in USD per kWh")
    renewable_percentage: float = Field(
        description="Fraction of energy from renewable sources (0.0-1.0)"
    )
    ppa_available: bool = Field(
        default=False,
        description="Whether a Power Purchase Agreement is in place",
    )

    # Waste indicators
    zombie_rate: float = Field(
        description="Fraction of servers that are zombies (0.0-1.0)"
    )
    overprov_rate: float = Field(
        description="Fraction of servers that are overprovisioned (0.0-1.0)"
    )

    # Fleet age
    min_server_age_months: int = Field(description="Minimum server age in months")
    max_server_age_months: int = Field(description="Maximum server age in months")

    # Location and environment
    location: str = Field(description="Geographic location label")
    region: str = Field(description="Cloud-style region identifier")
    carbon_intensity: float = Field(
        description="Grid carbon intensity in gCO2/kWh"
    )

    # Infrastructure capacity
    total_power_capacity_mw: float = Field(
        description="Total facility power capacity in megawatts"
    )
    energy_source: str = Field(
        description="Primary energy source description"
    )


# ---------------------------------------------------------------------------
# Profile definitions
# ---------------------------------------------------------------------------

SMALL_STARTUP = DCProfile(
    name="small_startup",
    description=(
        "Small AI startup with a modest GPU cluster for inference workloads, "
        "relying on air cooling and limited renewable energy."
    ),
    server_count=50,
    gpu_percentage=0.20,
    gpu_training_ratio=0.20,
    rack_count=4,
    pue_target=1.4,
    cooling_type="air",
    energy_cost_per_kwh=0.12,
    renewable_percentage=0.10,
    ppa_available=False,
    zombie_rate=0.08,
    overprov_rate=0.15,
    min_server_age_months=6,
    max_server_age_months=36,
    location="US-West",
    region="us-west-2",
    carbon_intensity=350.0,
    total_power_capacity_mw=0.5,
    energy_source="Grid mix with 10% solar",
)

MEDIUM_ENTERPRISE = DCProfile(
    name="medium_enterprise",
    description=(
        "Mid-size enterprise data center with a mixed GPU fleet for both "
        "training and inference, using hybrid cooling and moderate renewable adoption."
    ),
    server_count=500,
    gpu_percentage=0.35,
    gpu_training_ratio=0.50,
    rack_count=30,
    pue_target=1.35,
    cooling_type="hybrid",
    energy_cost_per_kwh=0.10,
    renewable_percentage=0.25,
    ppa_available=False,
    zombie_rate=0.12,
    overprov_rate=0.20,
    min_server_age_months=6,
    max_server_age_months=60,
    location="US-East",
    region="us-east-1",
    carbon_intensity=400.0,
    total_power_capacity_mw=5.0,
    energy_source="Grid mix with 25% wind and solar",
)

LARGE_HYPERSCALE = DCProfile(
    name="large_hyperscale",
    description=(
        "Hyperscale AI training facility with aggressive liquid cooling, "
        "high renewable penetration, and a Power Purchase Agreement for clean energy."
    ),
    server_count=5000,
    gpu_percentage=0.50,
    gpu_training_ratio=0.70,
    rack_count=200,
    pue_target=1.12,
    cooling_type="liquid",
    energy_cost_per_kwh=0.08,
    renewable_percentage=0.60,
    ppa_available=True,
    zombie_rate=0.05,
    overprov_rate=0.10,
    min_server_age_months=6,
    max_server_age_months=48,
    location="EU-North",
    region="eu-north-1",
    carbon_intensity=150.0,
    total_power_capacity_mw=50.0,
    energy_source="Hydro and wind PPA with grid backup",
)

LEGACY_MIXED = DCProfile(
    name="legacy_mixed",
    description=(
        "Aging enterprise facility with legacy hardware, poor cooling efficiency, "
        "high zombie and overprovisioning rates, and minimal renewable energy."
    ),
    server_count=300,
    gpu_percentage=0.15,
    gpu_training_ratio=0.15,
    rack_count=25,
    pue_target=1.6,
    cooling_type="air",
    energy_cost_per_kwh=0.15,
    renewable_percentage=0.05,
    ppa_available=False,
    zombie_rate=0.20,
    overprov_rate=0.30,
    min_server_age_months=24,
    max_server_age_months=96,
    location="US-Central",
    region="us-central-1",
    carbon_intensity=550.0,
    total_power_capacity_mw=3.0,
    energy_source="Grid mix, predominantly natural gas",
)

# ---------------------------------------------------------------------------
# Profile registry
# ---------------------------------------------------------------------------

PROFILES: dict[str, DCProfile] = {
    "small_startup": SMALL_STARTUP,
    "medium_enterprise": MEDIUM_ENTERPRISE,
    "large_hyperscale": LARGE_HYPERSCALE,
    "legacy_mixed": LEGACY_MIXED,
}


def get_profile(name: str) -> DCProfile:
    """Return the profile for the given name.

    Parameters
    ----------
    name:
        One of ``small_startup``, ``medium_enterprise``,
        ``large_hyperscale``, or ``legacy_mixed``.

    Returns
    -------
    DCProfile
        The matching data center profile.

    Raises
    ------
    KeyError
        If *name* does not match any registered profile.
    """
    try:
        return PROFILES[name]
    except KeyError:
        available = ", ".join(sorted(PROFILES.keys()))
        raise KeyError(
            f"Unknown profile '{name}'. Available profiles: {available}"
        ) from None
