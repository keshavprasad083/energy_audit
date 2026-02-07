# Energy Audit - AI Data Center Energy Assessment Tool

## Project Overview

A Python CLI tool that assesses energy usage and consumption by data centers and cloud servers running AI workloads. It applies **Vijay Govindarajan's 3-Box Strategy** framework to present results organized around three strategic pillars:

- **Box 1: Manage the Present** — Current energy efficiency, PUE scoring, utilization rates, cost breakdown
- **Box 2: Selectively Forget the Past** — Zombie servers, legacy hardware, over-provisioned resources, cooling waste
- **Box 3: Create the Future** — Capacity forecasting, hardware refresh cycles, workload scheduling optimization, renewable energy

## Key Design Decisions

- **Python CLI** using Click + Rich for terminal output
- **Simulated data** with seeded RNG for reproducibility (designed for real data source plug-in later)
- **Pydantic v2** for all data models
- **ReportLab** for PDF generation with embedded **Matplotlib** charts
- **Rich** for terminal formatting (tables, panels, progress bars, colored output)
- **ASCII charts** (Unicode block/braille characters) for terminal; Matplotlib charts for PDF
- **Weighted scoring** with transparent breakdown for each box

## Project Structure

```
src/energy_audit/
├── cli/           # Click commands (app.py, commands/)
├── data/          # Pydantic models, DC profiles, simulated data generator
├── scoring/       # 3-box scoring engine with weighted sub-metrics
├── analysis/      # Domain analyzers (zombie, overprovisioning, cooling, etc.)
├── recommendations/  # Recommendation engine with impact calculation
└── reporting/     # Terminal renderer, ASCII charts, Matplotlib charts, PDF builder
```

## CLI Commands

```bash
energy-audit run [-p PROFILE] [-s SEED] [--export-pdf PATH]   # Full 3-box audit
energy-audit present [-p PROFILE] [-s SEED]                    # Box 1 only
energy-audit forget [-p PROFILE] [-s SEED]                     # Box 2 only
energy-audit future [-p PROFILE] [-s SEED]                     # Box 3 only
energy-audit export -f FORMAT -o OUTPUT [-p PROFILE]           # Export report
energy-audit dashboard [-p PROFILE]                            # Compact summary
```

**Profiles**: `small_startup`, `medium_enterprise`, `large_hyperscale`, `legacy_mixed`

## Scoring System

### Overall Score = Box1 (40%) + Box2 (30%) + Box3 (30%)

**Box 1 (Manage Present)**: PUE(25%) + Utilization(20%) + Cost(20%) + Cooling(15%) + Availability(10%) + Carbon(10%)
**Box 2 (Forget Past)**: Zombies(30%) + OverProvisioned(25%) + Legacy(20%) + CoolingWaste(15%) + Stranded(10%)
**Box 3 (Create Future)**: Forecast(20%) + HWRefresh(20%) + Scheduling(20%) + Renewable(20%) + Trend(20%)

### Grades
- A (85-100): Excellent / Green
- B (70-84): Good / Green
- C (55-69): Average / Yellow
- D (40-54): Below Average / Red
- F (0-39): Critical / Red

## Industry Benchmarks Used

- **PUE**: Industry avg 1.56, best-in-class <1.2, regulatory target 1.2 (2026)
- **GPU Power**: Training servers 700-1200W/chip, inference 300-500W
- **Rack Density**: Traditional 8kW, AI/GPU 30kW+
- **Energy Cost**: $0.07-0.25/kWh depending on region

## Dependencies

click, rich, rich-click, pydantic, numpy, matplotlib, reportlab

## Development

```bash
pip install -e ".[dev]"        # Install with dev dependencies
pytest tests/                   # Run tests
energy-audit run -p medium_enterprise -s 42   # Test run
```

## Build & Run Instructions

```bash
cd /Users/keshavprasad083/Projects/energy-audit
python -m venv .venv
source .venv/bin/activate
pip install -e .
energy-audit --help
```

## Coding Conventions

- Python 3.11+
- Pydantic v2 for all data models
- Type hints on all functions
- Rich Console for all terminal output (no raw print())
- Matplotlib Agg backend for headless chart rendering
- All random data via seeded numpy Generator for reproducibility
- Click decorators for CLI commands
- Line length: 100 characters
- Linting: ruff
- Testing: pytest
