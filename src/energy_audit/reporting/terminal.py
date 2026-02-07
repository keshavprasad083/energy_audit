"""Rich terminal report renderer.

Composes Rich tables, panels, and ASCII charts into the primary
user-facing terminal output for the energy audit.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule

from energy_audit.data.models import AuditResult, BoxScore, Recommendation
from energy_audit.scoring.weights import BOX1_NAME, BOX2_NAME, BOX3_NAME
from energy_audit.reporting.ascii_charts import (
    horizontal_bar,
    mini_gauge,
    score_gauge,
    sparkline,
    percentage_bar,
)


class TerminalRenderer:
    """Renders audit results to the terminal using Rich."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render(self, result: AuditResult, show_details: bool = True) -> None:
        """Render the full audit report to the terminal."""
        self._render_header(result)
        self._render_overall_score(result)
        self._render_box_scores(result)
        if show_details:
            self._render_box_detail(result.box1, BOX1_NAME)
            self._render_box_detail(result.box2, BOX2_NAME)
            self._render_box_detail(result.box3, BOX3_NAME)
        self._render_recommendations(result.recommendations)
        self._render_executive_summary(result)
        self._render_footer(result)

    def render_dashboard(self, result: AuditResult) -> None:
        """Render a compact single-screen dashboard."""
        self._render_header(result)
        self._render_overall_score(result)
        self._render_box_scores(result)
        self._render_key_metrics(result)
        top_recs = result.recommendations[:5]
        if top_recs:
            self._render_recommendations(top_recs)

    def render_box(self, result: AuditResult, box_number: int) -> None:
        """Render a single box in detail."""
        self._render_header(result)
        box = {1: result.box1, 2: result.box2, 3: result.box3}[box_number]
        names = {1: BOX1_NAME, 2: BOX2_NAME, 3: BOX3_NAME}
        self._render_box_detail(box, names[box_number])
        # Show recommendations for this box
        box_recs = [r for r in result.recommendations if r.box_number == box_number]
        if box_recs:
            self._render_recommendations(box_recs)

    # ------------------------------------------------------------------
    # Private rendering methods
    # ------------------------------------------------------------------

    def _render_header(self, result: AuditResult) -> None:
        dc = result.data_center
        header_text = Text()
        header_text.append("ENERGY AUDIT", style="bold cyan")
        header_text.append(" | ", style="dim")
        header_text.append(f"{dc.config.name}", style="bold")
        header_text.append(f" ({dc.config.location})", style="dim")
        header_text.append(" | ", style="dim")
        header_text.append(f"{dc.total_servers} servers", style="")
        header_text.append(f" | {dc.gpu_server_count} GPU", style="")
        header_text.append(f" | {len(dc.racks)} racks", style="")

        self.console.print()
        self.console.print(Panel(header_text, title="Energy Audit Assessment"))

    def _render_overall_score(self, result: AuditResult) -> None:
        color = result.overall_grade.color
        gauge = score_gauge(result.overall_score, width=30)

        self.console.print()
        self.console.print(
            f"  [bold]OVERALL SCORE[/bold]: {gauge}"
        )

    def _render_box_scores(self, result: AuditResult) -> None:
        """Render three box scores side by side."""
        panels = []
        for box in [result.box1, result.box2, result.box3]:
            color = box.grade.color
            gauge = score_gauge(box.overall_score, width=15)
            panel_content = f"{gauge}"
            panels.append(
                Panel(
                    panel_content,
                    title=f"[bold]BOX {box.box_number}[/bold] | {box.box_name}",
                    border_style=color,
                    width=36,
                )
            )
        self.console.print()
        self.console.print(Columns(panels, padding=(0, 1)))

    def _render_box_detail(self, box: BoxScore, description: str) -> None:
        """Render detailed sub-metric breakdown for a box."""
        color = box.grade.color

        self.console.print()
        self.console.print(Rule(
            f"[bold]BOX {box.box_number}: {box.box_name.upper()}[/bold] - {description}",
            style=color,
        ))

        # Sub-metrics table
        if box.sub_metrics:
            table = Table(show_header=True, header_style="bold", padding=(0, 1))
            table.add_column("Metric", style="bold", min_width=20)
            table.add_column("Value", justify="right", min_width=10)
            table.add_column("Score", justify="center", min_width=15)
            table.add_column("Weight", justify="right", min_width=8)
            table.add_column("Grade", justify="center", min_width=6)

            for sm in box.sub_metrics:
                grade_color = sm.grade.color
                table.add_row(
                    sm.name,
                    f"{sm.value:.2f}",
                    mini_gauge(sm.score),
                    f"{sm.weight:.0%}",
                    f"[{grade_color}]{sm.grade.value}[/{grade_color}]",
                )

            self.console.print(table)

        # Findings
        if box.findings:
            self.console.print()
            self.console.print("  [bold]Findings:[/bold]")
            for finding in box.findings:
                self.console.print(f"    [dim]\u2022[/dim] {finding}")

    def _render_recommendations(self, recommendations: list[Recommendation]) -> None:
        """Render ranked recommendations table."""
        self.console.print()
        self.console.print(Rule("[bold]RECOMMENDATIONS[/bold]"))

        table = Table(show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("#", justify="right", style="bold", width=3)
        table.add_column("Box", justify="center", width=4)
        table.add_column("Recommendation", min_width=30)
        table.add_column("Monthly Savings", justify="right", min_width=14)
        table.add_column("Energy Saved", justify="right", min_width=12)
        table.add_column("Effort", justify="center", width=8)
        table.add_column("Impact", justify="center", width=8)

        for rec in recommendations:
            effort_color = {"low": "green", "medium": "yellow", "high": "red"}.get(
                rec.effort, "white"
            )
            impact_color = {"high": "green", "medium": "yellow", "low": "red"}.get(
                rec.impact, "white"
            )
            table.add_row(
                str(rec.rank),
                str(rec.box_number),
                rec.title,
                f"${rec.monthly_savings_dollars:,.0f}",
                f"{rec.monthly_energy_savings_kwh:,.0f} kWh",
                f"[{effort_color}]{rec.effort}[/{effort_color}]",
                f"[{impact_color}]{rec.impact}[/{impact_color}]",
            )

        self.console.print(table)

        # Total savings
        total = sum(r.monthly_savings_dollars for r in recommendations)
        total_kwh = sum(r.monthly_energy_savings_kwh for r in recommendations)
        self.console.print(
            f"\n  [bold]Total Potential Savings:[/bold] "
            f"[green]${total:,.0f}/month[/green] "
            f"([green]${total * 12:,.0f}/year[/green]) | "
            f"[green]{total_kwh:,.0f} kWh/month[/green]"
        )

    def _render_executive_summary(self, result: AuditResult) -> None:
        """Render the executive summary in a panel."""
        self.console.print()
        self.console.print(
            Panel(
                result.executive_summary,
                title="[bold]EXECUTIVE SUMMARY[/bold]",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _render_key_metrics(self, result: AuditResult) -> None:
        """Render key metrics for the dashboard view."""
        dc = result.data_center

        table = Table(show_header=False, padding=(0, 2), box=None)
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")

        pue_readings = [r.pue for r in dc.energy_readings if r.pue > 0]
        pue_spark = sparkline(pue_readings[-168:], width=30) if pue_readings else "N/A"

        table.add_row("Avg PUE", f"{dc.avg_pue:.3f}  {pue_spark}")
        table.add_row("Total Energy (30d)", f"{dc.total_energy_kwh:,.0f} kWh")
        table.add_row("Total Cost (30d)", f"${dc.total_cost:,.2f}")
        table.add_row("CPU Utilization", percentage_bar("", dc.avg_cpu_utilization * 100, width=15))
        table.add_row("GPU Utilization", percentage_bar("", dc.avg_gpu_utilization * 100, width=15))
        table.add_row("Zombie Servers", f"[red]{dc.zombie_count}[/red] / {dc.total_servers}")
        table.add_row(
            "Overprovisioned",
            f"[yellow]{dc.overprovisioned_count}[/yellow] / {dc.total_servers}",
        )
        table.add_row("Avg Server Age", f"{dc.avg_server_age_months:.0f} months")

        self.console.print()
        self.console.print(Panel(table, title="[bold]KEY METRICS[/bold]"))

    def _render_footer(self, result: AuditResult) -> None:
        """Render the report footer."""
        self.console.print()
        self.console.print(Rule(style="dim"))
        self.console.print(
            f"  [dim]Generated: {result.timestamp.strftime('%Y-%m-%d %H:%M UTC')} | "
            f"energy-audit v0.1.0[/dim]"
        )
        self.console.print()
