"""Box 2: Legacy & Waste -- scoring of waste and legacy burden.

Evaluates how effectively the facility retires zombie servers, decommissions
over-provisioned resources, refreshes legacy hardware, eliminates cooling
waste, and reclaims stranded rack capacity.
"""

from __future__ import annotations

from energy_audit.data.models import (
    CoolingType,
    DataCenter,
    BoxScore,
    Grade,
    SubMetricScore,
)
from energy_audit.scoring.thresholds import (
    COP_BENCHMARK_AIR,
    COP_BENCHMARK_LIQUID,
    USEFUL_LIFE_MONTHS,
    WARRANTY_MONTHS,
    score_to_grade,
)
from energy_audit.scoring.weights import (
    BOX2_COOLING_WASTE_WEIGHT,
    BOX2_LEGACY_WEIGHT,
    BOX2_NAME,
    BOX2_OVERPROV_WEIGHT,
    BOX2_STRANDED_WEIGHT,
    BOX2_ZOMBIE_WEIGHT,
)


# ---------------------------------------------------------------------------
# Individual sub-metric scorers
# ---------------------------------------------------------------------------

def _score_zombie(dc: DataCenter) -> tuple[float, float, list[str]]:
    """Score zombie server prevalence.

    Formula: max(0, 100 - zombie_pct * 500)
    Returns (zombie_pct, score, findings).
    """
    findings: list[str] = []
    total = dc.total_servers
    if total == 0:
        return 0.0, 100.0, findings

    zombie_count = dc.zombie_count
    zombie_pct = zombie_count / total
    score = max(0.0, 100.0 - zombie_pct * 500.0)

    if zombie_count > 0:
        findings.append(
            f"{zombie_count} zombie server(s) detected ({zombie_pct:.1%} of fleet) "
            f"-- consuming power with no useful output."
        )
        # Estimate wasted power
        zombie_servers = [s for s in dc.servers if s.is_zombie]
        wasted_kw = sum(s.current_power_watts for s in zombie_servers) / 1000.0
        if wasted_kw > 0:
            findings.append(
                f"Zombie servers consume approximately {wasted_kw:.1f} kW "
                f"(${wasted_kw * 720 * dc.config.energy_cost_per_kwh:,.0f}/month)."
            )

    return round(zombie_pct, 4), round(score, 2), findings


def _score_overprovisioned(dc: DataCenter) -> tuple[float, float, list[str]]:
    """Score over-provisioned resource prevalence.

    Formula: max(0, 100 - overprov_pct * 400)
    Returns (overprov_pct, score, findings).
    """
    findings: list[str] = []
    total = dc.total_servers
    if total == 0:
        return 0.0, 100.0, findings

    overprov_count = dc.overprovisioned_count
    overprov_pct = overprov_count / total
    score = max(0.0, 100.0 - overprov_pct * 400.0)

    if overprov_count > 0:
        findings.append(
            f"{overprov_count} over-provisioned server(s) ({overprov_pct:.1%} of fleet) "
            f"-- allocated resources significantly exceed demand."
        )

    return round(overprov_pct, 4), round(score, 2), findings


def _score_legacy(dc: DataCenter) -> tuple[float, float, list[str]]:
    """Score legacy hardware burden.

    Based on % servers past warranty and % past useful life.
    Formula: max(0, 100 - past_warranty_pct * 150 - past_useful_life_pct * 300)
    Returns (avg_age_months, score, findings).
    """
    findings: list[str] = []
    total = dc.total_servers
    if total == 0:
        return 0.0, 100.0, findings

    past_warranty = sum(1 for s in dc.servers if s.age_months > s.warranty_months)
    past_useful = sum(1 for s in dc.servers if s.age_months > USEFUL_LIFE_MONTHS)

    past_warranty_pct = past_warranty / total
    past_useful_pct = past_useful / total

    score = max(0.0, 100.0 - past_warranty_pct * 150.0 - past_useful_pct * 300.0)

    if past_warranty > 0:
        findings.append(
            f"{past_warranty} server(s) ({past_warranty_pct:.1%}) are past warranty "
            f"-- increased failure risk and maintenance costs."
        )
    if past_useful > 0:
        findings.append(
            f"{past_useful} server(s) ({past_useful_pct:.1%}) exceed "
            f"{USEFUL_LIFE_MONTHS}-month useful life -- candidates for decommission."
        )

    return round(dc.avg_server_age_months, 2), round(score, 2), findings


def _score_cooling_waste(dc: DataCenter) -> tuple[float, float, list[str]]:
    """Score cooling waste.

    Based on cooling systems running above 85% capacity or below COP benchmark.
    Formula: 100 - waste_pct * 200
    Returns (waste_pct, score, findings).
    """
    findings: list[str] = []
    if not dc.cooling_systems:
        return 0.0, 100.0, findings

    waste_count = 0
    for cs in dc.cooling_systems:
        # Determine the relevant COP benchmark
        if cs.cooling_type == CoolingType.liquid:
            benchmark = COP_BENCHMARK_LIQUID
        else:
            benchmark = COP_BENCHMARK_AIR

        is_overloaded = cs.load_pct > 85.0
        is_inefficient = cs.cop < benchmark

        if is_overloaded or is_inefficient:
            waste_count += 1

        if is_overloaded:
            findings.append(
                f"Cooling system '{cs.name or cs.id}' running at {cs.load_pct:.0f}% "
                f"capacity -- risk of thermal throttling."
            )
        if is_inefficient:
            findings.append(
                f"Cooling system '{cs.name or cs.id}' COP {cs.cop:.1f} is below "
                f"benchmark {benchmark:.1f} -- upgrade or maintenance needed."
            )

    waste_pct = waste_count / len(dc.cooling_systems)
    score = max(0.0, 100.0 - waste_pct * 200.0)

    return round(waste_pct, 4), round(score, 2), findings


def _score_stranded(dc: DataCenter) -> tuple[float, float, list[str]]:
    """Score stranded rack capacity.

    Based on racks with power utilization < 30%.
    Formula: 100 - stranded_pct * 300
    Returns (stranded_pct, score, findings).
    """
    findings: list[str] = []
    if not dc.racks:
        return 0.0, 100.0, findings

    stranded_count = sum(
        1 for r in dc.racks
        if r.power_utilization_pct < 30.0
    )
    stranded_pct = stranded_count / len(dc.racks)
    score = max(0.0, 100.0 - stranded_pct * 300.0)

    if stranded_count > 0:
        findings.append(
            f"{stranded_count} rack(s) ({stranded_pct:.1%}) have power utilization "
            f"below 30% -- consider consolidation to reduce overhead."
        )
        # Estimate stranded capacity
        stranded_racks = [r for r in dc.racks if r.power_utilization_pct < 30.0]
        wasted_kw = sum(r.max_power_kw - r.current_power_kw for r in stranded_racks)
        findings.append(
            f"Approximately {wasted_kw:.0f} kW of rack capacity is stranded "
            f"across under-utilized racks."
        )

    return round(stranded_pct, 4), round(score, 2), findings


# ---------------------------------------------------------------------------
# Box 2 orchestrator
# ---------------------------------------------------------------------------

def score_box2(dc: DataCenter) -> BoxScore:
    """Compute the Box 2 (Legacy & Waste) score.

    Evaluates waste and legacy burden across five sub-metrics: zombie servers,
    over-provisioned resources, legacy hardware, cooling waste, and stranded
    rack capacity.
    """
    all_findings: list[str] = []

    # --- Zombie ---
    zombie_val, zombie_score, zombie_findings = _score_zombie(dc)
    zombie_grade = Grade(score_to_grade(zombie_score))
    all_findings.extend(zombie_findings)

    # --- Over-provisioned ---
    overprov_val, overprov_score, overprov_findings = _score_overprovisioned(dc)
    overprov_grade = Grade(score_to_grade(overprov_score))
    all_findings.extend(overprov_findings)

    # --- Legacy ---
    legacy_val, legacy_score, legacy_findings = _score_legacy(dc)
    legacy_grade = Grade(score_to_grade(legacy_score))
    all_findings.extend(legacy_findings)

    # --- Cooling waste ---
    cool_val, cool_score, cool_findings = _score_cooling_waste(dc)
    cool_grade = Grade(score_to_grade(cool_score))
    all_findings.extend(cool_findings)

    # --- Stranded ---
    stranded_val, stranded_score, stranded_findings = _score_stranded(dc)
    stranded_grade = Grade(score_to_grade(stranded_score))
    all_findings.extend(stranded_findings)

    # --- Build sub-metrics list ---
    sub_metrics = [
        SubMetricScore(
            name="Zombie Servers",
            value=round(zombie_val * 100, 2),
            score=zombie_score,
            weight=BOX2_ZOMBIE_WEIGHT,
            grade=zombie_grade,
            description=f"{dc.zombie_count} zombie server(s) ({zombie_val:.1%} of fleet)",
        ),
        SubMetricScore(
            name="Over-Provisioned Resources",
            value=round(overprov_val * 100, 2),
            score=overprov_score,
            weight=BOX2_OVERPROV_WEIGHT,
            grade=overprov_grade,
            description=(
                f"{dc.overprovisioned_count} over-provisioned server(s) "
                f"({overprov_val:.1%} of fleet)"
            ),
        ),
        SubMetricScore(
            name="Legacy Hardware",
            value=legacy_val,
            score=legacy_score,
            weight=BOX2_LEGACY_WEIGHT,
            grade=legacy_grade,
            description=f"Average server age: {legacy_val:.0f} months",
        ),
        SubMetricScore(
            name="Cooling Waste",
            value=round(cool_val * 100, 2),
            score=cool_score,
            weight=BOX2_COOLING_WASTE_WEIGHT,
            grade=cool_grade,
            description=(
                f"{round(cool_val * 100, 1)}% of cooling systems are overloaded "
                f"or below COP benchmark"
            ),
        ),
        SubMetricScore(
            name="Stranded Capacity",
            value=round(stranded_val * 100, 2),
            score=stranded_score,
            weight=BOX2_STRANDED_WEIGHT,
            grade=stranded_grade,
            description=(
                f"{round(stranded_val * 100, 1)}% of racks have <30% power utilization"
            ),
        ),
    ]

    # --- Weighted overall ---
    overall = (
        zombie_score * BOX2_ZOMBIE_WEIGHT
        + overprov_score * BOX2_OVERPROV_WEIGHT
        + legacy_score * BOX2_LEGACY_WEIGHT
        + cool_score * BOX2_COOLING_WASTE_WEIGHT
        + stranded_score * BOX2_STRANDED_WEIGHT
    )
    overall = round(overall, 2)
    overall_grade = Grade(score_to_grade(overall))

    return BoxScore(
        box_number=2,
        box_name=BOX2_NAME,
        overall_score=overall,
        grade=overall_grade,
        sub_metrics=sub_metrics,
        findings=all_findings,
    )
