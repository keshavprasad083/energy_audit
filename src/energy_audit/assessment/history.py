# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Persistence and history tracking for maturity assessments.

Assessments are saved to ``~/.energy-audit/assessments/`` with a lightweight
index at ``~/.energy-audit/assessment_history.json`` for fast lookups.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from energy_audit.assessment.models import (
    AssessmentHistory,
    AssessmentHistoryEntry,
    AssessmentResult,
)

DEFAULT_BASE_DIR = Path.home() / ".energy-audit"
ASSESSMENTS_DIR_NAME = "assessments"
HISTORY_INDEX_NAME = "assessment_history.json"


def _ensure_dirs(base_dir: Path) -> Path:
    """Create the assessments directory if it doesn't exist."""
    assessments_dir = base_dir / ASSESSMENTS_DIR_NAME
    assessments_dir.mkdir(parents=True, exist_ok=True)
    return assessments_dir


def _load_index(base_dir: Path) -> AssessmentHistory:
    """Load the history index, creating an empty one if missing."""
    index_path = base_dir / HISTORY_INDEX_NAME
    if index_path.exists():
        data = json.loads(index_path.read_text())
        return AssessmentHistory.model_validate(data)
    return AssessmentHistory()


def _save_index(history: AssessmentHistory, base_dir: Path) -> None:
    """Write the history index to disk."""
    index_path = base_dir / HISTORY_INDEX_NAME
    base_dir.mkdir(parents=True, exist_ok=True)
    index_path.write_text(history.model_dump_json(indent=2))


def save_assessment(
    result: AssessmentResult,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> Path:
    """Save a completed assessment and update the history index.

    Returns the path to the saved JSON file.
    """
    assessments_dir = _ensure_dirs(base_dir)

    # Build filename: facility_YYYYMMDD_HHMMSS.json
    safe_name = result.facility_name.lower().replace(" ", "_").replace("/", "_")
    ts = result.timestamp.strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_name}_{ts}.json"
    file_path = assessments_dir / filename

    # Write full result
    file_path.write_text(result.model_dump_json(indent=2))

    # Update index
    history = _load_index(base_dir)
    entry = AssessmentHistoryEntry(
        facility_name=result.facility_name,
        assessor_name=result.assessor_name,
        timestamp=result.timestamp,
        overall_score=result.overall_score,
        overall_grade=result.overall_grade,
        overall_maturity=result.overall_maturity,
        file_path=str(file_path),
    )
    history.entries.append(entry)
    _save_index(history, base_dir)

    return file_path


def load_assessment(file_path: str | Path) -> AssessmentResult:
    """Load a single assessment from its JSON file."""
    path = Path(file_path)
    data = json.loads(path.read_text())
    return AssessmentResult.model_validate(data)


def get_all_history(
    base_dir: Path = DEFAULT_BASE_DIR,
) -> list[AssessmentHistoryEntry]:
    """Return all assessment history entries, newest first."""
    history = _load_index(base_dir)
    return sorted(history.entries, key=lambda e: e.timestamp, reverse=True)


def get_facility_history(
    facility_name: str,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> list[AssessmentHistoryEntry]:
    """Return history entries for a specific facility, newest first."""
    entries = get_all_history(base_dir)
    return [e for e in entries if e.facility_name.lower() == facility_name.lower()]


def get_latest_assessment(
    facility_name: str,
    base_dir: Path = DEFAULT_BASE_DIR,
) -> AssessmentResult | None:
    """Load the most recent assessment for a facility, or None."""
    entries = get_facility_history(facility_name, base_dir)
    if not entries:
        return None
    return load_assessment(entries[0].file_path)


def compare_assessments(
    result_a: AssessmentResult,
    result_b: AssessmentResult,
) -> dict[str, dict]:
    """Compare two assessment results, returning deltas per pillar.

    Returns a dict keyed by pillar display name with:
      - score_a, score_b, delta
      - maturity_a, maturity_b
      - improved (bool)
    """
    scores_a = {ps.pillar: ps for ps in result_a.pillar_scores}
    scores_b = {ps.pillar: ps for ps in result_b.pillar_scores}

    comparison: dict[str, dict] = {}
    for pillar in scores_a:
        ps_a = scores_a[pillar]
        ps_b = scores_b.get(pillar)
        if not ps_b:
            continue
        delta = ps_b.score - ps_a.score
        comparison[ps_a.display_name] = {
            "score_a": ps_a.score,
            "score_b": ps_b.score,
            "delta": round(delta, 1),
            "maturity_a": ps_a.maturity.value,
            "maturity_b": ps_b.maturity.value,
            "improved": delta > 0,
        }

    # Overall
    overall_delta = result_b.overall_score - result_a.overall_score
    comparison["Overall"] = {
        "score_a": result_a.overall_score,
        "score_b": result_b.overall_score,
        "delta": round(overall_delta, 1),
        "maturity_a": result_a.overall_maturity.value,
        "maturity_b": result_b.overall_maturity.value,
        "improved": overall_delta > 0,
    }

    return comparison
