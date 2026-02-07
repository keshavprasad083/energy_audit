# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Master scoring orchestrator for the energy audit framework.

Delegates to the individual box scorers and computes the weighted overall
score and grade.
"""

from __future__ import annotations

from energy_audit.data.models import DataCenter, BoxScore, Grade
from energy_audit.scoring.box1_present import score_box1
from energy_audit.scoring.box2_forget import score_box2
from energy_audit.scoring.box3_future import score_box3
from energy_audit.scoring.weights import BOX1_WEIGHT, BOX2_WEIGHT, BOX3_WEIGHT
from energy_audit.scoring.thresholds import score_to_grade


class ScoringEngine:
    """Orchestrates scoring across all three strategy boxes.

    Usage::

        engine = ScoringEngine()
        box1, box2, box3, overall, grade = engine.score(data_center)
    """

    def score(
        self, dc: DataCenter
    ) -> tuple[BoxScore, BoxScore, BoxScore, float, Grade]:
        """Run the full scoring pipeline.

        Args:
            dc: A fully populated ``DataCenter`` snapshot.

        Returns:
            A 5-tuple of ``(box1, box2, box3, overall_score, overall_grade)``
            where *overall_score* is the weighted average (0-100) and
            *overall_grade* is the corresponding letter grade.
        """
        box1 = score_box1(dc)
        box2 = score_box2(dc)
        box3 = score_box3(dc)

        overall = (
            box1.overall_score * BOX1_WEIGHT
            + box2.overall_score * BOX2_WEIGHT
            + box3.overall_score * BOX3_WEIGHT
        )
        overall = round(overall, 2)
        grade = Grade(score_to_grade(overall))

        return box1, box2, box3, overall, grade
