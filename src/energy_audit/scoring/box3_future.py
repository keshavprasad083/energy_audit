# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Box 3: Future Readiness -- scoring of forward-looking readiness.

Evaluates the facility's preparedness for future growth including capacity
forecasting, hardware refresh planning, workload scheduling optimization,
renewable energy adoption, and efficiency trend direction.
"""

from __future__ import annotations

from energy_audit.data.models import (
    DataCenter,
    BoxScore,
    Grade,
    SubMetricScore,
)
from energy_audit.scoring.thresholds import (
    REFRESH_WINDOW_MAX,
    REFRESH_WINDOW_MIN,
    score_to_grade,
)
from energy_audit.scoring.weights import (
    BOX3_FORECAST_WEIGHT,
    BOX3_NAME,
    BOX3_REFRESH_WEIGHT,
    BOX3_RENEWABLE_WEIGHT,
    BOX3_SCHEDULING_WEIGHT,
    BOX3_TREND_WEIGHT,
)


# ---------------------------------------------------------------------------
# Individual sub-metric scorers
# ---------------------------------------------------------------------------

def _score_forecast(dc: DataCenter) -> tuple[float, float, list[str]]:
    """Score forecast readiness based on power headroom.

    Estimates months to capacity exhaustion via linear extrapolation from
    the energy reading trend.  If months_to_capacity > 24: 100, > 12: 70,
    > 6: 40, else 10.

    Returns (months_to_capacity, score, findings).
    """
    findings: list[str] = []

    total_capacity_kw = dc.config.total_power_capacity_mw * 1000.0

    if not dc.energy_readings or total_capacity_kw <= 0:
        return 0.0, 50.0, ["Insufficient data to forecast capacity runway."]

    # Sort readings chronologically
    readings = sorted(dc.energy_readings, key=lambda r: r.timestamp)

    # Current power usage (average of last 24 readings or all if fewer)
    recent = readings[-24:] if len(readings) >= 24 else readings
    current_avg_kw = sum(r.total_facility_power_kw for r in recent) / len(recent)

    # Estimate growth rate from trend
    if len(readings) >= 48:
        early = readings[:24]
        late = readings[-24:]
        early_avg = sum(r.total_facility_power_kw for r in early) / len(early)
        late_avg = sum(r.total_facility_power_kw for r in late) / len(late)

        # Hours between the midpoints of early and late windows
        hours_span = max(1, len(readings) - 24)
        growth_kw_per_hour = (late_avg - early_avg) / hours_span

        if growth_kw_per_hour > 0:
            remaining_kw = total_capacity_kw - current_avg_kw
            hours_to_capacity = remaining_kw / growth_kw_per_hour
            months_to_capacity = hours_to_capacity / (24.0 * 30.0)
        else:
            # Flat or declining usage -- effectively infinite runway
            months_to_capacity = 120.0
    else:
        # Not enough data for trend -- estimate based on headroom only
        headroom_pct = (total_capacity_kw - current_avg_kw) / total_capacity_kw
        if headroom_pct > 0.50:
            months_to_capacity = 36.0
        elif headroom_pct > 0.25:
            months_to_capacity = 18.0
        else:
            months_to_capacity = 6.0

    months_to_capacity = max(0.0, min(120.0, months_to_capacity))

    # Score
    if months_to_capacity > 24:
        score = 100.0
    elif months_to_capacity > 12:
        score = 70.0
    elif months_to_capacity > 6:
        score = 40.0
    else:
        score = 10.0

    utilization_pct = (current_avg_kw / total_capacity_kw) * 100.0
    findings.append(
        f"Current power utilization: {utilization_pct:.0f}% of {dc.config.total_power_capacity_mw:.1f} MW capacity."
    )
    findings.append(
        f"Estimated {months_to_capacity:.0f} months until capacity exhaustion."
    )
    if months_to_capacity < 12:
        findings.append(
            "CRITICAL: Less than 12 months of capacity runway -- "
            "expansion planning needed immediately."
        )

    return round(months_to_capacity, 1), round(score, 2), findings


def _score_refresh(dc: DataCenter) -> tuple[float, float, list[str]]:
    """Score hardware refresh planning.

    Percentage of fleet within optimal refresh window (36-60 months).
    Higher percentage = higher score.

    Returns (pct_in_window, score, findings).
    """
    findings: list[str] = []
    total = dc.total_servers
    if total == 0:
        return 0.0, 50.0, findings

    in_window = sum(
        1 for s in dc.servers
        if REFRESH_WINDOW_MIN <= s.age_months <= REFRESH_WINDOW_MAX
    )
    too_young = sum(1 for s in dc.servers if s.age_months < REFRESH_WINDOW_MIN)
    too_old = sum(1 for s in dc.servers if s.age_months > REFRESH_WINDOW_MAX)

    pct_in_window = in_window / total
    score = pct_in_window * 100.0

    # Penalize heavily for servers past useful life
    if too_old > 0:
        old_penalty = (too_old / total) * 50.0
        score = max(0.0, score - old_penalty)
        findings.append(
            f"{too_old} server(s) ({too_old / total:.1%}) are past the "
            f"{REFRESH_WINDOW_MAX}-month refresh window -- prioritize replacement."
        )

    if in_window > 0:
        findings.append(
            f"{in_window} server(s) ({pct_in_window:.1%}) are within the optimal "
            f"{REFRESH_WINDOW_MIN}-{REFRESH_WINDOW_MAX} month refresh window."
        )

    return round(pct_in_window, 4), round(max(0.0, min(100.0, score)), 2), findings


def _score_scheduling(dc: DataCenter) -> tuple[float, float, list[str]]:
    """Score workload scheduling optimization potential.

    Percentage of schedulable workloads multiplied by estimated off-peak
    savings potential.

    Returns (schedulable_pct, score, findings).
    """
    findings: list[str] = []
    if not dc.workloads:
        return 0.0, 50.0, ["No workload data available for scheduling analysis."]

    total_workloads = len(dc.workloads)
    schedulable = [w for w in dc.workloads if w.is_schedulable]
    schedulable_count = len(schedulable)
    schedulable_pct = schedulable_count / total_workloads

    # Estimate off-peak savings: schedulable workloads that could shift to
    # lower cost / lower carbon periods.  Assume 15% savings potential per
    # schedulable workload.
    savings_factor = 0.15
    schedulable_power_kw = sum(w.power_consumption_kw for w in schedulable)
    total_power_kw = sum(w.power_consumption_kw for w in dc.workloads)
    schedulable_power_pct = (
        schedulable_power_kw / total_power_kw if total_power_kw > 0 else 0.0
    )

    # Score: combination of what % is schedulable and the power share
    score = min(100.0, (schedulable_pct * 60.0 + schedulable_power_pct * 40.0))

    if schedulable_count > 0:
        potential_savings_kwh = schedulable_power_kw * 720.0 * savings_factor
        potential_cost_savings = potential_savings_kwh * dc.config.energy_cost_per_kwh
        findings.append(
            f"{schedulable_count} of {total_workloads} workloads ({schedulable_pct:.1%}) "
            f"are schedulable for off-peak operation."
        )
        findings.append(
            f"Potential monthly savings from scheduling: "
            f"{potential_savings_kwh:,.0f} kWh (${potential_cost_savings:,.0f})."
        )
    else:
        findings.append(
            "No schedulable workloads identified -- consider time-shifting "
            "batch and training jobs."
        )

    return round(schedulable_pct, 4), round(score, 2), findings


def _score_renewable(dc: DataCenter) -> tuple[float, float, list[str]]:
    """Score renewable energy adoption.

    Score = renewable_percentage * 100 (since it is a 0-1 fraction).
    Bonus +10 if PPA is available but renewable < 0.5.

    Returns (renewable_pct, score, findings).
    """
    findings: list[str] = []
    renewable = dc.config.renewable_percentage  # 0.0-1.0 fraction
    score = renewable * 100.0

    # Bonus for untapped PPA potential
    if dc.config.ppa_available and renewable < 0.50:
        score = min(100.0, score + 10.0)
        findings.append(
            f"Power Purchase Agreement is available but renewable mix is only "
            f"{renewable:.0%} -- significant opportunity to increase green energy."
        )

    if renewable >= 0.80:
        findings.append(
            f"Excellent renewable energy adoption at {renewable:.0%}."
        )
    elif renewable >= 0.50:
        findings.append(
            f"Moderate renewable adoption at {renewable:.0%} -- room for improvement."
        )
    else:
        findings.append(
            f"Low renewable energy at {renewable:.0%} -- explore solar, wind, or PPA options."
        )

    return round(renewable, 4), round(min(100.0, score), 2), findings


def _score_trend(dc: DataCenter) -> tuple[float, float, list[str]]:
    """Score efficiency trend direction.

    Compares first 7 days (168 hours) PUE average to last 7 days PUE average.
    Improving = 100, stable = 60, degrading = 20.

    Returns (trend_delta, score, findings).
    """
    findings: list[str] = []
    readings = sorted(dc.energy_readings, key=lambda r: r.timestamp)
    valid = [r for r in readings if r.pue > 0]

    if len(valid) < 48:
        findings.append("Insufficient PUE data to determine efficiency trend.")
        return 0.0, 60.0, findings  # Neutral when no data

    # First 7 days = 168 hours
    window = min(168, len(valid) // 3)  # At least 1/3 of data for each window
    early_readings = valid[:window]
    late_readings = valid[-window:]

    early_avg = sum(r.pue for r in early_readings) / len(early_readings)
    late_avg = sum(r.pue for r in late_readings) / len(late_readings)

    delta = late_avg - early_avg  # Negative = improving (PUE going down)

    if delta < -0.02:
        # Improving
        score = 100.0
        findings.append(
            f"PUE trend is improving: {early_avg:.3f} -> {late_avg:.3f} "
            f"(delta: {delta:+.3f})."
        )
    elif delta > 0.02:
        # Degrading
        score = 20.0
        findings.append(
            f"PUE trend is degrading: {early_avg:.3f} -> {late_avg:.3f} "
            f"(delta: {delta:+.3f}) -- investigate root cause."
        )
    else:
        # Stable
        score = 60.0
        findings.append(
            f"PUE trend is stable: {early_avg:.3f} -> {late_avg:.3f} "
            f"(delta: {delta:+.3f})."
        )

    return round(delta, 4), round(score, 2), findings


# ---------------------------------------------------------------------------
# Box 3 orchestrator
# ---------------------------------------------------------------------------

def score_box3(dc: DataCenter) -> BoxScore:
    """Compute the Box 3 (Future Readiness) score.

    Evaluates forward-looking readiness across five sub-metrics: forecast
    readiness, hardware refresh planning, scheduling optimization, renewable
    energy adoption, and efficiency trend direction.
    """
    all_findings: list[str] = []

    # --- Forecast ---
    forecast_val, forecast_score, forecast_findings = _score_forecast(dc)
    forecast_grade = Grade(score_to_grade(forecast_score))
    all_findings.extend(forecast_findings)

    # --- Refresh ---
    refresh_val, refresh_score, refresh_findings = _score_refresh(dc)
    refresh_grade = Grade(score_to_grade(refresh_score))
    all_findings.extend(refresh_findings)

    # --- Scheduling ---
    sched_val, sched_score, sched_findings = _score_scheduling(dc)
    sched_grade = Grade(score_to_grade(sched_score))
    all_findings.extend(sched_findings)

    # --- Renewable ---
    renew_val, renew_score, renew_findings = _score_renewable(dc)
    renew_grade = Grade(score_to_grade(renew_score))
    all_findings.extend(renew_findings)

    # --- Trend ---
    trend_val, trend_score, trend_findings = _score_trend(dc)
    trend_grade = Grade(score_to_grade(trend_score))
    all_findings.extend(trend_findings)

    # --- Build sub-metrics list ---
    sub_metrics = [
        SubMetricScore(
            name="Forecast Readiness",
            value=forecast_val,
            score=forecast_score,
            weight=BOX3_FORECAST_WEIGHT,
            grade=forecast_grade,
            description=f"Estimated {forecast_val:.0f} months until capacity exhaustion",
        ),
        SubMetricScore(
            name="Hardware Refresh",
            value=round(refresh_val * 100, 2),
            score=refresh_score,
            weight=BOX3_REFRESH_WEIGHT,
            grade=refresh_grade,
            description=(
                f"{refresh_val:.1%} of fleet within optimal "
                f"{REFRESH_WINDOW_MIN}-{REFRESH_WINDOW_MAX} month window"
            ),
        ),
        SubMetricScore(
            name="Scheduling Optimization",
            value=round(sched_val * 100, 2),
            score=sched_score,
            weight=BOX3_SCHEDULING_WEIGHT,
            grade=sched_grade,
            description=f"{sched_val:.1%} of workloads are schedulable for off-peak",
        ),
        SubMetricScore(
            name="Renewable Energy",
            value=round(renew_val * 100, 2),
            score=renew_score,
            weight=BOX3_RENEWABLE_WEIGHT,
            grade=renew_grade,
            description=f"{renew_val:.0%} of energy from renewable sources",
        ),
        SubMetricScore(
            name="Efficiency Trend",
            value=trend_val,
            score=trend_score,
            weight=BOX3_TREND_WEIGHT,
            grade=trend_grade,
            description=f"PUE trend delta: {trend_val:+.4f} (negative = improving)",
        ),
    ]

    # --- Weighted overall ---
    overall = (
        forecast_score * BOX3_FORECAST_WEIGHT
        + refresh_score * BOX3_REFRESH_WEIGHT
        + sched_score * BOX3_SCHEDULING_WEIGHT
        + renew_score * BOX3_RENEWABLE_WEIGHT
        + trend_score * BOX3_TREND_WEIGHT
    )
    overall = round(overall, 2)
    overall_grade = Grade(score_to_grade(overall))

    return BoxScore(
        box_number=3,
        box_name=BOX3_NAME,
        overall_score=overall,
        grade=overall_grade,
        sub_metrics=sub_metrics,
        findings=all_findings,
    )
