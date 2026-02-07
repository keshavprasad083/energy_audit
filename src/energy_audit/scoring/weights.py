"""Scoring weight constants for the energy audit framework.

All weights within a box must sum to 1.0.  The three box weights define
the contribution of each assessment pillar to the overall facility score.
"""

# ---------------------------------------------------------------------------
# Box display names (single source of truth for all modules)
# ---------------------------------------------------------------------------
BOX1_NAME = "Current Operations"
BOX2_NAME = "Legacy & Waste"
BOX3_NAME = "Future Readiness"

# ---------------------------------------------------------------------------
# Box weights in overall score
# ---------------------------------------------------------------------------
BOX1_WEIGHT = 0.40  # Current Operations
BOX2_WEIGHT = 0.30  # Legacy & Waste
BOX3_WEIGHT = 0.30  # Future Readiness

# ---------------------------------------------------------------------------
# Box 1 sub-metric weights (must sum to 1.0)
# ---------------------------------------------------------------------------
BOX1_PUE_WEIGHT = 0.25
BOX1_UTILIZATION_WEIGHT = 0.20
BOX1_COST_WEIGHT = 0.20
BOX1_COOLING_WEIGHT = 0.15
BOX1_AVAILABILITY_WEIGHT = 0.10
BOX1_CARBON_WEIGHT = 0.10

# ---------------------------------------------------------------------------
# Box 2 sub-metric weights (must sum to 1.0)
# ---------------------------------------------------------------------------
BOX2_ZOMBIE_WEIGHT = 0.30
BOX2_OVERPROV_WEIGHT = 0.25
BOX2_LEGACY_WEIGHT = 0.20
BOX2_COOLING_WASTE_WEIGHT = 0.15
BOX2_STRANDED_WEIGHT = 0.10

# ---------------------------------------------------------------------------
# Box 3 sub-metric weights (must sum to 1.0)
# ---------------------------------------------------------------------------
BOX3_FORECAST_WEIGHT = 0.20
BOX3_REFRESH_WEIGHT = 0.20
BOX3_SCHEDULING_WEIGHT = 0.20
BOX3_RENEWABLE_WEIGHT = 0.20
BOX3_TREND_WEIGHT = 0.20
