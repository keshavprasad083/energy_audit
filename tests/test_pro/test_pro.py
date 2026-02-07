# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Tests for the energy-audit pro module."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from energy_audit.data.models import AuditResult, Grade
from energy_audit.pro import _PRO_AVAILABLE, check_dependency
from energy_audit.pro.config import (
    CollectorSourceConfig,
    CredentialRef,
    FacilityConfig,
    ProConfig,
    load_config,
)
from energy_audit.pro.collectors import COLLECTOR_REGISTRY, get_collector, register_collector
from energy_audit.pro.collectors.base import (
    CollectorResult,
    DataCollector,
    RawCoolingData,
    RawEnergyReading,
    RawServerData,
)
from energy_audit.pro.mapper import DataCenterMapper

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Module availability
# ---------------------------------------------------------------------------

class TestProInit:
    def test_pro_available(self):
        assert _PRO_AVAILABLE is True

    def test_check_dependency_exists(self):
        # stdlib module should not raise
        check_dependency("json", "pip install json")

    def test_check_dependency_missing(self):
        with pytest.raises(ImportError, match="requires 'nonexistent_pkg_xyz'"):
            check_dependency("nonexistent_pkg_xyz", "pip install nonexistent_pkg_xyz")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_load_config_yaml(self):
        cfg = load_config(FIXTURES / "config.yaml")
        assert cfg.facility.name == "Test Facility"
        assert len(cfg.sources) == 1
        assert cfg.sources[0].type == "csv"

    def test_load_config_json_source(self):
        cfg = load_config(FIXTURES / "config_json.yaml")
        assert cfg.facility.name == "JSON Test Facility"
        assert cfg.sources[0].type == "json"

    def test_config_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path.yaml")

    def test_facility_defaults(self):
        f = FacilityConfig(name="Test")
        assert f.location == "Unknown"
        assert f.pue_target == 1.4

    def test_credential_ref_value(self):
        cred = CredentialRef(value="secret123")
        assert cred.resolve() == "secret123"

    def test_credential_ref_env_var(self):
        os.environ["_TEST_CRED_VAR"] = "env_secret"
        try:
            cred = CredentialRef(env_var="_TEST_CRED_VAR")
            assert cred.resolve() == "env_secret"
        finally:
            del os.environ["_TEST_CRED_VAR"]

    def test_credential_ref_none_raises(self):
        cred = CredentialRef()
        with pytest.raises(ValueError, match="Could not resolve"):
            cred.resolve()

    def test_collector_source_config_defaults(self):
        src = CollectorSourceConfig(type="csv")
        assert src.enabled is True
        assert src.timeout_seconds == 30
        assert src.retry_count == 2

    def test_pro_config_min_sources(self):
        with pytest.raises(Exception):
            ProConfig(
                facility=FacilityConfig(name="Empty"),
                sources=[],
            )


# ---------------------------------------------------------------------------
# Collector registry
# ---------------------------------------------------------------------------

class TestCollectorRegistry:
    def test_get_csv_collector(self):
        cls = get_collector("csv")
        assert cls is not None

    def test_get_json_collector(self):
        cls = get_collector("json")
        assert cls is not None

    def test_get_snmp_collector(self):
        cls = get_collector("snmp")
        assert cls is not None

    def test_get_ipmi_collector(self):
        cls = get_collector("ipmi")
        assert cls is not None

    def test_get_redfish_collector(self):
        cls = get_collector("redfish")
        assert cls is not None

    def test_get_aws_collector(self):
        cls = get_collector("aws")
        assert cls is not None

    def test_get_azure_collector(self):
        cls = get_collector("azure")
        assert cls is not None

    def test_get_gcp_collector(self):
        cls = get_collector("gcp")
        assert cls is not None

    def test_unknown_collector_raises(self):
        with pytest.raises(KeyError, match="Unknown collector"):
            get_collector("nonexistent_collector_xyz")

    def test_all_collectors_registered(self):
        # Trigger lazy loading
        get_collector("csv")
        expected = {"csv", "json", "snmp", "ipmi", "redfish", "aws", "azure", "gcp"}
        assert expected.issubset(set(COLLECTOR_REGISTRY.keys()))


# ---------------------------------------------------------------------------
# File import collector
# ---------------------------------------------------------------------------

class TestFileImportCollector:
    def _make_config(self, *paths: str, type: str = "csv") -> CollectorSourceConfig:
        return CollectorSourceConfig(
            type=type,
            endpoints=[str(p) for p in paths],
        )

    def test_csv_server_import(self):
        cfg = self._make_config(FIXTURES / "servers.csv")
        cls = get_collector("csv")
        collector = cls(cfg)
        result = collector.collect()

        assert len(result.errors) == 0
        assert len(result.servers) == 8
        assert result.servers[0].hostname == "web-01"
        assert result.servers[0].power_watts == 180.0
        assert result.servers[0].cpu_utilization == 0.65

    def test_csv_energy_import(self):
        cfg = self._make_config(FIXTURES / "energy.csv")
        cls = get_collector("csv")
        collector = cls(cfg)
        result = collector.collect()

        assert len(result.energy_readings) == 10
        assert result.energy_readings[0].total_power_kw == 150.5
        assert result.energy_readings[0].it_power_kw == 100.2

    def test_json_import(self):
        cfg = self._make_config(FIXTURES / "servers.json", type="json")
        cls = get_collector("json")
        collector = cls(cfg)
        result = collector.collect()

        assert len(result.servers) == 4
        assert result.servers[0].hostname == "api-01"
        assert result.servers[2].gpu_utilization == 0.88

    def test_missing_file_error(self):
        cfg = self._make_config("/nonexistent/file.csv")
        cls = get_collector("csv")
        collector = cls(cfg)
        result = collector.collect()

        assert len(result.errors) == 1
        assert "not found" in result.errors[0].lower()

    def test_discover(self):
        cfg = self._make_config(FIXTURES / "servers.csv")
        cls = get_collector("csv")
        collector = cls(cfg)
        endpoints = collector.discover()

        assert len(endpoints) == 1
        assert "bytes" in endpoints[0]

    def test_test_connection(self):
        cfg = self._make_config(FIXTURES / "servers.csv")
        cls = get_collector("csv")
        collector = cls(cfg)
        assert collector.test_connection() is True

    def test_test_connection_no_files(self):
        cfg = self._make_config("/nonexistent/file.csv")
        cls = get_collector("csv")
        collector = cls(cfg)
        assert collector.test_connection() is False


# ---------------------------------------------------------------------------
# Simulated collectors (SNMP, IPMI, Redfish, Cloud)
# ---------------------------------------------------------------------------

class TestSimulatedCollectors:
    def _make_sim_config(self, collector_type: str) -> CollectorSourceConfig:
        return CollectorSourceConfig(
            type=collector_type,
            endpoints=["10.0.0.1", "10.0.0.2"],
            options={"simulate": True, "seed": 42},
        )

    def test_snmp_simulate_collect(self):
        cfg = self._make_sim_config("snmp")
        cls = get_collector("snmp")
        collector = cls(cfg)
        result = collector.collect()

        assert isinstance(result, CollectorResult)
        assert len(result.servers) > 0
        assert all(s.hostname for s in result.servers)
        assert all(s.power_watts is not None and s.power_watts > 0 for s in result.servers)

    def test_snmp_simulate_discover(self):
        cfg = self._make_sim_config("snmp")
        cls = get_collector("snmp")
        collector = cls(cfg)
        endpoints = collector.discover()
        assert len(endpoints) > 0

    def test_snmp_simulate_test_connection(self):
        cfg = self._make_sim_config("snmp")
        cls = get_collector("snmp")
        collector = cls(cfg)
        assert collector.test_connection() is True

    def test_ipmi_simulate_collect(self):
        cfg = self._make_sim_config("ipmi")
        cls = get_collector("ipmi")
        collector = cls(cfg)
        result = collector.collect()

        assert isinstance(result, CollectorResult)
        assert len(result.servers) > 0
        # IPMI should provide temperature data
        has_temp = any(s.inlet_temp_celsius is not None for s in result.servers)
        assert has_temp, "IPMI should provide inlet temperature"

    def test_ipmi_simulate_discover(self):
        cfg = self._make_sim_config("ipmi")
        cls = get_collector("ipmi")
        collector = cls(cfg)
        endpoints = collector.discover()
        assert len(endpoints) > 0

    def test_redfish_simulate_collect(self):
        cfg = self._make_sim_config("redfish")
        cls = get_collector("redfish")
        collector = cls(cfg)
        result = collector.collect()

        assert isinstance(result, CollectorResult)
        assert len(result.servers) > 0
        # Redfish should provide model info
        has_model = any(s.model is not None for s in result.servers)
        assert has_model, "Redfish should provide model info"

    def test_redfish_simulate_discover(self):
        cfg = self._make_sim_config("redfish")
        cls = get_collector("redfish")
        collector = cls(cfg)
        endpoints = collector.discover()
        assert len(endpoints) > 0

    def test_aws_simulate_collect(self):
        cfg = self._make_sim_config("aws")
        cls = get_collector("aws")
        collector = cls(cfg)
        result = collector.collect()

        assert isinstance(result, CollectorResult)
        assert len(result.servers) >= 10  # 15-25 instances

    def test_azure_simulate_collect(self):
        cfg = self._make_sim_config("azure")
        cls = get_collector("azure")
        collector = cls(cfg)
        result = collector.collect()

        assert isinstance(result, CollectorResult)
        assert len(result.servers) >= 5

    def test_gcp_simulate_collect(self):
        cfg = self._make_sim_config("gcp")
        cls = get_collector("gcp")
        collector = cls(cfg)
        result = collector.collect()

        assert isinstance(result, CollectorResult)
        assert len(result.servers) >= 5


# ---------------------------------------------------------------------------
# Mapper
# ---------------------------------------------------------------------------

class TestMapper:
    @pytest.fixture()
    def facility(self) -> FacilityConfig:
        return FacilityConfig(
            name="Test DC",
            location="Test City",
            pue_target=1.4,
            cooling_type="air",
            energy_cost_per_kwh=0.12,
            carbon_intensity_gco2_per_kwh=400.0,
        )

    @pytest.fixture()
    def basic_collector_result(self) -> CollectorResult:
        now = datetime.now(timezone.utc)
        return CollectorResult(
            source_type="test",
            servers=[
                RawServerData(
                    hostname="srv-01",
                    server_type_hint="cpu",
                    power_watts=250.0,
                    cpu_utilization=0.65,
                    memory_utilization=0.40,
                    memory_total_gb=64.0,
                ),
                RawServerData(
                    hostname="gpu-01",
                    server_type_hint="gpu_training",
                    power_watts=900.0,
                    cpu_utilization=0.30,
                    gpu_utilization=0.85,
                    memory_total_gb=512.0,
                ),
                RawServerData(
                    hostname="zombie-01",
                    server_type_hint="cpu",
                    power_watts=100.0,
                    cpu_utilization=0.01,
                    gpu_utilization=0.0,
                ),
            ],
            energy_readings=[
                RawEnergyReading(
                    timestamp=now,
                    total_power_kw=150.0,
                    it_power_kw=100.0,
                )
            ],
        )

    def test_map_produces_datacenter(self, facility, basic_collector_result):
        mapper = DataCenterMapper(facility)
        dc = mapper.map([basic_collector_result])

        assert dc.config.name == "Test DC"
        assert len(dc.servers) == 3
        assert len(dc.energy_readings) == 720
        assert len(dc.racks) >= 1
        assert len(dc.workloads) >= 1
        assert len(dc.cooling_systems) >= 1

    def test_zombie_detection(self, facility, basic_collector_result):
        mapper = DataCenterMapper(facility)
        dc = mapper.map([basic_collector_result])

        zombies = [s for s in dc.servers if s.is_zombie]
        assert len(zombies) >= 1
        zombie = next(s for s in dc.servers if s.name == "zombie-01")
        assert zombie.is_zombie is True

    def test_server_type_mapping(self, facility, basic_collector_result):
        mapper = DataCenterMapper(facility)
        dc = mapper.map([basic_collector_result])

        gpu = next(s for s in dc.servers if s.name == "gpu-01")
        assert gpu.server_type.value == "gpu_training"
        assert gpu.current_power_watts == 900.0

    def test_energy_readings_padded_to_720(self, facility, basic_collector_result):
        mapper = DataCenterMapper(facility)
        dc = mapper.map([basic_collector_result])
        assert len(dc.energy_readings) == 720

    def test_synthesize_readings_when_none(self, facility):
        result = CollectorResult(
            source_type="test",
            servers=[
                RawServerData(hostname="srv-01", power_watts=200.0),
            ],
        )
        mapper = DataCenterMapper(facility)
        dc = mapper.map([result])
        assert len(dc.energy_readings) == 720
        assert all(r.total_facility_power_kw > 0 for r in dc.energy_readings)

    def test_rack_synthesis(self, facility):
        servers = [
            RawServerData(hostname=f"srv-{i:03d}", power_watts=200.0)
            for i in range(50)
        ]
        result = CollectorResult(source_type="test", servers=servers)
        mapper = DataCenterMapper(facility)
        dc = mapper.map([result])

        assert len(dc.racks) == 3  # 50 servers / 20 per rack = 3 racks

    def test_multi_collector_merge(self, facility):
        r1 = CollectorResult(
            source_type="snmp",
            servers=[
                RawServerData(hostname="shared-host", power_watts=300.0),
            ],
        )
        r2 = CollectorResult(
            source_type="ipmi",
            servers=[
                RawServerData(
                    hostname="shared-host",
                    cpu_utilization=0.55,
                    inlet_temp_celsius=23.0,
                ),
            ],
        )
        mapper = DataCenterMapper(facility)
        dc = mapper.map([r1, r2])

        assert len(dc.servers) == 1  # deduplicated
        server = dc.servers[0]
        assert server.current_power_watts == 300.0  # from SNMP
        assert server.cpu_utilization == 0.55  # from IPMI

    def test_power_estimation_without_reading(self, facility):
        result = CollectorResult(
            source_type="test",
            servers=[
                RawServerData(
                    hostname="no-power",
                    server_type_hint="cpu",
                    cpu_utilization=0.50,
                ),
            ],
        )
        mapper = DataCenterMapper(facility)
        dc = mapper.map([result])

        server = dc.servers[0]
        # Power should be estimated: TDP * (0.30 + 0.70 * util)
        expected = 250.0 * (0.30 + 0.70 * 0.50)  # 162.5W
        assert abs(server.current_power_watts - expected) < 0.1

    def test_cooling_system_synthesis(self, facility):
        result = CollectorResult(
            source_type="test",
            servers=[
                RawServerData(hostname="srv-01", power_watts=500.0),
            ],
        )
        mapper = DataCenterMapper(facility)
        dc = mapper.map([result])

        assert len(dc.cooling_systems) == 1
        cs = dc.cooling_systems[0]
        assert cs.cooling_type.value == "air"
        assert cs.cop == 3.0


# ---------------------------------------------------------------------------
# End-to-end: CSV → DataCenter → Scoring
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_csv_to_scored_audit(self):
        cfg = load_config(FIXTURES / "config.yaml")
        source = cfg.sources[0]

        cls = get_collector(source.type)
        collector = cls(source)
        result = collector.collect()

        mapper = DataCenterMapper(cfg.facility)
        dc = mapper.map([result])

        from energy_audit.scoring.engine import ScoringEngine
        engine = ScoringEngine()
        box1, box2, box3, overall_score, overall_grade = engine.score(dc)

        assert 0 <= overall_score <= 100
        assert isinstance(overall_grade, Grade)
        assert len(dc.servers) == 8

    def test_simulated_snmp_to_scored_audit(self):
        cfg = load_config(FIXTURES / "snmp_sim.yaml")
        source = cfg.sources[0]

        cls = get_collector(source.type)
        collector = cls(source)
        result = collector.collect()

        mapper = DataCenterMapper(cfg.facility)
        dc = mapper.map([result])

        from energy_audit.scoring.engine import ScoringEngine
        engine = ScoringEngine()
        box1, box2, box3, overall_score, overall_grade = engine.score(dc)

        assert 0 <= overall_score <= 100
        assert len(dc.servers) > 0


# ---------------------------------------------------------------------------
# Fleet analysis
# ---------------------------------------------------------------------------

class TestFleet:
    def _make_audit_result(self, name: str, score: float) -> AuditResult:
        """Build a minimal AuditResult using simulated data."""
        from energy_audit.data.profiles import get_profile
        from energy_audit.data.generator import DataCenterGenerator
        from energy_audit.scoring.engine import ScoringEngine
        from energy_audit.recommendations.engine import RecommendationEngine
        from energy_audit.reporting.executive_summary import generate_executive_summary

        profile = get_profile("small_startup")
        gen = DataCenterGenerator(profile, seed=42)
        dc = gen.generate()
        engine = ScoringEngine()
        box1, box2, box3, overall_score, overall_grade = engine.score(dc)
        rec_engine = RecommendationEngine()
        recommendations = rec_engine.generate(dc, box1, box2, box3)
        executive_summary = generate_executive_summary(
            dc, box1, box2, box3, overall_score, overall_grade, recommendations
        )
        return AuditResult(
            data_center=dc,
            box1=box1,
            box2=box2,
            box3=box3,
            overall_score=overall_score,
            overall_grade=overall_grade,
            recommendations=recommendations,
            executive_summary=executive_summary,
        )

    def test_build_fleet_report(self):
        from energy_audit.pro.fleet import build_fleet_report

        r1 = self._make_audit_result("Site A", 75.0)
        r2 = self._make_audit_result("Site B", 60.0)

        report = build_fleet_report({"Site A": r1, "Site B": r2})

        assert len(report.sites) == 2
        assert report.total_servers > 0
        assert report.avg_score > 0
        assert report.total_power_kw > 0

    def test_fleet_report_empty(self):
        from energy_audit.pro.fleet import build_fleet_report

        report = build_fleet_report({})
        assert len(report.sites) == 0
        assert report.total_servers == 0
        assert report.best_site == "N/A"

    def test_fleet_renderer(self):
        from io import StringIO
        from rich.console import Console
        from energy_audit.pro.fleet import build_fleet_report
        from energy_audit.pro.fleet_renderer import FleetRenderer

        r = self._make_audit_result("HQ", 80.0)
        report = build_fleet_report({"HQ": r})

        buf = StringIO()
        console = Console(file=buf, force_terminal=True)
        renderer = FleetRenderer(console)
        renderer.render(report)

        output = buf.getvalue()
        assert "HQ" in output


# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------

class TestCompliance:
    @pytest.fixture()
    def audit_result(self) -> AuditResult:
        from energy_audit.data.profiles import get_profile
        from energy_audit.data.generator import DataCenterGenerator
        from energy_audit.scoring.engine import ScoringEngine
        from energy_audit.recommendations.engine import RecommendationEngine
        from energy_audit.reporting.executive_summary import generate_executive_summary

        profile = get_profile("medium_enterprise")
        gen = DataCenterGenerator(profile, seed=42)
        dc = gen.generate()
        engine = ScoringEngine()
        box1, box2, box3, overall_score, overall_grade = engine.score(dc)
        rec_engine = RecommendationEngine()
        recommendations = rec_engine.generate(dc, box1, box2, box3)
        executive_summary = generate_executive_summary(
            dc, box1, box2, box3, overall_score, overall_grade, recommendations
        )
        return AuditResult(
            data_center=dc,
            box1=box1,
            box2=box2,
            box3=box3,
            overall_score=overall_score,
            overall_grade=overall_grade,
            recommendations=recommendations,
            executive_summary=executive_summary,
        )

    def test_eu_eed_compliance(self, audit_result):
        from energy_audit.pro.compliance.eu_eed import EUEEDCompliance

        report = EUEEDCompliance().assess(audit_result)

        assert report.framework_name.startswith("EU Energy Efficiency")
        assert report.total_checks == 8
        assert 0 <= report.compliance_percentage <= 100
        assert len(report.checks) == 8

    def test_iso_50001_compliance(self, audit_result):
        from energy_audit.pro.compliance.iso_50001 import ISO50001Compliance

        report = ISO50001Compliance().assess(audit_result)

        assert "ISO 50001" in report.framework_name
        assert report.total_checks == 7
        assert len(report.checks) == 7

    def test_sec_climate_compliance(self, audit_result):
        from energy_audit.pro.compliance.sec_climate import SECClimateCompliance

        report = SECClimateCompliance().assess(audit_result)

        assert "SEC" in report.framework_name
        assert report.total_checks == 6
        assert len(report.checks) == 6

    def test_compliance_status_enum(self):
        from energy_audit.pro.compliance import ComplianceStatus

        # Enum values may be lowercase or uppercase depending on implementation
        assert "compliant" in ComplianceStatus.COMPLIANT.value.lower()
        assert "non_compliant" in ComplianceStatus.NON_COMPLIANT.value.lower()
        assert "partial" in ComplianceStatus.PARTIAL.value.lower()
        assert "not_applicable" in ComplianceStatus.NOT_APPLICABLE.value.lower()


# ---------------------------------------------------------------------------
# Cloud power models
# ---------------------------------------------------------------------------

class TestPowerModels:
    def test_aws_power_lookup(self):
        from energy_audit.pro.collectors.cloud.power_models import estimate_power

        assert estimate_power("aws", "p4d.24xlarge") == 2500
        assert estimate_power("aws", "t3.micro") == 5

    def test_azure_power_lookup(self):
        from energy_audit.pro.collectors.cloud.power_models import estimate_power

        power = estimate_power("azure", "Standard_B1s")
        assert power > 0

    def test_gcp_power_lookup(self):
        from energy_audit.pro.collectors.cloud.power_models import estimate_power

        power = estimate_power("gcp", "e2-micro")
        assert power > 0

    def test_unknown_instance_default(self):
        from energy_audit.pro.collectors.cloud.power_models import estimate_power

        power = estimate_power("aws", "totally-unknown-instance")
        assert power == 150  # default


# ---------------------------------------------------------------------------
# Raw data models
# ---------------------------------------------------------------------------

class TestRawDataModels:
    def test_raw_server_data_minimal(self):
        s = RawServerData(hostname="test-srv")
        assert s.hostname == "test-srv"
        assert s.power_watts is None
        assert s.tags == {}

    def test_raw_server_data_full(self):
        s = RawServerData(
            hostname="gpu-01",
            server_type_hint="gpu_training",
            power_watts=950.0,
            cpu_utilization=0.30,
            gpu_utilization=0.90,
            memory_utilization=0.65,
            memory_total_gb=512.0,
            inlet_temp_celsius=22.5,
            outlet_temp_celsius=38.0,
            age_months=12,
            rack_id="rack-gpu-1",
        )
        assert s.power_watts == 950.0
        assert s.gpu_utilization == 0.90

    def test_raw_energy_reading(self):
        r = RawEnergyReading(
            timestamp=datetime.now(timezone.utc),
            total_power_kw=100.0,
            it_power_kw=70.0,
        )
        assert r.total_power_kw == 100.0
        assert r.cooling_power_kw is None

    def test_raw_cooling_data(self):
        c = RawCoolingData(name="CRAC-1", cooling_type="air", cop=3.5)
        assert c.cop == 3.5

    def test_collector_result(self):
        r = CollectorResult(
            source_type="test",
            servers=[RawServerData(hostname="a")],
        )
        assert len(r.servers) == 1
        assert r.source_type == "test"
        assert len(r.errors) == 0
