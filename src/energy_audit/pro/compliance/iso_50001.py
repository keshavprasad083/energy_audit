# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""ISO 50001 Energy Management System (EnMS) compliance mapping.

Maps data-center audit results to the key requirements of ISO 50001:2018
for establishing, implementing, and continually improving an energy
management system.
"""

from __future__ import annotations

from datetime import datetime, timezone

from energy_audit.data.models import AuditResult
from energy_audit.pro.compliance import (
    ComplianceCheck,
    ComplianceReport,
    ComplianceStatus,
)


class ISO50001Compliance:
    """Assess an :class:`AuditResult` against ISO 50001:2018 requirements."""

    FRAMEWORK_NAME = "ISO 50001 Energy Management System"
    FRAMEWORK_VERSION = "ISO 50001:2018"

    # Thresholds -----------------------------------------------------------
    MIN_READINGS_FOR_BASELINE = 168  # at least 7 days of hourly data
    MIN_READINGS_FOR_MONITORING = 720  # 30 days continuous
    MIN_IMPROVEMENT_TARGET_PCT = 2.0  # 2 % year-over-year improvement target
    MIN_UTILIZATION_FOR_EFFICIENCY = 0.30  # 30 % avg CPU utilisation

    def assess(self, result: AuditResult) -> ComplianceReport:
        """Run all ISO 50001 compliance checks and return a report."""
        checks: list[ComplianceCheck] = [
            self._check_energy_baseline(result),
            self._check_energy_performance_indicators(result),
            self._check_monitoring_plan(result),
            self._check_targets_set(result),
            self._check_management_review(result),
            self._check_continual_improvement(result),
            self._check_operational_control(result),
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

    def _check_energy_baseline(self, result: AuditResult) -> ComplianceCheck:
        """Clause 4.4.4 — An energy baseline must be established."""
        readings = result.data_center.energy_readings
        hours = len(readings)

        if hours >= self.MIN_READINGS_FOR_BASELINE:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif hours > 0:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                f"Only {hours} hours of data collected. A robust energy baseline "
                f"requires at least {self.MIN_READINGS_FOR_BASELINE} hours "
                "(7 days) of continuous metering."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "No energy data available. Establish metering infrastructure "
                "to collect at least 7 days of hourly readings as a baseline."
            )

        return ComplianceCheck(
            check_id="ISO50001-001",
            name="Energy Baseline Established",
            description=(
                "An energy baseline using a suitable data period must be "
                "established for normalisation and comparison (Clause 4.4.4)."
            ),
            status=status,
            current_value=f"{hours} hours of energy data",
            required_value=f">= {self.MIN_READINGS_FOR_BASELINE} hours",
            recommendation=recommendation,
        )

    def _check_energy_performance_indicators(self, result: AuditResult) -> ComplianceCheck:
        """Clause 4.4.5 — Energy Performance Indicators (EnPIs) must be defined."""
        dc = result.data_center
        has_pue = dc.avg_pue > 0
        has_utilization = dc.avg_cpu_utilization > 0
        has_energy = dc.total_energy_kwh > 0

        indicators_available = sum([has_pue, has_utilization, has_energy])

        if indicators_available >= 3:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif indicators_available >= 1:
            status = ComplianceStatus.PARTIAL
            missing = []
            if not has_pue:
                missing.append("PUE")
            if not has_utilization:
                missing.append("utilization metrics")
            if not has_energy:
                missing.append("total energy consumption")
            recommendation = (
                f"Missing EnPIs: {', '.join(missing)}. Define and track all "
                "relevant energy performance indicators."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "No energy performance indicators are available. Define EnPIs "
                "such as PUE, energy per compute unit, and utilization rates."
            )

        return ComplianceCheck(
            check_id="ISO50001-002",
            name="Energy Performance Indicators (EnPIs)",
            description=(
                "The organisation must determine EnPIs that are appropriate "
                "for measuring and monitoring energy performance (Clause 4.4.5)."
            ),
            status=status,
            current_value=f"{indicators_available}/3 key indicators available",
            required_value="PUE, utilization, and energy consumption tracked",
            recommendation=recommendation,
        )

    def _check_monitoring_plan(self, result: AuditResult) -> ComplianceCheck:
        """Clause 4.6.1 — A monitoring, measurement, and analysis plan must exist."""
        readings = result.data_center.energy_readings
        hours = len(readings)

        # Check whether sub-metering exists (IT vs. cooling vs. lighting)
        has_submetering = False
        if readings:
            sample = readings[0]
            has_submetering = (
                sample.it_equipment_power_kw > 0
                and sample.cooling_power_kw > 0
            )

        if hours >= self.MIN_READINGS_FOR_MONITORING and has_submetering:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif hours >= self.MIN_READINGS_FOR_BASELINE and has_submetering:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                f"Only {hours} hours of monitored data. Extend to at least "
                f"{self.MIN_READINGS_FOR_MONITORING} hours for full compliance."
            )
        elif hours >= self.MIN_READINGS_FOR_BASELINE:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                "Sub-metering for IT, cooling, and lighting loads is missing. "
                "Deploy granular metering to support a complete monitoring plan."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "Insufficient monitoring data and no sub-metering detected. "
                "Implement a comprehensive energy monitoring plan with granular metering."
            )

        return ComplianceCheck(
            check_id="ISO50001-003",
            name="Monitoring and Measurement Plan",
            description=(
                "A plan for monitoring, measurement, and analysis of energy "
                "performance must be defined and implemented (Clause 4.6.1)."
            ),
            status=status,
            current_value=(
                f"{hours} hours monitored; "
                f"sub-metering {'detected' if has_submetering else 'not detected'}"
            ),
            required_value=(
                f">= {self.MIN_READINGS_FOR_MONITORING} hours with IT/cooling sub-metering"
            ),
            recommendation=recommendation,
        )

    def _check_targets_set(self, result: AuditResult) -> ComplianceCheck:
        """Clause 4.4.6 — Energy objectives and targets must be established."""
        dc = result.data_center
        has_pue_target = dc.config.pue_target > 1.0
        has_renewable_target = dc.config.renewable_percentage > 0

        if has_pue_target and has_renewable_target:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif has_pue_target or has_renewable_target:
            status = ComplianceStatus.PARTIAL
            missing = []
            if not has_pue_target:
                missing.append("PUE target")
            if not has_renewable_target:
                missing.append("renewable energy target")
            recommendation = (
                f"Missing targets: {', '.join(missing)}. Set quantifiable "
                "energy objectives consistent with the energy policy."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "No energy targets detected. Establish measurable objectives "
                "for PUE improvement, renewable procurement, and energy reduction."
            )

        return ComplianceCheck(
            check_id="ISO50001-004",
            name="Energy Objectives and Targets",
            description=(
                "Measurable energy objectives and targets must be established "
                "at relevant functions and levels (Clause 4.4.6)."
            ),
            status=status,
            current_value=(
                f"PUE target: {dc.config.pue_target:.2f}; "
                f"renewable target: {dc.config.renewable_percentage:.0%}"
            ),
            required_value="Quantifiable PUE and renewable energy targets set",
            recommendation=recommendation,
        )

    def _check_management_review(self, result: AuditResult) -> ComplianceCheck:
        """Clause 4.7 — Management review evidence.

        We infer management engagement from the presence of a non-trivial
        executive summary (indicating leadership reporting is in place).
        """
        summary = result.executive_summary.strip()

        if len(summary) >= 100:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif len(summary) > 0:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                "Executive summary is minimal. Ensure regular management reviews "
                "cover energy performance, policy compliance, and improvement actions."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "No evidence of management review. Schedule regular reviews "
                "covering energy performance, EnPI trends, and action status."
            )

        return ComplianceCheck(
            check_id="ISO50001-005",
            name="Management Review",
            description=(
                "Top management must review the EnMS at planned intervals to "
                "ensure its continuing suitability and effectiveness (Clause 4.7)."
            ),
            status=status,
            current_value=(
                f"Executive summary: {len(summary)} chars"
            ),
            required_value="Regular management review with documented outputs",
            recommendation=recommendation,
        )

    def _check_continual_improvement(self, result: AuditResult) -> ComplianceCheck:
        """Clause 4.7.3 — Evidence of continual improvement.

        We evaluate whether recommendations exist and quantify potential
        savings, indicating an improvement pipeline is in place.
        """
        recs = result.recommendations
        total_savings_kwh = sum(r.monthly_energy_savings_kwh for r in recs)
        dc = result.data_center
        monthly_energy = dc.total_energy_kwh / max(len(dc.energy_readings) / 720, 1)

        improvement_pct = 0.0
        if monthly_energy > 0:
            improvement_pct = (total_savings_kwh / monthly_energy) * 100

        if len(recs) >= 3 and improvement_pct >= self.MIN_IMPROVEMENT_TARGET_PCT:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif len(recs) >= 1:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                f"Identified {len(recs)} improvement actions with "
                f"{improvement_pct:.1f}% potential savings. Aim for at least "
                f"{self.MIN_IMPROVEMENT_TARGET_PCT}% annual improvement."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "No improvement actions identified. Conduct an energy review "
                "and develop action plans for continual energy performance improvement."
            )

        return ComplianceCheck(
            check_id="ISO50001-006",
            name="Continual Improvement Evidence",
            description=(
                "The organisation must continually improve energy performance "
                "and the EnMS (Clause 4.7.3)."
            ),
            status=status,
            current_value=(
                f"{len(recs)} actions; {improvement_pct:.1f}% potential savings"
            ),
            required_value=(
                f">= 3 actions with >= {self.MIN_IMPROVEMENT_TARGET_PCT}% improvement"
            ),
            recommendation=recommendation,
        )

    def _check_operational_control(self, result: AuditResult) -> ComplianceCheck:
        """Clause 4.5.5 — Operational control of significant energy uses.

        Assessed by checking whether zombie and overprovisioned servers
        (wasteful operational states) are kept to a minimum.
        """
        dc = result.data_center
        total = len(dc.servers)
        if total == 0:
            return ComplianceCheck(
                check_id="ISO50001-007",
                name="Operational Control",
                description="Operational control of significant energy uses.",
                status=ComplianceStatus.NOT_APPLICABLE,
                current_value="N/A",
                required_value="< 5% zombie/overprovisioned servers",
                recommendation="No server data available for assessment.",
            )

        zombies = sum(1 for s in dc.servers if s.is_zombie)
        overprov = sum(1 for s in dc.servers if s.is_overprovisioned)
        waste_pct = ((zombies + overprov) / total) * 100

        if waste_pct <= 5.0:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif waste_pct <= 15.0:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                f"{waste_pct:.1f}% of servers are zombie or overprovisioned. "
                "Implement automated rightsizing and decommission idle assets."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                f"{waste_pct:.1f}% of servers are zombie or overprovisioned, "
                "indicating poor operational control. Establish policies for "
                "regular capacity reviews and automated idle-server shutdown."
            )

        return ComplianceCheck(
            check_id="ISO50001-007",
            name="Operational Control",
            description=(
                "Operational criteria and controls must be established for "
                "significant energy uses to prevent energy waste (Clause 4.5.5)."
            ),
            status=status,
            current_value=(
                f"{zombies} zombies + {overprov} overprovisioned "
                f"= {waste_pct:.1f}% of {total} servers"
            ),
            required_value="< 5% zombie/overprovisioned servers",
            recommendation=recommendation,
        )
