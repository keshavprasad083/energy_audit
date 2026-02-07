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

    with console.status("[bold cyan]Running 3-Box scoring engine..."):
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

    Assess energy consumption using Vijay Govindarajan's 3-Box Strategy:

    \b
      Box 1 (Present): Current energy efficiency analysis
      Box 2 (Past):    Identify legacy waste and zombie resources
      Box 3 (Future):  Forecast needs and optimization opportunities
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
@click.pass_context
def run(
    ctx: click.Context,
    profile: str,
    seed: int | None,
    export_pdf: str | None,
    export_json: str | None,
    show_details: bool,
) -> None:
    """Run a full 3-box energy audit."""
    console: Console = ctx.obj["console"]
    result = _run_audit(profile, seed, console)

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
    """Box 1: Analyze current energy consumption (Manage the Present)."""
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
    """Box 2: Identify legacy waste and zombies (Selectively Forget the Past)."""
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
    """Box 3: Forecast needs and opportunities (Create the Future)."""
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
