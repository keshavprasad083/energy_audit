# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Anti-bias analysis for the energy maturity assessment.

Detects inconsistencies, overconfidence, status-quo inertia, and blind spots
to help respondents get an honest picture of their facility's maturity.
"""

from __future__ import annotations

from energy_audit.assessment.models import (
    Answer,
    AssessmentResult,
    BiasAnalysis,
    ConsistencyWarning,
    Pillar,
    PillarScore,
)
from energy_audit.assessment.questions import QUESTION_MAP, get_questions_by_pillar

# Thresholds
CONSISTENCY_GAP_THRESHOLD = 50  # Points gap that triggers a warning
OVERCONFIDENCE_PILLAR_SCORE = 75  # Pillar score above which we check confidence
OVERCONFIDENCE_TOP_ANSWER_RATE = 0.40  # >40% top answers
OVERCONFIDENCE_EVIDENCE_RATE = 0.50  # <50% provided evidence
DRIFT_THRESHOLD = 20  # Points change that triggers a drift alert


class BiasDetector:
    """Analyzes assessment answers for bias, inconsistency, and blind spots."""

    def analyze(
        self,
        answers: list[Answer],
        pillar_scores: list[PillarScore],
        previous_result: AssessmentResult | None = None,
    ) -> BiasAnalysis:
        """Run all bias checks and return a consolidated analysis."""
        answer_map = {a.question_id: a for a in answers}

        consistency = self._check_consistency(answer_map)
        overconfidence = self._check_overconfidence(answers, pillar_scores)
        sq_score = self._compute_status_quo_score(answer_map)
        ev_rate = self._compute_evidence_rate(answers)
        drift = self._check_drift(pillar_scores, previous_result)
        blind = self._synthesize_blind_spots(consistency, overconfidence, drift)

        return BiasAnalysis(
            consistency_warnings=consistency,
            overconfidence_pillars=overconfidence,
            status_quo_score=sq_score,
            evidence_rate=ev_rate,
            blind_spots=blind,
            drift_alerts=drift,
        )

    # ------------------------------------------------------------------
    # Consistency: related questions should be within CONSISTENCY_GAP_THRESHOLD
    # ------------------------------------------------------------------

    def _check_consistency(
        self, answer_map: dict[str, Answer]
    ) -> list[ConsistencyWarning]:
        warnings: list[ConsistencyWarning] = []
        checked: set[tuple[str, str]] = set()

        for qid, answer in answer_map.items():
            question = QUESTION_MAP.get(qid)
            if not question or not question.related_question_id:
                continue

            pair = tuple(sorted([qid, question.related_question_id]))
            if pair in checked:
                continue
            checked.add(pair)

            related_answer = answer_map.get(question.related_question_id)
            if not related_answer:
                continue

            related_q = QUESTION_MAP.get(question.related_question_id)
            if not related_q:
                continue

            gap = abs(answer.selected_score - related_answer.selected_score)
            if gap >= CONSISTENCY_GAP_THRESHOLD:
                warnings.append(ConsistencyWarning(
                    question_id_a=qid,
                    question_id_b=question.related_question_id,
                    topic_a=question.topic,
                    topic_b=related_q.topic,
                    score_a=answer.selected_score,
                    score_b=related_answer.selected_score,
                    gap=gap,
                    message=(
                        f"'{question.topic}' ({answer.selected_score}) and "
                        f"'{related_q.topic}' ({related_answer.selected_score}) "
                        f"have a {gap}-point gap — these topics are related and "
                        f"large discrepancies may indicate blind spots."
                    ),
                ))

        return warnings

    # ------------------------------------------------------------------
    # Overconfidence: high pillar score + many top answers + low evidence
    # ------------------------------------------------------------------

    def _check_overconfidence(
        self,
        answers: list[Answer],
        pillar_scores: list[PillarScore],
    ) -> list[str]:
        flagged: list[str] = []
        answer_map = {a.question_id: a for a in answers}

        for ps in pillar_scores:
            if ps.pillar == Pillar.ORG:
                continue
            if ps.score < OVERCONFIDENCE_PILLAR_SCORE:
                continue

            pillar_questions = get_questions_by_pillar(ps.pillar)
            pillar_answers = [
                answer_map[q.id] for q in pillar_questions if q.id in answer_map
            ]
            if not pillar_answers:
                continue

            top_count = sum(1 for a in pillar_answers if a.selected_score == 100)
            top_rate = top_count / len(pillar_answers)

            evidence_count = sum(
                1 for a in pillar_answers
                if a.selected_score >= 75 and a.evidence
            )
            high_score_count = sum(
                1 for a in pillar_answers if a.selected_score >= 75
            )
            ev_rate = evidence_count / high_score_count if high_score_count > 0 else 1.0

            if top_rate > OVERCONFIDENCE_TOP_ANSWER_RATE and ev_rate < OVERCONFIDENCE_EVIDENCE_RATE:
                flagged.append(
                    f"{ps.display_name}: scored {ps.score:.0f} with "
                    f"{top_rate:.0%} top-maturity answers but only "
                    f"{ev_rate:.0%} supported by evidence"
                )

        return flagged

    # ------------------------------------------------------------------
    # Status quo: invert bias-indicator question averages
    # ------------------------------------------------------------------

    def _compute_status_quo_score(self, answer_map: dict[str, Answer]) -> float:
        """Higher score = more resistance to change (inertia)."""
        bias_scores: list[int] = []
        for qid, answer in answer_map.items():
            question = QUESTION_MAP.get(qid)
            if question and question.bias_indicator:
                bias_scores.append(answer.selected_score)

        if not bias_scores:
            return 50.0

        avg = sum(bias_scores) / len(bias_scores)
        return round(100.0 - avg, 1)

    # ------------------------------------------------------------------
    # Evidence rate
    # ------------------------------------------------------------------

    def _compute_evidence_rate(self, answers: list[Answer]) -> float:
        """Fraction of high-score answers that provided evidence."""
        high_answers = [a for a in answers if a.selected_score >= 75]
        if not high_answers:
            return 0.0
        evidenced = sum(1 for a in high_answers if a.evidence)
        return round(evidenced / len(high_answers), 3)

    # ------------------------------------------------------------------
    # Historical drift
    # ------------------------------------------------------------------

    def _check_drift(
        self,
        current_pillars: list[PillarScore],
        previous: AssessmentResult | None,
    ) -> list[str]:
        if not previous:
            return []

        alerts: list[str] = []
        prev_map = {ps.pillar: ps.score for ps in previous.pillar_scores}

        for ps in current_pillars:
            prev_score = prev_map.get(ps.pillar)
            if prev_score is None:
                continue
            delta = ps.score - prev_score
            if abs(delta) >= DRIFT_THRESHOLD:
                direction = "increased" if delta > 0 else "decreased"
                alerts.append(
                    f"{ps.display_name} {direction} by {abs(delta):.0f} points "
                    f"({prev_score:.0f} → {ps.score:.0f}) — review what changed"
                )

        return alerts

    # ------------------------------------------------------------------
    # Blind spot synthesis
    # ------------------------------------------------------------------

    def _synthesize_blind_spots(
        self,
        consistency: list[ConsistencyWarning],
        overconfidence: list[str],
        drift: list[str],
    ) -> list[str]:
        spots: list[str] = []

        if consistency:
            spots.append(
                f"{len(consistency)} consistency gap(s) detected between related "
                f"topics — review these areas for potential blind spots"
            )

        if overconfidence:
            spots.append(
                f"{len(overconfidence)} pillar(s) show potential overconfidence — "
                f"high scores with limited supporting evidence"
            )

        if drift:
            spots.append(
                f"{len(drift)} significant score change(s) from previous assessment — "
                f"verify these shifts reflect real improvements or regressions"
            )

        return spots
