# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Pro CLI commands — data ingestion, fleet analysis, compliance, API."""

from __future__ import annotations

import click
from rich.console import Console

from energy_audit.pro.config import load_config
from energy_audit.pro.collectors import get_collector
from energy_audit.pro.mapper import DataCenterMapper


@click.group("pro")
def pro_cli() -> None:
    """Pro features: real data ingestion, fleet analysis, compliance."""
    pass


@pro_cli.command()
@click.option("--config", "-c", type=click.Path(exists=True), required=True,
              help="Path to pro YAML config file")
@click.pass_context
def discover(ctx: click.Context, config: str) -> None:
    """Discover available endpoints from configured data sources."""
    console: Console = ctx.obj["console"]
    cfg = load_config(config)

    for source in cfg.sources:
        if not source.enabled:
            continue
        console.print(f"\n[bold cyan]{source.type.upper()}[/] collector:")
        try:
            collector_cls = get_collector(source.type)
            collector = collector_cls(source)
            endpoints = collector.discover()
            for ep in endpoints:
                console.print(f"  [green]\u2713[/] {ep}")
            ok = collector.test_connection()
            status = "[green]connected[/]" if ok else "[red]unreachable[/]"
            console.print(f"  Connection: {status}")
        except Exception as exc:
            console.print(f"  [red]Error: {exc}[/]")


@pro_cli.command()
@click.option("--config", "-c", type=click.Path(exists=True), required=True,
              help="Path to pro YAML config file")
@click.option("--export-pdf", type=click.Path(), default=None,
              help="Export results to PDF")
@click.option("--export-json", type=click.Path(), default=None,
              help="Export results to JSON")
@click.pass_context
def audit(ctx: click.Context, config: str, export_pdf: str | None, export_json: str | None) -> None:
    """Run an energy audit using real data from configured sources."""
    console: Console = ctx.obj["console"]
    result = _run_pro_audit(config, console)

    from energy_audit.reporting.terminal import TerminalRenderer
    renderer = TerminalRenderer(console)
    renderer.render(result)

    if export_pdf:
        from energy_audit.cli.app import _export_pdf
        _export_pdf(result, export_pdf, console)

    if export_json:
        from energy_audit.cli.app import _export_json
        _export_json(result, export_json, console)


@pro_cli.command()
@click.option("--configs", "-c", type=click.Path(exists=True), required=True,
              help="Directory containing per-site YAML config files")
@click.pass_context
def fleet(ctx: click.Context, configs: str) -> None:
    """Run fleet analysis across multiple sites."""
    import os
    from energy_audit.pro.fleet import build_fleet_report
    from energy_audit.pro.fleet_renderer import FleetRenderer

    console: Console = ctx.obj["console"]
    config_dir = configs

    yaml_files = sorted(
        f for f in os.listdir(config_dir)
        if f.endswith((".yaml", ".yml"))
    )

    if not yaml_files:
        console.print(f"[red]No YAML config files found in {config_dir}[/]")
        return

    results = {}
    for fname in yaml_files:
        path = os.path.join(config_dir, fname)
        site_name = fname.rsplit(".", 1)[0]
        with console.status(f"[bold cyan]Auditing site: {site_name}..."):
            try:
                result = _run_pro_audit(path, console)
                results[site_name] = result
            except Exception as exc:
                console.print(f"  [red]Failed {site_name}: {exc}[/]")

    if not results:
        console.print("[red]No sites audited successfully[/]")
        return

    report = build_fleet_report(results)
    renderer = FleetRenderer(console)
    renderer.render(report)


@pro_cli.command()
@click.option("--config", "-c", type=click.Path(exists=True), required=True,
              help="Path to pro YAML config file")
@click.option("--framework", "-f",
              type=click.Choice(["eu-eed", "iso-50001", "sec-climate"]),
              required=True, help="Compliance framework to assess against")
@click.pass_context
def compliance(ctx: click.Context, config: str, framework: str) -> None:
    """Assess compliance against regulatory frameworks."""
    from rich.table import Table
    from rich.panel import Panel

    console: Console = ctx.obj["console"]
    result = _run_pro_audit(config, console)

    if framework == "eu-eed":
        from energy_audit.pro.compliance.eu_eed import EUEEDCompliance
        report = EUEEDCompliance().assess(result)
    elif framework == "iso-50001":
        from energy_audit.pro.compliance.iso_50001 import ISO50001Compliance
        report = ISO50001Compliance().assess(result)
    elif framework == "sec-climate":
        from energy_audit.pro.compliance.sec_climate import SECClimateCompliance
        report = SECClimateCompliance().assess(result)
    else:
        console.print(f"[red]Unknown framework: {framework}[/]")
        return

    # Render compliance report
    console.print(f"\n[bold]{report.framework_name} v{report.framework_version}[/]\n")

    table = Table(title="Compliance Checks", show_lines=True)
    table.add_column("ID", style="dim", width=16)
    table.add_column("Check", width=30)
    table.add_column("Status", width=16)
    table.add_column("Current", width=14)
    table.add_column("Required", width=14)
    table.add_column("Recommendation", width=40)

    status_colors = {
        "COMPLIANT": "green",
        "NON_COMPLIANT": "red",
        "PARTIAL": "yellow",
        "NOT_APPLICABLE": "dim",
    }

    for check in report.checks:
        color = status_colors.get(check.status.value, "white")
        table.add_row(
            check.check_id,
            check.name,
            f"[{color}]{check.status.value}[/]",
            check.current_value,
            check.required_value,
            check.recommendation,
        )

    console.print(table)

    pct = report.compliance_percentage
    pct_color = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
    console.print(Panel(
        f"[{pct_color}]{report.compliant_count}/{report.total_checks} checks passed "
        f"({pct:.0f}% compliant)[/]",
        title="Summary",
    ))


@pro_cli.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", "-p", default=8080, type=int, help="Bind port")
@click.pass_context
def serve(ctx: click.Context, host: str, port: int) -> None:
    """Start the REST API server."""
    from energy_audit.pro import check_dependency
    check_dependency("fastapi", "pip install -e '.[pro-api]'")
    check_dependency("uvicorn", "pip install -e '.[pro-api]'")

    console: Console = ctx.obj["console"]
    console.print(f"[bold cyan]Starting API server on {host}:{port}...[/]")

    from energy_audit.pro.api.server import create_app
    import uvicorn

    app = create_app()
    uvicorn.run(app, host=host, port=port)


def _run_pro_audit(config_path: str, console: Console):
    """Run the full pro audit pipeline and return an AuditResult."""
    from energy_audit.data.models import AuditResult
    from energy_audit.recommendations.engine import RecommendationEngine
    from energy_audit.reporting.executive_summary import generate_executive_summary
    from energy_audit.scoring.engine import ScoringEngine

    cfg = load_config(config_path)

    # Collect from all enabled sources
    results = []
    for source in cfg.sources:
        if not source.enabled:
            continue
        with console.status(f"[bold cyan]Collecting from {source.type}..."):
            collector_cls = get_collector(source.type)
            collector = collector_cls(source)
            result = collector.collect()
            results.append(result)

            if result.errors:
                for err in result.errors:
                    console.print(f"  [red]Error:[/] {err}")
            if result.warnings:
                for warn in result.warnings:
                    console.print(f"  [yellow]Warning:[/] {warn}")

    # Map to DataCenter
    with console.status("[bold cyan]Mapping collected data..."):
        mapper = DataCenterMapper(cfg.facility)
        dc = mapper.map(results)

    console.print(
        f"  [green]Mapped:[/] {len(dc.servers)} servers, "
        f"{len(dc.racks)} racks, {len(dc.energy_readings)} readings"
    )

    # Score
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
