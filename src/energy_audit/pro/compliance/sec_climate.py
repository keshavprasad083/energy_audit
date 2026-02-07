# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""SEC Climate Disclosure compliance assessment.

Evaluates a data-center audit result against the SEC's climate-related
disclosure rules, focusing on greenhouse gas emissions (Scope 1 & 2),
energy consumption reporting, climate risk assessment, and transition
planning.
"""

from __future__ import annotations

from datetime import datetime, timezone

from energy_audit.data.models import AuditResult
from energy_audit.pro.compliance import (
    ComplianceCheck,
    ComplianceReport,
    ComplianceStatus,
)


class SECClimateCompliance:
    """Assess an :class:`AuditResult` against SEC climate disclosure rules."""

    FRAMEWORK_NAME = "SEC Climate-Related Disclosure"
    FRAMEWORK_VERSION = "Final Rule S7-10-22 (2024)"

    # Constants for emission estimation -----------------------------------
    # Scope 1: on-site combustion (e.g. backup diesel generators)
    # Estimated as a fraction of total facility power for facilities with
    # natural_gas or mixed energy sources.
    SCOPE1_GENERATOR_EMISSION_FACTOR = 0.25  # kg CO2 per kWh (diesel)

    # Scope 2: purchased electricity
    # Uses the grid carbon intensity from the data-center config.

    def assess(self, result: AuditResult) -> ComplianceReport:
        """Run all SEC climate disclosure checks and return a report."""
        checks: list[ComplianceCheck] = [
            self._check_scope1_emissions(result),
            self._check_scope2_emissions(result),
            self._check_energy_consumption_disclosed(result),
            self._check_climate_risk_assessment(result),
            self._check_transition_plan(result),
            self._check_governance_oversight(result),
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
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_annual_energy_kwh(result: AuditResult) -> float:
        """Extrapolate annual energy from the readings window."""
        dc = result.data_center
        readings = dc.energy_readings
        if not readings:
            return 0.0
        total_kwh = sum(r.total_facility_power_kw for r in readings)
        hours = len(readings)
        return (total_kwh / hours) * 8760 if hours > 0 else 0.0

    @staticmethod
    def _estimate_scope2_tonnes(result: AuditResult) -> float:
        """Estimate Scope 2 emissions (purchased electricity) in tonnes CO2.

        Scope 2 = annual energy (kWh) * grid carbon intensity (gCO2/kWh) / 1e6
        """
        dc = result.data_center
        readings = dc.energy_readings
        if not readings:
            return 0.0
        avg_power_kw = (
            sum(r.total_facility_power_kw for r in readings) / len(readings)
        )
        annual_kwh = avg_power_kw * 8760
        intensity = dc.config.carbon_intensity_gco2_per_kwh
        return round(annual_kwh * intensity / 1_000_000, 2)

    def _estimate_scope1_tonnes(self, result: AuditResult) -> float:
        """Estimate Scope 1 emissions (on-site combustion) in tonnes CO2.

        For facilities using natural gas or mixed sources we assume 5 % of
        total energy comes from on-site backup generators / gas turbines.
        """
        dc = result.data_center
        source = dc.config.energy_source.lower()
        if source not in ("natural_gas", "mixed"):
            return 0.0

        annual_kwh = self._estimate_annual_energy_kwh(result)
        # Assume 5 % of energy from on-site combustion
        onsite_kwh = annual_kwh * 0.05
        return round(onsite_kwh * self.SCOPE1_GENERATOR_EMISSION_FACTOR / 1000, 2)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_scope1_emissions(self, result: AuditResult) -> ComplianceCheck:
        """Scope 1 (direct) GHG emissions must be calculated and disclosed."""
        scope1 = self._estimate_scope1_tonnes(result)
        source = result.data_center.config.energy_source.lower()

        if source in ("natural_gas", "mixed"):
            if scope1 > 0:
                status = ComplianceStatus.COMPLIANT
                recommendation = ""
            else:
                status = ComplianceStatus.NON_COMPLIANT
                recommendation = (
                    "On-site combustion sources detected but Scope 1 emissions "
                    "could not be estimated. Meter fuel consumption for generators "
                    "and apply EPA emission factors."
                )
        else:
            # Grid-only or renewables — Scope 1 is likely zero/negligible
            status = ComplianceStatus.COMPLIANT
            recommendation = ""

        return ComplianceCheck(
            check_id="SEC-CLIMATE-001",
            name="Scope 1 GHG Emissions",
            description=(
                "Direct greenhouse gas emissions from sources owned or controlled "
                "by the registrant must be calculated and disclosed."
            ),
            status=status,
            current_value=(
                f"{scope1:,.1f} tonnes CO2/yr"
                if scope1 > 0
                else "Negligible (no on-site combustion)"
            ),
            required_value="Scope 1 emissions calculated and disclosed",
            recommendation=recommendation,
        )

    def _check_scope2_emissions(self, result: AuditResult) -> ComplianceCheck:
        """Scope 2 (indirect — purchased electricity) emissions must be disclosed."""
        scope2 = self._estimate_scope2_tonnes(result)
        intensity = result.data_center.config.carbon_intensity_gco2_per_kwh
        readings = result.data_center.energy_readings

        if not readings:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "No energy data available to calculate Scope 2 emissions. "
                "Deploy energy metering and obtain grid emission factors."
            )
        elif intensity <= 0:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                "Energy data available but grid carbon intensity is not set. "
                "Obtain location-based emission factors from the grid operator."
            )
        elif scope2 > 0:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        else:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                "Scope 2 estimate is zero despite having energy data. "
                "Verify carbon intensity and energy readings."
            )

        return ComplianceCheck(
            check_id="SEC-CLIMATE-002",
            name="Scope 2 GHG Emissions",
            description=(
                "Indirect greenhouse gas emissions from purchased electricity "
                "must be calculated using location-based or market-based methods."
            ),
            status=status,
            current_value=(
                f"{scope2:,.1f} tonnes CO2/yr"
                if scope2 > 0
                else "Not calculated"
            ),
            required_value="Scope 2 emissions calculated and disclosed",
            recommendation=recommendation,
        )

    def _check_energy_consumption_disclosed(self, result: AuditResult) -> ComplianceCheck:
        """Total energy consumption must be disclosed."""
        annual_kwh = self._estimate_annual_energy_kwh(result)
        annual_mwh = annual_kwh / 1000
        readings = result.data_center.energy_readings

        if len(readings) >= 720 and annual_kwh > 0:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif len(readings) >= 168 and annual_kwh > 0:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                f"Only {len(readings)} hours of data available. Full annual "
                "disclosure requires at least 30 days for reliable extrapolation."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "Insufficient energy data for disclosure. Implement metering "
                "and collect at least 30 days of continuous data."
            )

        return ComplianceCheck(
            check_id="SEC-CLIMATE-003",
            name="Energy Consumption Disclosure",
            description=(
                "Total energy consumed, disaggregated by source, must be "
                "disclosed in SEC filings."
            ),
            status=status,
            current_value=(
                f"{annual_mwh:,.0f} MWh/yr (estimated)"
                if annual_kwh > 0
                else "Not available"
            ),
            required_value="Annual energy consumption disclosed",
            recommendation=recommendation,
        )

    def _check_climate_risk_assessment(self, result: AuditResult) -> ComplianceCheck:
        """Climate-related risks and their financial impact must be assessed.

        We infer risk assessment readiness from:
        - Availability of carbon data (emissions quantified)
        - Renewable energy strategy (mitigation in progress)
        - Energy cost data (financial impact measurable)
        """
        dc = result.data_center
        has_carbon = dc.config.carbon_intensity_gco2_per_kwh > 0
        has_renewable_strategy = dc.config.renewable_percentage > 0 or dc.config.ppa_available
        has_cost_data = dc.config.energy_cost_per_kwh > 0

        factors_met = sum([has_carbon, has_renewable_strategy, has_cost_data])

        if factors_met == 3:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif factors_met >= 1:
            status = ComplianceStatus.PARTIAL
            missing = []
            if not has_carbon:
                missing.append("grid carbon intensity data")
            if not has_renewable_strategy:
                missing.append("renewable energy / PPA strategy")
            if not has_cost_data:
                missing.append("energy cost data for financial impact")
            recommendation = (
                f"Missing risk assessment inputs: {', '.join(missing)}. "
                "Complete these to enable full climate risk disclosure."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "No climate risk inputs available. Assess physical risks "
                "(extreme weather, cooling costs) and transition risks "
                "(carbon pricing, regulatory changes)."
            )

        return ComplianceCheck(
            check_id="SEC-CLIMATE-004",
            name="Climate Risk Assessment",
            description=(
                "Material climate-related risks, their actual or likely "
                "financial impacts, and the registrant's risk management "
                "processes must be disclosed."
            ),
            status=status,
            current_value=f"{factors_met}/3 risk assessment factors available",
            required_value="Carbon, mitigation strategy, and financial impact assessed",
            recommendation=recommendation,
        )

    def _check_transition_plan(self, result: AuditResult) -> ComplianceCheck:
        """A climate transition plan must be in place if material risks exist.

        We assess transition readiness through:
        - Renewable energy percentage (decarbonisation pathway)
        - Energy efficiency improvements (PUE trend toward best practice)
        - Actionable recommendations (improvement pipeline)
        """
        dc = result.data_center
        renewable = dc.config.renewable_percentage
        pue = dc.avg_pue
        recs = result.recommendations

        transition_score = 0
        if renewable >= 0.50:
            transition_score += 1
        if 0 < pue <= 1.4:
            transition_score += 1
        if len(recs) >= 3:
            transition_score += 1

        if transition_score == 3:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif transition_score >= 1:
            status = ComplianceStatus.PARTIAL
            gaps = []
            if renewable < 0.50:
                gaps.append(f"renewable share is {renewable:.0%} (target >= 50%)")
            if pue <= 0 or pue > 1.4:
                gaps.append(f"PUE of {pue:.3f} exceeds best-practice threshold")
            if len(recs) < 3:
                gaps.append("fewer than 3 actionable improvement items")
            recommendation = (
                "Transition plan gaps: " + "; ".join(gaps) + ". "
                "Develop a roadmap with milestones for decarbonisation."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "No evidence of a climate transition plan. Develop a "
                "time-bound roadmap covering renewable procurement, efficiency "
                "targets, and emission reduction milestones."
            )

        return ComplianceCheck(
            check_id="SEC-CLIMATE-005",
            name="Climate Transition Plan",
            description=(
                "If the registrant has adopted a transition plan for managing "
                "climate-related risks, it must be disclosed."
            ),
            status=status,
            current_value=(
                f"Renewable: {renewable:.0%}; PUE: {pue:.3f}; "
                f"Actions: {len(recs)}"
            ),
            required_value="Transition plan with renewable, efficiency, and reduction targets",
            recommendation=recommendation,
        )

    def _check_governance_oversight(self, result: AuditResult) -> ComplianceCheck:
        """Board/management oversight of climate-related risks must be disclosed.

        Inferred from the quality of reporting outputs — an executive summary
        and scored audit indicate governance mechanisms are in place.
        """
        has_summary = len(result.executive_summary.strip()) >= 50
        has_scoring = result.overall_score > 0
        has_recs = len(result.recommendations) > 0

        evidence = sum([has_summary, has_scoring, has_recs])

        if evidence == 3:
            status = ComplianceStatus.COMPLIANT
            recommendation = ""
        elif evidence >= 1:
            status = ComplianceStatus.PARTIAL
            recommendation = (
                "Some governance evidence exists but may be incomplete. "
                "Ensure board-level reporting on climate risks, energy audits, "
                "and sustainability targets is formalised."
            )
        else:
            status = ComplianceStatus.NON_COMPLIANT
            recommendation = (
                "No evidence of governance oversight of climate-related risks. "
                "Establish board/committee responsibility for climate strategy, "
                "regular reporting, and target-setting."
            )

        return ComplianceCheck(
            check_id="SEC-CLIMATE-006",
            name="Governance and Oversight",
            description=(
                "The registrant must describe the board's oversight and "
                "management's role in assessing and managing climate-related risks."
            ),
            status=status,
            current_value=f"{evidence}/3 governance indicators present",
            required_value="Executive summary, scored audit, and improvement actions",
            recommendation=recommendation,
        )
