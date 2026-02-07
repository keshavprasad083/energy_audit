# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Tests for the interactive energy maturity assessment module."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from energy_audit.assessment.bias import BiasDetector
from energy_audit.assessment.engine import AssessmentEngine
from energy_audit.assessment.history import (
    compare_assessments,
    get_all_history,
    get_facility_history,
    get_latest_assessment,
    load_assessment,
    save_assessment,
)
from energy_audit.assessment.models import (
    Answer,
    AnswerOption,
    AssessmentResult,
    BiasAnalysis,
    ConsistencyWarning,
    MaturityLevel,
    Pillar,
    PillarScore,
    Question,
)
from energy_audit.assessment.questions import (
    ALL_QUESTIONS,
    BOX1_QUESTIONS,
    BOX2_QUESTIONS,
    BOX3_QUESTIONS,
    ORG_QUESTIONS,
    QUESTION_MAP,
    get_questions_by_pillar,
    validate_weights,
)
from energy_audit.assessment.report import AssessmentRenderer
from energy_audit.data.models import Grade


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestMaturityLevel:
    def test_from_score_boundaries(self):
        assert MaturityLevel.from_score(0) == MaturityLevel.AD_HOC
        assert MaturityLevel.from_score(20) == MaturityLevel.AD_HOC
        assert MaturityLevel.from_score(21) == MaturityLevel.REACTIVE
        assert MaturityLevel.from_score(40) == MaturityLevel.REACTIVE
        assert MaturityLevel.from_score(41) == MaturityLevel.DEFINED
        assert MaturityLevel.from_score(60) == MaturityLevel.DEFINED
        assert MaturityLevel.from_score(61) == MaturityLevel.OPTIMIZED
        assert MaturityLevel.from_score(80) == MaturityLevel.OPTIMIZED
        assert MaturityLevel.from_score(81) == MaturityLevel.LEADING
        assert MaturityLevel.from_score(100) == MaturityLevel.LEADING

    def test_color(self):
        assert MaturityLevel.AD_HOC.color == "red"
        assert MaturityLevel.LEADING.color == "green"

    def test_description(self):
        assert "formal" in MaturityLevel.AD_HOC.description.lower()
        assert "innovation" in MaturityLevel.LEADING.description.lower()


class TestPillar:
    def test_display_names(self):
        assert Pillar.BOX1.display_name == "Current Operations"
        assert Pillar.BOX2.display_name == "Legacy & Waste"
        assert Pillar.BOX3.display_name == "Future Readiness"
        assert "Organizational" in Pillar.ORG.display_name


class TestAnswerOption:
    def test_valid(self):
        opt = AnswerOption(label="Test", score=50)
        assert opt.label == "Test"
        assert opt.score == 50

    def test_score_range(self):
        with pytest.raises(Exception):
            AnswerOption(label="Bad", score=101)


# ---------------------------------------------------------------------------
# Question bank tests
# ---------------------------------------------------------------------------


class TestQuestions:
    def test_total_count(self):
        assert len(ALL_QUESTIONS) == 35

    def test_per_pillar_count(self):
        assert len(BOX1_QUESTIONS) == 10
        assert len(BOX2_QUESTIONS) == 10
        assert len(BOX3_QUESTIONS) == 10
        assert len(ORG_QUESTIONS) == 5

    def test_get_questions_by_pillar(self):
        for pillar in Pillar:
            questions = get_questions_by_pillar(pillar)
            assert all(q.pillar == pillar for q in questions)

    def test_weights_sum_to_one(self):
        totals = validate_weights()
        for pillar, total in totals.items():
            assert abs(total - 1.0) < 0.001, f"{pillar} weights sum to {total}"

    def test_each_question_has_5_options(self):
        for q in ALL_QUESTIONS:
            assert len(q.options) == 5, f"{q.id} has {len(q.options)} options"

    def test_option_scores_are_0_25_50_75_100(self):
        for q in ALL_QUESTIONS:
            scores = [o.score for o in q.options]
            assert scores == [0, 25, 50, 75, 100], f"{q.id}: {scores}"

    def test_unique_ids(self):
        ids = [q.id for q in ALL_QUESTIONS]
        assert len(ids) == len(set(ids)), "Duplicate question IDs found"

    def test_question_map_complete(self):
        assert len(QUESTION_MAP) == 35
        for q in ALL_QUESTIONS:
            assert q.id in QUESTION_MAP

    def test_related_question_ids_are_valid(self):
        for q in ALL_QUESTIONS:
            if q.related_question_id:
                assert q.related_question_id in QUESTION_MAP, (
                    f"{q.id} references unknown question {q.related_question_id}"
                )


# ---------------------------------------------------------------------------
# Scoring tests (non-interactive)
# ---------------------------------------------------------------------------


def _make_answers(score: int = 50) -> list[Answer]:
    """Create answers for all questions with the given score."""
    return [
        Answer(
            question_id=q.id,
            selected_score=score,
            selected_label=q.options[score // 25].label,
        )
        for q in ALL_QUESTIONS
    ]


class TestScoring:
    def test_mid_score_produces_defined_maturity(self):
        engine = AssessmentEngine()
        answers = _make_answers(50)
        pillar_scores, overall, grade, maturity, bias = engine.score_answers(answers)

        assert len(pillar_scores) == 4
        assert 40 <= overall <= 60
        assert maturity == MaturityLevel.DEFINED

    def test_all_top_produces_leading(self):
        engine = AssessmentEngine()
        answers = _make_answers(100)
        _, overall, grade, maturity, _ = engine.score_answers(answers)

        assert overall == 100.0
        assert grade == Grade.A
        assert maturity == MaturityLevel.LEADING

    def test_all_bottom_produces_ad_hoc(self):
        engine = AssessmentEngine()
        answers = _make_answers(0)
        _, overall, grade, maturity, _ = engine.score_answers(answers)

        assert overall == 0.0
        assert grade == Grade.F
        assert maturity == MaturityLevel.AD_HOC

    def test_org_pillar_excluded_from_overall(self):
        engine = AssessmentEngine()
        # Give org questions a very different score
        answers = []
        for q in ALL_QUESTIONS:
            if q.pillar == Pillar.ORG:
                answers.append(Answer(
                    question_id=q.id, selected_score=100,
                    selected_label="Top",
                ))
            else:
                answers.append(Answer(
                    question_id=q.id, selected_score=50,
                    selected_label="Mid",
                ))

        _, overall, _, _, _ = engine.score_answers(answers)
        # Overall should be ~50, not pulled up by org=100
        assert 45 <= overall <= 55

    def test_pillar_score_has_correct_fields(self):
        engine = AssessmentEngine()
        answers = _make_answers(75)
        pillar_scores, _, _, _, _ = engine.score_answers(answers)

        for ps in pillar_scores:
            assert 0 <= ps.score <= 100
            assert isinstance(ps.maturity, MaturityLevel)
            assert isinstance(ps.grade, Grade)
            assert ps.question_count > 0
            assert ps.display_name  # computed field works


# ---------------------------------------------------------------------------
# Bias detection tests
# ---------------------------------------------------------------------------


class TestBiasDetector:
    def test_consistency_warning_on_large_gap(self):
        """Related questions with ≥50 point gap should trigger warning."""
        detector = BiasDetector()
        # b1_q01 and b1_q09 are related
        answers = _make_answers(50)
        answer_map = {a.question_id: a for a in answers}
        # Create large gap
        answer_map["b1_q01"] = Answer(
            question_id="b1_q01", selected_score=100, selected_label="Top"
        )
        answer_map["b1_q09"] = Answer(
            question_id="b1_q09", selected_score=0, selected_label="Bottom"
        )

        engine = AssessmentEngine()
        ps, _, _, _, _ = engine.score_answers(list(answer_map.values()))
        bias = detector.analyze(list(answer_map.values()), ps)

        assert len(bias.consistency_warnings) >= 1
        ids = {
            (w.question_id_a, w.question_id_b)
            for w in bias.consistency_warnings
        }
        assert ("b1_q01", "b1_q09") in ids or ("b1_q09", "b1_q01") in ids

    def test_no_consistency_warning_on_small_gap(self):
        detector = BiasDetector()
        answers = _make_answers(50)  # All same score
        engine = AssessmentEngine()
        ps, _, _, _, _ = engine.score_answers(answers)
        bias = detector.analyze(answers, ps)
        assert len(bias.consistency_warnings) == 0

    def test_status_quo_score(self):
        detector = BiasDetector()
        # All low scores on bias questions -> high status quo inertia
        answers = _make_answers(0)
        engine = AssessmentEngine()
        ps, _, _, _, _ = engine.score_answers(answers)
        bias = detector.analyze(answers, ps)
        # sq = 100 - avg(0) = 100
        assert bias.status_quo_score == 100.0

    def test_evidence_rate(self):
        detector = BiasDetector()
        answers = _make_answers(75)
        # Add evidence to half of them
        for i, a in enumerate(answers):
            if i % 2 == 0:
                answers[i] = Answer(
                    question_id=a.question_id,
                    selected_score=a.selected_score,
                    selected_label=a.selected_label,
                    evidence="We have documentation",
                )

        engine = AssessmentEngine()
        ps, _, _, _, _ = engine.score_answers(answers)
        bias = detector.analyze(answers, ps)
        assert 0.4 <= bias.evidence_rate <= 0.6

    def test_drift_detection(self):
        detector = BiasDetector()
        engine = AssessmentEngine()

        old_answers = _make_answers(25)
        old_ps, old_overall, old_grade, old_mat, _ = engine.score_answers(old_answers)
        previous = AssessmentResult(
            facility_name="Test",
            pillar_scores=old_ps,
            overall_score=old_overall,
            overall_grade=old_grade,
            overall_maturity=old_mat,
            answers=old_answers,
        )

        new_answers = _make_answers(75)
        new_ps, _, _, _, _ = engine.score_answers(new_answers)
        bias = detector.analyze(new_answers, new_ps, previous)

        assert len(bias.drift_alerts) > 0


# ---------------------------------------------------------------------------
# History / persistence tests
# ---------------------------------------------------------------------------


def _make_result(facility: str = "TestDC", score: int = 50) -> AssessmentResult:
    engine = AssessmentEngine()
    answers = _make_answers(score)
    ps, overall, grade, maturity, bias = engine.score_answers(answers)
    return AssessmentResult(
        facility_name=facility,
        assessor_name="Tester",
        pillar_scores=ps,
        overall_score=overall,
        overall_grade=grade,
        overall_maturity=maturity,
        answers=answers,
        bias_analysis=bias,
    )


class TestHistory:
    def test_save_and_load(self, tmp_path: Path):
        result = _make_result()
        path = save_assessment(result, base_dir=tmp_path)
        assert path.exists()

        loaded = load_assessment(path)
        assert loaded.facility_name == "TestDC"
        assert loaded.overall_score == result.overall_score

    def test_get_all_history(self, tmp_path: Path):
        save_assessment(_make_result("DC-A"), base_dir=tmp_path)
        save_assessment(_make_result("DC-B"), base_dir=tmp_path)

        entries = get_all_history(base_dir=tmp_path)
        assert len(entries) == 2

    def test_get_facility_history(self, tmp_path: Path):
        save_assessment(_make_result("DC-A"), base_dir=tmp_path)
        save_assessment(_make_result("DC-A"), base_dir=tmp_path)
        save_assessment(_make_result("DC-B"), base_dir=tmp_path)

        entries = get_facility_history("DC-A", base_dir=tmp_path)
        assert len(entries) == 2
        assert all(e.facility_name == "DC-A" for e in entries)

    def test_get_latest_assessment(self, tmp_path: Path):
        save_assessment(_make_result("DC-A", score=25), base_dir=tmp_path)
        save_assessment(_make_result("DC-A", score=75), base_dir=tmp_path)

        latest = get_latest_assessment("DC-A", base_dir=tmp_path)
        assert latest is not None
        assert latest.overall_score > 50  # Should be the 75-score one

    def test_get_latest_returns_none(self, tmp_path: Path):
        result = get_latest_assessment("Nonexistent", base_dir=tmp_path)
        assert result is None

    def test_compare_assessments(self):
        a = _make_result(score=25)
        b = _make_result(score=75)
        comp = compare_assessments(a, b)

        assert "Overall" in comp
        assert comp["Overall"]["delta"] > 0
        assert comp["Overall"]["improved"] is True


# ---------------------------------------------------------------------------
# Report renderer tests (smoke tests — verify no exceptions)
# ---------------------------------------------------------------------------


class TestAssessmentRenderer:
    def test_render_no_crash(self):
        from rich.console import Console
        console = Console(file=open("/dev/null", "w"), no_color=True)
        renderer = AssessmentRenderer(console)
        result = _make_result()
        renderer.render(result)  # Should not raise

    def test_render_history_no_crash(self):
        from rich.console import Console
        console = Console(file=open("/dev/null", "w"), no_color=True)
        renderer = AssessmentRenderer(console)
        renderer.render_history([])  # Empty list
        renderer.render_history([
            {
                "facility": "Test",
                "assessor": "Tester",
                "date": "2025-01-01",
                "score": 50,
                "grade": "C",
                "grade_color": "yellow",
                "maturity": "Defined",
                "maturity_color": "yellow",
            }
        ])

    def test_render_comparison_no_crash(self):
        from rich.console import Console
        console = Console(file=open("/dev/null", "w"), no_color=True)
        renderer = AssessmentRenderer(console)
        a = _make_result(score=25)
        b = _make_result(score=75)
        comp = compare_assessments(a, b)
        renderer.render_comparison(comp, a, b)


# ---------------------------------------------------------------------------
# CLI integration tests (basic invocation)
# ---------------------------------------------------------------------------


class TestCLI:
    def test_assess_help(self):
        from click.testing import CliRunner
        from energy_audit.cli.app import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["assess", "--help"])
        assert result.exit_code == 0
        assert "35 questions" in result.output

    def test_assess_history_empty(self, tmp_path: Path, monkeypatch):
        from click.testing import CliRunner
        from energy_audit.cli.app import cli
        import energy_audit.assessment.history as hist_mod

        monkeypatch.setattr(hist_mod, "DEFAULT_BASE_DIR", tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["assess", "--history"])
        assert result.exit_code == 0
        assert "No assessments found" in result.output

    def test_assess_compare_requires_facility(self):
        from click.testing import CliRunner
        from energy_audit.cli.app import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["assess", "--compare"])
        assert result.exit_code == 0
        assert "requires" in result.output
