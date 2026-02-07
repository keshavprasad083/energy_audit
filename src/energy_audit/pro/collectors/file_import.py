# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""CSV and JSON file import collector.

Reads exported monitoring data from CSV or JSON files and produces
a :class:`CollectorResult` that the mapper converts to a ``DataCenter``.
Uses only stdlib — no extra dependencies required.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from energy_audit.pro.collectors import register_collector
from energy_audit.pro.collectors.base import (
    CollectorResult,
    RawCoolingData,
    RawEnergyReading,
    RawServerData,
)
from energy_audit.pro.config import CollectorSourceConfig


class FileImportCollector:
    """Import server and energy data from CSV or JSON files."""

    def __init__(self, config: CollectorSourceConfig) -> None:
        self.config = config
        self.options = config.options
        self.endpoints = config.endpoints

    def collect(self) -> CollectorResult:
        """Read all configured files and merge into a single result."""
        servers: list[RawServerData] = []
        energy: list[RawEnergyReading] = []
        cooling: list[RawCoolingData] = []
        errors: list[str] = []
        warnings: list[str] = []

        for path_str in self.endpoints:
            path = Path(path_str).expanduser()
            if not path.exists():
                errors.append(f"File not found: {path}")
                continue

            try:
                if path.suffix.lower() == ".csv":
                    s, e, c = self._read_csv(path)
                elif path.suffix.lower() == ".json":
                    s, e, c = self._read_json(path)
                else:
                    errors.append(f"Unsupported file type: {path.suffix}")
                    continue
                servers.extend(s)
                energy.extend(e)
                cooling.extend(c)
            except Exception as exc:
                errors.append(f"Error reading {path}: {exc}")

        if not servers and not energy:
            warnings.append("No server or energy data found in any file")

        return CollectorResult(
            source_type=self.config.type,
            servers=servers,
            energy_readings=energy,
            cooling_data=cooling,
            errors=errors,
            warnings=warnings,
        )

    def discover(self) -> list[str]:
        """List configured file paths and their status."""
        results = []
        for path_str in self.endpoints:
            path = Path(path_str).expanduser()
            if path.exists():
                size = path.stat().st_size
                results.append(f"{path} ({size:,} bytes)")
            else:
                results.append(f"{path} (not found)")
        return results

    def test_connection(self) -> bool:
        """Check that at least one file exists."""
        return any(Path(p).expanduser().exists() for p in self.endpoints)

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------

    def _read_csv(
        self, path: Path
    ) -> tuple[list[RawServerData], list[RawEnergyReading], list[RawCoolingData]]:
        """Read a CSV file. Auto-detects whether it contains server or energy data."""
        col_map = self.options.get("column_map", {})

        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return [], [], []

            fields_lower = {fn.lower(): fn for fn in reader.fieldnames}

            # Detect type by looking for distinguishing columns
            if _has_any(fields_lower, ["hostname", "server", "host", "name"]):
                return self._parse_server_csv(reader, col_map, fields_lower), [], []
            elif _has_any(fields_lower, ["timestamp", "time", "datetime"]):
                return [], self._parse_energy_csv(reader, col_map, fields_lower), []
            else:
                return self._parse_server_csv(reader, col_map, fields_lower), [], []

    def _parse_server_csv(
        self,
        reader: csv.DictReader,
        col_map: dict[str, str],
        fields_lower: dict[str, str],
    ) -> list[RawServerData]:
        servers = []
        for row in reader:
            mapped = _apply_column_map(row, col_map)
            hostname = (
                mapped.get("hostname")
                or mapped.get("server")
                or mapped.get("host")
                or mapped.get("name")
                or f"server-{len(servers)}"
            )
            servers.append(RawServerData(
                hostname=hostname,
                ip_address=mapped.get("ip_address") or mapped.get("ip"),
                server_type_hint=mapped.get("server_type") or mapped.get("type"),
                power_watts=_float_or_none(mapped.get("power_watts") or mapped.get("power")),
                tdp_watts=_float_or_none(mapped.get("tdp_watts") or mapped.get("tdp")),
                cpu_utilization=_fraction_or_none(
                    mapped.get("cpu_utilization") or mapped.get("cpu_util") or mapped.get("cpu")
                ),
                gpu_utilization=_fraction_or_none(
                    mapped.get("gpu_utilization") or mapped.get("gpu_util") or mapped.get("gpu")
                ),
                memory_utilization=_fraction_or_none(
                    mapped.get("memory_utilization") or mapped.get("mem_util") or mapped.get("memory")
                ),
                memory_total_gb=_float_or_none(
                    mapped.get("memory_total_gb") or mapped.get("mem_total")
                ),
                memory_used_gb=_float_or_none(
                    mapped.get("memory_used_gb") or mapped.get("mem_used")
                ),
                age_months=_int_or_none(mapped.get("age_months") or mapped.get("age")),
                warranty_months=_int_or_none(
                    mapped.get("warranty_months") or mapped.get("warranty")
                ),
                rack_id=mapped.get("rack_id") or mapped.get("rack"),
                model=mapped.get("model"),
                serial=mapped.get("serial"),
            ))
        return servers

    def _parse_energy_csv(
        self,
        reader: csv.DictReader,
        col_map: dict[str, str],
        fields_lower: dict[str, str],
    ) -> list[RawEnergyReading]:
        readings = []
        for row in reader:
            mapped = _apply_column_map(row, col_map)
            ts_str = (
                mapped.get("timestamp")
                or mapped.get("time")
                or mapped.get("datetime")
            )
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            readings.append(RawEnergyReading(
                timestamp=ts,
                total_power_kw=_float_or_none(
                    mapped.get("total_power_kw") or mapped.get("total_power")
                ),
                it_power_kw=_float_or_none(
                    mapped.get("it_power_kw") or mapped.get("it_power")
                ),
                cooling_power_kw=_float_or_none(
                    mapped.get("cooling_power_kw") or mapped.get("cooling_power")
                ),
                lighting_power_kw=_float_or_none(mapped.get("lighting_power_kw")),
                ups_loss_kw=_float_or_none(mapped.get("ups_loss_kw")),
            ))
        return readings

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    def _read_json(
        self, path: Path
    ) -> tuple[list[RawServerData], list[RawEnergyReading], list[RawCoolingData]]:
        """Read a JSON file. Supports structured or flat list formats."""
        with open(path) as f:
            data = json.load(f)

        servers: list[RawServerData] = []
        energy: list[RawEnergyReading] = []
        cooling: list[RawCoolingData] = []

        if isinstance(data, dict):
            # Structured format: {"servers": [...], "energy_readings": [...]}
            if "servers" in data:
                for item in data["servers"]:
                    servers.append(RawServerData.model_validate(item))
            if "energy_readings" in data:
                for item in data["energy_readings"]:
                    energy.append(RawEnergyReading.model_validate(item))
            if "cooling_systems" in data or "cooling_data" in data:
                for item in data.get("cooling_systems", data.get("cooling_data", [])):
                    cooling.append(RawCoolingData.model_validate(item))
        elif isinstance(data, list) and data:
            # Flat list — try to detect type from first item
            first = data[0]
            if "hostname" in first or "host" in first:
                for item in data:
                    if "hostname" not in item and "host" in item:
                        item["hostname"] = item.pop("host")
                    servers.append(RawServerData.model_validate(item))
            elif "timestamp" in first:
                for item in data:
                    energy.append(RawEnergyReading.model_validate(item))

        return servers, energy, cooling


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_any(fields_lower: dict[str, str], candidates: list[str]) -> bool:
    return any(c in fields_lower for c in candidates)


def _apply_column_map(row: dict[str, str], col_map: dict[str, str]) -> dict[str, str]:
    """Apply column mapping and normalize keys to lowercase."""
    reverse_map = {v: k for k, v in col_map.items()}
    result: dict[str, str] = {}
    for key, value in row.items():
        mapped_key = reverse_map.get(key, key).lower().strip()
        result[mapped_key] = value.strip() if isinstance(value, str) else value
    return result


def _float_or_none(val: Any) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _fraction_or_none(val: Any) -> float | None:
    """Parse a utilization value, converting percentage to fraction if needed."""
    f = _float_or_none(val)
    if f is None:
        return None
    if f > 1.0:
        f = f / 100.0
    return max(0.0, min(1.0, f))


def _int_or_none(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# Self-register
register_collector("csv", FileImportCollector)
register_collector("json", FileImportCollector)
