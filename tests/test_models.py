"""Tests for core Pydantic data models."""

from __future__ import annotations

import pytest

from energy_audit.data.models import (
    DataCenter,
    EnergyReading,
    Grade,
    Server,
    ServerType,
    AuditResult,
    Recommendation,
)
from datetime import datetime, timezone


class TestServer:
    """Tests for Server computed fields."""

    def _make_server(self, **overrides) -> Server:
        defaults = {
            "id": "srv-001",
            "name": "test-server",
            "server_type": ServerType.cpu,
            "tdp_watts": 500.0,
            "current_power_watts": 250.0,
            "cpu_utilization": 0.6,
            "age_months": 24,
            "warranty_months": 36,
        }
        defaults.update(overrides)
        return Server(**defaults)

    def test_power_efficiency_ratio(self):
        srv = self._make_server(tdp_watts=500.0, current_power_watts=250.0)
        assert srv.power_efficiency_ratio == 0.5

    def test_power_efficiency_ratio_zero_tdp(self):
        srv = self._make_server(tdp_watts=0.01, current_power_watts=0.0)
        assert srv.power_efficiency_ratio == 0.0

    def test_cpu_utilization_pct(self):
        srv = self._make_server(cpu_utilization=0.75)
        assert srv.cpu_utilization_pct == 75.0

    def test_gpu_utilization_pct(self):
        srv = self._make_server(gpu_utilization=0.45)
        assert srv.gpu_utilization_pct == 45.0

    def test_is_past_warranty_false(self):
        srv = self._make_server(age_months=24, warranty_months=36)
        assert srv.is_past_warranty is False

    def test_is_past_warranty_true(self):
        srv = self._make_server(age_months=40, warranty_months=36)
        assert srv.is_past_warranty is True

    def test_is_past_warranty_exact(self):
        srv = self._make_server(age_months=36, warranty_months=36)
        assert srv.is_past_warranty is False


class TestEnergyReading:
    """Tests for EnergyReading computed fields."""

    def test_pue_normal(self):
        reading = EnergyReading(
            timestamp=datetime.now(timezone.utc),
            total_facility_power_kw=150.0,
            it_equipment_power_kw=100.0,
            cooling_power_kw=40.0,
            lighting_power_kw=5.0,
            ups_loss_kw=5.0,
        )
        assert reading.pue == 1.5

    def test_pue_zero_it_power(self):
        reading = EnergyReading(
            timestamp=datetime.now(timezone.utc),
            total_facility_power_kw=50.0,
            it_equipment_power_kw=0.0,
            cooling_power_kw=40.0,
            lighting_power_kw=5.0,
            ups_loss_kw=5.0,
        )
        assert reading.pue == 0.0


class TestDataCenter:
    """Tests for DataCenter aggregate computed properties."""

    def test_total_servers(self, medium_dc: DataCenter):
        assert medium_dc.total_servers == len(medium_dc.servers)
        assert medium_dc.total_servers > 0

    def test_zombie_count(self, medium_dc: DataCenter):
        expected = sum(1 for s in medium_dc.servers if s.is_zombie)
        assert medium_dc.zombie_count == expected

    def test_overprovisioned_count(self, medium_dc: DataCenter):
        expected = sum(1 for s in medium_dc.servers if s.is_overprovisioned)
        assert medium_dc.overprovisioned_count == expected

    def test_avg_pue_positive(self, medium_dc: DataCenter):
        assert medium_dc.avg_pue > 1.0

    def test_total_cost_positive(self, medium_dc: DataCenter):
        assert medium_dc.total_cost > 0

    def test_energy_readings_count(self, medium_dc: DataCenter):
        assert len(medium_dc.energy_readings) == 720


class TestGrade:
    """Tests for Grade enum properties."""

    def test_color_a(self):
        assert Grade.A.color == "green"

    def test_color_b(self):
        assert Grade.B.color == "green"

    def test_color_c(self):
        assert Grade.C.color == "yellow"

    def test_color_d(self):
        assert Grade.D.color == "red"

    def test_color_f(self):
        assert Grade.F.color == "red"


class TestAuditResult:
    """Tests for AuditResult computed properties."""

    def test_total_monthly_savings(self, scored_result: AuditResult):
        expected = round(
            sum(r.monthly_savings_dollars for r in scored_result.recommendations), 2
        )
        assert scored_result.total_monthly_savings == expected

    def test_total_monthly_savings_positive(self, scored_result: AuditResult):
        assert scored_result.total_monthly_savings > 0
