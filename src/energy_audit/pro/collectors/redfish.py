# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Redfish REST API data collector.

Queries BMC endpoints (Dell iDRAC, HPE iLO, Lenovo XCC) via the DMTF
Redfish standard to collect power, thermal, and asset data from bare-metal
servers.  Supports a ``simulate=True`` option for testing without real
hardware.
"""

from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timezone
from typing import Any

from energy_audit.pro.collectors import register_collector
from energy_audit.pro.collectors.base import (
    CollectorResult,
    RawCoolingData,
    RawEnergyReading,
    RawServerData,
)
from energy_audit.pro.config import CollectorSourceConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Simulated server catalogue
# ---------------------------------------------------------------------------

_SIMULATED_SERVERS: list[dict[str, Any]] = [
    {
        "hostname": "idrac-gpu-01",
        "ip": "10.0.1.11",
        "model": "Dell PowerEdge R760xa",
        "serial": "DELL-SVC-7X9K01",
        "bios": "2.22.1",
        "firmware": "7.00.00.00 (iDRAC9)",
        "server_type": "gpu_training",
        "mem_total_gb": 512,
        "mem_used_gb": 480,
        "processors": 2,
        "power_capacity": 2400,
        "power_range": (1350, 1850),
        "inlet_range": (22.0, 27.0),
        "outlet_range": (38.0, 48.0),
        "fan_range": (4500, 9200),
    },
    {
        "hostname": "ilo-cpu-01",
        "ip": "10.0.1.21",
        "model": "HPE ProLiant DL380 Gen11",
        "serial": "HPE-MXQ4280123",
        "bios": "U46 v3.10",
        "firmware": "3.05 (iLO 6)",
        "server_type": "cpu",
        "mem_total_gb": 256,
        "mem_used_gb": 180,
        "processors": 2,
        "power_capacity": 1600,
        "power_range": (320, 580),
        "inlet_range": (20.0, 25.0),
        "outlet_range": (32.0, 40.0),
        "fan_range": (3200, 7800),
    },
    {
        "hostname": "xcc-storage-01",
        "ip": "10.0.1.31",
        "model": "Lenovo ThinkSystem SR650 V3",
        "serial": "LNV-J300AB12",
        "bios": "IVE1 v3.30",
        "firmware": "4.10 (XCC)",
        "server_type": "storage",
        "mem_total_gb": 128,
        "mem_used_gb": 64,
        "processors": 2,
        "power_capacity": 1100,
        "power_range": (280, 440),
        "inlet_range": (21.0, 26.0),
        "outlet_range": (30.0, 38.0),
        "fan_range": (2800, 6500),
    },
    {
        "hostname": "idrac-gpu-02",
        "ip": "10.0.1.12",
        "model": "Dell PowerEdge XE9680",
        "serial": "DELL-SVC-8A2J45",
        "bios": "1.8.1",
        "firmware": "7.10.30.00 (iDRAC9)",
        "server_type": "gpu_training",
        "mem_total_gb": 2048,
        "mem_used_gb": 1920,
        "processors": 2,
        "power_capacity": 6000,
        "power_range": (3800, 5200),
        "inlet_range": (23.0, 28.0),
        "outlet_range": (45.0, 58.0),
        "fan_range": (6000, 12000),
    },
    {
        "hostname": "ilo-inf-01",
        "ip": "10.0.1.22",
        "model": "HPE ProLiant DL380a Gen11",
        "serial": "HPE-MXQ4280456",
        "bios": "U46 v3.12",
        "firmware": "3.05 (iLO 6)",
        "server_type": "gpu_inference",
        "mem_total_gb": 512,
        "mem_used_gb": 410,
        "processors": 2,
        "power_capacity": 2000,
        "power_range": (650, 1100),
        "inlet_range": (21.0, 26.0),
        "outlet_range": (36.0, 46.0),
        "fan_range": (4000, 8500),
    },
    {
        "hostname": "idrac-cpu-03",
        "ip": "10.0.1.13",
        "model": "Dell PowerEdge R660",
        "serial": "DELL-SVC-3M7N89",
        "bios": "1.10.2",
        "firmware": "7.00.60.05 (iDRAC9)",
        "server_type": "cpu",
        "mem_total_gb": 256,
        "mem_used_gb": 140,
        "processors": 2,
        "power_capacity": 1400,
        "power_range": (260, 520),
        "inlet_range": (20.0, 25.0),
        "outlet_range": (31.0, 39.0),
        "fan_range": (3000, 7200),
    },
    {
        "hostname": "xcc-cpu-02",
        "ip": "10.0.1.32",
        "model": "Lenovo ThinkSystem SR630 V3",
        "serial": "LNV-J300CD78",
        "bios": "IVE1 v3.20",
        "firmware": "4.00 (XCC)",
        "server_type": "cpu",
        "mem_total_gb": 128,
        "mem_used_gb": 88,
        "processors": 1,
        "power_capacity": 750,
        "power_range": (180, 340),
        "inlet_range": (20.0, 24.0),
        "outlet_range": (29.0, 36.0),
        "fan_range": (2500, 5800),
    },
]


class RedfishCollector:
    """Collect server power, thermal, and asset data via Redfish REST API.

    When ``config.options["simulate"]`` is ``True``, returns plausible
    synthetic data modelled on Dell iDRAC, HPE iLO, and Lenovo XCC
    responses.  Otherwise queries real BMC endpoints using ``httpx``.
    """

    def __init__(self, config: CollectorSourceConfig) -> None:
        self.config = config
        self.options = config.options
        self.endpoints = config.endpoints
        self.simulate = bool(self.options.get("simulate", False))

        # Deterministic randomness: hash the sorted endpoint list so the
        # same config always produces the same simulated fleet.
        seed_material = ":".join(sorted(self.endpoints)) or "redfish-sim"
        seed_int = int(hashlib.sha256(seed_material.encode()).hexdigest()[:8], 16)
        self._rng = random.Random(seed_int)

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

    def collect(self) -> CollectorResult:
        """Run data collection and return raw data."""
        if self.simulate:
            return self._collect_simulated()
        return self._collect_live()

    def discover(self) -> list[str]:
        """Discover available Redfish endpoints / managed systems."""
        if self.simulate:
            count = self._sim_server_count()
            descriptions: list[str] = []
            for spec in self._pick_simulated_servers(count):
                descriptions.append(
                    f"{spec['hostname']} ({spec['model']}) @ {spec['ip']} [simulated]"
                )
            return descriptions
        return self._discover_live()

    def test_connection(self) -> bool:
        """Test that the collector can reach its Redfish targets."""
        if self.simulate:
            return True
        return self._test_connection_live()

    # ------------------------------------------------------------------
    # Simulated collection
    # ------------------------------------------------------------------

    def _sim_server_count(self) -> int:
        """Return the number of simulated servers (5-8)."""
        return self._rng.randint(5, min(8, len(_SIMULATED_SERVERS)))

    def _pick_simulated_servers(self, count: int) -> list[dict[str, Any]]:
        """Pick *count* servers from the catalogue (deterministic)."""
        pool = list(_SIMULATED_SERVERS)
        self._rng.shuffle(pool)
        return pool[:count]

    def _collect_simulated(self) -> CollectorResult:
        """Generate a plausible simulated Redfish data set."""
        count = self._sim_server_count()
        fleet = self._pick_simulated_servers(count)

        servers: list[RawServerData] = []
        energy_readings: list[RawEnergyReading] = []
        cooling_data: list[RawCoolingData] = []
        warnings: list[str] = ["Simulated Redfish data — not from real hardware"]

        total_power_w = 0.0

        for spec in fleet:
            power_w = self._rng.uniform(*spec["power_range"])
            inlet_c = round(self._rng.uniform(*spec["inlet_range"]), 1)
            outlet_c = round(self._rng.uniform(*spec["outlet_range"]), 1)
            fan_rpm = self._rng.randint(*spec["fan_range"])
            cpu_util = round(self._rng.uniform(0.10, 0.92), 2)
            mem_util = round(spec["mem_used_gb"] / spec["mem_total_gb"], 2)
            gpu_util: float | None = None
            if spec["server_type"] in ("gpu_training", "gpu_inference"):
                gpu_util = round(self._rng.uniform(0.30, 0.95), 2)

            total_power_w += power_w

            servers.append(RawServerData(
                hostname=spec["hostname"],
                ip_address=spec["ip"],
                server_type_hint=spec["server_type"],
                model=spec["model"],
                serial=spec["serial"],
                firmware_version=spec["firmware"],
                power_watts=round(power_w, 1),
                tdp_watts=float(spec["power_capacity"]),
                cpu_utilization=cpu_util,
                gpu_utilization=gpu_util,
                memory_utilization=mem_util,
                memory_total_gb=float(spec["mem_total_gb"]),
                memory_used_gb=float(spec["mem_used_gb"]),
                inlet_temp_celsius=inlet_c,
                outlet_temp_celsius=outlet_c,
                tags={
                    "bios_version": spec["bios"],
                    "bmc_firmware": spec["firmware"],
                    "processor_count": str(spec["processors"]),
                    "fan_speed_rpm": str(fan_rpm),
                    "power_capacity_watts": str(spec["power_capacity"]),
                    "redfish_source": "simulated",
                },
            ))

        # Aggregate energy reading
        now = datetime.now(timezone.utc)
        total_it_kw = total_power_w / 1000.0
        # Estimate cooling at ~35 % of IT load for simulation
        cooling_kw = total_it_kw * self._rng.uniform(0.30, 0.40)
        energy_readings.append(RawEnergyReading(
            timestamp=now,
            total_power_kw=round(total_it_kw + cooling_kw, 2),
            it_power_kw=round(total_it_kw, 2),
            cooling_power_kw=round(cooling_kw, 2),
        ))

        # Simulated CRAC / in-row cooling unit
        cooling_data.append(RawCoolingData(
            name="CRAC-A1 (simulated)",
            cooling_type="air",
            cop=round(self._rng.uniform(2.8, 3.8), 1),
            capacity_kw=round(total_it_kw * 1.4, 1),
            current_load_kw=round(cooling_kw, 1),
        ))

        return CollectorResult(
            source_type="redfish",
            servers=servers,
            energy_readings=energy_readings,
            cooling_data=cooling_data,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Live Redfish collection (requires httpx)
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        """Create an httpx client with authentication and TLS settings."""
        from energy_audit.pro import check_dependency

        check_dependency("httpx", "pip install -e '.[pro-redfish]'")
        import httpx  # noqa: E402

        username: str | None = None
        password: str | None = None
        if self.config.credentials:
            cred_str = self.config.credentials.resolve()
            # Expect "user:password" format
            if ":" in cred_str:
                username, password = cred_str.split(":", 1)
            else:
                username = cred_str
                password = ""

        auth = (username, password) if username else None
        verify_ssl = bool(self.options.get("verify_ssl", False))

        return httpx.Client(
            auth=auth,
            verify=verify_ssl,
            timeout=float(self.config.timeout_seconds),
            headers={"Accept": "application/json"},
        )

    def _collect_live(self) -> CollectorResult:
        """Query real Redfish endpoints and build a CollectorResult."""
        servers: list[RawServerData] = []
        energy_readings: list[RawEnergyReading] = []
        cooling_data: list[RawCoolingData] = []
        errors: list[str] = []
        warnings: list[str] = []

        client = self._get_client()
        try:
            for endpoint in self.endpoints:
                base_url = self._normalise_url(endpoint)
                try:
                    srv, eng, cool, errs, warns = self._collect_from_endpoint(
                        client, base_url
                    )
                    servers.extend(srv)
                    energy_readings.extend(eng)
                    cooling_data.extend(cool)
                    errors.extend(errs)
                    warnings.extend(warns)
                except Exception as exc:
                    errors.append(f"Error collecting from {endpoint}: {exc}")
        finally:
            client.close()

        return CollectorResult(
            source_type="redfish",
            servers=servers,
            energy_readings=energy_readings,
            cooling_data=cooling_data,
            errors=errors,
            warnings=warnings,
        )

    def _collect_from_endpoint(
        self,
        client: Any,
        base_url: str,
    ) -> tuple[
        list[RawServerData],
        list[RawEnergyReading],
        list[RawCoolingData],
        list[str],
        list[str],
    ]:
        """Collect data from a single Redfish service root."""
        servers: list[RawServerData] = []
        energy_readings: list[RawEnergyReading] = []
        cooling_data: list[RawCoolingData] = []
        errors: list[str] = []
        warnings: list[str] = []

        # --- Enumerate systems ---
        systems_url = f"{base_url}/redfish/v1/Systems"
        resp = client.get(systems_url)
        resp.raise_for_status()
        systems_data = resp.json()

        members = systems_data.get("Members", [])
        if not members:
            warnings.append(f"No systems found at {systems_url}")
            return servers, energy_readings, cooling_data, errors, warnings

        for member_ref in members:
            member_uri = member_ref.get("@odata.id", "")
            if not member_uri:
                continue
            system_url = f"{base_url}{member_uri}"
            try:
                server = self._fetch_system(client, base_url, system_url)
                if server:
                    servers.append(server)
            except Exception as exc:
                errors.append(f"Error fetching system {member_uri}: {exc}")

        # --- Enumerate chassis for power / thermal ---
        chassis_url = f"{base_url}/redfish/v1/Chassis"
        try:
            resp = client.get(chassis_url)
            resp.raise_for_status()
            chassis_data = resp.json()

            for chassis_ref in chassis_data.get("Members", []):
                chassis_uri = chassis_ref.get("@odata.id", "")
                if not chassis_uri:
                    continue
                try:
                    eng, cool = self._fetch_chassis_readings(
                        client, base_url, chassis_uri
                    )
                    energy_readings.extend(eng)
                    cooling_data.extend(cool)
                except Exception as exc:
                    errors.append(
                        f"Error fetching chassis data {chassis_uri}: {exc}"
                    )
        except Exception as exc:
            warnings.append(f"Could not enumerate chassis at {base_url}: {exc}")

        return servers, energy_readings, cooling_data, errors, warnings

    def _fetch_system(
        self, client: Any, base_url: str, system_url: str
    ) -> RawServerData | None:
        """Fetch a single system resource and parse into RawServerData."""
        resp = client.get(system_url)
        resp.raise_for_status()
        data = resp.json()

        hostname = (
            data.get("HostName")
            or data.get("Name")
            or data.get("Id")
            or "unknown"
        )
        model = data.get("Model")
        serial = data.get("SerialNumber")
        bios_version = data.get("BiosVersion")

        # Power
        power_watts: float | None = None
        power_state = data.get("PowerState")
        if power_state == "Off":
            power_watts = 0.0

        # Processor summary
        proc_summary = data.get("ProcessorSummary", {})
        proc_count = proc_summary.get("Count")

        # Memory summary
        mem_summary = data.get("MemorySummary", {})
        mem_total_gib = mem_summary.get("TotalSystemMemoryGiB")

        tags: dict[str, str] = {}
        if bios_version:
            tags["bios_version"] = bios_version
        if proc_count is not None:
            tags["processor_count"] = str(proc_count)
        proc_model = proc_summary.get("Model")
        if proc_model:
            tags["processor_model"] = proc_model
        manufacturer = data.get("Manufacturer")
        if manufacturer:
            tags["manufacturer"] = manufacturer

        return RawServerData(
            hostname=hostname,
            model=model,
            serial=serial,
            firmware_version=bios_version,
            power_watts=power_watts,
            memory_total_gb=float(mem_total_gib) if mem_total_gib else None,
            tags=tags,
        )

    def _fetch_chassis_readings(
        self, client: Any, base_url: str, chassis_uri: str
    ) -> tuple[list[RawEnergyReading], list[RawCoolingData]]:
        """Fetch Power and Thermal data for a single chassis."""
        energy_readings: list[RawEnergyReading] = []
        cooling_data: list[RawCoolingData] = []
        now = datetime.now(timezone.utc)

        # --- Power ---
        power_url = f"{base_url}{chassis_uri}/Power"
        try:
            resp = client.get(power_url)
            if resp.status_code == 200:
                power_data = resp.json()
                total_watts = 0.0
                for ctrl in power_data.get("PowerControl", []):
                    consumed = ctrl.get("PowerConsumedWatts")
                    if consumed is not None:
                        total_watts += float(consumed)
                if total_watts > 0:
                    energy_readings.append(RawEnergyReading(
                        timestamp=now,
                        it_power_kw=round(total_watts / 1000.0, 3),
                    ))
        except Exception as exc:
            logger.debug("Could not read %s: %s", power_url, exc)

        # --- Thermal ---
        thermal_url = f"{base_url}{chassis_uri}/Thermal"
        try:
            resp = client.get(thermal_url)
            if resp.status_code == 200:
                thermal_data = resp.json()
                for fan in thermal_data.get("Fans", []):
                    fan_name = fan.get("Name", fan.get("FanName", "Fan"))
                    reading = fan.get("Reading") or fan.get("CurrentReading")
                    if reading is not None:
                        cooling_data.append(RawCoolingData(
                            name=fan_name,
                            cooling_type="air",
                        ))
        except Exception as exc:
            logger.debug("Could not read %s: %s", thermal_url, exc)

        return energy_readings, cooling_data

    # ------------------------------------------------------------------
    # Live discovery and connection test
    # ------------------------------------------------------------------

    def _discover_live(self) -> list[str]:
        """Query each endpoint's Redfish service root for system info."""
        results: list[str] = []
        client = self._get_client()
        try:
            for endpoint in self.endpoints:
                base_url = self._normalise_url(endpoint)
                try:
                    resp = client.get(f"{base_url}/redfish/v1/Systems")
                    resp.raise_for_status()
                    data = resp.json()
                    count = len(data.get("Members", []))
                    results.append(
                        f"{endpoint}: {count} system(s) discovered"
                    )
                except Exception as exc:
                    results.append(f"{endpoint}: discovery failed ({exc})")
        finally:
            client.close()
        return results

    def _test_connection_live(self) -> bool:
        """Attempt to reach the Redfish service root on each endpoint."""
        if not self.endpoints:
            return False

        client = self._get_client()
        try:
            for endpoint in self.endpoints:
                base_url = self._normalise_url(endpoint)
                try:
                    resp = client.get(f"{base_url}/redfish/v1")
                    if resp.status_code == 200:
                        return True
                except Exception:
                    continue
        finally:
            client.close()
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_url(endpoint: str) -> str:
        """Ensure the endpoint has a scheme and no trailing slash."""
        url = endpoint.rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        return url


# ---------------------------------------------------------------------------
# Self-register
# ---------------------------------------------------------------------------
register_collector("redfish", RedfishCollector)
