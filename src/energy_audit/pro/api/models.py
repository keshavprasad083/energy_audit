# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""API request/response Pydantic models for the REST interface."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class AuditRequest(BaseModel):
    """Request body for the ``POST /api/v1/audit`` endpoint."""

    config_path: str | None = Field(
        default=None,
        description="Path to a pro YAML config file on the server filesystem.",
    )
    inline_config: dict[str, Any] | None = Field(
        default=None,
        description="Inline configuration dict (alternative to config_path).",
    )
    profile: str = Field(
        default="medium_enterprise",
        description="Simulated data-center profile when no real config is supplied.",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed for reproducible simulated data generation.",
    )


class ComplianceRequest(BaseModel):
    """Request body for the ``POST /api/v1/compliance`` endpoint."""

    config_path: str = Field(
        ...,
        description="Path to the pro YAML config file to audit for compliance.",
    )
    framework: Literal["eu-eed", "iso-50001", "sec-climate"] = Field(
        ...,
        description="Regulatory compliance framework to check against.",
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class AuditResponse(BaseModel):
    """Response body returned by the ``POST /api/v1/audit`` endpoint."""

    overall_score: float = Field(
        ..., ge=0, le=100, description="Weighted overall audit score (0-100)."
    )
    overall_grade: str = Field(
        ..., description="Overall letter grade (A-F)."
    )
    box1_score: float = Field(
        ..., ge=0, le=100, description="Box 1: Current Operations score."
    )
    box2_score: float = Field(
        ..., ge=0, le=100, description="Box 2: Legacy & Waste score."
    )
    box3_score: float = Field(
        ..., ge=0, le=100, description="Box 3: Future Readiness score."
    )
    server_count: int = Field(
        ..., ge=0, description="Number of servers in the audited facility."
    )
    pue: float = Field(
        ..., ge=0, description="Average Power Usage Effectiveness."
    )
    recommendation_count: int = Field(
        ..., ge=0, description="Number of recommendations generated."
    )
    executive_summary: str = Field(
        ..., description="Executive summary suitable for leadership review."
    )


class ComplianceResponse(BaseModel):
    """Response body returned by the ``POST /api/v1/compliance`` endpoint."""

    framework: str = Field(
        ..., description="Compliance framework that was evaluated."
    )
    compliance_percentage: float = Field(
        ..., ge=0, le=100, description="Overall compliance percentage."
    )
    compliant_count: int = Field(
        ..., ge=0, description="Number of checks that passed."
    )
    total_checks: int = Field(
        ..., ge=0, description="Total number of compliance checks executed."
    )
    checks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Individual compliance check results.",
    )


class HealthResponse(BaseModel):
    """Response body returned by the ``GET /api/v1/health`` endpoint."""

    status: str = Field(
        ..., description="Service health status (e.g. 'ok')."
    )
    version: str = Field(
        ..., description="Application version string."
    )
    pro_available: bool = Field(
        ..., description="Whether the Pro module is installed and available."
    )
