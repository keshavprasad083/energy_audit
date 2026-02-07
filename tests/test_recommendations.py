# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Tests for the recommendation engine."""

from __future__ import annotations

from energy_audit.data.models import AuditResult


class TestRecommendations:
    """Tests for recommendation generation and ordering."""

    def test_non_empty(self, scored_result: AuditResult):
        assert len(scored_result.recommendations) > 0

    def test_sorted_by_savings(self, scored_result: AuditResult):
        savings = [r.monthly_savings_dollars for r in scored_result.recommendations]
        assert savings == sorted(savings, reverse=True)

    def test_sequential_ranks(self, scored_result: AuditResult):
        ranks = [r.rank for r in scored_result.recommendations]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_valid_box_numbers(self, scored_result: AuditResult):
        for rec in scored_result.recommendations:
            assert rec.box_number in (1, 2, 3)

    def test_valid_effort_values(self, scored_result: AuditResult):
        for rec in scored_result.recommendations:
            assert rec.effort in ("low", "medium", "high")

    def test_valid_impact_values(self, scored_result: AuditResult):
        for rec in scored_result.recommendations:
            assert rec.impact in ("low", "medium", "high")

    def test_positive_savings(self, scored_result: AuditResult):
        for rec in scored_result.recommendations:
            assert rec.monthly_savings_dollars >= 0
            assert rec.monthly_energy_savings_kwh >= 0
