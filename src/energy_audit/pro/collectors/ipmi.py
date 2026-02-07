# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""IPMI/BMC data collector for data center energy auditing.

Connects to server BMCs via IPMI to collect power consumption, thermal
data, and asset information.  Supports a ``simulate=True`` option for
testing without real BMC hardware.

Requires the ``pyghmi`` library when operating against real hardware::

    pip install -e '.[pro-ipmi]'
"""

from __future__ import annotations

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
# Simulated BMC data
# ---------------------------------------------------------------------------

_SIM_SERVER_MODELS = [
    "Dell PowerEdge R750",
    "Dell PowerEdge R650",
    "HPE ProLiant DL380 Gen10",
    "HPE ProLiant DL360 Gen10",
    "Supermicro SYS-6029P-TRT",
    "Supermicro SYS-1029U-TRTP",
    "Lenovo ThinkSystem SR650",
    "Lenovo ThinkSystem SR630",
    "Cisco UCS C240 M6",
    "Cisco UCS C220 M6",
]

_SIM_FIRMWARE_VERSIONS = [
    "iDRAC9 6.10.30.00",
    "iDRAC9 5.10.50.00",
    "iLO5 2.72",
    "iLO5 2.65",
    "IPMI 2.0 rev 1.1",
    "BMC 13.0.6",
    "XCC 7.92",
    "CIMC 4.2(2a)",
]

_SIM_RACK_IDS = ["rack-A01", "rack-A02", "rack-B01", "rack-B02", "rack-C01"]


def _generate_simulated_servers(
    endpoints: list[str],
    rng: random.Random,
) -> list[RawServerData]:
    """Generate plausible fake BMC data for testing."""
    count = rng.randint(6, 10) if not endpoints else len(endpoints)

    servers: list[RawServerData] = []
    for i in range(count):
        if endpoints and i < len(endpoints):
            hostname = endpoints[i]
        else:
            hostname = f"bmc-node{i + 1:02d}.dc.local"

        power_watts = round(rng.uniform(250.0, 800.0), 1)
        inlet_temp = round(rng.uniform(20.0, 26.0), 1)
        outlet_temp = round(rng.uniform(32.0, 42.0), 1)
        cpu_util = round(rng.uniform(0.10, 0.95), 2)
        age_months = rng.randint(12, 60)
        warranty_months = rng.choice([36, 48, 60])

        model = rng.choice(_SIM_SERVER_MODELS)
        firmware = rng.choice(_SIM_FIRMWARE_VERSIONS)
        serial = f"SN{rng.randint(100000, 999999)}"
        rack_id = rng.choice(_SIM_RACK_IDS)

        # Derive a plausible TDP from the measured power
        tdp = round(power_watts * rng.uniform(1.1, 1.4), 1)

        servers.append(RawServerData(
            hostname=hostname,
            ip_address=f"10.0.{rng.randint(1, 254)}.{rng.randint(1, 254)}",
            server_type_hint="cpu",
            power_watts=power_watts,
            tdp_watts=tdp,
            cpu_utilization=cpu_util,
            memory_utilization=round(rng.uniform(0.20, 0.85), 2),
            inlet_temp_celsius=inlet_temp,
            outlet_temp_celsius=outlet_temp,
            model=model,
            serial=serial,
            firmware_version=firmware,
            age_months=age_months,
            warranty_months=warranty_months,
            rack_id=rack_id,
            tags={"collector": "ipmi", "mode": "simulated"},
        ))

    return servers


def _generate_simulated_energy(
    servers: list[RawServerData],
    rng: random.Random,
) -> list[RawEnergyReading]:
    """Create a single aggregate energy reading from simulated servers."""
    total_it_kw = sum(
        (s.power_watts or 0.0) for s in servers
    ) / 1000.0

    # Simulate PUE between 1.3 and 1.6
    pue = round(rng.uniform(1.3, 1.6), 2)
    cooling_kw = round(total_it_kw * (pue - 1.0) * rng.uniform(0.6, 0.8), 3)
    ups_loss_kw = round(total_it_kw * rng.uniform(0.02, 0.06), 3)
    lighting_kw = round(rng.uniform(0.5, 2.0), 3)
    total_kw = round(total_it_kw + cooling_kw + ups_loss_kw + lighting_kw, 3)

    return [RawEnergyReading(
        timestamp=datetime.now(tz=timezone.utc),
        total_power_kw=total_kw,
        it_power_kw=round(total_it_kw, 3),
        cooling_power_kw=cooling_kw,
        lighting_power_kw=lighting_kw,
        ups_loss_kw=ups_loss_kw,
    )]


def _generate_simulated_cooling(rng: random.Random) -> list[RawCoolingData]:
    """Generate a basic simulated cooling data entry."""
    return [RawCoolingData(
        name="CRAC-Sim-01",
        cooling_type="air",
        cop=round(rng.uniform(2.5, 4.5), 1),
        capacity_kw=round(rng.uniform(50.0, 200.0), 1),
        current_load_kw=round(rng.uniform(20.0, 120.0), 1),
    )]


# ---------------------------------------------------------------------------
# Real IPMI collection helpers
# ---------------------------------------------------------------------------

def _collect_via_ipmi(
    endpoint: str,
    username: str,
    password: str,
    timeout: int,
) -> RawServerData:
    """Collect data from a single BMC using pyghmi.

    Reads power via DCMI (falling back to sensor readings), thermal
    sensors, and asset/FRU information.
    """
    from pyghmi.ipmi import command as ipmi_command  # type: ignore[import-untyped]

    conn = ipmi_command.Command(
        bmc=endpoint,
        userid=username,
        password=password,
        timeout=timeout,
    )

    # -- Power --
    power_watts: float | None = None
    try:
        dcmi = conn.get_dcmi_power_reading()
        if isinstance(dcmi, dict):
            power_watts = float(dcmi.get("current_power", 0))
    except Exception:
        logger.debug("DCMI power not available on %s, trying sensors", endpoint)

    # Fall back to sensor-based power reading
    if power_watts is None or power_watts == 0:
        try:
            for sensor in conn.get_sensor_data():
                name_lower = sensor.get("name", "").lower()
                if "power" in name_lower and "watt" in sensor.get("units", "").lower():
                    power_watts = float(sensor.get("value", 0))
                    break
        except Exception:
            logger.warning("Could not read power sensors from %s", endpoint)

    # -- Temperature sensors --
    inlet_temp: float | None = None
    outlet_temp: float | None = None
    try:
        for sensor in conn.get_sensor_data():
            name_lower = sensor.get("name", "").lower()
            if sensor.get("units", "").lower() not in ("degrees c", "celsius", "c"):
                continue
            value = float(sensor.get("value", 0))
            if any(kw in name_lower for kw in ("inlet", "ambient", "intake")):
                inlet_temp = value
            elif any(kw in name_lower for kw in ("outlet", "exhaust")):
                outlet_temp = value
    except Exception:
        logger.warning("Could not read temperature sensors from %s", endpoint)

    # -- Asset / FRU information --
    model: str | None = None
    serial: str | None = None
    firmware_version: str | None = None
    try:
        fru = conn.get_inventory()
        if isinstance(fru, dict):
            product = fru.get("product", {})
            model = product.get("product_name") or product.get("model")
            serial = product.get("serial_number")
    except Exception:
        logger.debug("Could not read FRU inventory from %s", endpoint)

    try:
        fw = conn.get_firmware()
        if isinstance(fw, list) and fw:
            firmware_version = str(fw[0].get("version", ""))
        elif isinstance(fw, dict):
            firmware_version = str(fw.get("version", ""))
    except Exception:
        logger.debug("Could not read firmware info from %s", endpoint)

    return RawServerData(
        hostname=endpoint,
        power_watts=power_watts,
        inlet_temp_celsius=inlet_temp,
        outlet_temp_celsius=outlet_temp,
        model=model,
        serial=serial,
        firmware_version=firmware_version,
        tags={"collector": "ipmi", "mode": "live"},
    )


# ---------------------------------------------------------------------------
# IPMICollector
# ---------------------------------------------------------------------------

class IPMICollector:
    """Collect power, thermal, and asset data from server BMCs via IPMI.

    Configuration options (via ``config.options``):

    * ``simulate`` (bool): If ``True``, generate plausible fake data
      instead of contacting real BMCs.  Defaults to ``False``.
    * ``seed`` (int | None): RNG seed for reproducible simulation output.
    * ``username`` / ``password``: BMC credentials (can also be supplied
      via ``config.credentials``).
    """

    def __init__(self, config: CollectorSourceConfig) -> None:
        self.config = config
        self.options: dict[str, Any] = config.options
        self.endpoints: list[str] = config.endpoints
        self.simulate: bool = self.options.get("simulate", False)

    # ---- DataCollector protocol methods ------------------------------------

    def collect(self) -> CollectorResult:
        """Run data collection and return raw data."""
        servers: list[RawServerData] = []
        energy: list[RawEnergyReading] = []
        cooling: list[RawCoolingData] = []
        errors: list[str] = []
        warnings: list[str] = []

        if self.simulate:
            seed = self.options.get("seed")
            rng = random.Random(seed)

            servers = _generate_simulated_servers(self.endpoints, rng)
            energy = _generate_simulated_energy(servers, rng)
            cooling = _generate_simulated_cooling(rng)
            warnings.append(
                "IPMI collector running in simulation mode — data is synthetic"
            )
            logger.info(
                "IPMI simulation: generated %d servers", len(servers)
            )
        else:
            from energy_audit.pro import check_dependency
            check_dependency("pyghmi", "pip install -e '.[pro-ipmi]'")

            username, password = self._resolve_credentials()

            if not self.endpoints:
                errors.append(
                    "No BMC endpoints configured. Add endpoints to the "
                    "collector source config or use simulate=True."
                )
                return CollectorResult(
                    source_type="ipmi",
                    servers=servers,
                    energy_readings=energy,
                    cooling_data=cooling,
                    errors=errors,
                    warnings=warnings,
                )

            for endpoint in self.endpoints:
                try:
                    server = _collect_via_ipmi(
                        endpoint=endpoint,
                        username=username,
                        password=password,
                        timeout=self.config.timeout_seconds,
                    )
                    servers.append(server)
                except Exception as exc:
                    msg = f"Failed to collect from BMC {endpoint}: {exc}"
                    logger.error(msg)
                    errors.append(msg)

            # Build an aggregate energy reading from live server data
            if servers:
                total_it_kw = sum(
                    (s.power_watts or 0.0) for s in servers
                ) / 1000.0
                energy.append(RawEnergyReading(
                    timestamp=datetime.now(tz=timezone.utc),
                    it_power_kw=round(total_it_kw, 3),
                ))

        return CollectorResult(
            source_type="ipmi",
            servers=servers,
            energy_readings=energy,
            cooling_data=cooling,
            errors=errors,
            warnings=warnings,
        )

    def discover(self) -> list[str]:
        """Discover available BMC endpoints and report their status."""
        results: list[str] = []

        if self.simulate:
            count = max(len(self.endpoints), random.randint(6, 10))
            results.append(
                f"[simulate] Would discover {count} BMC endpoint(s)"
            )
            for ep in self.endpoints:
                results.append(f"  - {ep} (simulated)")
            return results

        from energy_audit.pro import check_dependency
        check_dependency("pyghmi", "pip install -e '.[pro-ipmi]'")

        if not self.endpoints:
            results.append("No BMC endpoints configured")
            return results

        username, password = self._resolve_credentials()

        for endpoint in self.endpoints:
            try:
                from pyghmi.ipmi import command as ipmi_command  # type: ignore[import-untyped]

                conn = ipmi_command.Command(
                    bmc=endpoint,
                    userid=username,
                    password=password,
                    timeout=self.config.timeout_seconds,
                )
                # A quick health check: read BMC device ID
                devid = conn.get_device_id()
                if devid:
                    results.append(
                        f"{endpoint}: reachable (manufacturer={devid.get('manufacturer_id', 'N/A')})"
                    )
                else:
                    results.append(f"{endpoint}: reachable (no device ID)")
            except Exception as exc:
                results.append(f"{endpoint}: unreachable ({exc})")

        return results

    def test_connection(self) -> bool:
        """Test that the collector can reach at least one BMC."""
        if self.simulate:
            return True

        from energy_audit.pro import check_dependency
        check_dependency("pyghmi", "pip install -e '.[pro-ipmi]'")

        if not self.endpoints:
            return False

        username, password = self._resolve_credentials()

        for endpoint in self.endpoints:
            try:
                from pyghmi.ipmi import command as ipmi_command  # type: ignore[import-untyped]

                conn = ipmi_command.Command(
                    bmc=endpoint,
                    userid=username,
                    password=password,
                    timeout=self.config.timeout_seconds,
                )
                conn.get_device_id()
                return True
            except Exception:
                logger.debug("Connection test failed for %s", endpoint)
                continue

        return False

    # ---- Internal helpers --------------------------------------------------

    def _resolve_credentials(self) -> tuple[str, str]:
        """Resolve BMC username and password from config.

        Checks ``config.options`` first (for convenience), then falls
        back to ``config.credentials`` for production use.
        """
        username = self.options.get("username", "")
        password = self.options.get("password", "")

        if not username and self.config.credentials:
            # Credentials ref stores a "user:pass" string
            try:
                cred_value = self.config.credentials.resolve()
                if ":" in cred_value:
                    username, password = cred_value.split(":", 1)
                else:
                    username = cred_value
            except ValueError:
                logger.warning("Could not resolve IPMI credentials")

        if not username:
            username = "ADMIN"
        if not password:
            password = "ADMIN"
            logger.warning(
                "Using default IPMI credentials — configure credentials "
                "for production use"
            )

        return username, password


# ---------------------------------------------------------------------------
# Self-register
# ---------------------------------------------------------------------------

register_collector("ipmi", IPMICollector)
