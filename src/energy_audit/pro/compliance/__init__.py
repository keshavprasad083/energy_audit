# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Compliance framework mappings for regulatory reporting.

Provides shared models used by all compliance framework modules
(EU EED, ISO 50001, SEC Climate Disclosure, etc.).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ComplianceStatus(str, Enum):
    """Outcome of a single compliance check."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"


class ComplianceCheck(BaseModel):
    """A single pass/fail compliance check within a framework assessment."""

    check_id: str = Field(..., description="Unique identifier for this check")
    name: str = Field(..., description="Short human-readable check name")
    description: str = Field(
        ..., description="Detailed description of what the check evaluates"
    )
    status: ComplianceStatus = Field(
        ..., description="Result of the check"
    )
    current_value: str = Field(
        ..., description="The current measured or observed value"
    )
    required_value: str = Field(
        ..., description="The value required for full compliance"
    )
    recommendation: str = Field(
        default="",
        description="Actionable recommendation when the check is not fully compliant",
    )


class ComplianceReport(BaseModel):
    """Aggregated compliance report for a single regulatory framework."""

    framework_name: str = Field(
        ..., description="Name of the compliance framework"
    )
    framework_version: str = Field(
        ..., description="Version or revision of the framework"
    )
    assessed_at: datetime = Field(
        ..., description="UTC timestamp of the assessment"
    )
    checks: list[ComplianceCheck] = Field(
        default_factory=list, description="Individual check results"
    )
    compliant_count: int = Field(
        ..., ge=0, description="Number of checks that are fully compliant"
    )
    total_checks: int = Field(
        ..., ge=0, description="Total number of checks evaluated"
    )
    compliance_percentage: float = Field(
        ..., ge=0, le=100,
        description="Percentage of checks that are fully compliant",
    )
