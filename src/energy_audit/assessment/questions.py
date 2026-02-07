# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""35-question bank for the interactive energy maturity assessment.

Questions are organized by pillar:
  - Box 1: Current Operations (10 questions, weights sum to 1.0)
  - Box 2: Legacy & Waste (10 questions, weights sum to 1.0)
  - Box 3: Future Readiness (10 questions, weights sum to 1.0)
  - Organizational & Bias Detection (5 questions, weights sum to 1.0)

Each question has exactly 5 options scored 0/25/50/75/100.
"""

from __future__ import annotations

from energy_audit.assessment.models import AnswerOption, Pillar, Question


def _opts(labels: list[str]) -> list[AnswerOption]:
    """Build 5 AnswerOptions from labels, scored 0/25/50/75/100."""
    scores = [0, 25, 50, 75, 100]
    return [AnswerOption(label=lbl, score=s) for lbl, s in zip(labels, scores)]


# =========================================================================
# Box 1 — Current Operations (10 questions)
# =========================================================================

BOX1_QUESTIONS: list[Question] = [
    Question(
        id="b1_q01",
        pillar=Pillar.BOX1,
        topic="Energy Monitoring",
        text="How comprehensive is your facility's energy monitoring infrastructure?",
        weight=0.12,
        options=_opts([
            "No energy monitoring in place",
            "Basic utility-level metering only",
            "Per-zone or per-PDU metering with monthly reviews",
            "Server-level monitoring with weekly dashboards",
            "Real-time per-server monitoring with automated alerting and analytics",
        ]),
        related_question_id="b1_q09",
    ),
    Question(
        id="b1_q02",
        pillar=Pillar.BOX1,
        topic="PUE Tracking",
        text="How do you track and manage your Power Usage Effectiveness (PUE)?",
        weight=0.12,
        options=_opts([
            "We don't track PUE",
            "Annual PUE calculation from utility bills",
            "Monthly PUE tracking with targets set",
            "Continuous PUE monitoring with trend analysis",
            "Real-time PUE optimization with sub-1.3 target and automated adjustments",
        ]),
        bias_indicator=True,
    ),
    Question(
        id="b1_q03",
        pillar=Pillar.BOX1,
        topic="Utilization Awareness",
        text="How well do you understand and manage server utilization across your fleet?",
        weight=0.12,
        options=_opts([
            "No visibility into server utilization",
            "Spot checks on individual servers when issues arise",
            "Monthly utilization reports for major clusters",
            "Continuous monitoring with utilization targets per workload type",
            "AI-driven workload placement optimizing utilization fleet-wide",
        ]),
        related_question_id="b2_q04",
    ),
    Question(
        id="b1_q04",
        pillar=Pillar.BOX1,
        topic="Cooling Management",
        text="How mature is your cooling management strategy?",
        weight=0.10,
        options=_opts([
            "Fixed cooling settings with no adjustment",
            "Seasonal adjustments based on outside temperature",
            "Hot/cold aisle containment with temperature monitoring",
            "Dynamic cooling control based on real-time thermal data",
            "Liquid cooling for high-density racks with predictive thermal management",
        ]),
        related_question_id="b2_q09",
    ),
    Question(
        id="b1_q05",
        pillar=Pillar.BOX1,
        topic="Power Budgeting",
        text="How do you manage power capacity and allocation?",
        weight=0.10,
        options=_opts([
            "No formal power budgeting",
            "Rough estimates based on nameplate ratings",
            "Per-rack power budgets reviewed quarterly",
            "Dynamic power capping with alerts at 80% threshold",
            "Predictive power modeling integrated with capacity planning",
        ]),
    ),
    Question(
        id="b1_q06",
        pillar=Pillar.BOX1,
        topic="Cost Visibility",
        text="How granular is your understanding of energy costs?",
        weight=0.10,
        options=_opts([
            "Only total facility electricity bill",
            "Cost broken down by major systems (IT vs cooling vs lighting)",
            "Per-department or per-team cost allocation",
            "Per-application cost modeling with chargeback",
            "Real-time cost-per-workload dashboards with optimization recommendations",
        ]),
        bias_indicator=True,
    ),
    Question(
        id="b1_q07",
        pillar=Pillar.BOX1,
        topic="Incident Response",
        text="How do you handle energy-related incidents (outages, overcapacity events)?",
        weight=0.08,
        options=_opts([
            "Reactive response only when systems fail",
            "Basic runbooks for common power issues",
            "Documented escalation procedures with post-incident reviews",
            "Proactive alerting with automated failover for power events",
            "Predictive incident prevention with self-healing infrastructure",
        ]),
    ),
    Question(
        id="b1_q08",
        pillar=Pillar.BOX1,
        topic="Environmental Monitoring",
        text="How do you monitor environmental conditions (temperature, humidity)?",
        weight=0.08,
        options=_opts([
            "No environmental sensors deployed",
            "Room-level temperature checks during walkthroughs",
            "Per-row sensor arrays with threshold alerts",
            "Dense sensor grid with trend analysis and zone mapping",
            "Digital twin with real-time CFD modeling and automated response",
        ]),
    ),
    Question(
        id="b1_q09",
        pillar=Pillar.BOX1,
        topic="Metering Calibration",
        text="How do you ensure the accuracy of your energy measurements?",
        weight=0.08,
        options=_opts([
            "No calibration program",
            "Utility meter only — rely on provider accuracy",
            "Annual calibration of main meters",
            "Quarterly calibration with cross-reference between meters",
            "Continuous validation with redundant measurement and drift detection",
        ]),
        related_question_id="b1_q01",
    ),
    Question(
        id="b1_q10",
        pillar=Pillar.BOX1,
        topic="Efficiency KPIs",
        text="How do you track and act on energy efficiency key performance indicators?",
        weight=0.10,
        options=_opts([
            "No formal KPIs defined",
            "PUE tracked but no action plan tied to it",
            "Multiple KPIs tracked (PUE, WUE, CUE) with quarterly reviews",
            "KPI dashboards with automated trend alerts and improvement targets",
            "KPIs embedded in team objectives with continuous improvement cycles",
        ]),
        bias_indicator=True,
    ),
]

# =========================================================================
# Box 2 — Legacy & Waste (10 questions)
# =========================================================================

BOX2_QUESTIONS: list[Question] = [
    Question(
        id="b2_q01",
        pillar=Pillar.BOX2,
        topic="Decommissioning Process",
        text="How structured is your hardware decommissioning process?",
        weight=0.12,
        options=_opts([
            "No formal decommissioning process",
            "Ad-hoc removal when racks are full",
            "Annual decommissioning review with asset list",
            "Quarterly lifecycle reviews with automated decommission triggers",
            "Continuous lifecycle management with automated workflows and ITAM integration",
        ]),
        related_question_id="b2_q02",
        bias_indicator=True,
    ),
    Question(
        id="b2_q02",
        pillar=Pillar.BOX2,
        topic="Zombie Audit Frequency",
        text="How often do you identify and remediate idle (zombie) servers?",
        weight=0.12,
        options=_opts([
            "Never — we don't look for zombies",
            "Only when someone complains about capacity",
            "Semi-annual zombie audits",
            "Monthly automated scans with owner notification",
            "Continuous monitoring with auto-flagging and 30-day reclaim policy",
        ]),
        related_question_id="b2_q01",
    ),
    Question(
        id="b2_q03",
        pillar=Pillar.BOX2,
        topic="Warranty Tracking",
        text="How do you track hardware warranty status across your fleet?",
        weight=0.08,
        options=_opts([
            "No warranty tracking",
            "Spreadsheet updated when issues arise",
            "CMDB with warranty dates but no automated alerts",
            "Automated alerts 90 days before warranty expiration",
            "Integrated lifecycle management with warranty, refresh, and budget planning",
        ]),
    ),
    Question(
        id="b2_q04",
        pillar=Pillar.BOX2,
        topic="VM Right-Sizing",
        text="How do you ensure virtual machines and containers are right-sized?",
        weight=0.12,
        options=_opts([
            "No right-sizing practices",
            "Manual review when performance issues occur",
            "Quarterly right-sizing reports from monitoring tools",
            "Automated recommendations with one-click resize",
            "Continuous auto-scaling with ML-based demand prediction",
        ]),
        related_question_id="b1_q03",
    ),
    Question(
        id="b2_q05",
        pillar=Pillar.BOX2,
        topic="Stranded Capacity",
        text="How do you manage stranded (allocated but unused) capacity?",
        weight=0.10,
        options=_opts([
            "No visibility into stranded capacity",
            "Aware of the problem but no measurement",
            "Annual capacity audit identifies stranded resources",
            "Automated detection with reclamation workflows",
            "Real-time capacity marketplace with dynamic reallocation",
        ]),
        bias_indicator=True,
    ),
    Question(
        id="b2_q06",
        pillar=Pillar.BOX2,
        topic="Technical Debt Awareness",
        text="How aware are you of infrastructure technical debt and its energy impact?",
        weight=0.08,
        options=_opts([
            "No concept of infrastructure technical debt",
            "Aware of aging systems but no quantification",
            "Technical debt register with energy impact estimates",
            "Quantified debt with prioritized remediation roadmap",
            "Continuous debt measurement integrated into planning and budgeting",
        ]),
    ),
    Question(
        id="b2_q07",
        pillar=Pillar.BOX2,
        topic="Legacy Refresh Triggers",
        text="What triggers a hardware refresh decision?",
        weight=0.10,
        options=_opts([
            "Hardware runs until it fails",
            "Refresh when vendor ends support",
            "Fixed refresh cycles (e.g. every 5 years)",
            "TCO-based refresh with energy efficiency analysis",
            "Predictive analytics drive refresh timing based on efficiency degradation",
        ]),
    ),
    Question(
        id="b2_q08",
        pillar=Pillar.BOX2,
        topic="Data Retention Policies",
        text="How do data retention policies impact your storage energy usage?",
        weight=0.08,
        options=_opts([
            "No formal data retention policies",
            "Policies exist but are not enforced",
            "Enforced retention with annual storage audits",
            "Automated tiering and archival based on access patterns",
            "AI-driven lifecycle management with energy-aware data placement",
        ]),
    ),
    Question(
        id="b2_q09",
        pillar=Pillar.BOX2,
        topic="Cooling Modernization",
        text="How proactively do you modernize cooling for legacy areas?",
        weight=0.10,
        options=_opts([
            "Legacy cooling unchanged since installation",
            "Minimal fixes when cooling failures occur",
            "Planned upgrades for worst-performing zones",
            "Rolling modernization program with ROI tracking",
            "Cutting-edge cooling deployed as part of continuous facility optimization",
        ]),
        related_question_id="b1_q04",
    ),
    Question(
        id="b2_q10",
        pillar=Pillar.BOX2,
        topic="Asset Lifecycle System",
        text="How mature is your IT asset management (ITAM) system?",
        weight=0.10,
        options=_opts([
            "No ITAM system — relying on tribal knowledge",
            "Spreadsheet-based asset tracking",
            "CMDB with basic asset records and manual updates",
            "Integrated ITAM with automated discovery and lifecycle tracking",
            "Full ITAM/DCIM integration with real-time inventory and energy correlation",
        ]),
        bias_indicator=True,
    ),
]

# =========================================================================
# Box 3 — Future Readiness (10 questions)
# =========================================================================

BOX3_QUESTIONS: list[Question] = [
    Question(
        id="b3_q01",
        pillar=Pillar.BOX3,
        topic="Capacity Forecasting",
        text="How do you forecast future capacity and energy needs?",
        weight=0.12,
        options=_opts([
            "No forecasting — react to shortages as they happen",
            "Annual budget estimates based on historical growth",
            "Quarterly rolling forecasts with business input",
            "Scenario-based modeling with multiple growth projections",
            "ML-driven forecasting integrated with business planning and procurement",
        ]),
        bias_indicator=True,
    ),
    Question(
        id="b3_q02",
        pillar=Pillar.BOX3,
        topic="Hardware Refresh Policy",
        text="How does your hardware refresh policy consider energy efficiency?",
        weight=0.10,
        options=_opts([
            "Energy efficiency not considered in refresh decisions",
            "Energy efficiency is a secondary factor after cost",
            "TCO analysis includes energy costs in refresh planning",
            "Energy efficiency targets drive refresh priorities",
            "Continuous fleet optimization with energy as a primary constraint",
        ]),
        related_question_id="b2_q07",
    ),
    Question(
        id="b3_q03",
        pillar=Pillar.BOX3,
        topic="Renewable Energy Commitment",
        text="What is your facility's renewable energy strategy?",
        weight=0.12,
        options=_opts([
            "No renewable energy plans",
            "Purchasing RECs or carbon offsets",
            "On-site renewable generation covers <25% of demand",
            "PPAs or on-site renewables covering 25-75% of demand",
            "100% renewable target achieved or contracted with 24/7 matching",
        ]),
    ),
    Question(
        id="b3_q04",
        pillar=Pillar.BOX3,
        topic="Workload Scheduling",
        text="How do you optimize workload scheduling for energy efficiency?",
        weight=0.10,
        options=_opts([
            "No energy-aware scheduling",
            "Manual scheduling to avoid peak hours",
            "Time-of-use optimization for batch workloads",
            "Carbon-aware scheduling shifting loads to low-carbon periods",
            "AI-orchestrated scheduling optimizing across energy, carbon, and cost",
        ]),
    ),
    Question(
        id="b3_q05",
        pillar=Pillar.BOX3,
        topic="Sustainability Reporting",
        text="How mature is your sustainability reporting and disclosure?",
        weight=0.08,
        options=_opts([
            "No sustainability reporting",
            "Basic energy usage reported in annual report",
            "GHG inventory (Scope 1 and 2) published annually",
            "Full GHG reporting (Scope 1-3) with science-based targets",
            "TCFD/CDP-aligned reporting with verified data and reduction trajectory",
        ]),
        bias_indicator=True,
    ),
    Question(
        id="b3_q06",
        pillar=Pillar.BOX3,
        topic="Innovation Adoption",
        text="How quickly does your team evaluate and adopt new efficiency technologies?",
        weight=0.08,
        options=_opts([
            "No process for evaluating new technologies",
            "Evaluate when vendors approach us",
            "Annual technology review with pilot budget",
            "Dedicated innovation team with quarterly POC pipeline",
            "Continuous experimentation culture with rapid deployment for proven tech",
        ]),
    ),
    Question(
        id="b3_q07",
        pillar=Pillar.BOX3,
        topic="Cloud/Hybrid Strategy",
        text="How does your cloud/hybrid strategy consider energy efficiency?",
        weight=0.10,
        options=_opts([
            "No cloud strategy or energy not a factor",
            "Cloud used ad-hoc with no efficiency comparison",
            "Workload placement considers cloud provider PUE and regions",
            "Formal cloud-first policy with energy efficiency criteria",
            "Dynamic burst-to-cloud with real-time energy/cost optimization",
        ]),
    ),
    Question(
        id="b3_q08",
        pillar=Pillar.BOX3,
        topic="AI/ML Workload Planning",
        text="How prepared is your facility for growing AI/ML workload energy demands?",
        weight=0.10,
        options=_opts([
            "No planning for AI/ML energy demands",
            "Aware of growing demand but no specific plans",
            "Power and cooling assessments for GPU expansion",
            "Dedicated high-density zones with liquid cooling roadmap",
            "Purpose-built AI infrastructure with efficient training pipelines and inference optimization",
        ]),
    ),
    Question(
        id="b3_q09",
        pillar=Pillar.BOX3,
        topic="Regulatory Preparedness",
        text="How prepared are you for upcoming energy and sustainability regulations?",
        weight=0.10,
        options=_opts([
            "Not aware of upcoming regulations",
            "Aware but no preparation started",
            "Compliance gap analysis completed",
            "Remediation plan in progress with timeline",
            "Ahead of regulations with proactive compliance and policy engagement",
        ]),
    ),
    Question(
        id="b3_q10",
        pillar=Pillar.BOX3,
        topic="Workforce Training",
        text="How do you train your team on energy-efficient operations?",
        weight=0.10,
        options=_opts([
            "No energy-related training",
            "Informal knowledge sharing among team members",
            "Annual training sessions on efficiency best practices",
            "Structured training program with certifications",
            "Continuous learning culture with energy efficiency embedded in all roles",
        ]),
    ),
]

# =========================================================================
# Organizational & Bias Detection (5 questions)
# =========================================================================

ORG_QUESTIONS: list[Question] = [
    Question(
        id="org_q01",
        pillar=Pillar.ORG,
        topic="Change Management",
        text="How effective is your organization at implementing energy efficiency changes?",
        weight=0.20,
        options=_opts([
            "Changes are resisted and rarely implemented",
            "Changes happen only under executive mandate",
            "Formal change process but slow adoption",
            "Agile change management with stakeholder buy-in",
            "Culture of continuous improvement with bottom-up innovation",
        ]),
        bias_indicator=True,
    ),
    Question(
        id="org_q02",
        pillar=Pillar.ORG,
        topic="Cross-Team Collaboration",
        text="How well do facilities, IT, and finance teams collaborate on energy decisions?",
        weight=0.20,
        options=_opts([
            "Teams work in silos with no energy collaboration",
            "Occasional meetings when major decisions needed",
            "Regular cross-functional reviews (quarterly)",
            "Shared KPIs and joint planning sessions",
            "Integrated team structure with shared accountability for energy outcomes",
        ]),
    ),
    Question(
        id="org_q03",
        pillar=Pillar.ORG,
        topic="Executive Sponsorship",
        text="What level of executive sponsorship exists for energy efficiency initiatives?",
        weight=0.20,
        options=_opts([
            "No executive awareness of energy efficiency",
            "Executives aware but it's not a priority",
            "VP-level sponsor with allocated budget",
            "C-level champion with energy on the board agenda",
            "CEO-sponsored sustainability strategy with public commitments",
        ]),
        bias_indicator=True,
    ),
    Question(
        id="org_q04",
        pillar=Pillar.ORG,
        topic="Recommendation Follow-Through",
        text="What percentage of past energy audit recommendations have been implemented?",
        weight=0.20,
        options=_opts([
            "No previous audits or recommendations tracked",
            "Less than 25% of recommendations implemented",
            "25-50% implemented within 12 months",
            "50-75% implemented with documented outcomes",
            "Over 75% implemented with measured energy savings",
        ]),
        bias_indicator=True,
    ),
    Question(
        id="org_q05",
        pillar=Pillar.ORG,
        topic="Status Quo Resistance",
        text="How would you characterize your organization's attitude toward operational changes?",
        weight=0.20,
        options=_opts([
            "Strong preference for keeping things as they are",
            "Cautious — changes require extensive justification",
            "Open to change with proper business case",
            "Proactively seeking improvements",
            "Disruptive mindset — constantly questioning the status quo",
        ]),
        bias_indicator=True,
    ),
]

# =========================================================================
# Combined question list and lookup
# =========================================================================

ALL_QUESTIONS: list[Question] = BOX1_QUESTIONS + BOX2_QUESTIONS + BOX3_QUESTIONS + ORG_QUESTIONS

QUESTION_MAP: dict[str, Question] = {q.id: q for q in ALL_QUESTIONS}


def get_questions_by_pillar(pillar: Pillar) -> list[Question]:
    """Return all questions for a given pillar."""
    return [q for q in ALL_QUESTIONS if q.pillar == pillar]


def validate_weights() -> dict[Pillar, float]:
    """Validate that weights sum to 1.0 for each pillar. Returns pillar totals."""
    totals: dict[Pillar, float] = {}
    for pillar in Pillar:
        questions = get_questions_by_pillar(pillar)
        total = sum(q.weight for q in questions)
        totals[pillar] = round(total, 6)
    return totals
