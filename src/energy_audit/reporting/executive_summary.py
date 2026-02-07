"""Generate a crisp executive summary readable in under 2 minutes."""

from __future__ import annotations

from energy_audit.data.models import (
    AuditResult,
    BoxScore,
    DataCenter,
    Grade,
    Recommendation,
)


def generate_executive_summary(
    dc: DataCenter,
    box1: BoxScore,
    box2: BoxScore,
    box3: BoxScore,
    overall_score: float,
    overall_grade: Grade,
    recommendations: list[Recommendation],
) -> str:
    """Build the executive summary text.

    Structure:
    1. One-sentence verdict
    2. Top finding per box (3 findings)
    3. Quick wins (top 3 low-effort recommendations)
    4. Total potential monthly savings
    5. Critical action call (if any Red scores)
    """
    parts: list[str] = []

    # --- 1. Verdict ---
    grade_desc = {
        Grade.A: "excellent, industry-leading",
        Grade.B: "good, above-average",
        Grade.C: "average with significant optimization opportunities",
        Grade.D: "below average requiring urgent attention",
        Grade.F: "critical, with major efficiency issues",
    }
    desc = grade_desc.get(overall_grade, "needs assessment")

    parts.append(
        f"Your data center '{dc.config.name}' scores {overall_score:.0f}/100 "
        f"(Grade {overall_grade.value}), rated as {desc}."
    )

    # --- 2. Top finding per box ---
    parts.append("")
    parts.append("KEY FINDINGS:")
    for box in [box1, box2, box3]:
        finding = box.findings[0] if box.findings else "No specific findings."
        color_tag = box.grade.color
        parts.append(
            f"  [{color_tag}]Box {box.box_number} ({box.box_name})[/{color_tag}]: "
            f"{finding}"
        )

    # --- 3. Quick wins ---
    low_effort = [r for r in recommendations if r.effort == "low"]
    low_effort.sort(key=lambda r: r.monthly_savings_dollars, reverse=True)
    top_quick_wins = low_effort[:3]

    if top_quick_wins:
        parts.append("")
        parts.append("QUICK WINS:")
        for r in top_quick_wins:
            parts.append(
                f"  - {r.title}: save ${r.monthly_savings_dollars:,.0f}/month "
                f"({r.monthly_energy_savings_kwh:,.0f} kWh) | Effort: {r.effort}"
            )

    # --- 4. Total savings ---
    total_savings = sum(r.monthly_savings_dollars for r in recommendations)
    total_energy_savings = sum(r.monthly_energy_savings_kwh for r in recommendations)

    parts.append("")
    parts.append(
        f"TOTAL POTENTIAL SAVINGS: ${total_savings:,.0f}/month "
        f"(${total_savings * 12:,.0f}/year) | "
        f"{total_energy_savings:,.0f} kWh/month energy reduction"
    )

    # --- 5. Critical action ---
    red_boxes = [b for b in [box1, box2, box3] if b.overall_score < 50]
    if red_boxes:
        parts.append("")
        parts.append("CRITICAL ACTION NEEDED:")
        for b in red_boxes:
            parts.append(
                f"  Box {b.box_number} ({b.box_name}) scored {b.overall_score:.0f}/100 "
                f"(Grade {b.grade.value}). Immediate attention recommended."
            )

    return "\n".join(parts)
