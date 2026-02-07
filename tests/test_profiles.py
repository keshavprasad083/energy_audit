"""Tests for data center profile definitions."""

from __future__ import annotations

import pytest

from energy_audit.data.profiles import DCProfile, PROFILES, get_profile


class TestProfiles:
    """Tests for profile registration and retrieval."""

    @pytest.mark.parametrize("name", [
        "small_startup",
        "medium_enterprise",
        "large_hyperscale",
        "legacy_mixed",
    ])
    def test_get_profile_returns_correct_type(self, name: str):
        profile = get_profile(name)
        assert isinstance(profile, DCProfile)
        assert profile.name == name

    def test_get_profile_unknown_raises(self):
        with pytest.raises(KeyError):
            get_profile("nonexistent_profile")

    def test_all_profiles_registered(self):
        expected = {"small_startup", "medium_enterprise", "large_hyperscale", "legacy_mixed"}
        assert set(PROFILES.keys()) == expected

    @pytest.mark.parametrize("name", list(PROFILES.keys()))
    def test_profile_constraints(self, name: str):
        profile = get_profile(name)
        assert profile.server_count > 0
        assert 0 <= profile.gpu_percentage <= 1
        assert profile.pue_target > 1.0
        assert profile.energy_cost_per_kwh > 0
