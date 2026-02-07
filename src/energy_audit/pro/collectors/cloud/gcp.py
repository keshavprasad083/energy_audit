# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""GCP Compute Engine cloud collector.

Collects GCE instance metadata and utilisation metrics from Google Cloud.
In *simulate* mode (the default) realistic fake data is generated.  In
*live* mode the collector uses **google-cloud-compute** and
**google-cloud-monitoring** to enumerate instances and pull metrics.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from energy_audit.pro.collectors import register_collector
from energy_audit.pro.collectors.base import CollectorResult, RawEnergyReading, RawServerData
from energy_audit.pro.collectors.cloud.power_models import GCP_INSTANCE_POWER, estimate_power
from energy_audit.pro.config import CollectorSourceConfig


# ---------------------------------------------------------------------------
# Simulated instance catalogue
# ---------------------------------------------------------------------------

_SIM_MACHINE_TYPES: list[str] = [
    "e2-micro", "e2-small", "e2-medium",
    "e2-standard-2", "e2-standard-4", "e2-standard-8",
    "n2-standard-2", "n2-standard-4", "n2-standard-8",
    "n2-standard-16", "n2-standard-32",
    "c2-standard-4", "c2-standard-8", "c2-standard-16",
    "c2-standard-30",
    "a2-highgpu-1g", "a2-highgpu-2g", "a2-highgpu-4g",
    "a2-highgpu-8g",
    "g2-standard-4", "g2-standard-8", "g2-standard-12",
    "g2-standard-16",
]

_SIM_ZONES: list[str] = [
    "us-central1-a", "us-central1-b", "us-east1-b",
    "europe-west1-b", "asia-east1-a",
]


def _server_type_hint_for(machine_type: str) -> str:
    """Derive a server_type_hint from the GCP machine type family."""
    family = machine_type.split("-")[0]
    if family == "a2":
        return "gpu_training"
    if family == "g2":
        return "gpu_inference"
    return "cpu"


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class GCPCollector:
    """Collect GCE instance data from Google Cloud or via simulation."""

    def __init__(self, config: CollectorSourceConfig) -> None:
        self.config = config
        self.options: dict[str, Any] = config.options
        self._simulate = self.options.get("simulate", True)
        self._project: str = self.options.get("project", "")
        self._zone: str = self.options.get("zone", "us-central1-a")
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
        """List available GCE instances."""
        if self._simulate:
            return [f"[simulate] Would discover GCE instances in project {self._project}"]
        return self._discover_live()

    def test_connection(self) -> bool:
        """Verify GCP credentials are valid."""
        if self._simulate:
            return True
        return self._test_live()

    # ------------------------------------------------------------------
    # Simulated collection
    # ------------------------------------------------------------------

    def _collect_simulated(self) -> CollectorResult:
        rng = random.Random(self._seed)
        count = rng.randint(10, 20)

        zone = self._zone
        project = self._project or "sim-project-001"

        servers: list[RawServerData] = []
        energy_readings: list[RawEnergyReading] = []
        warnings: list[str] = []

        now = datetime.now(tz=timezone.utc)

        for i in range(count):
            machine_type = rng.choice(_SIM_MACHINE_TYPES)
            chosen_zone = rng.choice(_SIM_ZONES)
            instance_name = f"gce-{rng.choice(['web', 'api', 'worker', 'ml', 'db', 'cache'])}-{rng.randint(1, 99):02d}"
            instance_id = str(rng.randint(1000000000000000, 9999999999999999))

            cpu_util = round(rng.uniform(0.03, 0.88), 3)
            mem_util = round(rng.uniform(0.10, 0.86), 3)

            # GPU utilisation only for accelerator families
            family = machine_type.split("-")[0]
            gpu_util: float | None = None
            if family in ("a2", "g2"):
                gpu_util = round(rng.uniform(0.06, 0.94), 3)

            power_watts = estimate_power("gcp", machine_type)
            effective_power = round(power_watts * (0.3 + 0.7 * cpu_util), 1)

            server = RawServerData(
                hostname=instance_name,
                ip_address=f"10.{rng.randint(128, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
                server_type_hint=_server_type_hint_for(machine_type),
                power_watts=effective_power,
                tdp_watts=power_watts,
                cpu_utilization=cpu_util,
                gpu_utilization=gpu_util,
                memory_utilization=mem_util,
                model=machine_type,
                rack_id=chosen_zone,
                tags={
                    "cloud": "gcp",
                    "instance_id": instance_id,
                    "machine_type": machine_type,
                    "project": project,
                    "zone": chosen_zone,
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
            f"Simulated {count} GCE instances in project {project} "
            f"(seed={self._seed})"
        )

        return CollectorResult(
            source_type="gcp",
            servers=servers,
            energy_readings=energy_readings,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Live GCP collection
    # ------------------------------------------------------------------

    def _collect_live(self) -> CollectorResult:
        from energy_audit.pro import check_dependency
        check_dependency("google.cloud.compute_v1", "pip install google-cloud-compute")
        check_dependency("google.cloud.monitoring_v3", "pip install google-cloud-monitoring")

        from google.cloud import compute_v1  # type: ignore[import-untyped]
        from google.cloud import monitoring_v3  # type: ignore[import-untyped]

        errors: list[str] = []
        warnings: list[str] = []
        servers: list[RawServerData] = []
        energy_readings: list[RawEnergyReading] = []

        try:
            instances_client = compute_v1.InstancesClient()
            monitoring_client = monitoring_v3.MetricServiceClient()

            now = datetime.now(tz=timezone.utc)

            # List instances — scope to zone or aggregate across all zones
            zone = self._zone
            if zone:
                request = compute_v1.ListInstancesRequest(
                    project=self._project,
                    zone=zone,
                )
                instance_list = instances_client.list(request=request)
            else:
                agg_request = compute_v1.AggregatedListInstancesRequest(
                    project=self._project,
                )
                instance_list = self._flatten_aggregated(
                    instances_client.aggregated_list(request=agg_request)
                )

            for instance in instance_list:
                server = self._parse_gce_instance(
                    instance, monitoring_client, now,
                )
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
            errors.append(f"GCP collection error: {exc}")

        return CollectorResult(
            source_type="gcp",
            servers=servers,
            energy_readings=energy_readings,
            errors=errors,
            warnings=warnings,
        )

    def _parse_gce_instance(
        self,
        instance: Any,
        monitoring_client: Any,
        now: datetime,
    ) -> RawServerData | None:
        """Convert a GCE Instance object into RawServerData."""
        instance_name: str = instance.name
        instance_id: str = str(instance.id)

        # machine_type is a full URL; extract the short name
        machine_type_url: str = instance.machine_type
        machine_type = machine_type_url.rsplit("/", 1)[-1]

        # zone is also a full URL
        zone_url: str = instance.zone
        zone = zone_url.rsplit("/", 1)[-1]

        # Only collect running instances
        if instance.status != "RUNNING":
            return None

        cpu_util = self._get_gcp_metric(
            monitoring_client, self._project, instance_id,
            "compute.googleapis.com/instance/cpu/utilization",
            now, period_minutes=30,
        )

        power_watts = estimate_power("gcp", machine_type)
        effective_power = power_watts
        if cpu_util is not None:
            effective_power = round(power_watts * (0.3 + 0.7 * cpu_util), 1)

        gcp_labels: dict[str, str] = {}
        if instance.labels:
            gcp_labels = {f"gcp_label_{k}": v for k, v in instance.labels.items()}

        network_ip: str | None = None
        if instance.network_interfaces:
            first_nic = instance.network_interfaces[0]
            network_ip = first_nic.network_i_p if hasattr(first_nic, "network_i_p") else None

        return RawServerData(
            hostname=instance_name,
            ip_address=network_ip,
            server_type_hint=_server_type_hint_for(machine_type),
            power_watts=effective_power,
            tdp_watts=power_watts,
            cpu_utilization=cpu_util,
            model=machine_type,
            rack_id=zone,
            tags={
                "cloud": "gcp",
                "instance_id": instance_id,
                "machine_type": machine_type,
                "project": self._project,
                "zone": zone,
                **gcp_labels,
            },
        )

    @staticmethod
    def _get_gcp_metric(
        monitoring_client: Any,
        project: str,
        instance_id: str,
        metric_type: str,
        now: datetime,
        *,
        period_minutes: int = 30,
    ) -> float | None:
        """Fetch the average of a Cloud Monitoring metric over the recent window."""
        from datetime import timedelta

        try:
            from google.cloud.monitoring_v3 import (  # type: ignore[import-untyped]
                Aggregation,
                ListTimeSeriesRequest,
                TimeInterval,
            )
            from google.protobuf.timestamp_pb2 import Timestamp  # type: ignore[import-untyped]

            end_time = Timestamp()
            end_time.FromDatetime(now)
            start_time = Timestamp()
            start_time.FromDatetime(now - timedelta(minutes=period_minutes))

            interval = TimeInterval(start_time=start_time, end_time=end_time)
            aggregation = Aggregation(
                alignment_period={"seconds": period_minutes * 60},
                per_series_aligner=Aggregation.Aligner.ALIGN_MEAN,
            )

            request = ListTimeSeriesRequest(
                name=f"projects/{project}",
                filter=(
                    f'metric.type = "{metric_type}" AND '
                    f'resource.labels.instance_id = "{instance_id}"'
                ),
                interval=interval,
                aggregation=aggregation,
                view=ListTimeSeriesRequest.TimeSeriesView.FULL,
            )

            results = monitoring_client.list_time_series(request=request)
            for ts in results:
                for point in reversed(ts.points):
                    value = point.value.double_value
                    if value is not None:
                        # GCP cpu/utilization is already 0-1
                        return round(value, 4)
        except Exception:
            pass
        return None

    @staticmethod
    def _flatten_aggregated(aggregated_list: Any) -> list[Any]:
        """Flatten aggregated_list response into a plain list of instances."""
        instances: list[Any] = []
        for _zone, response in aggregated_list:
            if response.instances:
                instances.extend(response.instances)
        return instances

    # ------------------------------------------------------------------
    # Live helpers
    # ------------------------------------------------------------------

    def _discover_live(self) -> list[str]:
        from energy_audit.pro import check_dependency
        check_dependency("google.cloud.compute_v1", "pip install google-cloud-compute")

        from google.cloud import compute_v1  # type: ignore[import-untyped]

        client = compute_v1.InstancesClient()
        results: list[str] = []

        if self._zone:
            request = compute_v1.ListInstancesRequest(
                project=self._project,
                zone=self._zone,
            )
            for instance in client.list(request=request):
                mt = instance.machine_type.rsplit("/", 1)[-1]
                zone = instance.zone.rsplit("/", 1)[-1]
                results.append(f"{instance.name}: {mt} ({zone})")
        else:
            agg_request = compute_v1.AggregatedListInstancesRequest(
                project=self._project,
            )
            for _zone, response in client.aggregated_list(request=agg_request):
                if response.instances:
                    for instance in response.instances:
                        mt = instance.machine_type.rsplit("/", 1)[-1]
                        zone = instance.zone.rsplit("/", 1)[-1]
                        results.append(f"{instance.name}: {mt} ({zone})")
        return results

    def _test_live(self) -> bool:
        from energy_audit.pro import check_dependency
        check_dependency("google.cloud.compute_v1", "pip install google-cloud-compute")

        from google.cloud import compute_v1  # type: ignore[import-untyped]

        try:
            client = compute_v1.InstancesClient()
            # Attempt a lightweight call to verify credentials
            request = compute_v1.ListInstancesRequest(
                project=self._project,
                zone=self._zone or "us-central1-a",
                max_results=1,
            )
            next(iter(client.list(request=request)), None)
            return True
        except Exception:
            return False


# Self-register
register_collector("gcp", GCPCollector)
