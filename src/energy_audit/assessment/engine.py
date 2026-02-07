# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Interactive assessment engine — runs the survey and computes scores.

The engine presents questions via Rich prompts, collects answers,
computes weighted pillar scores and overall maturity, then runs
bias analysis before producing an ``AssessmentResult``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.text import Text

from energy_audit.assessment.bias import BiasDetector
from energy_audit.assessment.models import (
    Answer,
    AssessmentResult,
    BiasAnalysis,
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
    get_questions_by_pillar,
)
from energy_audit.data.models import Grade
from energy_audit.scoring.thresholds import score_to_grade
from energy_audit.scoring.weights import (
    BOX1_NAME,
    BOX1_WEIGHT,
    BOX2_NAME,
    BOX2_WEIGHT,
    BOX3_NAME,
    BOX3_WEIGHT,
)


class AssessmentEngine:
    """Runs the interactive maturity assessment survey."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, previous: AssessmentResult | None = None) -> AssessmentResult:
        """Run the full interactive assessment and return the result."""
        self._render_welcome()

        facility_name = Prompt.ask(
            "\n[bold cyan]Facility name[/]", console=self.console
        )
        assessor_name = Prompt.ask(
            "[bold cyan]Your name (assessor)[/]", console=self.console, default=""
        )

        answers: list[Answer] = []

        # Walk through each pillar section
        sections = [
            (f"Box 1: {BOX1_NAME}", BOX1_QUESTIONS),
            (f"Box 2: {BOX2_NAME}", BOX2_QUESTIONS),
            (f"Box 3: {BOX3_NAME}", BOX3_QUESTIONS),
            ("Organizational & Bias Detection", ORG_QUESTIONS),
        ]

        for section_name, questions in sections:
            self.console.print()
            self.console.rule(f"[bold magenta]{section_name}[/]")
            for i, question in enumerate(questions, 1):
                answer = self._ask_question(question, i, len(questions))
                answers.append(answer)

        # Score
        pillar_scores = self._compute_pillar_scores(answers)
        overall_score, overall_grade, overall_maturity = self._compute_overall(
            pillar_scores
        )

        # Bias analysis
        detector = BiasDetector()
        bias = detector.analyze(answers, pillar_scores, previous)

        return AssessmentResult(
            facility_name=facility_name,
            assessor_name=assessor_name,
            timestamp=datetime.now(timezone.utc),
            pillar_scores=pillar_scores,
            overall_score=overall_score,
            overall_grade=overall_grade,
            overall_maturity=overall_maturity,
            answers=answers,
            bias_analysis=bias,
        )

    def score_answers(
        self,
        answers: list[Answer],
        previous: AssessmentResult | None = None,
    ) -> tuple[list[PillarScore], float, Grade, MaturityLevel, BiasAnalysis]:
        """Score a list of answers without interactive prompts.

        Useful for testing and programmatic use.
        """
        pillar_scores = self._compute_pillar_scores(answers)
        overall_score, overall_grade, overall_maturity = self._compute_overall(
            pillar_scores
        )
        detector = BiasDetector()
        bias = detector.analyze(answers, pillar_scores, previous)
        return pillar_scores, overall_score, overall_grade, overall_maturity, bias

    # ------------------------------------------------------------------
    # Interactive prompts
    # ------------------------------------------------------------------

    def _render_welcome(self) -> None:
        welcome = Text()
        welcome.append("ENERGY MATURITY ASSESSMENT\n", style="bold cyan")
        welcome.append(
            "Answer 35 questions about your data center operations.\n",
            style="dim",
        )
        welcome.append(
            "For each question, select the option (1-5) that best describes "
            "your current state.\nFor top-maturity answers, you'll be asked "
            "to provide supporting evidence.",
            style="dim",
        )
        self.console.print(Panel(welcome, border_style="cyan"))

    def _ask_question(
        self, question: Question, index: int, total: int
    ) -> Answer:
        """Present a single question and collect the answer."""
        self.console.print()
        self.console.print(
            f"  [bold]{index}/{total}[/] [cyan]{question.topic}[/]"
        )
        self.console.print(f"  {question.text}")
        self.console.print()

        for i, opt in enumerate(question.options, 1):
            self.console.print(f"    [dim]{i}.[/] {opt.label}")

        choice = IntPrompt.ask(
            "\n  [bold]Your choice[/]",
            console=self.console,
            choices=[str(i) for i in range(1, 6)],
        )

        selected = question.options[choice - 1]
        evidence = None

        # Evidence prompt for high-maturity answers
        if selected.score >= question.evidence_threshold:
            self.console.print(
                "  [yellow]This is a high-maturity answer. "
                "What evidence supports this?[/]"
            )
            evidence = Prompt.ask(
                "  [dim]Evidence (press Enter to skip)[/]",
                console=self.console,
                default="",
            )
            if not evidence:
                evidence = None

        return Answer(
            question_id=question.id,
            selected_score=selected.score,
            selected_label=selected.label,
            evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _compute_pillar_scores(self, answers: list[Answer]) -> list[PillarScore]:
        """Compute weighted score for each pillar."""
        answer_map = {a.question_id: a for a in answers}
        scores: list[PillarScore] = []

        for pillar in Pillar:
            questions = get_questions_by_pillar(pillar)
            pillar_answers: list[Answer] = []
            weighted_sum = 0.0

            for q in questions:
                answer = answer_map.get(q.id)
                if answer:
                    weighted_sum += answer.selected_score * q.weight
                    pillar_answers.append(answer)

            score = round(weighted_sum, 2)
            maturity = MaturityLevel.from_score(score)
            grade = Grade(score_to_grade(score))

            scores.append(PillarScore(
                pillar=pillar,
                score=score,
                maturity=maturity,
                grade=grade,
                question_count=len(pillar_answers),
                answers=pillar_answers,
            ))

        return scores

    def _compute_overall(
        self, pillar_scores: list[PillarScore]
    ) -> tuple[float, Grade, MaturityLevel]:
        """Compute overall score from Box 1-3 (org excluded)."""
        score_map = {ps.pillar: ps.score for ps in pillar_scores}

        overall = (
            score_map.get(Pillar.BOX1, 0) * BOX1_WEIGHT
            + score_map.get(Pillar.BOX2, 0) * BOX2_WEIGHT
            + score_map.get(Pillar.BOX3, 0) * BOX3_WEIGHT
        )
        overall = round(overall, 2)
        grade = Grade(score_to_grade(overall))
        maturity = MaturityLevel.from_score(overall)

        return overall, grade, maturity
