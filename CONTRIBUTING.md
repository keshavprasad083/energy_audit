# Contributing to energy-audit

Thank you for your interest in contributing! This document outlines the process for contributing to this project.

## How to Contribute

### Fork and Branch Workflow

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/your-username/energy-audit.git
   cd energy-audit
   ```
3. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/my-new-feature
   ```
4. **Make your changes** and commit with clear, descriptive messages
5. **Push** your branch to your fork:
   ```bash
   git push origin feature/my-new-feature
   ```
6. **Open a Pull Request** against the `main` branch of this repository

### Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/ -v
```

### Linting

```bash
ruff check src/
ruff format src/
```

### Pull Request Guidelines

- Keep PRs focused on a single change
- Include tests for new functionality
- Ensure all existing tests pass before submitting
- Follow the existing code style (see Code Style section below)
- Update documentation if your change affects user-facing behavior

## Contributor License Agreement (CLA)

By submitting a pull request to this project, you agree to the following terms:

1. You **assign copyright** of your contribution to the founding author (Keshav), granting the author full ownership of the contributed code.

2. This assignment allows the author to retain **dual-licensing rights**, meaning the author may, at their sole discretion, license the project (including your contributions) under alternative license terms in the future.

3. You confirm that your contribution is your **original work** and that you have the legal right to assign copyright.

4. Your contribution will be distributed under the project's current license (GNU Affero General Public License v3.0) unless the author exercises dual-licensing rights.

If you do not agree to these terms, please do not submit a pull request.

## Architecture

The data flows through a simple pipeline:

```
Profile → Generator → DataCenter → Scoring → Recommendations → Reporting
```

1. **Profile** (`data/profiles.py`): Defines a data center's characteristics (server count, GPU ratio, cooling type, etc.)
2. **Generator** (`data/generator.py`): Produces a simulated `DataCenter` snapshot from a profile using seeded RNG
3. **DataCenter** (`data/models.py`): Pydantic model containing servers, racks, energy readings, and configuration
4. **Scoring** (`scoring/engine.py`): Runs three box scorers that produce `BoxScore` objects with sub-metric breakdowns
5. **Recommendations** (`recommendations/engine.py`): Analyzes the data center and scores to generate ranked suggestions
6. **Reporting** (`reporting/`): Renders results to terminal (Rich), PDF (ReportLab), or JSON

## How to Add a New Profile

Edit `src/energy_audit/data/profiles.py`:

```python
PROFILES["my_new_profile"] = DCProfile(
    name="my_new_profile",
    display_name="My Custom Data Center",
    region="US-West",
    num_servers=200,
    gpu_ratio=0.5,
    # ... see DCProfile fields for all options
)
```

The profile will automatically appear in CLI `--profile` choices.

## How to Add a New Analyzer

1. Create `src/energy_audit/analysis/my_analyzer.py`:

```python
from energy_audit.data.models import DataCenter

def analyze_something(dc: DataCenter) -> dict:
    """Analyze a specific aspect of the data center."""
    # Your analysis logic here
    return {"finding": "value", "score": 85.0}
```

2. Export it in `src/energy_audit/analysis/__init__.py`
3. Wire it into the recommendation engine if it should produce recommendations

## How to Add a New Scoring Sub-Metric

1. Add the weight constant to `src/energy_audit/scoring/weights.py`
2. Ensure all weights in the box still sum to 1.0
3. Add the scorer function to the relevant `box*_*.py` file
4. Add the sub-metric to the box's main `score_box*()` function

## Code Style

- Python 3.11+
- Type hints on all functions
- Pydantic v2 for data models
- Rich Console for terminal output (no `print()`)
- Seeded numpy Generator for all random data
- Line length: 100 characters
- Linter: ruff
