# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Pydantic models for the interactive energy maturity assessment."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field

from energy_audit.data.models import Grade


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MaturityLevel(str, Enum):
    """Facility maturity classification based on assessment score."""

    AD_HOC = "Ad-hoc"
    REACTIVE = "Reactive"
    DEFINED = "Defined"
    OPTIMIZED = "Optimized"
    LEADING = "Leading"

    @classmethod
    def from_score(cls, score: float) -> MaturityLevel:
        """Return the maturity level for a given 0-100 score."""
        if score >= 81:
            return cls.LEADING
        if score >= 61:
            return cls.OPTIMIZED
        if score >= 41:
            return cls.DEFINED
        if score >= 21:
            return cls.REACTIVE
        return cls.AD_HOC

    @property
    def color(self) -> str:
        """Terminal color for this maturity level."""
        return {
            MaturityLevel.LEADING: "green",
            MaturityLevel.OPTIMIZED: "blue",
            MaturityLevel.DEFINED: "yellow",
            MaturityLevel.REACTIVE: "dark_orange",
            MaturityLevel.AD_HOC: "red",
        }[self]

    @property
    def description(self) -> str:
        """One-line description of what this maturity level means."""
        return {
            MaturityLevel.AD_HOC: "No formal processes; reactive firefighting",
            MaturityLevel.REACTIVE: "Basic monitoring but limited proactive management",
            MaturityLevel.DEFINED: "Documented processes and regular reviews",
            MaturityLevel.OPTIMIZED: "Data-driven decisions and continuous improvement",
            MaturityLevel.LEADING: "Industry-leading practices and innovation",
        }[self]


class Pillar(str, Enum):
    """Assessment pillar — maps to the three scoring boxes plus organizational."""

    BOX1 = "box1"
    BOX2 = "box2"
    BOX3 = "box3"
    ORG = "org"

    @property
    def display_name(self) -> str:
        """Human-readable pillar name."""
        from energy_audit.scoring.weights import BOX1_NAME, BOX2_NAME, BOX3_NAME
        return {
            Pillar.BOX1: BOX1_NAME,
            Pillar.BOX2: BOX2_NAME,
            Pillar.BOX3: BOX3_NAME,
            Pillar.ORG: "Organizational & Bias Detection",
        }[self]


# ---------------------------------------------------------------------------
# Question / Answer models
# ---------------------------------------------------------------------------

class AnswerOption(BaseModel):
    """A single selectable option within a question."""

    label: str = Field(..., description="Short display text for this option")
    score: int = Field(..., ge=0, le=100, description="Score value (0/25/50/75/100)")


class Question(BaseModel):
    """A single assessment question."""

    id: str = Field(..., description="Unique question identifier (e.g. 'b1_q01')")
    pillar: Pillar = Field(..., description="Which pillar this question belongs to")
    topic: str = Field(..., description="Short topic label (e.g. 'Energy Monitoring')")
    text: str = Field(..., description="The full question text presented to the user")
    options: list[AnswerOption] = Field(
        ..., min_length=5, max_length=5,
        description="Exactly 5 options scored 0/25/50/75/100",
    )
    weight: float = Field(
        ..., gt=0, le=1.0,
        description="Weight within its pillar (pillar weights sum to 1.0)",
    )
    related_question_id: Optional[str] = Field(
        default=None,
        description="ID of a related question for consistency checking",
    )
    bias_indicator: bool = Field(
        default=False,
        description="True if this question helps detect status-quo bias",
    )
    evidence_threshold: int = Field(
        default=75,
        description="Score at or above which an evidence prompt is triggered",
    )


class Answer(BaseModel):
    """A user's response to a single question."""

    question_id: str = Field(..., description="ID of the question answered")
    selected_score: int = Field(
        ..., ge=0, le=100,
        description="Score value of the selected option",
    )
    selected_label: str = Field(..., description="Label of the selected option")
    evidence: Optional[str] = Field(
        default=None,
        description="Free-text evidence provided for high-maturity answers",
    )


# ---------------------------------------------------------------------------
# Scoring models
# ---------------------------------------------------------------------------

class PillarScore(BaseModel):
    """Weighted score for one assessment pillar."""

    pillar: Pillar
    score: float = Field(..., ge=0, le=100, description="Weighted pillar score (0-100)")
    maturity: MaturityLevel
    grade: Grade
    question_count: int = Field(..., ge=0)
    answers: list[Answer] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_name(self) -> str:
        """Human-readable pillar name."""
        return self.pillar.display_name


class ConsistencyWarning(BaseModel):
    """A detected inconsistency between two related answers."""

    question_id_a: str
    question_id_b: str
    topic_a: str
    topic_b: str
    score_a: int
    score_b: int
    gap: int = Field(..., ge=0, description="Absolute score gap between the two answers")
    message: str = Field(..., description="Human-readable warning text")


class BiasAnalysis(BaseModel):
    """Aggregated bias and quality analysis of assessment responses."""

    consistency_warnings: list[ConsistencyWarning] = Field(default_factory=list)
    overconfidence_pillars: list[str] = Field(
        default_factory=list,
        description="Pillar names flagged for overconfidence",
    )
    status_quo_score: float = Field(
        default=50.0, ge=0, le=100,
        description="Status-quo inertia score (higher = more resistance to change)",
    )
    evidence_rate: float = Field(
        default=0.0, ge=0, le=1.0,
        description="Fraction of high-score answers that provided evidence",
    )
    blind_spots: list[str] = Field(
        default_factory=list,
        description="Synthesized blind-spot alerts",
    )
    drift_alerts: list[str] = Field(
        default_factory=list,
        description="Alerts for significant score changes from previous assessment",
    )


# ---------------------------------------------------------------------------
# Assessment result (top-level)
# ---------------------------------------------------------------------------

class AssessmentResult(BaseModel):
    """Complete result of an interactive maturity assessment."""

    model_config = {"frozen": False, "populate_by_name": True}

    facility_name: str = Field(..., description="Name of the assessed facility")
    assessor_name: str = Field(default="", description="Name of the person completing the survey")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the assessment was completed",
    )
    pillar_scores: list[PillarScore] = Field(
        ..., description="Scores for each pillar (Box1, Box2, Box3, Org)",
    )
    overall_score: float = Field(..., ge=0, le=100, description="Weighted overall score")
    overall_grade: Grade
    overall_maturity: MaturityLevel
    answers: list[Answer] = Field(default_factory=list, description="All individual answers")
    bias_analysis: BiasAnalysis = Field(default_factory=BiasAnalysis)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def box1_score(self) -> Optional[PillarScore]:
        """Box 1 pillar score, if present."""
        return next((p for p in self.pillar_scores if p.pillar == Pillar.BOX1), None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def box2_score(self) -> Optional[PillarScore]:
        """Box 2 pillar score, if present."""
        return next((p for p in self.pillar_scores if p.pillar == Pillar.BOX2), None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def box3_score(self) -> Optional[PillarScore]:
        """Box 3 pillar score, if present."""
        return next((p for p in self.pillar_scores if p.pillar == Pillar.BOX3), None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def org_score(self) -> Optional[PillarScore]:
        """Organizational pillar score, if present."""
        return next((p for p in self.pillar_scores if p.pillar == Pillar.ORG), None)


# ---------------------------------------------------------------------------
# History models
# ---------------------------------------------------------------------------

class AssessmentHistoryEntry(BaseModel):
    """Lightweight entry for the assessment history index."""

    facility_name: str
    assessor_name: str
    timestamp: datetime
    overall_score: float
    overall_grade: Grade
    overall_maturity: MaturityLevel
    file_path: str = Field(..., description="Path to the full assessment JSON file")


class AssessmentHistory(BaseModel):
    """Index of all saved assessments for fast lookup."""

    entries: list[AssessmentHistoryEntry] = Field(default_factory=list)
