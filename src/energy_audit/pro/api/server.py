# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""FastAPI application factory for the energy audit REST API."""

from __future__ import annotations

from energy_audit.pro import check_dependency

check_dependency("fastapi", "pip install -e '.[pro-api]'")

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from energy_audit.pro.api.routes import router  # noqa: E402


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns
    -------
    FastAPI
        A fully configured application instance with CORS middleware
        and all API routes included.
    """
    app = FastAPI(
        title="Energy Audit API",
        description=(
            "REST API for AI data-center energy assessments. "
            "Run audits, check regulatory compliance, and retrieve "
            "scored results programmatically."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — allow all origins for development; tighten in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app
