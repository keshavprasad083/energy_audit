# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Tests for the simulated data center generator."""

from __future__ import annotations

import pytest

from energy_audit.data.generator import DataCenterGenerator
from energy_audit.data.models import DataCenter
from energy_audit.data.profiles import PROFILES, get_profile


class TestGenerator:
    """Tests for DataCenterGenerator."""

    @pytest.mark.parametrize("profile_name", list(PROFILES.keys()))
    def test_generates_valid_datacenter(self, profile_name: str):
        profile = get_profile(profile_name)
        gen = DataCenterGenerator(profile, seed=42)
        dc = gen.generate()

        assert isinstance(dc, DataCenter)
        assert dc.total_servers > 0
        assert len(dc.racks) > 0
        assert len(dc.energy_readings) == 720
        assert len(dc.cooling_systems) > 0

    def test_seed_reproducibility(self):
        profile = get_profile("medium_enterprise")
        dc1 = DataCenterGenerator(profile, seed=42).generate()
        dc2 = DataCenterGenerator(profile, seed=42).generate()

        assert dc1.total_servers == dc2.total_servers
        assert dc1.avg_pue == dc2.avg_pue
        assert dc1.zombie_count == dc2.zombie_count
        assert dc1.total_cost == dc2.total_cost

    def test_different_seed_differs(self):
        profile = get_profile("medium_enterprise")
        dc1 = DataCenterGenerator(profile, seed=42).generate()
        dc2 = DataCenterGenerator(profile, seed=99).generate()

        # Server count is deterministic from profile, but utilization/costs differ
        assert dc1.avg_pue != dc2.avg_pue or dc1.total_cost != dc2.total_cost

    def test_server_count_matches_profile(self):
        profile = get_profile("medium_enterprise")
        gen = DataCenterGenerator(profile, seed=42)
        dc = gen.generate()
        assert dc.total_servers == profile.server_count
