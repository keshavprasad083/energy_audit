# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Map raw collector data to the core DataCenter model.

This is the bridge between the pro data ingestion layer and the
core scoring/analysis/reporting pipeline. The mapper merges data
from multiple collectors, fills missing fields with sensible defaults,
and validates the result against the Pydantic DataCenter contract.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from energy_audit.data.models import (
    CoolingSystem,
    CoolingType,
    DataCenter,
    DataCenterConfig,
    EnergyReading,
    Rack,
    Server,
    ServerType,
    Workload,
    WorkloadType,
)
from energy_audit.pro.collectors.base import (
    CollectorResult,
    RawCoolingData,
    RawEnergyReading,
    RawServerData,
)
from energy_audit.pro.config import FacilityConfig


def _uid() -> str:
    return uuid.uuid4().hex[:8]


# Default TDP by server type (same ranges as the generator)
_DEFAULT_TDP: dict[str, float] = {
    "cpu": 250.0,
    "gpu_training": 950.0,
    "gpu_inference": 450.0,
    "storage": 150.0,
}

_SERVER_TYPE_MAP: dict[str, ServerType] = {
    "cpu": ServerType.cpu,
    "gpu_training": ServerType.gpu_training,
    "gpu_inference": ServerType.gpu_inference,
    "gpu": ServerType.gpu_training,
    "storage": ServerType.storage,
}

_WORKLOAD_TYPE_MAP: dict[ServerType, WorkloadType] = {
    ServerType.cpu: WorkloadType.general_compute,
    ServerType.gpu_training: WorkloadType.ai_training,
    ServerType.gpu_inference: WorkloadType.ai_inference,
    ServerType.storage: WorkloadType.storage,
}


class DataCenterMapper:
    """Maps raw collector results to the core ``DataCenter`` model."""

    def __init__(self, facility: FacilityConfig) -> None:
        self.facility = facility

    def map(self, results: list[CollectorResult]) -> DataCenter:
        """Merge all collector results and produce a ``DataCenter``."""
        # 1. Merge raw server data (deduplicate by hostname)
        merged_servers = self._merge_servers(results)

        # 2. Build Server model instances
        servers = [self._build_server(raw) for raw in merged_servers]

        # 3. Build racks (from rack_id tags or synthesize)
        racks = self._build_racks(servers, merged_servers)

        # 4. Build energy readings (merge + interpolate)
        energy_readings = self._build_energy_readings(results, servers)

        # 5. Build cooling systems
        cooling_systems = self._build_cooling_systems(results, servers)

        # 6. Build workloads (group by server type)
        workloads = self._build_workloads(servers)

        # 7. Build config
        config = self._build_config()

        dc = DataCenter(
            config=config,
            servers=servers,
            racks=racks,
            workloads=workloads,
            energy_readings=energy_readings,
            cooling_systems=cooling_systems,
        )

        return dc

    # ------------------------------------------------------------------
    # Server merging and building
    # ------------------------------------------------------------------

    def _merge_servers(
        self, results: list[CollectorResult]
    ) -> list[RawServerData]:
        """Merge server data from multiple collectors, deduplicating by hostname."""
        by_host: dict[str, RawServerData] = {}

        for result in results:
            for raw in result.servers:
                key = raw.hostname.lower()
                if key in by_host:
                    existing = by_host[key]
                    by_host[key] = self._merge_raw_server(existing, raw)
                else:
                    by_host[key] = raw

        return list(by_host.values())

    @staticmethod
    def _merge_raw_server(a: RawServerData, b: RawServerData) -> RawServerData:
        """Merge two raw server records, preferring non-None from *b*."""
        data = a.model_dump()
        for key, val in b.model_dump().items():
            if val is not None and key != "hostname":
                data[key] = val
        return RawServerData.model_validate(data)

    def _build_server(self, raw: RawServerData) -> Server:
        """Convert a RawServerData to a core Server model."""
        stype = _SERVER_TYPE_MAP.get(
            (raw.server_type_hint or "cpu").lower(), ServerType.cpu
        )
        tdp = raw.tdp_watts or _DEFAULT_TDP.get(stype.value, 250.0)
        cpu_util = raw.cpu_utilization or 0.0
        gpu_util = raw.gpu_utilization or 0.0
        mem_util = raw.memory_utilization or 0.0

        # Compute memory utilization from used/total if available
        if mem_util == 0.0 and raw.memory_used_gb and raw.memory_total_gb:
            mem_util = min(raw.memory_used_gb / raw.memory_total_gb, 1.0)

        # Estimate power if not provided
        power = raw.power_watts
        if power is None:
            effective_util = max(cpu_util, gpu_util)
            power = tdp * (0.30 + 0.70 * effective_util)

        # Zombie detection: powered on but very low utilization
        is_zombie = cpu_util < 0.05 and gpu_util < 0.05 and power > 50

        # Overprovisioned: high memory allocation but low CPU
        is_overprov = mem_util > 0.7 and cpu_util < 0.20

        age = raw.age_months or 24
        warranty = raw.warranty_months or 60

        return Server(
            id=_uid(),
            name=raw.hostname,
            server_type=stype,
            rack_id=raw.rack_id or "",
            tdp_watts=tdp,
            current_power_watts=power,
            cpu_utilization=cpu_util,
            gpu_utilization=gpu_util,
            memory_utilization=mem_util,
            memory_allocated_gb=raw.memory_used_gb or 0.0,
            memory_total_gb=raw.memory_total_gb or 0.0,
            age_months=age,
            warranty_months=warranty,
            is_zombie=is_zombie,
            is_overprovisioned=is_overprov,
        )

    # ------------------------------------------------------------------
    # Racks
    # ------------------------------------------------------------------

    def _build_racks(
        self, servers: list[Server], raw_servers: list[RawServerData]
    ) -> list[Rack]:
        """Build racks from rack_id assignments or synthesize them."""
        rack_map: dict[str, list[Server]] = defaultdict(list)

        # Group by rack_id
        for server, raw in zip(servers, raw_servers):
            rack_id = raw.rack_id or "default"
            rack_map[rack_id].append(server)

        # If everything is in "default", split into racks of ~20 servers
        if list(rack_map.keys()) == ["default"]:
            all_servers = rack_map["default"]
            rack_map = {}
            for i in range(0, len(all_servers), 20):
                rid = f"rack-{(i // 20) + 1:03d}"
                rack_map[rid] = all_servers[i : i + 20]

        cooling = CoolingType(self.facility.cooling_type)
        racks = []
        for rid, rack_servers in rack_map.items():
            power_kw = sum(s.current_power_watts for s in rack_servers) / 1000
            max_power = max(power_kw * 1.5, 10.0)
            racks.append(Rack(
                id=rid,
                name=f"Rack {rid}",
                location=f"Row A",
                max_power_kw=round(max_power, 2),
                current_power_kw=round(power_kw, 2),
                cooling_type=cooling,
                server_ids=[s.id for s in rack_servers],
                inlet_temp_celsius=22.0,
                outlet_temp_celsius=35.0,
            ))

        # Update server rack_id references
        for rack in racks:
            for sid in rack.server_ids:
                for s in servers:
                    if s.id == sid:
                        s.rack_id = rack.id

        return racks

    # ------------------------------------------------------------------
    # Energy readings
    # ------------------------------------------------------------------

    def _build_energy_readings(
        self, results: list[CollectorResult], servers: list[Server]
    ) -> list[EnergyReading]:
        """Build 720 hourly energy readings from collector data."""
        # Collect all raw readings
        raw_readings: list[RawEnergyReading] = []
        for result in results:
            raw_readings.extend(result.energy_readings)

        if raw_readings:
            return self._normalize_readings(raw_readings, servers)
        else:
            return self._synthesize_readings(servers)

    def _normalize_readings(
        self, raw: list[RawEnergyReading], servers: list[Server]
    ) -> list[EnergyReading]:
        """Normalize raw readings to 720 hourly entries."""
        raw.sort(key=lambda r: r.timestamp)

        # Estimate IT power from servers if not in readings
        it_power_estimate = sum(s.current_power_watts for s in servers) / 1000

        readings = []
        for r in raw[:720]:
            it_kw = r.it_power_kw or it_power_estimate
            total_kw = r.total_power_kw or (it_kw * self.facility.pue_target)
            cooling_kw = r.cooling_power_kw or (total_kw - it_kw) * 0.7
            lighting_kw = r.lighting_power_kw or (total_kw - it_kw) * 0.1
            ups_kw = r.ups_loss_kw or (total_kw - it_kw) * 0.2

            readings.append(EnergyReading(
                timestamp=r.timestamp,
                total_facility_power_kw=round(total_kw, 2),
                it_equipment_power_kw=round(it_kw, 2),
                cooling_power_kw=round(cooling_kw, 2),
                lighting_power_kw=round(lighting_kw, 2),
                ups_loss_kw=round(ups_kw, 2),
            ))

        # Pad to 720 if needed
        if len(readings) < 720:
            readings = self._pad_readings(readings, 720, servers)

        return readings[:720]

    def _synthesize_readings(self, servers: list[Server]) -> list[EnergyReading]:
        """Generate 720 synthetic readings when no real data is available."""
        it_power_kw = sum(s.current_power_watts for s in servers) / 1000
        pue = self.facility.pue_target
        total_kw = it_power_kw * pue
        cooling_kw = (total_kw - it_power_kw) * 0.7
        lighting_kw = (total_kw - it_power_kw) * 0.1
        ups_kw = (total_kw - it_power_kw) * 0.2

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=720)

        readings = []
        for h in range(720):
            ts = start + timedelta(hours=h)
            readings.append(EnergyReading(
                timestamp=ts,
                total_facility_power_kw=round(total_kw, 2),
                it_equipment_power_kw=round(it_power_kw, 2),
                cooling_power_kw=round(cooling_kw, 2),
                lighting_power_kw=round(lighting_kw, 2),
                ups_loss_kw=round(ups_kw, 2),
            ))

        return readings

    def _pad_readings(
        self, readings: list[EnergyReading], target: int, servers: list[Server]
    ) -> list[EnergyReading]:
        """Pad a list of readings to the target count by repeating the last entry."""
        if not readings:
            return self._synthesize_readings(servers)

        last = readings[-1]
        while len(readings) < target:
            ts = last.timestamp + timedelta(hours=len(readings))
            readings.append(EnergyReading(
                timestamp=ts,
                total_facility_power_kw=last.total_facility_power_kw,
                it_equipment_power_kw=last.it_equipment_power_kw,
                cooling_power_kw=last.cooling_power_kw,
                lighting_power_kw=last.lighting_power_kw,
                ups_loss_kw=last.ups_loss_kw,
            ))

        return readings

    # ------------------------------------------------------------------
    # Cooling systems
    # ------------------------------------------------------------------

    def _build_cooling_systems(
        self, results: list[CollectorResult], servers: list[Server]
    ) -> list[CoolingSystem]:
        """Build cooling systems from raw data or synthesize."""
        raw_cooling: list[RawCoolingData] = []
        for result in results:
            raw_cooling.extend(result.cooling_data)

        if raw_cooling:
            systems = []
            for rc in raw_cooling:
                ct = CoolingType(rc.cooling_type) if rc.cooling_type in ("air", "liquid", "hybrid") else CoolingType.air
                systems.append(CoolingSystem(
                    id=_uid(),
                    name=rc.name or f"Cooling-{_uid()}",
                    cooling_type=ct,
                    cop=rc.cop or 3.5,
                    capacity_kw=rc.capacity_kw or 500.0,
                    current_load_kw=rc.current_load_kw or 200.0,
                ))
            return systems

        # Synthesize a single cooling system
        total_power_kw = sum(s.current_power_watts for s in servers) / 1000
        ct = CoolingType(self.facility.cooling_type) if self.facility.cooling_type in ("air", "liquid", "hybrid") else CoolingType.air
        cop = {"air": 3.0, "liquid": 5.0, "hybrid": 4.0}.get(ct.value, 3.0)
        cooling_load = total_power_kw * 0.35

        return [CoolingSystem(
            id=_uid(),
            name="Primary Cooling",
            cooling_type=ct,
            cop=cop,
            capacity_kw=round(cooling_load * 1.5, 2),
            current_load_kw=round(cooling_load, 2),
        )]

    # ------------------------------------------------------------------
    # Workloads
    # ------------------------------------------------------------------

    def _build_workloads(self, servers: list[Server]) -> list[Workload]:
        """Group servers into workloads by type."""
        by_type: dict[ServerType, list[Server]] = defaultdict(list)
        for s in servers:
            by_type[s.server_type].append(s)

        workloads = []
        for stype, type_servers in by_type.items():
            wtype = _WORKLOAD_TYPE_MAP.get(stype, WorkloadType.general_compute)
            power = sum(s.current_power_watts for s in type_servers) / 1000
            workloads.append(Workload(
                id=_uid(),
                name=f"{wtype.value} workload",
                workload_type=wtype,
                server_ids=[s.id for s in type_servers],
                power_consumption_kw=round(power, 2),
                is_schedulable=wtype in (WorkloadType.ai_training, WorkloadType.database),
                priority=2 if wtype == WorkloadType.ai_training else 3,
            ))

        return workloads

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _build_config(self) -> DataCenterConfig:
        f = self.facility
        return DataCenterConfig(
            name=f.name,
            location=f.location,
            region=f.region,
            total_power_capacity_mw=f.total_power_capacity_mw,
            energy_cost_per_kwh=f.energy_cost_per_kwh,
            carbon_intensity_gco2_per_kwh=f.carbon_intensity_gco2_per_kwh,
            renewable_percentage=f.renewable_percentage,
            ppa_available=f.ppa_available,
            energy_source=f.energy_source,
            pue_target=f.pue_target,
            cooling_type=f.cooling_type,
        )
