# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""EU Energy Efficiency Directive (EED) compliance assessment.

Evaluates a data-center audit result against the recast EU Energy Efficiency
Directive requirements for data centers (Article 12 / Annex VI), which
mandate PUE limits, energy disclosure, waste heat reuse, renewable energy
targets, and Water Usage Effectiveness (WUE) reporting.
"""

from __future__ import annotations

from datetime import datetime, timezone

from energy_audit.data.models import AuditResult
from energy_audit.pro.compliance import (
    ComplianceCheck,
    ComplianceReport,
    ComplianceStatus,
)


class EUEEDCompliance:
    """Assess an :class:`AuditResult` against the EU EED framework."""

    FRAMEWORK_NAME = "EU Energy Efficiency Directive (Recast)"
    FRAMEWORK_VERSION = "2023/1791 — Article 12 / Annex VI"

    # Thresholds -----------------------------------------------------------
    PUE_TARGET_2027 = 1.2
    RENEWABLE_ENERGY_MIN = 0.50  # 50 %
    WUE_TARGET = 0.40  # litres per kWh
    WASTE_HEAT_REUSE_MIN = 0.10  # 10 % of total heat
    MAX_IDLE_POWER_FRACTION = 0.10  # idle draw should be <10 % of peak

    def assess(self, result: AuditResult) -> ComplianceReport:
        """Run all EU EED compliance checks and return a report."""
        checks: list[ComplianceCheck] = [
            self._check_pue(result),
            self._check_energy_disclosure(result),
            self._check_waste_heat_reuse(result),
            self._check_renewable_energy(result),
            self._check_wue_reporting(result),
            self._check_energy_monitoring(result),
            self._check_idle_power(result),
            self._check_cooling_efficiency(result),
        ]

        compliant = sum(
            1 for c in checks if c.status == ComplianceStatus.COMPLIANT
        )
        total = len(checks)
        pct = round((compliant / total) * 100, 1) if total else 0.0

        return ComplianceReport(
            framework_name=self.FRAMEWORK_NAME,
            framework_version=self.FRAMEWORK_VERSION,
            assessed_at=datetime.now(timezone.utc),
            checks=checks,
            compliant_count=compliant,
            total_checks=total,
            compliance_percentage=pct,
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_pue(self, result: AuditResult) -> ComplianceCheck:
        """PUE must be <= 1.2 by 2027."""
        dc = result.data_center
        avg_pue = dc.avg_pue

        if avg_pue <= 0:
            status = ComplianceStatus.NOT_APPLICABLE
            recommendation = "No valid PUE readings available; install metering."
        elif avg_pue <= self.PUE_TARGET_2027:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif avg_pue <= 1.4:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                f"PUE of {avg_pue:.3f} is above the 2027 target of "
                f"{self.PUE_TARGET_2027}. Optimise cooling and power distribution."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                f"PUE of {avg_pue:.3f} significantly exceeds the "
                f"{self.PUE_TARGET_2027} target. Consider liquid cooling, "
                "hot/cold aisle containment, and UPS upgrades."
            )

        return ComplianceCheck(
            check_id="EU-EED-001",
            name="PUE Target (2027)",
            description=(
                "Average Power Usage Effectiveness must not exceed "
                f"{self.PUE_TARGET_2027} for facilities above 500 kW."
            ),
            status=status,
            current_value=f"{avg_pue:.3f}" if avg_pue > 0 else "N/A",
            required_value=f"<= {self.PUE_TARGET_2027}",
            recommendation=recommendation,
        )

    def _check_energy_disclosure(self, result: AuditResult) -> ComplianceCheck:
        """Annual energy consumption must be reported to the national authority."""
        dc = result.data_center
        has_readings = len(dc.energy_readings) > 0
        total_energy = dc.total_energy_kwh

        if has_readings and total_energy > 0:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "Energy metering data is missing or incomplete. "
                "Deploy sub-metering to capture IT, cooling, and total facility power."
            )

        return ComplianceCheck(
            check_id="EU-EED-002",
            name="Energy Consumption Disclosure",
            description=(
                "Annual energy consumption data must be collected and reported "
                "to the relevant national authority."
            ),
            status=status,
            current_value=f"{total_energy:,.0f} kWh" if total_energy > 0 else "N/A",
            required_value="Annual energy data available",
            recommendation=recommendation,
        )

    def _check_waste_heat_reuse(self, result: AuditResult) -> ComplianceCheck:
        """Assess whether waste heat reuse programmes are in place.

        This is a qualitative check — without dedicated waste-heat sensors we
        estimate from cooling delta-T whether heat recovery is plausible.
        """
        dc = result.data_center
        racks = dc.racks
        if not racks:
            return ComplianceCheck(
                check_id="EU-EED-003",
                name="Waste Heat Reuse",
                description="Waste heat recovery and reuse should be evaluated.",
                status=ComplianceStatus.NOT_APPLICABLE,
                current_value="N/A",
                required_value=f">= {self.WASTE_HEAT_REUSE_MIN:.0%} heat reuse",
                recommendation="No rack data available to evaluate waste heat.",
            )

        avg_delta = sum(r.delta_temp_celsius for r in racks) / len(racks)
        # High delta-T (>15 C) suggests significant waste heat potential
        if avg_delta > 15:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                f"Average rack delta-T of {avg_delta:.1f} C indicates substantial "
                "waste heat. Evaluate district heating or heat-pump integration."
            )
        elif avg_delta > 10:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                "Moderate waste heat potential exists. Consider heat recovery "
                "for office space or nearby facilities."
            )
        else:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""

        return ComplianceCheck(
            check_id="EU-EED-003",
            name="Waste Heat Reuse",
            description=(
                "Facilities must assess and, where feasible, implement waste "
                "heat recovery programmes."
            ),
            status=status,
            current_value=f"Avg rack delta-T: {avg_delta:.1f} C",
            required_value=f">= {self.WASTE_HEAT_REUSE_MIN:.0%} heat reuse",
            recommendation=recommendation,
        )

    def _check_renewable_energy(self, result: AuditResult) -> ComplianceCheck:
        """Renewable energy share must meet minimum threshold."""
        pct = result.data_center.config.renewable_percentage

        if pct >= self.RENEWABLE_ENERGY_MIN:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif pct >= self.RENEWABLE_ENERGY_MIN * 0.5:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                f"Renewable share of {pct:.0%} is below the {self.RENEWABLE_ENERGY_MIN:.0%} "
                "target. Explore on-site solar, PPAs, or green tariffs."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                f"Renewable share of {pct:.0%} is well below the "
                f"{self.RENEWABLE_ENERGY_MIN:.0%} target. Procure renewable energy "
                "certificates or negotiate a Power Purchase Agreement."
            )

        return ComplianceCheck(
            check_id="EU-EED-004",
            name="Renewable Energy Share",
            description=(
                f"At least {self.RENEWABLE_ENERGY_MIN:.0%} of energy should come "
                "from renewable sources."
            ),
            status=status,
            current_value=f"{pct:.0%}",
            required_value=f">= {self.RENEWABLE_ENERGY_MIN:.0%}",
            recommendation=recommendation,
        )

    def _check_wue_reporting(self, result: AuditResult) -> ComplianceCheck:
        """Water Usage Effectiveness (WUE) must be reported.

        Without direct water metering we mark this as NOT_APPLICABLE or use
        cooling type as a proxy.
        """
        cooling_type = result.data_center.config.cooling_type.lower()

        if cooling_type == "liquid":
            status = ComplianceStatus.PARTIAL
            recommendation = (
                "Liquid cooling is in use — ensure water consumption is metered "
                f"and WUE stays below {self.WUE_TARGET} L/kWh."
            )
            current = "Liquid cooling — WUE metering recommended"
        elif cooling_type == "hybrid":
            status = ComplianceStatus.PARTIAL
            recommendation = (
                "Hybrid cooling may use water. Install water meters and report WUE."
            )
            current = "Hybrid cooling — WUE metering recommended"
        else:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
            current = "Air cooling — minimal water usage expected"

        return ComplianceCheck(
            check_id="EU-EED-005",
            name="WUE Reporting",
            description=(
                "Water Usage Effectiveness must be measured and reported annually."
            ),
            status=status,
            current_value=current,
            required_value=f"WUE reported; target <= {self.WUE_TARGET} L/kWh",
            recommendation=recommendation,
        )

    def _check_energy_monitoring(self, result: AuditResult) -> ComplianceCheck:
        """Continuous energy monitoring must be in place."""
        readings = result.data_center.energy_readings
        hours = len(readings)

        if hours >= 720:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif hours >= 168:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                f"Only {hours} hours of energy data available. EU EED expects "
                "continuous monitoring with at least 30 days of granular data."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "Insufficient energy monitoring data. Deploy sub-metering across "
                "IT load, cooling, lighting, and UPS systems."
            )

        return ComplianceCheck(
            check_id="EU-EED-006",
            name="Continuous Energy Monitoring",
            description=(
                "Facilities must implement continuous, granular energy monitoring."
            ),
            status=status,
            current_value=f"{hours} hours of readings",
            required_value=">= 720 hours (30 days) of continuous data",
            recommendation=recommendation,
        )

    def _check_idle_power(self, result: AuditResult) -> ComplianceCheck:
        """Idle power draw should be minimised."""
        dc = result.data_center
        servers = dc.servers
        if not servers:
            return ComplianceCheck(
                check_id="EU-EED-007",
                name="Idle Power Management",
                description="Servers should minimise idle power consumption.",
                status=ComplianceStatus.NOT_APPLICABLE,
                current_value="N/A",
                required_value=f"Idle fraction < {self.MAX_IDLE_POWER_FRACTION:.0%}",
                recommendation="No server data available.",
            )

        total_power = sum(s.current_power_watts for s in servers)
        total_tdp = sum(s.tdp_watts for s in servers)
        avg_utilization = sum(s.cpu_utilization for s in servers) / len(servers)

        # Estimate idle fraction: low utilization with high power ratio
        idle_fraction = 0.0
        if total_tdp > 0:
            power_ratio = total_power / total_tdp
            idle_fraction = max(0.0, power_ratio - avg_utilization)

        if idle_fraction <= self.MAX_IDLE_POWER_FRACTION:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                f"Estimated idle power fraction of {idle_fraction:.0%} exceeds "
                f"{self.MAX_IDLE_POWER_FRACTION:.0%}. Enable power capping, "
                "C-state management, or consolidate underutilised servers."
            )

        return ComplianceCheck(
            check_id="EU-EED-007",
            name="Idle Power Management",
            description=(
                "Server idle power consumption should be minimised through "
                "power management features and workload consolidation."
            ),
            status=status,
            current_value=f"Estimated idle fraction: {idle_fraction:.0%}",
            required_value=f"Idle fraction < {self.MAX_IDLE_POWER_FRACTION:.0%}",
            recommendation=recommendation,
        )

    def _check_cooling_efficiency(self, result: AuditResult) -> ComplianceCheck:
        """Cooling systems should operate efficiently (COP evaluation)."""
        cooling = result.data_center.cooling_systems
        if not cooling:
            return ComplianceCheck(
                check_id="EU-EED-008",
                name="Cooling System Efficiency",
                description="Cooling systems must operate at efficient COP levels.",
                status=ComplianceStatus.NOT_APPLICABLE,
                current_value="N/A",
                required_value="Average COP >= 4.0",
                recommendation="No cooling system data available for assessment.",
            )

        avg_cop = sum(c.cop for c in cooling) / len(cooling)

        if avg_cop >= 4.0:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif avg_cop >= 3.0:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                f"Average cooling COP of {avg_cop:.1f} is adequate but below "
                "best practice (>= 4.0). Consider upgrading to higher-efficiency "
                "chillers or free cooling where climate allows."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                f"Average cooling COP of {avg_cop:.1f} is poor. Replace aging "
                "CRAC/CRAH units and evaluate economiser or free-cooling modes."
            )

        return ComplianceCheck(
            check_id="EU-EED-008",
            name="Cooling System Efficiency",
            description=(
                "Cooling systems should achieve a Coefficient of Performance (COP) "
                "of at least 4.0 for compliance with EU EED best-practice guidance."
            ),
            status=status,
            current_value=f"Avg COP: {avg_cop:.1f}",
            required_value="Average COP >= 4.0",
            recommendation=recommendation,
        )
