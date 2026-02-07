# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Rich terminal rendering for fleet comparison reports."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from energy_audit.pro.fleet import FleetReport


class FleetRenderer:
    """Renders a :class:`FleetReport` as Rich tables and summary panels."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, report: FleetReport) -> None:
        """Render the full fleet comparison to the terminal.

        Displays a table comparing all sites followed by a summary panel
        with fleet-wide totals and averages.
        """
        self._render_site_table(report)
        self._render_summary_panel(report)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _grade_color(grade_value: str) -> str:
        """Return a Rich color string based on the letter grade."""
        if grade_value in ("A", "B"):
            return "green"
        if grade_value == "C":
            return "yellow"
        return "red"

    def _render_site_table(self, report: FleetReport) -> None:
        """Render the per-site comparison table."""
        table = Table(
            title="Fleet Site Comparison",
            show_header=True,
            header_style="bold",
            padding=(0, 1),
        )

        table.add_column("Site", style="bold", min_width=16)
        table.add_column("Location", min_width=14)
        table.add_column("Servers", justify="right", min_width=8)
        table.add_column("Score", justify="right", min_width=7)
        table.add_column("Grade", justify="center", min_width=6)
        table.add_column("PUE", justify="right", min_width=6)
        table.add_column("Power (kW)", justify="right", min_width=10)
        table.add_column("Zombies", justify="right", min_width=8)
        table.add_column("Carbon (t/yr)", justify="right", min_width=12)

        for site in report.sites:
            grade_str = site.overall_grade.value
            color = self._grade_color(grade_str)

            table.add_row(
                site.site_name,
                site.location,
                str(site.server_count),
                f"{site.overall_score:.1f}",
                f"[{color}]{grade_str}[/{color}]",
                f"{site.pue:.3f}",
                f"{site.total_power_kw:,.1f}",
                str(site.zombie_count),
                f"{site.carbon_tonnes_year:,.1f}",
            )

        self.console.print()
        self.console.print(table)

    def _render_summary_panel(self, report: FleetReport) -> None:
        """Render the fleet-wide summary panel beneath the table."""
        num_sites = len(report.sites)

        avg_pue = 0.0
        if num_sites:
            pue_values = [s.pue for s in report.sites if s.pue > 0]
            if pue_values:
                avg_pue = sum(pue_values) / len(pue_values)

        total_zombies = sum(s.zombie_count for s in report.sites)

        lines = [
            f"[bold]Sites analysed:[/bold]         {num_sites}",
            f"[bold]Total servers:[/bold]          {report.total_servers:,}",
            f"[bold]Average score:[/bold]          {report.avg_score:.1f}",
            f"[bold]Best site:[/bold]              [green]{report.best_site}[/green]",
            f"[bold]Worst site:[/bold]             [red]{report.worst_site}[/red]",
            f"[bold]Total power:[/bold]            {report.total_power_kw:,.1f} kW",
            f"[bold]Average PUE:[/bold]            {avg_pue:.3f}",
            f"[bold]Total zombies:[/bold]          {total_zombies}",
            f"[bold]Total carbon:[/bold]           {report.total_carbon_tonnes_year:,.1f} t CO2/yr",
        ]

        self.console.print()
        self.console.print(
            Panel(
                "\n".join(lines),
                title="[bold]Fleet Summary[/bold]",
                border_style="cyan",
                padding=(1, 2),
            )
        )
        self.console.print()
