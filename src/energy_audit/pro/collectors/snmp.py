# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""SNMP data collector for data center energy auditing.

Polls PDU power meters, server host-resource MIBs, and thermal sensors
via SNMPv2c/v3.  Supports APC, Raritan, and ServerTech PDU OID families.

When ``config.options["simulate"]`` is *True* the collector generates
plausible fake data so the full pipeline can be exercised without real
hardware.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone
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
# Well-known SNMP OIDs for data-center equipment
# ---------------------------------------------------------------------------

# PDU power OIDs (outlet-level active power in tenths-of-watts)
PDU_POWER_OIDS: dict[str, str] = {
    "apc": "1.3.6.1.4.1.318.1.1.26.9.4.3.1.7",       # rPDU2OutletMeteredStatusActivePower
    "raritan": "1.3.6.1.4.1.13742.6.5.4.3.1.4",       # outletActivePower
    "servertech": "1.3.6.1.4.1.1718.3.2.3.1.12",      # outletLoadValue
}

# Host-resources MIB for CPU utilization
HR_PROCESSOR_LOAD_OID = "1.3.6.1.2.1.25.3.3.1.2"       # hrProcessorLoad (%)

# Host-resources MIB for memory
HR_STORAGE_SIZE_OID = "1.3.6.1.2.1.25.2.3.1.5"         # hrStorageSize
HR_STORAGE_USED_OID = "1.3.6.1.2.1.25.2.3.1.6"         # hrStorageUsed
HR_STORAGE_UNITS_OID = "1.3.6.1.2.1.25.2.3.1.4"        # hrStorageAllocationUnits

# Entity MIB for thermal sensors
ENTITY_SENSOR_VALUE_OID = "1.3.6.1.2.1.99.1.1.1.4"     # entPhySensorValue
ENTITY_SENSOR_TYPE_OID = "1.3.6.1.2.1.99.1.1.1.1"      # entPhySensorType (8 = celsius)

# sysDescr for basic identification
SYS_DESCR_OID = "1.3.6.1.2.1.1.1.0"
SYS_NAME_OID = "1.3.6.1.2.1.1.5.0"


# ---------------------------------------------------------------------------
# SNMPCollector
# ---------------------------------------------------------------------------

class SNMPCollector:
    """Collect server power, utilization, and thermal data over SNMP.

    Parameters
    ----------
    config : CollectorSourceConfig
        Collector source configuration.  Recognised ``options`` keys:

        * ``simulate`` (bool) -- generate synthetic data instead of polling.
        * ``community`` (str) -- SNMPv2c community string (default ``"public"``).
        * ``version`` (str) -- ``"2c"`` or ``"3"`` (default ``"2c"``).
        * ``port`` (int) -- UDP port (default ``161``).
        * ``pdu_vendor`` (str) -- ``"apc"``, ``"raritan"``, or ``"servertech"``.
        * ``seed`` (int) -- RNG seed for deterministic simulation output.
    """

    def __init__(self, config: CollectorSourceConfig) -> None:
        self.config = config
        self.endpoints = config.endpoints
        self.options = config.options
        self.simulate = config.options.get("simulate", False)
        self.timeout = config.timeout_seconds
        self.retries = config.retry_count

    # ------------------------------------------------------------------
    # DataCollector protocol
    # ------------------------------------------------------------------

    def collect(self) -> CollectorResult:
        """Run data collection and return raw data."""
        if self.simulate:
            return self._collect_simulated()
        return self._collect_snmp()

    def discover(self) -> list[str]:
        """Discover available SNMP endpoints. Returns descriptions."""
        if self.simulate:
            return [f"{ep} (simulated)" for ep in self.endpoints]
        return self._discover_snmp()

    def test_connection(self) -> bool:
        """Test that the collector can reach its target."""
        if self.simulate:
            return True
        return self._test_snmp_connection()

    # ------------------------------------------------------------------
    # Simulated data generation
    # ------------------------------------------------------------------

    def _collect_simulated(self) -> CollectorResult:
        """Generate plausible fake data for testing without real hardware."""
        seed = self.options.get("seed", 42)
        rng = random.Random(seed)

        server_count = rng.randint(8, 12)

        server_types = ["cpu", "gpu_training", "gpu_inference", "storage"]
        type_weights = [0.40, 0.15, 0.20, 0.25]

        rack_ids = [f"RACK-{r:02d}" for r in range(1, 5)]

        servers: list[RawServerData] = []
        total_it_power_kw = 0.0

        for i in range(server_count):
            stype = rng.choices(server_types, weights=type_weights, k=1)[0]

            # Decide if this server is a zombie (very low utilization)
            is_zombie = rng.random() < 0.20  # ~20% chance

            if stype == "gpu_training":
                power = rng.uniform(600, 1000)
                cpu_util = rng.uniform(0.30, 0.70) if not is_zombie else rng.uniform(0.01, 0.05)
                gpu_util = rng.uniform(0.60, 0.95) if not is_zombie else rng.uniform(0.01, 0.04)
                mem_total = rng.choice([256.0, 512.0, 1024.0])
            elif stype == "gpu_inference":
                power = rng.uniform(300, 600)
                cpu_util = rng.uniform(0.20, 0.55) if not is_zombie else rng.uniform(0.02, 0.05)
                gpu_util = rng.uniform(0.30, 0.80) if not is_zombie else rng.uniform(0.01, 0.03)
                mem_total = rng.choice([128.0, 256.0, 512.0])
            elif stype == "storage":
                power = rng.uniform(100, 350)
                cpu_util = rng.uniform(0.05, 0.30) if not is_zombie else rng.uniform(0.01, 0.03)
                gpu_util = None
                mem_total = rng.choice([64.0, 128.0])
            else:  # cpu
                power = rng.uniform(150, 500)
                cpu_util = rng.uniform(0.15, 0.85) if not is_zombie else rng.uniform(0.01, 0.05)
                gpu_util = None
                mem_total = rng.choice([64.0, 128.0, 256.0])

            mem_util = rng.uniform(0.20, 0.80) if not is_zombie else rng.uniform(0.05, 0.15)
            inlet_temp = rng.uniform(18.0, 28.0)
            outlet_temp = inlet_temp + rng.uniform(8.0, 20.0)

            hostname = f"srv-{stype.replace('_', '-')}-{i + 1:03d}"
            endpoint = self.endpoints[i % len(self.endpoints)] if self.endpoints else "10.0.0.1"

            servers.append(RawServerData(
                hostname=hostname,
                ip_address=endpoint,
                server_type_hint=stype,
                power_watts=round(power, 1),
                cpu_utilization=round(cpu_util, 4),
                gpu_utilization=round(gpu_util, 4) if gpu_util is not None else None,
                memory_utilization=round(mem_util, 4),
                memory_total_gb=mem_total,
                memory_used_gb=round(mem_total * mem_util, 1),
                inlet_temp_celsius=round(inlet_temp, 1),
                outlet_temp_celsius=round(outlet_temp, 1),
                rack_id=rng.choice(rack_ids),
                model=f"SIM-{stype.upper()}-{rng.randint(1000, 9999)}",
                age_months=rng.randint(3, 72),
                tags={"source": "snmp-simulated", "zombie": str(is_zombie).lower()},
            ))

            total_it_power_kw += power / 1000.0

        # Generate energy readings for the past 24 hours (hourly)
        now = datetime.now(tz=timezone.utc)
        energy_readings: list[RawEnergyReading] = []
        for hours_ago in range(24, 0, -1):
            ts = now - timedelta(hours=hours_ago)
            # Add some noise to simulate load variation
            load_factor = rng.uniform(0.85, 1.15)
            it_kw = round(total_it_power_kw * load_factor, 3)
            pue_factor = rng.uniform(1.3, 1.7)
            total_kw = round(it_kw * pue_factor, 3)
            cooling_kw = round(total_kw - it_kw - rng.uniform(0.5, 2.0), 3)
            cooling_kw = max(cooling_kw, 0.1)

            energy_readings.append(RawEnergyReading(
                timestamp=ts,
                total_power_kw=total_kw,
                it_power_kw=it_kw,
                cooling_power_kw=cooling_kw,
                ups_loss_kw=round(rng.uniform(0.1, 0.5), 3),
            ))

        # Simulated cooling data
        cooling_data = [
            RawCoolingData(
                name="CRAC-01",
                cooling_type="air",
                cop=rng.uniform(2.5, 4.0),
                capacity_kw=round(total_it_power_kw * 1.5, 1),
                current_load_kw=round(total_it_power_kw * rng.uniform(0.4, 0.7), 1),
            ),
        ]

        zombie_count = sum(1 for s in servers if s.tags.get("zombie") == "true")
        warnings: list[str] = []
        if zombie_count:
            warnings.append(
                f"Simulation includes {zombie_count} zombie server(s) with very low utilization"
            )

        return CollectorResult(
            source_type="snmp",
            servers=servers,
            energy_readings=energy_readings,
            cooling_data=cooling_data,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Real SNMP collection (requires pysnmp-lextudio)
    # ------------------------------------------------------------------

    def _collect_snmp(self) -> CollectorResult:
        """Poll SNMP OIDs from configured endpoints."""
        from energy_audit.pro import check_dependency
        check_dependency("pysnmp", "pip install -e '.[pro-snmp]'")

        from pysnmp.hlapi import (
            CommunityData,
            ContextData,
            ObjectIdentity,
            ObjectType,
            SnmpEngine,
            UdpTransportTarget,
            nextCmd,
        )

        community = self.options.get("community", "public")
        snmp_version = self.options.get("version", "2c")
        port = self.options.get("port", 161)
        pdu_vendor = self.options.get("pdu_vendor", "apc")

        servers: list[RawServerData] = []
        energy_readings: list[RawEnergyReading] = []
        cooling_data: list[RawCoolingData] = []
        errors: list[str] = []
        warnings: list[str] = []

        mp_model = 0 if snmp_version == "1" else 1  # 0=SNMPv1, 1=SNMPv2c

        for endpoint in self.endpoints:
            try:
                host_data = self._poll_host(
                    endpoint=endpoint,
                    community=community,
                    mp_model=mp_model,
                    port=port,
                    pdu_vendor=pdu_vendor,
                    snmp_engine=SnmpEngine,
                    community_data=CommunityData,
                    context_data=ContextData,
                    object_identity=ObjectIdentity,
                    object_type=ObjectType,
                    udp_transport_target=UdpTransportTarget,
                    next_cmd=nextCmd,
                )
                if host_data:
                    servers.append(host_data)
            except Exception as exc:
                msg = f"SNMP error polling {endpoint}: {exc}"
                logger.warning(msg)
                errors.append(msg)

        # Build a single energy reading from aggregated server power
        if servers:
            total_it_kw = sum(
                (s.power_watts or 0.0) / 1000.0 for s in servers
            )
            energy_readings.append(RawEnergyReading(
                timestamp=datetime.now(tz=timezone.utc),
                it_power_kw=round(total_it_kw, 3),
            ))

        if not servers:
            warnings.append("No servers responded to SNMP queries")

        return CollectorResult(
            source_type="snmp",
            servers=servers,
            energy_readings=energy_readings,
            cooling_data=cooling_data,
            errors=errors,
            warnings=warnings,
        )

    def _poll_host(
        self,
        endpoint: str,
        community: str,
        mp_model: int,
        port: int,
        pdu_vendor: str,
        *,
        snmp_engine: Any,
        community_data: Any,
        context_data: Any,
        object_identity: Any,
        object_type: Any,
        udp_transport_target: Any,
        next_cmd: Any,
    ) -> RawServerData | None:
        """Poll a single host for power, CPU, memory, and thermal data."""
        engine = snmp_engine()
        auth = community_data(community, mpModel=mp_model)
        transport = udp_transport_target(
            (endpoint, port),
            timeout=self.timeout,
            retries=self.retries,
        )
        context = context_data()

        # --- sysName for hostname ---
        hostname = endpoint
        sys_name = self._snmp_get_scalar(
            engine, auth, transport, context,
            object_identity, object_type, next_cmd,
            SYS_NAME_OID,
        )
        if sys_name:
            hostname = str(sys_name)

        # --- PDU power ---
        power_watts: float | None = None
        pdu_oid = PDU_POWER_OIDS.get(pdu_vendor)
        if pdu_oid:
            power_raw = self._snmp_walk_sum(
                engine, auth, transport, context,
                object_identity, object_type, next_cmd,
                pdu_oid,
            )
            if power_raw is not None:
                # Most PDU MIBs report tenths-of-watts
                power_watts = power_raw / 10.0

        # --- CPU utilization (hrProcessorLoad) ---
        cpu_values = self._snmp_walk_values(
            engine, auth, transport, context,
            object_identity, object_type, next_cmd,
            HR_PROCESSOR_LOAD_OID,
        )
        cpu_utilization: float | None = None
        if cpu_values:
            avg_load = sum(cpu_values) / len(cpu_values)
            cpu_utilization = round(avg_load / 100.0, 4)

        # --- Memory utilization (hrStorage) ---
        memory_utilization: float | None = None
        mem_sizes = self._snmp_walk_values(
            engine, auth, transport, context,
            object_identity, object_type, next_cmd,
            HR_STORAGE_SIZE_OID,
        )
        mem_useds = self._snmp_walk_values(
            engine, auth, transport, context,
            object_identity, object_type, next_cmd,
            HR_STORAGE_USED_OID,
        )
        if mem_sizes and mem_useds and sum(mem_sizes) > 0:
            memory_utilization = round(sum(mem_useds) / sum(mem_sizes), 4)

        # --- Thermal sensors (ENTITY-MIB) ---
        inlet_temp: float | None = None
        sensor_types = self._snmp_walk_indexed(
            engine, auth, transport, context,
            object_identity, object_type, next_cmd,
            ENTITY_SENSOR_TYPE_OID,
        )
        sensor_values = self._snmp_walk_indexed(
            engine, auth, transport, context,
            object_identity, object_type, next_cmd,
            ENTITY_SENSOR_VALUE_OID,
        )
        # Type 8 = celsius in ENTITY-SENSOR-MIB
        for idx, stype in sensor_types.items():
            if int(stype) == 8 and idx in sensor_values:
                inlet_temp = float(sensor_values[idx])
                break  # Take the first celsius sensor as inlet temperature

        return RawServerData(
            hostname=hostname,
            ip_address=endpoint,
            power_watts=power_watts,
            cpu_utilization=cpu_utilization,
            memory_utilization=memory_utilization,
            inlet_temp_celsius=inlet_temp,
            tags={"source": "snmp", "pdu_vendor": pdu_vendor},
        )

    # ------------------------------------------------------------------
    # SNMP helper methods
    # ------------------------------------------------------------------

    @staticmethod
    def _snmp_get_scalar(
        engine: Any, auth: Any, transport: Any, context: Any,
        object_identity: Any, object_type: Any, next_cmd: Any,
        oid: str,
    ) -> Any | None:
        """GET a single scalar OID value."""
        iterator = next_cmd(
            engine, auth, transport, context,
            object_type(object_identity(oid)),
            lexicographicMode=False,
        )
        for error_indication, error_status, _error_index, var_binds in iterator:
            if error_indication or error_status:
                return None
            for _oid, val in var_binds:
                return val
        return None

    @staticmethod
    def _snmp_walk_values(
        engine: Any, auth: Any, transport: Any, context: Any,
        object_identity: Any, object_type: Any, next_cmd: Any,
        oid: str,
    ) -> list[float]:
        """Walk a table OID and return numeric values."""
        values: list[float] = []
        iterator = next_cmd(
            engine, auth, transport, context,
            object_type(object_identity(oid)),
            lexicographicMode=False,
        )
        for error_indication, error_status, _error_index, var_binds in iterator:
            if error_indication or error_status:
                break
            for _oid, val in var_binds:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass
        return values

    @staticmethod
    def _snmp_walk_sum(
        engine: Any, auth: Any, transport: Any, context: Any,
        object_identity: Any, object_type: Any, next_cmd: Any,
        oid: str,
    ) -> float | None:
        """Walk a table OID and return the sum of numeric values."""
        values = SNMPCollector._snmp_walk_values(
            engine, auth, transport, context,
            object_identity, object_type, next_cmd,
            oid,
        )
        return sum(values) if values else None

    @staticmethod
    def _snmp_walk_indexed(
        engine: Any, auth: Any, transport: Any, context: Any,
        object_identity: Any, object_type: Any, next_cmd: Any,
        oid: str,
    ) -> dict[str, Any]:
        """Walk a table OID and return {last-index-component: value}."""
        indexed: dict[str, Any] = {}
        iterator = next_cmd(
            engine, auth, transport, context,
            object_type(object_identity(oid)),
            lexicographicMode=False,
        )
        for error_indication, error_status, _error_index, var_binds in iterator:
            if error_indication or error_status:
                break
            for full_oid, val in var_binds:
                # Extract the last component of the OID as the index
                idx = str(full_oid).rsplit(".", maxsplit=1)[-1]
                indexed[idx] = val
        return indexed

    # ------------------------------------------------------------------
    # Discovery and connection testing
    # ------------------------------------------------------------------

    def _discover_snmp(self) -> list[str]:
        """Query sysDescr on each endpoint to discover what is there."""
        from energy_audit.pro import check_dependency
        check_dependency("pysnmp", "pip install -e '.[pro-snmp]'")

        from pysnmp.hlapi import (
            CommunityData,
            ContextData,
            ObjectIdentity,
            ObjectType,
            SnmpEngine,
            UdpTransportTarget,
            nextCmd,
        )

        community = self.options.get("community", "public")
        port = self.options.get("port", 161)
        mp_model = 0 if self.options.get("version", "2c") == "1" else 1

        results: list[str] = []
        for endpoint in self.endpoints:
            engine = SnmpEngine()
            auth = CommunityData(community, mpModel=mp_model)
            transport = UdpTransportTarget(
                (endpoint, port), timeout=self.timeout, retries=self.retries,
            )
            context = ContextData()

            descr = self._snmp_get_scalar(
                engine, auth, transport, context,
                ObjectIdentity, ObjectType, nextCmd,
                SYS_DESCR_OID,
            )
            if descr:
                results.append(f"{endpoint}: {descr}")
            else:
                results.append(f"{endpoint}: no response")
        return results

    def _test_snmp_connection(self) -> bool:
        """Attempt a sysDescr GET on the first endpoint."""
        from energy_audit.pro import check_dependency
        check_dependency("pysnmp", "pip install -e '.[pro-snmp]'")

        from pysnmp.hlapi import (
            CommunityData,
            ContextData,
            ObjectIdentity,
            ObjectType,
            SnmpEngine,
            UdpTransportTarget,
            nextCmd,
        )

        if not self.endpoints:
            return False

        community = self.options.get("community", "public")
        port = self.options.get("port", 161)
        mp_model = 0 if self.options.get("version", "2c") == "1" else 1

        endpoint = self.endpoints[0]
        engine = SnmpEngine()
        auth = CommunityData(community, mpModel=mp_model)
        transport = UdpTransportTarget(
            (endpoint, port), timeout=self.timeout, retries=self.retries,
        )
        context = ContextData()

        result = self._snmp_get_scalar(
            engine, auth, transport, context,
            ObjectIdentity, ObjectType, nextCmd,
            SYS_DESCR_OID,
        )
        return result is not None


# ---------------------------------------------------------------------------
# Self-register
# ---------------------------------------------------------------------------
register_collector("snmp", SNMPCollector)
