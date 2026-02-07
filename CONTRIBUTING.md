# Contributing to energy-audit

## Development Setup

```bash
git clone https://github.com/yourusername/energy-audit.git
cd energy-audit
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v
```

## Linting

```bash
ruff check src/
ruff format src/
```

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
