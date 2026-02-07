# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Grade thresholds, color mappings, and industry benchmarks.

All benchmark values are documented with their scoring implications
so that auditors can trace every score back to a concrete reference.
"""

from energy_audit.data.models import Grade

# ---------------------------------------------------------------------------
# Grade thresholds (score -> letter grade)
# ---------------------------------------------------------------------------
GRADE_A_MIN = 85
GRADE_B_MIN = 70
GRADE_C_MIN = 55
GRADE_D_MIN = 40
# Below 40 = F

# ---------------------------------------------------------------------------
# Color thresholds
# ---------------------------------------------------------------------------
GREEN_MIN = 80
YELLOW_MIN = 50
# Below 50 = Red

# ---------------------------------------------------------------------------
# PUE benchmarks
# ---------------------------------------------------------------------------
PUE_EXCELLENT = 1.2   # Score = 80
PUE_GOOD = 1.4        # Score = 60
PUE_AVERAGE = 1.6     # Score = 40
PUE_POOR = 2.0        # Score = 0

# ---------------------------------------------------------------------------
# Utilization benchmarks (as 0-1 fractions)
# ---------------------------------------------------------------------------
UTIL_TARGET_CPU = 0.60     # Ideal CPU utilization
UTIL_TARGET_GPU = 0.75     # Ideal GPU utilization
ZOMBIE_THRESHOLD = 0.05    # Below this = zombie

# ---------------------------------------------------------------------------
# Cost benchmarks
# ---------------------------------------------------------------------------
COST_BENCHMARK_PER_KWH = 0.10  # USD

# ---------------------------------------------------------------------------
# Cooling benchmarks
# ---------------------------------------------------------------------------
COP_BENCHMARK_AIR = 3.0
COP_BENCHMARK_LIQUID = 5.0

# ---------------------------------------------------------------------------
# Carbon benchmarks
# ---------------------------------------------------------------------------
CARBON_LOW = 100      # gCO2/kWh, Score = 100
CARBON_HIGH = 500     # gCO2/kWh, Score = 0

# ---------------------------------------------------------------------------
# Age / lifecycle benchmarks
# ---------------------------------------------------------------------------
WARRANTY_MONTHS = 36
USEFUL_LIFE_MONTHS = 60
REFRESH_WINDOW_MIN = 36
REFRESH_WINDOW_MAX = 60

# ---------------------------------------------------------------------------
# Renewable energy benchmarks
# ---------------------------------------------------------------------------
RENEWABLE_EXCELLENT = 0.80  # 80% renewable = excellent
RENEWABLE_GOOD = 0.50


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def score_to_grade(score: float) -> str:
    """Convert a 0-100 numeric score to a letter grade string.

    Returns one of 'A', 'B', 'C', 'D', or 'F'.
    """
    if score >= GRADE_A_MIN:
        return Grade.A.value
    if score >= GRADE_B_MIN:
        return Grade.B.value
    if score >= GRADE_C_MIN:
        return Grade.C.value
    if score >= GRADE_D_MIN:
        return Grade.D.value
    return Grade.F.value


def score_to_color(score: float) -> str:
    """Convert a 0-100 numeric score to a color string.

    Returns 'green', 'yellow', or 'red'.
    """
    if score >= GREEN_MIN:
        return "green"
    if score >= YELLOW_MIN:
        return "yellow"
    return "red"
