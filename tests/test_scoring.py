# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Tests for the scoring engine."""

from __future__ import annotations

import pytest

from energy_audit.data.models import BoxScore, DataCenter, Grade
from energy_audit.scoring.engine import ScoringEngine
from energy_audit.scoring.thresholds import score_to_grade
from energy_audit.scoring.weights import BOX1_NAME, BOX2_NAME, BOX3_NAME


class TestScoringEngine:
    """Tests for ScoringEngine.score()."""

    def test_returns_five_tuple(self, medium_dc: DataCenter):
        engine = ScoringEngine()
        result = engine.score(medium_dc)
        assert len(result) == 5

    def test_box_scores_are_valid(self, medium_dc: DataCenter):
        engine = ScoringEngine()
        box1, box2, box3, overall, grade = engine.score(medium_dc)

        for box in (box1, box2, box3):
            assert isinstance(box, BoxScore)
            assert 0 <= box.overall_score <= 100
            assert isinstance(box.grade, Grade)
            assert len(box.sub_metrics) > 0

    def test_overall_score_range(self, medium_dc: DataCenter):
        engine = ScoringEngine()
        _, _, _, overall, _ = engine.score(medium_dc)
        assert 0 <= overall <= 100

    def test_overall_grade_valid(self, medium_dc: DataCenter):
        engine = ScoringEngine()
        _, _, _, _, grade = engine.score(medium_dc)
        assert isinstance(grade, Grade)

    def test_box_names_match_constants(self, medium_dc: DataCenter):
        engine = ScoringEngine()
        box1, box2, box3, _, _ = engine.score(medium_dc)

        assert box1.box_name == BOX1_NAME
        assert box2.box_name == BOX2_NAME
        assert box3.box_name == BOX3_NAME

    def test_box_numbers(self, medium_dc: DataCenter):
        engine = ScoringEngine()
        box1, box2, box3, _, _ = engine.score(medium_dc)

        assert box1.box_number == 1
        assert box2.box_number == 2
        assert box3.box_number == 3


class TestScoreToGrade:
    """Tests for grade threshold boundaries."""

    def test_grade_a(self):
        assert score_to_grade(100) == "A"
        assert score_to_grade(85) == "A"

    def test_grade_b(self):
        assert score_to_grade(84.9) == "B"
        assert score_to_grade(70) == "B"

    def test_grade_c(self):
        assert score_to_grade(69.9) == "C"
        assert score_to_grade(55) == "C"

    def test_grade_d(self):
        assert score_to_grade(54.9) == "D"
        assert score_to_grade(40) == "D"

    def test_grade_f(self):
        assert score_to_grade(39.9) == "F"
        assert score_to_grade(0) == "F"
