# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Simulated data center generator.

Given a :class:`DCProfile` and an optional random seed, this module
generates a complete :class:`DataCenter` instance with realistic
servers, racks, workloads, energy readings, and cooling systems.

All randomness flows through a seeded :class:`numpy.random.Generator`
so that identical seeds always produce identical data centers.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np

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
from energy_audit.data.profiles import DCProfile


def _uid() -> str:
    """Return a short unique id string."""
    return uuid.uuid4().hex[:8]


class DataCenterGenerator:
    """Generate a fully-populated :class:`DataCenter` from a profile.

    Parameters
    ----------
    profile:
        The data-center profile that governs all generation parameters.
    seed:
        Optional RNG seed for reproducibility.  When *None*, a random
        seed is chosen by NumPy.
    """

    def __init__(self, profile: DCProfile, seed: int | None = None) -> None:
        self.profile = profile
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> DataCenter:
        """Orchestrate full data center generation and return the result."""
        config = self._build_config()
        servers = self._generate_servers()
        racks = self._generate_racks(servers)
        cooling_systems = self._generate_cooling_systems()
        workloads = self._generate_workloads(servers)
        energy_readings = self._generate_energy_readings(servers)

        return DataCenter(
            config=config,
            servers=servers,
            racks=racks,
            workloads=workloads,
            energy_readings=energy_readings,
            cooling_systems=cooling_systems,
        )

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _build_config(self) -> DataCenterConfig:
        p = self.profile
        return DataCenterConfig(
            name=p.name,
            location=p.location,
            region=p.region,
            pue_target=p.pue_target,
            cooling_type=p.cooling_type,
            total_power_capacity_mw=p.total_power_capacity_mw,
            energy_cost_per_kwh=p.energy_cost_per_kwh,
            renewable_percentage=p.renewable_percentage,
            ppa_available=p.ppa_available,
            carbon_intensity_gco2_per_kwh=p.carbon_intensity,
            energy_source=p.energy_source,
        )

    # ------------------------------------------------------------------
    # Servers
    # ------------------------------------------------------------------

    def _generate_servers(self) -> list[Server]:
        p = self.profile
        n = p.server_count

        # Decide how many of each server type
        n_gpu = int(round(n * p.gpu_percentage))
        n_gpu_train = int(round(n_gpu * p.gpu_training_ratio))
        n_gpu_infer = n_gpu - n_gpu_train
        n_storage = max(1, int(round(n * 0.05)))  # ~5% storage nodes
        n_cpu = n - n_gpu - n_storage

        # Build ordered list of (server_type, count) batches
        batches: list[tuple[ServerType, int]] = [
            (ServerType.cpu, n_cpu),
            (ServerType.gpu_training, n_gpu_train),
            (ServerType.gpu_inference, n_gpu_infer),
            (ServerType.storage, n_storage),
        ]

        # Decide which indices are zombies / overprovisioned
        zombie_count = int(round(n * p.zombie_rate))
        overprov_count = int(round(n * p.overprov_rate))

        # Pick zombie and overprov indices from the full population.
        # A server can only be one of zombie or overprovisioned.
        all_indices = self.rng.permutation(n)
        zombie_indices = set(all_indices[:zombie_count].tolist())
        overprov_indices = set(
            all_indices[zombie_count: zombie_count + overprov_count].tolist()
        )

        servers: list[Server] = []
        idx = 0

        for stype, count in batches:
            for seq in range(count):
                is_zombie = idx in zombie_indices
                is_overprov = idx in overprov_indices

                server = self._make_server(
                    stype, seq, is_zombie, is_overprov
                )
                servers.append(server)
                idx += 1

        return servers

    def _make_server(
        self,
        stype: ServerType,
        seq: int,
        is_zombie: bool,
        is_overprov: bool,
    ) -> Server:
        """Create a single server with realistic power/utilization numbers."""
        rng = self.rng
        p = self.profile

        # --- naming --------------------------------------------------
        prefix_map = {
            ServerType.cpu: "srv-cpu",
            ServerType.gpu_training: "srv-gpu-t",
            ServerType.gpu_inference: "srv-gpu-i",
            ServerType.storage: "srv-stor",
        }
        name = f"{prefix_map[stype]}-{seq + 1:03d}"

        # --- TDP (max thermal design power) --------------------------
        if stype == ServerType.cpu:
            tdp = float(np.clip(rng.normal(250, 50), 150, 350))
            mem_total = float(rng.choice([64, 128, 256]))
        elif stype == ServerType.gpu_training:
            tdp = float(np.clip(rng.normal(950, 125), 700, 1200))
            mem_total = float(rng.choice([256, 512, 1024]))
        elif stype == ServerType.gpu_inference:
            tdp = float(np.clip(rng.normal(400, 50), 300, 500))
            mem_total = float(rng.choice([128, 256, 512]))
        else:  # storage
            tdp = float(np.clip(rng.normal(150, 25), 100, 200))
            mem_total = float(rng.choice([32, 64, 128]))

        # --- utilization (as 0.0-1.0 fractions) ----------------------
        if is_zombie:
            cpu_util = float(rng.uniform(0.0, 0.05))
            mem_util = float(rng.uniform(0.0, 0.10))
            gpu_util = float(rng.uniform(0.0, 0.02)) if stype in (
                ServerType.gpu_training, ServerType.gpu_inference
            ) else 0.0
        elif is_overprov:
            cpu_util = float(rng.uniform(0.05, 0.20))
            mem_util = float(rng.uniform(0.70, 0.95))
            gpu_util = float(rng.uniform(0.05, 0.15)) if stype in (
                ServerType.gpu_training, ServerType.gpu_inference
            ) else 0.0
        else:
            if stype == ServerType.cpu:
                cpu_util = float(np.clip(rng.beta(2, 3) * 0.80 + 0.05, 0.05, 0.85))
                mem_util = float(rng.uniform(0.20, 0.75))
                gpu_util = 0.0
            elif stype == ServerType.gpu_training:
                cpu_util = float(rng.uniform(0.30, 0.70))
                mem_util = float(rng.uniform(0.50, 0.90))
                gpu_util = float(rng.uniform(0.40, 0.99))
            elif stype == ServerType.gpu_inference:
                cpu_util = float(rng.uniform(0.15, 0.50))
                mem_util = float(rng.uniform(0.30, 0.70))
                gpu_util = float(rng.uniform(0.15, 0.80))
            else:  # storage
                cpu_util = float(rng.uniform(0.05, 0.30))
                mem_util = float(rng.uniform(0.10, 0.40))
                gpu_util = 0.0

        # Current power proportional to utilization against TDP.
        # Idle power ~30% of TDP; active power scales linearly to TDP.
        effective_util = max(cpu_util, gpu_util) if gpu_util > 0 else cpu_util
        current_power = tdp * (0.30 + 0.70 * effective_util)

        # --- age and warranty ----------------------------------------
        age_months = int(rng.integers(p.min_server_age_months, p.max_server_age_months + 1))
        warranty_months = 60 if rng.random() < 0.3 else 36

        mem_allocated = mem_total * mem_util

        return Server(
            id=_uid(),
            name=name,
            server_type=stype,
            tdp_watts=round(tdp, 1),
            current_power_watts=round(current_power, 1),
            cpu_utilization=round(cpu_util, 4),
            gpu_utilization=round(gpu_util, 4),
            memory_utilization=round(mem_util, 4),
            memory_allocated_gb=round(mem_allocated, 1),
            memory_total_gb=mem_total,
            age_months=age_months,
            warranty_months=warranty_months,
            is_zombie=is_zombie,
            is_overprovisioned=is_overprov,
        )

    # ------------------------------------------------------------------
    # Racks
    # ------------------------------------------------------------------

    def _generate_racks(self, servers: list[Server]) -> list[Rack]:
        p = self.profile
        rng = self.rng

        # Separate servers by broad category (GPU vs non-GPU)
        gpu_servers = [
            s for s in servers
            if s.server_type in (ServerType.gpu_training, ServerType.gpu_inference)
        ]
        non_gpu_servers = [
            s for s in servers
            if s.server_type not in (ServerType.gpu_training, ServerType.gpu_inference)
        ]

        # Decide rack split: roughly proportional to server counts
        total = len(servers)
        gpu_rack_count = (
            max(1, int(round(p.rack_count * len(gpu_servers) / total)))
            if gpu_servers else 0
        )
        cpu_rack_count = p.rack_count - gpu_rack_count

        racks: list[Rack] = []

        # Distribute non-GPU servers across CPU racks
        racks.extend(
            self._assign_servers_to_racks(
                non_gpu_servers,
                cpu_rack_count,
                prefix="rack-cpu",
                max_power_kw=8.0,
            )
        )

        # Distribute GPU servers across GPU racks
        if gpu_servers:
            racks.extend(
                self._assign_servers_to_racks(
                    gpu_servers,
                    gpu_rack_count,
                    prefix="rack-gpu",
                    max_power_kw=30.0,
                )
            )

        # Fill in thermal readings for each rack
        for rack in racks:
            inlet = float(rng.uniform(18.0, 27.0))
            delta = float(rng.uniform(8.0, 15.0))
            rack.inlet_temp_celsius = round(inlet, 1)
            rack.outlet_temp_celsius = round(inlet + delta, 1)

        return racks

    def _assign_servers_to_racks(
        self,
        servers: list[Server],
        rack_count: int,
        *,
        prefix: str,
        max_power_kw: float,
    ) -> list[Rack]:
        """Distribute *servers* across *rack_count* racks."""
        if rack_count == 0:
            return []

        # Round-robin assignment
        assignments: list[list[Server]] = [[] for _ in range(rack_count)]
        for i, srv in enumerate(servers):
            assignments[i % rack_count].append(srv)

        racks: list[Rack] = []
        for seq, group in enumerate(assignments):
            current_power_kw = sum(s.current_power_watts for s in group) / 1000.0
            rack_id = _uid()
            # Update server rack_id references
            for s in group:
                s.rack_id = rack_id
            racks.append(
                Rack(
                    id=rack_id,
                    name=f"{prefix}-{seq + 1:03d}",
                    server_ids=[s.id for s in group],
                    max_power_kw=max_power_kw,
                    current_power_kw=round(current_power_kw, 2),
                )
            )
        return racks

    # ------------------------------------------------------------------
    # Workloads
    # ------------------------------------------------------------------

    def _generate_workloads(self, servers: list[Server]) -> list[Workload]:
        workloads: list[Workload] = []

        # Group servers by type
        by_type: dict[ServerType, list[Server]] = {}
        for s in servers:
            by_type.setdefault(s.server_type, []).append(s)

        # GPU training workloads
        train_servers = by_type.get(ServerType.gpu_training, [])
        if train_servers:
            workloads.extend(
                self._cluster_workloads(
                    train_servers,
                    WorkloadType.ai_training,
                    group_min=2,
                    group_max=16,
                    name_prefix="wl-train",
                    is_schedulable=True,
                    priority=2,
                )
            )

        # GPU inference workloads
        infer_servers = by_type.get(ServerType.gpu_inference, [])
        if infer_servers:
            workloads.extend(
                self._cluster_workloads(
                    infer_servers,
                    WorkloadType.ai_inference,
                    group_min=1,
                    group_max=4,
                    name_prefix="wl-infer",
                    is_schedulable=False,
                    priority=1,
                )
            )

        # CPU workloads
        cpu_servers = by_type.get(ServerType.cpu, [])
        if cpu_servers:
            splits = self._split_list(cpu_servers, [0.40, 0.30, 0.30])
            wl_types = [
                (WorkloadType.general_compute, "wl-compute", True, 3),
                (WorkloadType.database, "wl-db", False, 1),
                (WorkloadType.web_serving, "wl-web", False, 2),
            ]
            for srv_group, (wtype, prefix, schedulable, prio) in zip(splits, wl_types):
                if srv_group:
                    workloads.extend(
                        self._cluster_workloads(
                            srv_group,
                            wtype,
                            group_min=1,
                            group_max=8,
                            name_prefix=prefix,
                            is_schedulable=schedulable,
                            priority=prio,
                        )
                    )

        # Storage workloads
        stor_servers = by_type.get(ServerType.storage, [])
        if stor_servers:
            workloads.extend(
                self._cluster_workloads(
                    stor_servers,
                    WorkloadType.storage,
                    group_min=1,
                    group_max=4,
                    name_prefix="wl-stor",
                    is_schedulable=False,
                    priority=4,
                )
            )

        return workloads

    def _cluster_workloads(
        self,
        servers: list[Server],
        wtype: WorkloadType,
        *,
        group_min: int,
        group_max: int,
        name_prefix: str,
        is_schedulable: bool,
        priority: int,
    ) -> list[Workload]:
        """Break *servers* into workload groups."""
        remaining = list(servers)
        workloads: list[Workload] = []
        seq = 0

        while remaining:
            max_size = min(group_max, len(remaining))
            min_size = min(group_min, max_size)
            if min_size == max_size:
                size = min_size
            else:
                size = int(self.rng.integers(min_size, max_size + 1))
            group = remaining[:size]
            remaining = remaining[size:]
            seq += 1

            power_kw = sum(s.current_power_watts for s in group) / 1000.0
            workloads.append(
                Workload(
                    id=_uid(),
                    name=f"{name_prefix}-{seq:03d}",
                    workload_type=wtype,
                    server_ids=[s.id for s in group],
                    power_consumption_kw=round(power_kw, 3),
                    is_schedulable=is_schedulable,
                    priority=priority,
                )
            )

        return workloads

    def _split_list(
        self, items: list, fractions: list[float]
    ) -> list[list]:
        """Split *items* into sub-lists according to *fractions*."""
        result: list[list] = []
        start = 0
        for i, frac in enumerate(fractions):
            if i == len(fractions) - 1:
                result.append(items[start:])
            else:
                end = start + int(round(len(items) * frac))
                result.append(items[start:end])
                start = end
        return result

    # ------------------------------------------------------------------
    # Energy readings
    # ------------------------------------------------------------------

    def _generate_energy_readings(
        self,
        servers: list[Server],
    ) -> list[EnergyReading]:
        rng = self.rng
        p = self.profile

        # Base IT power (kW)
        it_power_kw = sum(s.current_power_watts for s in servers) / 1000.0

        # Derived overhead factors
        cooling_factor = (p.pue_target - 1.0) * 0.7
        lighting_factor = 0.02
        ups_loss_factor = 0.05

        # 720 readings = 30 days x 24 hours
        num_readings = 720
        base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        readings: list[EnergyReading] = []

        for i in range(num_readings):
            ts = base_time + timedelta(hours=i)
            hour = ts.hour

            # Diurnal multiplier: peak at 14:00, trough at 04:00
            diurnal = 1.0 + 0.15 * math.sin(2 * math.pi * (hour - 4) / 24.0)

            # Per-reading noise +/- 3%
            noise = 1.0 + float(rng.uniform(-0.03, 0.03))

            multiplier = diurnal * noise

            it_kw = it_power_kw * multiplier
            cooling_kw = it_kw * cooling_factor
            lighting_kw = it_kw * lighting_factor
            ups_loss_kw = it_kw * ups_loss_factor

            total_kw = it_kw + cooling_kw + lighting_kw + ups_loss_kw

            readings.append(
                EnergyReading(
                    timestamp=ts,
                    it_equipment_power_kw=round(it_kw, 3),
                    cooling_power_kw=round(cooling_kw, 3),
                    lighting_power_kw=round(lighting_kw, 3),
                    ups_loss_kw=round(ups_loss_kw, 3),
                    total_facility_power_kw=round(total_kw, 3),
                )
            )

        return readings

    # ------------------------------------------------------------------
    # Cooling systems
    # ------------------------------------------------------------------

    def _generate_cooling_systems(self) -> list[CoolingSystem]:
        p = self.profile

        systems: list[CoolingSystem] = []

        if p.cooling_type == "air":
            systems.extend(self._make_cooling_units("air", count=max(1, p.rack_count // 4)))
        elif p.cooling_type == "liquid":
            systems.extend(self._make_cooling_units("liquid", count=max(1, p.rack_count // 8)))
        elif p.cooling_type == "hybrid":
            n_air = max(1, int(round(p.rack_count * 0.6 / 4)))
            n_liquid = max(1, int(round(p.rack_count * 0.4 / 8)))
            systems.extend(self._make_cooling_units("air", count=n_air))
            systems.extend(self._make_cooling_units("liquid", count=n_liquid))
        else:
            systems.extend(self._make_cooling_units("air", count=max(1, p.rack_count // 4)))

        return systems

    def _make_cooling_units(
        self, kind: str, count: int
    ) -> list[CoolingSystem]:
        rng = self.rng
        units: list[CoolingSystem] = []

        for seq in range(count):
            if kind == "air":
                cop = float(rng.uniform(2.0, 4.0))
                capacity_kw = float(rng.uniform(30.0, 80.0))
            else:  # liquid
                cop = float(rng.uniform(4.0, 6.0))
                capacity_kw = float(rng.uniform(80.0, 250.0))

            load_fraction = float(rng.uniform(0.50, 0.85))
            current_load_kw = capacity_kw * load_fraction

            units.append(
                CoolingSystem(
                    id=_uid(),
                    name=f"cool-{kind}-{seq + 1:03d}",
                    cooling_type=CoolingType(kind),
                    cop=round(cop, 2),
                    capacity_kw=round(capacity_kw, 1),
                    current_load_kw=round(current_load_kw, 1),
                )
            )

        return units
