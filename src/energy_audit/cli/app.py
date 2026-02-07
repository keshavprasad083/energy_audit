# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Main CLI application for energy-audit."""

from __future__ import annotations

import click
from rich.console import Console

from energy_audit.data.generator import DataCenterGenerator
from energy_audit.data.models import AuditResult, Grade
from energy_audit.data.profiles import PROFILES, get_profile
from energy_audit.recommendations.engine import RecommendationEngine
from energy_audit.reporting.executive_summary import generate_executive_summary
from energy_audit.reporting.terminal import TerminalRenderer
from energy_audit.scoring.engine import ScoringEngine

PROFILE_CHOICES = list(PROFILES.keys())


def _run_audit(profile_name: str, seed: int | None, console: Console) -> AuditResult:
    """Run a full audit and return the result."""
    profile = get_profile(profile_name)
    gen = DataCenterGenerator(profile, seed=seed)

    with console.status("[bold cyan]Generating data center simulation..."):
        dc = gen.generate()

    with console.status("[bold cyan]Running scoring engine..."):
        engine = ScoringEngine()
        box1, box2, box3, overall_score, overall_grade = engine.score(dc)

    with console.status("[bold cyan]Generating recommendations..."):
        rec_engine = RecommendationEngine()
        recommendations = rec_engine.generate(dc, box1, box2, box3)

    executive_summary = generate_executive_summary(
        dc, box1, box2, box3, overall_score, overall_grade, recommendations
    )

    return AuditResult(
        data_center=dc,
        box1=box1,
        box2=box2,
        box3=box3,
        overall_score=overall_score,
        overall_grade=overall_grade,
        recommendations=recommendations,
        executive_summary=executive_summary,
    )


@click.group()
@click.version_option(version="0.1.0")
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.pass_context
def cli(ctx: click.Context, no_color: bool) -> None:
    """energy-audit: AI Data Center Energy Assessment Tool

    Assess data center energy consumption across three pillars:

    \b
      Box 1 (Current Operations): Energy efficiency analysis
      Box 2 (Legacy & Waste):     Identify waste and zombie resources
      Box 3 (Future Readiness):   Forecast needs and opportunities
    """
    ctx.ensure_object(dict)
    ctx.obj["console"] = Console(no_color=no_color)


@cli.command()
@click.option(
    "--profile", "-p",
    type=click.Choice(PROFILE_CHOICES),
    default="medium_enterprise",
    help="Data center profile to simulate",
)
@click.option("--seed", "-s", type=int, default=None, help="Random seed for reproducibility")
@click.option(
    "--export-pdf", type=click.Path(), default=None,
    help="Export results to PDF at this path",
)
@click.option(
    "--export-json", type=click.Path(), default=None,
    help="Export raw results as JSON at this path",
)
@click.option("--show-details/--no-details", default=True, help="Show detailed scoring breakdown")
@click.option(
    "--source", type=click.Choice(["sim", "file", "live"]), default="sim",
    help="Data source: sim (simulated), file (CSV/JSON), live (real collectors)",
)
@click.option(
    "--config", "-c", type=click.Path(), default=None,
    help="Pro config YAML file (required for --source file/live)",
)
@click.pass_context
def run(
    ctx: click.Context,
    profile: str,
    seed: int | None,
    export_pdf: str | None,
    export_json: str | None,
    show_details: bool,
    source: str,
    config: str | None,
) -> None:
    """Run a full energy audit across all three pillars."""
    console: Console = ctx.obj["console"]

    if source == "sim":
        result = _run_audit(profile, seed, console)
    else:
        if not config:
            console.print("[red]--config/-c is required for --source file/live[/]")
            raise SystemExit(1)
        try:
            from energy_audit.pro.cli import _run_pro_audit
            result = _run_pro_audit(config, console)
        except ImportError:
            console.print("[red]Pro features require: pip install -e '.[pro]'[/]")
            raise SystemExit(1)

    renderer = TerminalRenderer(console)
    renderer.render(result, show_details=show_details)

    if export_pdf:
        _export_pdf(result, export_pdf, console)

    if export_json:
        _export_json(result, export_json, console)


@cli.command()
@click.option(
    "--profile", "-p",
    type=click.Choice(PROFILE_CHOICES),
    default="medium_enterprise",
    help="Data center profile to simulate",
)
@click.option("--seed", "-s", type=int, default=None, help="Random seed for reproducibility")
@click.pass_context
def present(ctx: click.Context, profile: str, seed: int | None) -> None:
    """Box 1: Analyze current energy consumption (Current Operations)."""
    console: Console = ctx.obj["console"]
    result = _run_audit(profile, seed, console)
    renderer = TerminalRenderer(console)
    renderer.render_box(result, box_number=1)


@cli.command()
@click.option(
    "--profile", "-p",
    type=click.Choice(PROFILE_CHOICES),
    default="medium_enterprise",
    help="Data center profile to simulate",
)
@click.option("--seed", "-s", type=int, default=None, help="Random seed for reproducibility")
@click.pass_context
def forget(ctx: click.Context, profile: str, seed: int | None) -> None:
    """Box 2: Identify legacy waste and zombies (Legacy & Waste)."""
    console: Console = ctx.obj["console"]
    result = _run_audit(profile, seed, console)
    renderer = TerminalRenderer(console)
    renderer.render_box(result, box_number=2)


@cli.command()
@click.option(
    "--profile", "-p",
    type=click.Choice(PROFILE_CHOICES),
    default="medium_enterprise",
    help="Data center profile to simulate",
)
@click.option("--seed", "-s", type=int, default=None, help="Random seed for reproducibility")
@click.pass_context
def future(ctx: click.Context, profile: str, seed: int | None) -> None:
    """Box 3: Forecast needs and opportunities (Future Readiness)."""
    console: Console = ctx.obj["console"]
    result = _run_audit(profile, seed, console)
    renderer = TerminalRenderer(console)
    renderer.render_box(result, box_number=3)


@cli.command()
@click.option(
    "--profile", "-p",
    type=click.Choice(PROFILE_CHOICES),
    default="medium_enterprise",
    help="Data center profile to simulate",
)
@click.option("--seed", "-s", type=int, default=None, help="Random seed for reproducibility")
@click.pass_context
def dashboard(ctx: click.Context, profile: str, seed: int | None) -> None:
    """Display a compact summary dashboard with key metrics."""
    console: Console = ctx.obj["console"]
    result = _run_audit(profile, seed, console)
    renderer = TerminalRenderer(console)
    renderer.render_dashboard(result)


@cli.command()
@click.option(
    "--format", "-f",
    type=click.Choice(["pdf", "json"]),
    default="pdf",
    help="Export format",
)
@click.option("--output", "-o", type=click.Path(), required=True, help="Output file path")
@click.option(
    "--profile", "-p",
    type=click.Choice(PROFILE_CHOICES),
    default="medium_enterprise",
    help="Data center profile to simulate",
)
@click.option("--seed", "-s", type=int, default=None, help="Random seed for reproducibility")
@click.pass_context
def export(
    ctx: click.Context,
    format: str,
    output: str,
    profile: str,
    seed: int | None,
) -> None:
    """Export audit report to PDF or JSON."""
    console: Console = ctx.obj["console"]
    result = _run_audit(profile, seed, console)

    if format == "pdf":
        _export_pdf(result, output, console)
    elif format == "json":
        _export_json(result, output, console)


def _export_pdf(result: AuditResult, path: str, console: Console) -> None:
    """Export to PDF."""
    try:
        from energy_audit.reporting.pdf_report import PDFReportGenerator

        with console.status("[bold cyan]Generating PDF report..."):
            generator = PDFReportGenerator()
            generator.generate(result, path)
        console.print(f"  [green]PDF report exported to:[/green] {path}")
    except ImportError:
        console.print("[red]PDF export requires reportlab. Install with: pip install reportlab[/red]")


def _export_json(result: AuditResult, path: str, console: Console) -> None:
    """Export to JSON."""
    import json

    with open(path, "w") as f:
        f.write(result.model_dump_json(indent=2))
    console.print(f"  [green]JSON report exported to:[/green] {path}")


# ---------------------------------------------------------------------------
# Interactive Maturity Assessment
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--history", is_flag=True, default=False,
    help="View past assessment history",
)
@click.option(
    "--compare", is_flag=True, default=False,
    help="Compare the two most recent assessments for a facility",
)
@click.option(
    "--facility", "-f", type=str, default=None,
    help="Facility name (for --history or --compare)",
)
@click.option(
    "--export-pdf", type=click.Path(), default=None,
    help="Export assessment report to PDF",
)
@click.pass_context
def assess(
    ctx: click.Context,
    history: bool,
    compare: bool,
    facility: str | None,
    export_pdf: str | None,
) -> None:
    """Run an interactive energy maturity assessment survey.

    \b
    Answer 35 questions about your data center operations to receive:
      - Maturity scores across three assessment pillars
      - Bias and consistency analysis
      - Gap analysis and improvement roadmap
      - Status quo risk indicators
    """
    console: Console = ctx.obj["console"]

    from energy_audit.assessment.engine import AssessmentEngine
    from energy_audit.assessment.history import (
        compare_assessments,
        get_all_history,
        get_facility_history,
        get_latest_assessment,
        load_assessment,
        save_assessment,
    )
    from energy_audit.assessment.report import AssessmentRenderer

    renderer = AssessmentRenderer(console)

    # --history mode
    if history:
        if facility:
            entries = get_facility_history(facility)
        else:
            entries = get_all_history()

        formatted = [
            {
                "facility": e.facility_name,
                "assessor": e.assessor_name,
                "date": e.timestamp.strftime("%Y-%m-%d"),
                "score": e.overall_score,
                "grade": e.overall_grade.value,
                "grade_color": e.overall_grade.color,
                "maturity": e.overall_maturity.value,
                "maturity_color": e.overall_maturity.color,
            }
            for e in entries
        ]
        renderer.render_history(formatted, facility_filter=facility)
        return

    # --compare mode
    if compare:
        if not facility:
            console.print("[red]--compare requires --facility/-f to specify which facility[/]")
            return
        entries = get_facility_history(facility)
        if len(entries) < 2:
            console.print(
                f"[yellow]Need at least 2 assessments for '{facility}' to compare. "
                f"Found {len(entries)}.[/]"
            )
            return
        result_b = load_assessment(entries[0].file_path)
        result_a = load_assessment(entries[1].file_path)
        comp = compare_assessments(result_a, result_b)
        renderer.render_comparison(comp, result_a, result_b)
        return

    # Interactive assessment
    previous = None
    if facility:
        previous = get_latest_assessment(facility)

    engine = AssessmentEngine(console)
    result = engine.run(previous=previous)

    # Save
    path = save_assessment(result)
    console.print(f"\n  [green]Assessment saved to:[/green] {path}")

    # Render report
    renderer.render(result)

    if export_pdf:
        console.print("[yellow]PDF export for assessments coming soon.[/]")


# ---------------------------------------------------------------------------
# Register Pro CLI (if installed)
# ---------------------------------------------------------------------------

try:
    from energy_audit.pro.cli import pro_cli
    cli.add_command(pro_cli)
except ImportError:
    pass  # Pro module not installed
