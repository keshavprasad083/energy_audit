# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Box 1: Current Operations -- scoring of current energy efficiency.

Evaluates real-time operational metrics including PUE, server utilization,
energy cost, cooling performance, availability, and carbon intensity.
"""

from __future__ import annotations

from energy_audit.data.models import (
    CoolingType,
    DataCenter,
    BoxScore,
    Grade,
    ServerType,
    SubMetricScore,
)
from energy_audit.scoring.thresholds import (
    COP_BENCHMARK_AIR,
    COP_BENCHMARK_LIQUID,
    COST_BENCHMARK_PER_KWH,
    UTIL_TARGET_CPU,
    UTIL_TARGET_GPU,
    score_to_grade,
)
from energy_audit.scoring.weights import (
    BOX1_AVAILABILITY_WEIGHT,
    BOX1_CARBON_WEIGHT,
    BOX1_COOLING_WEIGHT,
    BOX1_COST_WEIGHT,
    BOX1_NAME,
    BOX1_PUE_WEIGHT,
    BOX1_UTILIZATION_WEIGHT,
)


# ---------------------------------------------------------------------------
# Individual sub-metric scorers
# ---------------------------------------------------------------------------

def _score_pue(dc: DataCenter) -> tuple[float, float]:
    """Score PUE on a 0-100 scale.  PUE 1.0 = 100, PUE 2.0 = 0.

    Returns (raw_pue, score).
    """
    pue = dc.avg_pue
    if pue <= 0:
        # No valid readings -- assume worst case
        return 0.0, 0.0
    score = max(0.0, min(100.0, (2.0 - pue) / 1.0 * 100.0))
    return pue, round(score, 2)


def _score_utilization(dc: DataCenter) -> tuple[float, float]:
    """Score server utilization vs targets.

    GPU weight is 0.7 if GPU servers > 30% of fleet, else 0.4.
    Returns (avg_utilization_fraction, score).
    """
    if not dc.servers:
        return 0.0, 0.0

    # CPU score: how close avg CPU utilization is to target (0-1 fraction)
    cpu_avg = dc.avg_cpu_utilization  # 0.0-1.0
    cpu_score = max(0.0, min(100.0, (cpu_avg / UTIL_TARGET_CPU) * 100.0))
    # Penalize over-utilization (>90%) as it indicates capacity risk
    if cpu_avg > 0.90:
        cpu_score = max(0.0, cpu_score - (cpu_avg - 0.90) * 500.0)

    # GPU score
    gpu_avg = dc.avg_gpu_utilization  # 0.0-1.0
    gpu_score = max(0.0, min(100.0, (gpu_avg / UTIL_TARGET_GPU) * 100.0))
    if gpu_avg > 0.95:
        gpu_score = max(0.0, gpu_score - (gpu_avg - 0.95) * 500.0)

    # Determine GPU weight
    total = dc.total_servers
    gpu_count = dc.gpu_server_count
    gpu_fraction = gpu_count / total if total > 0 else 0.0
    gpu_weight = 0.7 if gpu_fraction > 0.30 else 0.4
    cpu_weight = 1.0 - gpu_weight

    combined_score = cpu_score * cpu_weight + gpu_score * gpu_weight
    avg_util = cpu_avg * cpu_weight + gpu_avg * gpu_weight

    return round(avg_util, 4), round(combined_score, 2)


def _score_cost(dc: DataCenter) -> tuple[float, float]:
    """Score energy cost efficiency.

    At or below benchmark = 100.  At 2x benchmark = 0.
    Returns (cost_per_kwh, score).
    """
    cost_per_kwh = dc.config.energy_cost_per_kwh
    if cost_per_kwh <= COST_BENCHMARK_PER_KWH:
        return cost_per_kwh, 100.0
    ratio = cost_per_kwh / COST_BENCHMARK_PER_KWH
    # Linear from 1.0 (100) to 2.0 (0)
    score = max(0.0, min(100.0, (2.0 - ratio) * 100.0))
    return cost_per_kwh, round(score, 2)


def _score_cooling(dc: DataCenter) -> tuple[float, float]:
    """Score cooling system efficiency using average COP.

    Returns (avg_cop, score).
    """
    if not dc.cooling_systems:
        return 0.0, 50.0  # No data -- neutral score

    total_cop = sum(cs.cop for cs in dc.cooling_systems)
    avg_cop = total_cop / len(dc.cooling_systems)

    # Determine benchmark based on dominant cooling type
    liquid_count = sum(
        1 for cs in dc.cooling_systems
        if cs.cooling_type == CoolingType.liquid
    )
    benchmark = (
        COP_BENCHMARK_LIQUID
        if liquid_count > len(dc.cooling_systems) / 2
        else COP_BENCHMARK_AIR
    )

    score = min(100.0, (avg_cop / benchmark) * 80.0)
    return round(avg_cop, 2), round(max(0.0, score), 2)


def _score_availability(dc: DataCenter) -> tuple[float, float]:
    """Score based on % of readings with PUE within 10% of target.

    >95% within target = 100, <80% = 0.
    Returns (pct_within_target, score).
    """
    target_pue = dc.config.pue_target
    valid_readings = [r for r in dc.energy_readings if r.pue > 0]
    if not valid_readings:
        return 0.0, 50.0  # No data -- neutral score

    tolerance = target_pue * 0.10
    within_count = sum(
        1 for r in valid_readings
        if abs(r.pue - target_pue) <= tolerance
    )
    pct_within = within_count / len(valid_readings)

    if pct_within >= 0.95:
        score = 100.0
    elif pct_within < 0.80:
        score = 0.0
    else:
        # Linear interpolation between 80% (0) and 95% (100)
        score = (pct_within - 0.80) / 0.15 * 100.0

    return round(pct_within, 4), round(score, 2)


def _score_carbon(dc: DataCenter) -> tuple[float, float]:
    """Score carbon intensity.

    500 gCO2/kWh = 0, 100 gCO2/kWh = 100.
    Formula: max(0, min(100, (500 - carbon) / 4.0))
    Returns (carbon_intensity, score).
    """
    carbon = dc.config.carbon_intensity_gco2_per_kwh
    score = max(0.0, min(100.0, (500.0 - carbon) / 4.0))
    return carbon, round(score, 2)


# ---------------------------------------------------------------------------
# Box 1 orchestrator
# ---------------------------------------------------------------------------

def score_box1(dc: DataCenter) -> BoxScore:
    """Compute the Box 1 (Current Operations) score.

    Evaluates current operational efficiency across six sub-metrics:
    PUE, utilization, cost, cooling, availability, and carbon intensity.
    """
    findings: list[str] = []

    # --- PUE ---
    pue_val, pue_score = _score_pue(dc)
    pue_grade = Grade(score_to_grade(pue_score))
    if pue_val > 0:
        findings.append(f"Average PUE is {pue_val:.2f} (score: {pue_score:.0f}/100).")
    if pue_val > 1.6:
        findings.append("PUE exceeds 1.6 -- significant overhead in non-IT power.")

    # --- Utilization ---
    util_val, util_score = _score_utilization(dc)
    util_grade = Grade(score_to_grade(util_score))
    if dc.avg_cpu_utilization < 0.30:
        findings.append(
            f"CPU utilization is critically low at "
            f"{dc.avg_cpu_utilization:.1%} -- consolidation recommended."
        )
    if dc.gpu_server_count > 0 and dc.avg_gpu_utilization < 0.40:
        findings.append(
            f"GPU utilization at {dc.avg_gpu_utilization:.1%} "
            f"indicates under-utilized accelerators."
        )

    # --- Cost ---
    cost_val, cost_score = _score_cost(dc)
    cost_grade = Grade(score_to_grade(cost_score))
    if cost_val > COST_BENCHMARK_PER_KWH * 1.5:
        findings.append(
            f"Energy cost ${cost_val:.3f}/kWh is significantly above "
            f"the ${COST_BENCHMARK_PER_KWH:.2f} benchmark."
        )

    # --- Cooling ---
    cool_val, cool_score = _score_cooling(dc)
    cool_grade = Grade(score_to_grade(cool_score))
    if cool_val > 0 and cool_val < COP_BENCHMARK_AIR:
        findings.append(
            f"Average cooling COP of {cool_val:.1f} is below the air-cooled "
            f"benchmark of {COP_BENCHMARK_AIR:.1f}."
        )

    # --- Availability ---
    avail_val, avail_score = _score_availability(dc)
    avail_grade = Grade(score_to_grade(avail_score))
    if avail_val < 0.85:
        findings.append(
            f"Only {avail_val:.1%} of readings are within 10% of target PUE "
            f"-- operational consistency needs improvement."
        )

    # --- Carbon ---
    carbon_val, carbon_score = _score_carbon(dc)
    carbon_grade = Grade(score_to_grade(carbon_score))
    if carbon_val > 300:
        findings.append(
            f"Carbon intensity of {carbon_val:.0f} gCO2/kWh is above average "
            f"-- consider renewable procurement."
        )

    # --- Build sub-metrics list ---
    sub_metrics = [
        SubMetricScore(
            name="PUE Efficiency",
            value=pue_val,
            score=pue_score,
            weight=BOX1_PUE_WEIGHT,
            grade=pue_grade,
            description=f"Power Usage Effectiveness: {pue_val:.2f} (1.0 = perfect)",
        ),
        SubMetricScore(
            name="Server Utilization",
            value=round(util_val * 100, 2),
            score=util_score,
            weight=BOX1_UTILIZATION_WEIGHT,
            grade=util_grade,
            description=(
                f"Weighted CPU/GPU utilization vs targets "
                f"(CPU: {dc.avg_cpu_utilization:.1%}, "
                f"GPU: {dc.avg_gpu_utilization:.1%})"
            ),
        ),
        SubMetricScore(
            name="Cost Efficiency",
            value=cost_val,
            score=cost_score,
            weight=BOX1_COST_WEIGHT,
            grade=cost_grade,
            description=f"Energy cost ${cost_val:.3f}/kWh vs ${COST_BENCHMARK_PER_KWH:.2f} benchmark",
        ),
        SubMetricScore(
            name="Cooling Performance",
            value=cool_val,
            score=cool_score,
            weight=BOX1_COOLING_WEIGHT,
            grade=cool_grade,
            description=f"Average cooling COP: {cool_val:.1f}",
        ),
        SubMetricScore(
            name="Operational Availability",
            value=round(avail_val * 100, 2),
            score=avail_score,
            weight=BOX1_AVAILABILITY_WEIGHT,
            grade=avail_grade,
            description=f"{avail_val:.1%} of readings within 10% of PUE target {dc.config.pue_target}",
        ),
        SubMetricScore(
            name="Carbon Intensity",
            value=carbon_val,
            score=carbon_score,
            weight=BOX1_CARBON_WEIGHT,
            grade=carbon_grade,
            description=f"Grid carbon intensity: {carbon_val:.0f} gCO2/kWh",
        ),
    ]

    # --- Weighted overall ---
    overall = (
        pue_score * BOX1_PUE_WEIGHT
        + util_score * BOX1_UTILIZATION_WEIGHT
        + cost_score * BOX1_COST_WEIGHT
        + cool_score * BOX1_COOLING_WEIGHT
        + avail_score * BOX1_AVAILABILITY_WEIGHT
        + carbon_score * BOX1_CARBON_WEIGHT
    )
    overall = round(overall, 2)
    overall_grade = Grade(score_to_grade(overall))

    return BoxScore(
        box_number=1,
        box_name=BOX1_NAME,
        overall_score=overall,
        grade=overall_grade,
        sub_metrics=sub_metrics,
        findings=findings,
    )
