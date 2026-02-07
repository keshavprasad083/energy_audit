# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Terminal report renderer for the interactive maturity assessment.

Follows the same Rich-based pattern as ``TerminalRenderer`` in the
reporting module.
"""

from __future__ import annotations

from rich.console import Console
from rich.columns import Columns
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from energy_audit.assessment.models import (
    AssessmentResult,
    MaturityLevel,
    Pillar,
    PillarScore,
)
from energy_audit.assessment.questions import QUESTION_MAP
from energy_audit.reporting.ascii_charts import mini_gauge, score_gauge


class AssessmentRenderer:
    """Renders assessment results to the terminal using Rich."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render(self, result: AssessmentResult) -> None:
        """Render the full assessment report."""
        self._render_header(result)
        self._render_overall_maturity(result)
        self._render_pillar_scores(result)
        self._render_pillar_details(result)
        self._render_bias_warnings(result)
        self._render_gap_analysis(result)
        self._render_improvement_roadmap(result)
        self._render_status_quo_indicator(result)
        self._render_footer()

    def render_history(
        self, entries: list[dict], facility_filter: str | None = None
    ) -> None:
        """Render assessment history table."""
        self.console.print()
        title = "Assessment History"
        if facility_filter:
            title += f" — {facility_filter}"
        self.console.print(Rule(f"[bold]{title}[/]"))

        if not entries:
            self.console.print("  [dim]No assessments found.[/]")
            return

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("#", justify="right", width=3)
        table.add_column("Facility", min_width=20)
        table.add_column("Assessor", min_width=15)
        table.add_column("Date", min_width=12)
        table.add_column("Score", justify="center", min_width=15)
        table.add_column("Grade", justify="center", width=6)
        table.add_column("Maturity", min_width=12)

        for i, entry in enumerate(entries, 1):
            grade_color = entry.get("grade_color", "white")
            mat_color = entry.get("maturity_color", "white")
            table.add_row(
                str(i),
                entry["facility"],
                entry["assessor"],
                entry["date"],
                mini_gauge(entry["score"]),
                f"[{grade_color}]{entry['grade']}[/{grade_color}]",
                f"[{mat_color}]{entry['maturity']}[/{mat_color}]",
            )

        self.console.print(table)

    def render_comparison(
        self,
        comparison: dict[str, dict],
        result_a: AssessmentResult,
        result_b: AssessmentResult,
    ) -> None:
        """Render a side-by-side comparison between two assessments."""
        self.console.print()
        self.console.print(Rule("[bold]Assessment Comparison[/]"))

        date_a = result_a.timestamp.strftime("%Y-%m-%d")
        date_b = result_b.timestamp.strftime("%Y-%m-%d")

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("Pillar", min_width=20)
        table.add_column(f"Score ({date_a})", justify="center", min_width=12)
        table.add_column(f"Score ({date_b})", justify="center", min_width=12)
        table.add_column("Delta", justify="center", min_width=10)
        table.add_column(f"Maturity ({date_a})", min_width=12)
        table.add_column(f"Maturity ({date_b})", min_width=12)

        for name, data in comparison.items():
            delta = data["delta"]
            if delta > 0:
                delta_str = f"[green]+{delta:.1f}[/]"
            elif delta < 0:
                delta_str = f"[red]{delta:.1f}[/]"
            else:
                delta_str = f"[dim]0.0[/]"

            table.add_row(
                name,
                mini_gauge(data["score_a"]),
                mini_gauge(data["score_b"]),
                delta_str,
                data["maturity_a"],
                data["maturity_b"],
            )

        self.console.print(table)

    # ------------------------------------------------------------------
    # Private rendering methods
    # ------------------------------------------------------------------

    def _render_header(self, result: AssessmentResult) -> None:
        header = Text()
        header.append("ENERGY MATURITY ASSESSMENT\n", style="bold cyan")
        header.append(f"Facility: {result.facility_name}", style="bold")
        if result.assessor_name:
            header.append(f" | Assessor: {result.assessor_name}", style="dim")
        header.append(
            f" | {result.timestamp.strftime('%Y-%m-%d %H:%M UTC')}", style="dim"
        )
        self.console.print()
        self.console.print(Panel(header, border_style="cyan"))

    def _render_overall_maturity(self, result: AssessmentResult) -> None:
        gauge = score_gauge(result.overall_score, width=30)
        mat = result.overall_maturity
        self.console.print()
        self.console.print(f"  [bold]OVERALL MATURITY[/]: {gauge}")
        self.console.print(
            f"  [bold]Level:[/] [{mat.color}]{mat.value}[/] — {mat.description}"
        )

    def _render_pillar_scores(self, result: AssessmentResult) -> None:
        """Render pillar scores side-by-side (Box 1-3 only)."""
        panels = []
        for ps in result.pillar_scores:
            if ps.pillar == Pillar.ORG:
                continue
            color = ps.grade.color
            gauge = score_gauge(ps.score, width=15)
            mat = ps.maturity
            content = f"{gauge}\n[{mat.color}]{mat.value}[/]"
            panels.append(
                Panel(
                    content,
                    title=f"[bold]{ps.display_name}[/]",
                    border_style=color,
                    width=36,
                )
            )
        self.console.print()
        self.console.print(Columns(panels, padding=(0, 1)))

    def _render_pillar_details(self, result: AssessmentResult) -> None:
        """Render per-question details for each pillar."""
        for ps in result.pillar_scores:
            color = ps.grade.color
            self.console.print()
            self.console.print(Rule(
                f"[bold]{ps.display_name.upper()}[/]",
                style=color,
            ))

            table = Table(show_header=True, header_style="bold", padding=(0, 1))
            table.add_column("Topic", style="bold", min_width=24)
            table.add_column("Score", justify="center", min_width=15)
            table.add_column("Weight", justify="right", min_width=8)
            table.add_column("Maturity", min_width=12)

            for answer in ps.answers:
                q = QUESTION_MAP.get(answer.question_id)
                if not q:
                    continue
                mat = MaturityLevel.from_score(answer.selected_score)
                table.add_row(
                    q.topic,
                    mini_gauge(answer.selected_score),
                    f"{q.weight:.0%}",
                    f"[{mat.color}]{mat.value}[/]",
                )

            self.console.print(table)

    def _render_bias_warnings(self, result: AssessmentResult) -> None:
        """Render bias and consistency warnings."""
        bias = result.bias_analysis
        has_warnings = (
            bias.consistency_warnings
            or bias.overconfidence_pillars
            or bias.blind_spots
            or bias.drift_alerts
        )
        if not has_warnings:
            return

        self.console.print()
        items: list[str] = []

        for cw in bias.consistency_warnings:
            items.append(f"[yellow]\u26a0[/] {cw.message}")

        for oc in bias.overconfidence_pillars:
            items.append(f"[yellow]\u26a0[/] Overconfidence: {oc}")

        for alert in bias.drift_alerts:
            items.append(f"[yellow]\u26a0[/] Drift: {alert}")

        for spot in bias.blind_spots:
            items.append(f"[yellow]\u2022[/] {spot}")

        content = "\n".join(items)
        self.console.print(Panel(
            content,
            title="[bold yellow]Bias & Consistency Analysis[/]",
            border_style="yellow",
        ))

    def _render_gap_analysis(self, result: AssessmentResult) -> None:
        """Render top gaps ranked by impact (weight * gap-to-100)."""
        self.console.print()
        self.console.print(Rule("[bold]GAP ANALYSIS[/]"))

        gaps: list[tuple[str, float, float, float, str]] = []
        for ps in result.pillar_scores:
            for answer in ps.answers:
                q = QUESTION_MAP.get(answer.question_id)
                if not q:
                    continue
                gap = 100 - answer.selected_score
                impact = gap * q.weight
                gaps.append((
                    q.topic,
                    answer.selected_score,
                    q.weight,
                    impact,
                    ps.display_name,
                ))

        gaps.sort(key=lambda g: g[3], reverse=True)
        top_gaps = gaps[:10]

        if not top_gaps:
            self.console.print("  [dim]No gaps identified.[/]")
            return

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("#", justify="right", width=3)
        table.add_column("Topic", min_width=24)
        table.add_column("Pillar", min_width=18)
        table.add_column("Current", justify="center", min_width=10)
        table.add_column("Gap", justify="center", min_width=8)
        table.add_column("Weight", justify="right", min_width=8)
        table.add_column("Impact", justify="right", min_width=8)

        for i, (topic, score, weight, impact, pillar) in enumerate(top_gaps, 1):
            gap = 100 - score
            gap_color = "red" if gap >= 50 else "yellow" if gap >= 25 else "green"
            table.add_row(
                str(i),
                topic,
                pillar,
                f"{score:.0f}",
                f"[{gap_color}]{gap:.0f}[/]",
                f"{weight:.0%}",
                f"{impact:.1f}",
            )

        self.console.print(table)

    def _render_improvement_roadmap(self, result: AssessmentResult) -> None:
        """Render an improvement roadmap based on gap analysis."""
        self.console.print()
        self.console.print(Rule("[bold]IMPROVEMENT ROADMAP[/]"))

        roadmap: list[tuple[str, float, str, str, str]] = []
        for ps in result.pillar_scores:
            for answer in ps.answers:
                q = QUESTION_MAP.get(answer.question_id)
                if not q:
                    continue
                gap = 100 - answer.selected_score
                if gap < 25:
                    continue
                current_mat = MaturityLevel.from_score(answer.selected_score)
                target_score = min(answer.selected_score + 25, 100)
                target_mat = MaturityLevel.from_score(target_score)
                action = self._suggest_action(q.topic, current_mat)
                roadmap.append((
                    q.topic,
                    gap * q.weight,
                    f"{current_mat.value} \u2192 {target_mat.value}",
                    action,
                    ps.display_name,
                ))

        roadmap.sort(key=lambda r: r[1], reverse=True)
        top = roadmap[:10]

        if not top:
            self.console.print("  [green]All areas at high maturity![/]")
            return

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("#", justify="right", width=3)
        table.add_column("Topic", min_width=20)
        table.add_column("Pillar", min_width=16)
        table.add_column("Transition", min_width=22)
        table.add_column("Suggested Action", min_width=30)

        for i, (topic, _, transition, action, pillar) in enumerate(top, 1):
            table.add_row(str(i), topic, pillar, transition, action)

        self.console.print(table)

    def _render_status_quo_indicator(self, result: AssessmentResult) -> None:
        """Render the status quo risk indicator."""
        sq = result.bias_analysis.status_quo_score
        ev = result.bias_analysis.evidence_rate

        self.console.print()

        if sq >= 70:
            color = "red"
            label = "HIGH INERTIA"
            msg = "Strong resistance to change detected — prioritize quick wins to build momentum"
        elif sq >= 40:
            color = "yellow"
            label = "MODERATE INERTIA"
            msg = "Some openness to change — focus on demonstrating ROI for key initiatives"
        else:
            color = "green"
            label = "LOW INERTIA"
            msg = "Organization appears receptive to change — leverage this for ambitious improvements"

        content = (
            f"  Status Quo Risk: [{color}]{label}[/] (score: {sq:.0f}/100)\n"
            f"  Evidence Rate: {ev:.0%} of high-maturity answers backed by evidence\n"
            f"  [dim]{msg}[/]"
        )
        self.console.print(Panel(
            content,
            title="[bold]Status Quo Indicators[/]",
            border_style=color,
        ))

    def _render_footer(self) -> None:
        self.console.print()
        self.console.print(
            "  [dim]Assessment saved. Run [bold]energy-audit assess --history[/bold] "
            "to view past assessments.[/]"
        )
        self.console.print()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _suggest_action(topic: str, current: MaturityLevel) -> str:
        """Generate a brief action suggestion based on topic and current level."""
        if current == MaturityLevel.AD_HOC:
            return f"Establish basic {topic.lower()} processes and documentation"
        if current == MaturityLevel.REACTIVE:
            return f"Implement regular {topic.lower()} reviews and tracking"
        if current == MaturityLevel.DEFINED:
            return f"Automate {topic.lower()} monitoring and set improvement targets"
        if current == MaturityLevel.OPTIMIZED:
            return f"Advance {topic.lower()} with predictive analytics and innovation"
        return f"Maintain leadership in {topic.lower()}"
