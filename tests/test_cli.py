# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Tests for the CLI layer using Click's CliRunner."""

from __future__ import annotations

from click.testing import CliRunner

from energy_audit.cli.app import cli


class TestCLI:
    """Tests for CLI commands."""

    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "energy-audit" in result.output

    def test_run_default(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "-p", "medium_enterprise", "-s", "42"])
        assert result.exit_code == 0
        assert "OVERALL SCORE" in result.output
        assert "BOX 1" in result.output

    def test_run_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "--profile" in result.output

    def test_present_command(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["present", "-p", "small_startup", "-s", "42"])
        assert result.exit_code == 0
        assert "BOX 1" in result.output

    def test_forget_command(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["forget", "-p", "small_startup", "-s", "42"])
        assert result.exit_code == 0
        assert "BOX 2" in result.output

    def test_future_command(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["future", "-p", "small_startup", "-s", "42"])
        assert result.exit_code == 0
        assert "BOX 3" in result.output

    def test_dashboard_command(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["dashboard", "-p", "small_startup", "-s", "42"])
        assert result.exit_code == 0
        assert "OVERALL SCORE" in result.output

    def test_no_branding_in_output(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "-p", "medium_enterprise", "-s", "42"])
        assert "Govindarajan" not in result.output
        assert "3-Box Strategy" not in result.output
