# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Azure VM cloud collector.

Collects virtual-machine metadata and utilisation metrics from Azure.
In *simulate* mode (the default) realistic fake data is generated.  In
*live* mode the collector uses **azure-identity**, **azure-mgmt-compute**,
and **azure-monitor-query** to enumerate VMs and pull metrics.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from energy_audit.pro.collectors import register_collector
from energy_audit.pro.collectors.base import CollectorResult, RawEnergyReading, RawServerData
from energy_audit.pro.collectors.cloud.power_models import AZURE_VM_POWER, estimate_power
from energy_audit.pro.config import CollectorSourceConfig


# ---------------------------------------------------------------------------
# Simulated VM catalogue
# ---------------------------------------------------------------------------

_SIM_VM_SIZES: list[str] = [
    "Standard_B1s", "Standard_B1ms", "Standard_B2s", "Standard_B2ms",
    "Standard_B4ms", "Standard_B8ms",
    "Standard_D2s_v5", "Standard_D4s_v5", "Standard_D8s_v5",
    "Standard_D16s_v5", "Standard_D32s_v5",
    "Standard_E2s_v5", "Standard_E4s_v5", "Standard_E8s_v5",
    "Standard_E16s_v5", "Standard_E32s_v5",
    "Standard_F2s_v2", "Standard_F4s_v2", "Standard_F8s_v2",
    "Standard_F16s_v2",
    "Standard_NC6s_v3", "Standard_NC12s_v3", "Standard_NC24s_v3",
    "Standard_NC4as_T4_v3", "Standard_NC8as_T4_v3",
    "Standard_ND40rs_v2",
    "Standard_NV6", "Standard_NV12",
]

_SIM_REGIONS: list[str] = [
    "eastus", "westus2", "westeurope", "southeastasia",
]


def _server_type_hint_for(vm_size: str) -> str:
    """Derive a server_type_hint from the Azure VM size prefix."""
    lower = vm_size.lower()
    if "_nd" in lower:
        return "gpu_training"
    if "_nc" in lower or "_nv" in lower:
        return "gpu_inference"
    if "_l" in lower:
        return "storage"
    return "cpu"


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class AzureCollector:
    """Collect VM data from Azure or via simulation."""

    def __init__(self, config: CollectorSourceConfig) -> None:
        self.config = config
        self.options: dict[str, Any] = config.options
        self._simulate = self.options.get("simulate", True)
        self._subscription_id: str = self.options.get("subscription_id", "")
        self._resource_group: str | None = self.options.get("resource_group")
        self._region = self.options.get("region", "eastus")
        self._seed: int | None = self.options.get("seed")

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

    def collect(self) -> CollectorResult:
        """Run data collection and return raw data."""
        if self._simulate:
            return self._collect_simulated()
        return self._collect_live()

    def discover(self) -> list[str]:
        """List available Azure VMs."""
        if self._simulate:
            return [f"[simulate] Would discover Azure VMs in subscription {self._subscription_id}"]
        return self._discover_live()

    def test_connection(self) -> bool:
        """Verify Azure credentials are valid."""
        if self._simulate:
            return True
        return self._test_live()

    # ------------------------------------------------------------------
    # Simulated collection
    # ------------------------------------------------------------------

    def _collect_simulated(self) -> CollectorResult:
        rng = random.Random(self._seed)
        count = rng.randint(10, 20)

        region = self._region
        resource_group = self._resource_group or f"rg-{region}-prod"

        servers: list[RawServerData] = []
        energy_readings: list[RawEnergyReading] = []
        warnings: list[str] = []

        now = datetime.now(tz=timezone.utc)

        for i in range(count):
            vm_size = rng.choice(_SIM_VM_SIZES)
            vm_name = f"vm-{rng.choice(['web', 'api', 'worker', 'ml', 'db', 'cache'])}-{rng.randint(1, 99):02d}"

            cpu_util = round(rng.uniform(0.03, 0.90), 3)
            mem_util = round(rng.uniform(0.12, 0.85), 3)

            # GPU utilisation only for N-series
            gpu_util: float | None = None
            lower = vm_size.lower()
            if "_nc" in lower or "_nd" in lower or "_nv" in lower:
                gpu_util = round(rng.uniform(0.08, 0.93), 3)

            power_watts = estimate_power("azure", vm_size)
            effective_power = round(power_watts * (0.3 + 0.7 * cpu_util), 1)

            resource_id = (
                f"/subscriptions/{self._subscription_id or 'sim-sub-001'}"
                f"/resourceGroups/{resource_group}"
                f"/providers/Microsoft.Compute/virtualMachines/{vm_name}"
            )

            server = RawServerData(
                hostname=vm_name,
                ip_address=f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
                server_type_hint=_server_type_hint_for(vm_size),
                power_watts=effective_power,
                tdp_watts=power_watts,
                cpu_utilization=cpu_util,
                gpu_utilization=gpu_util,
                memory_utilization=mem_util,
                model=vm_size,
                rack_id=region,
                tags={
                    "cloud": "azure",
                    "vm_size": vm_size,
                    "resource_group": resource_group,
                    "region": region,
                    "resource_id": resource_id,
                },
            )
            servers.append(server)

        # Aggregate energy reading
        total_it_kw = sum(s.power_watts for s in servers if s.power_watts) / 1000.0
        energy_readings.append(RawEnergyReading(
            timestamp=now,
            it_power_kw=round(total_it_kw, 3),
            total_power_kw=round(total_it_kw * 1.1, 3),
        ))

        warnings.append(
            f"Simulated {count} Azure VMs in {region} "
            f"(seed={self._seed})"
        )

        return CollectorResult(
            source_type="azure",
            servers=servers,
            energy_readings=energy_readings,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Live Azure collection
    # ------------------------------------------------------------------

    def _collect_live(self) -> CollectorResult:
        from energy_audit.pro import check_dependency
        check_dependency("azure.identity", "pip install azure-identity")
        check_dependency("azure.mgmt.compute", "pip install azure-mgmt-compute")
        check_dependency("azure.monitor.query", "pip install azure-monitor-query")

        from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
        from azure.mgmt.compute import ComputeManagementClient  # type: ignore[import-untyped]
        from azure.monitor.query import MetricsQueryClient  # type: ignore[import-untyped]

        errors: list[str] = []
        warnings: list[str] = []
        servers: list[RawServerData] = []
        energy_readings: list[RawEnergyReading] = []

        try:
            credential = DefaultAzureCredential()
            compute_client = ComputeManagementClient(credential, self._subscription_id)
            metrics_client = MetricsQueryClient(credential)

            now = datetime.now(tz=timezone.utc)

            if self._resource_group:
                vm_list = compute_client.virtual_machines.list(self._resource_group)
            else:
                vm_list = compute_client.virtual_machines.list_all()

            for vm in vm_list:
                server = self._parse_azure_vm(vm, metrics_client, now)
                if server is not None:
                    servers.append(server)

            if servers:
                total_it_kw = sum(s.power_watts for s in servers if s.power_watts) / 1000.0
                energy_readings.append(RawEnergyReading(
                    timestamp=now,
                    it_power_kw=round(total_it_kw, 3),
                    total_power_kw=round(total_it_kw * 1.1, 3),
                ))

        except ImportError:
            raise
        except Exception as exc:
            errors.append(f"Azure collection error: {exc}")

        return CollectorResult(
            source_type="azure",
            servers=servers,
            energy_readings=energy_readings,
            errors=errors,
            warnings=warnings,
        )

    def _parse_azure_vm(
        self,
        vm: Any,
        metrics_client: Any,
        now: datetime,
    ) -> RawServerData | None:
        """Convert an Azure VM object into RawServerData."""
        vm_name: str = vm.name
        vm_size: str = vm.hardware_profile.vm_size
        location: str = vm.location
        resource_id: str = vm.id

        cpu_util = self._get_azure_metric(
            metrics_client, resource_id,
            "Percentage CPU", now, period_minutes=30,
        )

        power_watts = estimate_power("azure", vm_size)
        effective_power = power_watts
        if cpu_util is not None:
            effective_power = round(power_watts * (0.3 + 0.7 * cpu_util), 1)

        azure_tags: dict[str, str] = {}
        if vm.tags:
            azure_tags = {f"azure_tag_{k}": v for k, v in vm.tags.items()}

        return RawServerData(
            hostname=vm_name,
            server_type_hint=_server_type_hint_for(vm_size),
            power_watts=effective_power,
            tdp_watts=power_watts,
            cpu_utilization=cpu_util,
            model=vm_size,
            rack_id=location,
            tags={
                "cloud": "azure",
                "vm_size": vm_size,
                "region": location,
                "resource_id": resource_id,
                **azure_tags,
            },
        )

    @staticmethod
    def _get_azure_metric(
        metrics_client: Any,
        resource_uri: str,
        metric_name: str,
        now: datetime,
        *,
        period_minutes: int = 30,
    ) -> float | None:
        """Fetch the average of an Azure Monitor metric over the recent window."""
        from datetime import timedelta

        try:
            response = metrics_client.query_resource(
                resource_uri,
                metric_names=[metric_name],
                timespan=timedelta(minutes=period_minutes),
            )
            for metric in response.metrics:
                for ts_element in metric.timeseries:
                    for data_point in reversed(ts_element.data):
                        if data_point.average is not None:
                            return round(data_point.average / 100.0, 4)
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Live helpers
    # ------------------------------------------------------------------

    def _discover_live(self) -> list[str]:
        from energy_audit.pro import check_dependency
        check_dependency("azure.identity", "pip install azure-identity")
        check_dependency("azure.mgmt.compute", "pip install azure-mgmt-compute")

        from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
        from azure.mgmt.compute import ComputeManagementClient  # type: ignore[import-untyped]

        credential = DefaultAzureCredential()
        compute_client = ComputeManagementClient(credential, self._subscription_id)

        results: list[str] = []
        if self._resource_group:
            vm_list = compute_client.virtual_machines.list(self._resource_group)
        else:
            vm_list = compute_client.virtual_machines.list_all()

        for vm in vm_list:
            vm_size = vm.hardware_profile.vm_size
            results.append(f"{vm.name}: {vm_size} ({vm.location})")
        return results

    def _test_live(self) -> bool:
        from energy_audit.pro import check_dependency
        check_dependency("azure.identity", "pip install azure-identity")
        check_dependency("azure.mgmt.compute", "pip install azure-mgmt-compute")

        from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
        from azure.mgmt.compute import ComputeManagementClient  # type: ignore[import-untyped]

        try:
            credential = DefaultAzureCredential()
            compute_client = ComputeManagementClient(credential, self._subscription_id)
            # Attempt a lightweight call to verify credentials
            next(iter(compute_client.virtual_machines.list_all()), None)
            return True
        except Exception:
            return False


# Self-register
register_collector("azure", AzureCollector)
