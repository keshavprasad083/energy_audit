# energy-audit

AI Data Center Energy Assessment Tool — analyze energy consumption, identify waste, and plan for sustainable growth.

## Overview

`energy-audit` evaluates data center energy usage across three assessment pillars:

- **Box 1: Current Operations** — PUE efficiency, server utilization, cost analysis, cooling performance, availability, carbon intensity
- **Box 2: Legacy & Waste** — Zombie servers, over-provisioned resources, legacy hardware, cooling waste, stranded capacity
- **Box 3: Future Readiness** — Capacity forecasting, hardware refresh planning, workload scheduling, renewable energy adoption, efficiency trends

Each pillar produces a weighted score (0–100) with sub-metric breakdowns. The overall facility score combines all three pillars into a single letter grade (A–F).

The tool also includes an **interactive maturity assessment** — a 35-question survey that data center engineers answer about their facility to receive maturity scores, bias analysis, gap analysis, and an improvement roadmap.

## Screenshots

### Full Audit Report

<img src="docs/screenshots/full_audit.svg" alt="Full audit output showing scores, sub-metrics, recommendations, and executive summary" />

### Dashboard View

Compact overview for quick assessment:

<img src="docs/screenshots/dashboard.svg" alt="Dashboard with key metrics and top recommendations" />

### Profile Comparison

**Large Hyperscale (5000 servers, Grade B)**

<img src="docs/screenshots/dashboard_hyperscale.svg" alt="Hyperscale facility dashboard showing Grade B" />

**Legacy Mixed (300 servers, Grade F)**

<img src="docs/screenshots/dashboard_legacy.svg" alt="Legacy facility dashboard showing Grade F" />

### Individual Pillar Detail

<details>
<summary>Box 1: Current Operations</summary>

<img src="docs/screenshots/box1_present.svg" alt="Box 1 Current Operations detail" />
</details>

<details>
<summary>Box 2: Legacy & Waste</summary>

<img src="docs/screenshots/box2_forget.svg" alt="Box 2 Legacy and Waste detail" />
</details>

<details>
<summary>Box 3: Future Readiness</summary>

<img src="docs/screenshots/box3_future.svg" alt="Box 3 Future Readiness detail" />
</details>

### Interactive Maturity Assessment

Full assessment report with maturity scores, bias analysis, gap analysis, and improvement roadmap:

<img src="docs/screenshots/assessment_report.svg" alt="Interactive maturity assessment report showing pillar scores, bias warnings, gap analysis, and improvement roadmap" />

<details>
<summary>Assessment History</summary>

<img src="docs/screenshots/assessment_history.svg" alt="Assessment history table showing past assessments across facilities" />
</details>

<details>
<summary>Assessment Comparison</summary>

<img src="docs/screenshots/assessment_comparison.svg" alt="Side-by-side comparison of two assessments showing score deltas and maturity transitions" />
</details>

### Sample Reports

- [Sample PDF Report](docs/samples/sample_report.pdf) — 8-page report with embedded charts, scoring tables, recommendations, and methodology appendix
- [Sample JSON Export](docs/samples/sample_results.json) — Full machine-readable audit output

## Features

- Rich terminal output with ASCII gauges, sparklines, and color-coded scoring
- **Interactive maturity assessment** with 35 questions, anti-bias detection, and improvement roadmap
- PDF reports with embedded Matplotlib charts (radar, pie, histogram, heatmap, and more)
- JSON export for programmatic consumption
- Four built-in data center profiles (small startup to large hyperscale)
- Seeded random data generation for reproducible results
- Actionable recommendations ranked by savings impact
- Assessment history tracking with facility comparison over time

## Quick Start

```bash
# Install
pip install -e .

# Run a full audit
energy-audit run -p medium_enterprise -s 42

# Export PDF report
energy-audit run -p large_hyperscale -s 42 --export-pdf report.pdf

# Export JSON
energy-audit run -p medium_enterprise -s 42 --export-json results.json
```

## CLI Commands

### Automated Audit

```bash
energy-audit run       # Full audit across all three pillars
energy-audit present   # Box 1 only (Current Operations)
energy-audit forget    # Box 2 only (Legacy & Waste)
energy-audit future    # Box 3 only (Future Readiness)
energy-audit dashboard # Compact summary view
```

All audit commands accept `--profile/-p` and `--seed/-s` options.

### Interactive Maturity Assessment

```bash
energy-audit assess                          # Launch 35-question interactive survey
energy-audit assess --history                # View all past assessments
energy-audit assess --history -f "My DC"     # View history for a specific facility
energy-audit assess --compare -f "My DC"     # Compare two most recent assessments
```

The assessment survey covers:
- **Box 1: Current Operations** (10 questions) — monitoring, PUE, utilization, cooling, cost visibility
- **Box 2: Legacy & Waste** (10 questions) — decommissioning, zombies, right-sizing, lifecycle management
- **Box 3: Future Readiness** (10 questions) — forecasting, renewables, AI/ML planning, regulations
- **Organizational** (5 questions) — change management, collaboration, executive sponsorship

Each response produces:
- **Maturity scores** per pillar with levels: Ad-hoc → Reactive → Defined → Optimized → Leading
- **Bias & consistency analysis** — flags overconfidence, inconsistencies between related answers, and status quo inertia
- **Gap analysis** — top improvement opportunities ranked by weighted impact
- **Improvement roadmap** — prioritized actions with target maturity transitions
- **Historical tracking** — assessments saved to `~/.energy-audit/assessments/` for trend analysis

### Profiles

| Profile | Servers | Description |
|---------|---------|-------------|
| `small_startup` | ~50 | Small cloud-native deployment |
| `medium_enterprise` | ~500 | Mid-size enterprise data center |
| `large_hyperscale` | ~5000 | Hyperscale AI/ML facility |
| `legacy_mixed` | ~300 | Aging facility with mixed hardware |

## Scoring System

### Overall Score = Box 1 (40%) + Box 2 (30%) + Box 3 (30%)

| Grade | Score Range | Meaning |
|-------|-------------|---------|
| A | 85–100 | Excellent |
| B | 70–84 | Good |
| C | 55–69 | Average |
| D | 40–54 | Below Average |
| F | 0–39 | Critical |

Each box contains 5–6 weighted sub-metrics. See `src/energy_audit/scoring/weights.py` for the full breakdown.

## Project Structure

```
src/energy_audit/
├── cli/              # Click CLI commands
├── data/             # Pydantic models, profiles, data generator
│   ├── models.py     # Core data models (Server, DataCenter, BoxScore, etc.)
│   ├── profiles.py   # Data center profile definitions
│   └── generator.py  # Simulated data generator with seeded RNG
├── assessment/       # Interactive maturity assessment (survey, bias detection, history)
├── scoring/          # Weighted scoring engine
│   ├── engine.py     # Master orchestrator
│   ├── weights.py    # All scoring weights (single source of truth)
│   ├── thresholds.py # Industry benchmark thresholds
│   └── box*.py       # Individual box scorers
├── analysis/         # Domain-specific analyzers
├── recommendations/  # Recommendation engine with impact calculation
└── reporting/        # Terminal (Rich), PDF (ReportLab), charts (Matplotlib)
```

## Extending

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add new profiles, analyzers, and scoring metrics.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
energy-audit run -p medium_enterprise -s 42
```

## License

v2.0+ is licensed under AGPLv3. Versions prior to v2.0 were released under the MIT license.

See [LICENSE](LICENSE) for full terms.
