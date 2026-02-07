# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Shared test fixtures for the energy audit test suite."""

from __future__ import annotations

import pytest

from energy_audit.data.generator import DataCenterGenerator
from energy_audit.data.models import AuditResult, DataCenter, Grade
from energy_audit.data.profiles import get_profile
from energy_audit.recommendations.engine import RecommendationEngine
from energy_audit.reporting.executive_summary import generate_executive_summary
from energy_audit.scoring.engine import ScoringEngine


@pytest.fixture()
def medium_dc() -> DataCenter:
    """A medium_enterprise DataCenter generated with seed 42."""
    profile = get_profile("medium_enterprise")
    gen = DataCenterGenerator(profile, seed=42)
    return gen.generate()


@pytest.fixture()
def scored_result(medium_dc: DataCenter) -> AuditResult:
    """A fully scored AuditResult from the medium_enterprise profile, seed 42."""
    engine = ScoringEngine()
    box1, box2, box3, overall_score, overall_grade = engine.score(medium_dc)

    rec_engine = RecommendationEngine()
    recommendations = rec_engine.generate(medium_dc, box1, box2, box3)

    executive_summary = generate_executive_summary(
        medium_dc, box1, box2, box3, overall_score, overall_grade, recommendations
    )

    return AuditResult(
        data_center=medium_dc,
        box1=box1,
        box2=box2,
        box3=box3,
        overall_score=overall_score,
        overall_grade=overall_grade,
        recommendations=recommendations,
        executive_summary=executive_summary,
    )
