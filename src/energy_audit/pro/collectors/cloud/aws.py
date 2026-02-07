# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""AWS EC2 cloud collector.

Collects instance metadata and utilisation metrics from AWS.  In
*simulate* mode (the default) realistic fake data is generated so the
rest of the pipeline can be exercised without cloud credentials.  In
*live* mode the collector uses **boto3** to enumerate EC2 instances and
pull CloudWatch CPU/memory metrics.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from energy_audit.pro.collectors import register_collector
from energy_audit.pro.collectors.base import CollectorResult, RawEnergyReading, RawServerData
from energy_audit.pro.collectors.cloud.power_models import AWS_INSTANCE_POWER, estimate_power
from energy_audit.pro.config import CollectorSourceConfig


# ---------------------------------------------------------------------------
# Simulated instance catalogue
# ---------------------------------------------------------------------------

_SIM_INSTANCE_TYPES: list[str] = [
    "t3.micro", "t3.small", "t3.medium", "t3.large", "t3.xlarge",
    "m5.large", "m5.xlarge", "m5.2xlarge", "m5.4xlarge", "m5.8xlarge",
    "c5.large", "c5.xlarge", "c5.2xlarge", "c5.4xlarge",
    "r5.large", "r5.xlarge", "r5.2xlarge",
    "g4dn.xlarge", "g4dn.2xlarge", "g4dn.4xlarge",
    "g5.xlarge", "g5.2xlarge", "g5.4xlarge",
    "p3.2xlarge", "p3.8xlarge",
    "p4d.24xlarge",
    "i3.large", "i3.xlarge", "i3.2xlarge",
    "d2.xlarge", "d2.2xlarge",
]

_SIM_REGIONS: list[str] = [
    "us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1",
]

_SIM_AZS: dict[str, list[str]] = {
    "us-east-1": ["us-east-1a", "us-east-1b", "us-east-1c"],
    "us-west-2": ["us-west-2a", "us-west-2b"],
    "eu-west-1": ["eu-west-1a", "eu-west-1b", "eu-west-1c"],
    "ap-southeast-1": ["ap-southeast-1a", "ap-southeast-1b"],
}


def _server_type_hint_for(instance_type: str) -> str:
    """Derive a server_type_hint from the instance family prefix."""
    family = instance_type.split(".")[0]
    if family in ("p3", "p4d"):
        return "gpu_training"
    if family in ("g4dn", "g5"):
        return "gpu_inference"
    if family in ("i3", "d2"):
        return "storage"
    return "cpu"


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

class AWSCollector:
    """Collect EC2 instance data from AWS or via simulation."""

    def __init__(self, config: CollectorSourceConfig) -> None:
        self.config = config
        self.options: dict[str, Any] = config.options
        self._simulate = self.options.get("simulate", True)
        self._region = self.options.get("region", "us-east-1")
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
        """List available EC2 instances."""
        if self._simulate:
            return [f"[simulate] Would discover EC2 instances in {self._region}"]
        return self._discover_live()

    def test_connection(self) -> bool:
        """Verify AWS credentials are valid."""
        if self._simulate:
            return True
        return self._test_live()

    # ------------------------------------------------------------------
    # Simulated collection
    # ------------------------------------------------------------------

    def _collect_simulated(self) -> CollectorResult:
        rng = random.Random(self._seed)
        count = rng.randint(15, 25)

        region = self._region
        azs = _SIM_AZS.get(region, [f"{region}a", f"{region}b"])

        servers: list[RawServerData] = []
        energy_readings: list[RawEnergyReading] = []
        warnings: list[str] = []

        now = datetime.now(tz=timezone.utc)

        for i in range(count):
            instance_type = rng.choice(_SIM_INSTANCE_TYPES)
            az = rng.choice(azs)
            instance_id = f"i-{rng.randint(0x1000000000, 0xFFFFFFFFFF):010x}"
            hostname = f"ip-10-{rng.randint(0, 255)}-{rng.randint(0, 255)}-{rng.randint(1, 254)}.{region}.compute.internal"

            cpu_util = round(rng.uniform(0.02, 0.92), 3)
            mem_util = round(rng.uniform(0.10, 0.88), 3)

            # GPU utilisation only for GPU families
            family = instance_type.split(".")[0]
            gpu_util: float | None = None
            if family in ("p3", "p4d", "g4dn", "g5"):
                gpu_util = round(rng.uniform(0.05, 0.95), 3)

            power_watts = estimate_power("aws", instance_type)
            # Modulate by utilisation
            effective_power = round(power_watts * (0.3 + 0.7 * cpu_util), 1)

            server = RawServerData(
                hostname=hostname,
                ip_address=f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
                server_type_hint=_server_type_hint_for(instance_type),
                power_watts=effective_power,
                tdp_watts=power_watts,
                cpu_utilization=cpu_util,
                gpu_utilization=gpu_util,
                memory_utilization=mem_util,
                model=instance_type,
                rack_id=az,
                tags={
                    "cloud": "aws",
                    "instance_id": instance_id,
                    "instance_type": instance_type,
                    "region": region,
                    "availability_zone": az,
                },
            )
            servers.append(server)

        # Aggregate energy reading
        total_it_kw = sum(s.power_watts for s in servers if s.power_watts) / 1000.0
        energy_readings.append(RawEnergyReading(
            timestamp=now,
            it_power_kw=round(total_it_kw, 3),
            total_power_kw=round(total_it_kw * 1.1, 3),  # ~1.1 PUE for cloud
        ))

        warnings.append(
            f"Simulated {count} EC2 instances in {region} "
            f"(seed={self._seed})"
        )

        return CollectorResult(
            source_type="aws",
            servers=servers,
            energy_readings=energy_readings,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Live AWS collection
    # ------------------------------------------------------------------

    def _collect_live(self) -> CollectorResult:
        from energy_audit.pro import check_dependency
        check_dependency("boto3", "pip install boto3")

        import boto3  # type: ignore[import-untyped]

        errors: list[str] = []
        warnings: list[str] = []
        servers: list[RawServerData] = []
        energy_readings: list[RawEnergyReading] = []

        try:
            session = boto3.Session(region_name=self._region)
            ec2 = session.client("ec2")
            cloudwatch = session.client("cloudwatch")

            paginator = ec2.get_paginator("describe_instances")
            filters = self.options.get("filters", [{"Name": "instance-state-name", "Values": ["running"]}])

            now = datetime.now(tz=timezone.utc)

            for page in paginator.paginate(Filters=filters):
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        server = self._parse_ec2_instance(instance, cloudwatch, now)
                        if server is not None:
                            servers.append(server)

            # Aggregate energy reading
            if servers:
                total_it_kw = sum(s.power_watts for s in servers if s.power_watts) / 1000.0
                energy_readings.append(RawEnergyReading(
                    timestamp=now,
                    it_power_kw=round(total_it_kw, 3),
                    total_power_kw=round(total_it_kw * 1.1, 3),
                ))

        except Exception as exc:
            errors.append(f"AWS collection error: {exc}")

        return CollectorResult(
            source_type="aws",
            servers=servers,
            energy_readings=energy_readings,
            errors=errors,
            warnings=warnings,
        )

    def _parse_ec2_instance(
        self,
        instance: dict[str, Any],
        cloudwatch: Any,
        now: datetime,
    ) -> RawServerData | None:
        """Convert a raw EC2 instance dict into RawServerData."""
        instance_id: str = instance["InstanceId"]
        instance_type: str = instance["InstanceType"]
        az: str = instance.get("Placement", {}).get("AvailabilityZone", self._region)

        # Resolve hostname from tags or private DNS
        name_tag = ""
        aws_tags: dict[str, str] = {}
        for tag in instance.get("Tags", []):
            aws_tags[tag["Key"]] = tag["Value"]
            if tag["Key"] == "Name":
                name_tag = tag["Value"]

        hostname = name_tag or instance.get("PrivateDnsName", instance_id)
        private_ip = instance.get("PrivateIpAddress")

        # Fetch CloudWatch CPU utilisation (average over last 30 min)
        cpu_util = self._get_cloudwatch_metric(
            cloudwatch, instance_id, "CPUUtilization",
            "AWS/EC2", now, period_minutes=30,
        )

        power_watts = estimate_power("aws", instance_type)
        effective_power = power_watts
        if cpu_util is not None:
            effective_power = round(power_watts * (0.3 + 0.7 * cpu_util), 1)

        return RawServerData(
            hostname=hostname,
            ip_address=private_ip,
            server_type_hint=_server_type_hint_for(instance_type),
            power_watts=effective_power,
            tdp_watts=power_watts,
            cpu_utilization=cpu_util,
            model=instance_type,
            rack_id=az,
            tags={
                "cloud": "aws",
                "instance_id": instance_id,
                "instance_type": instance_type,
                "region": self._region,
                "availability_zone": az,
                **{f"aws_tag_{k}": v for k, v in aws_tags.items()},
            },
        )

    @staticmethod
    def _get_cloudwatch_metric(
        cloudwatch: Any,
        instance_id: str,
        metric_name: str,
        namespace: str,
        now: datetime,
        *,
        period_minutes: int = 30,
    ) -> float | None:
        """Fetch the average of a CloudWatch metric over the recent window."""
        from datetime import timedelta

        try:
            resp = cloudwatch.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=now - timedelta(minutes=period_minutes),
                EndTime=now,
                Period=period_minutes * 60,
                Statistics=["Average"],
            )
            datapoints = resp.get("Datapoints", [])
            if datapoints:
                avg = datapoints[-1]["Average"]
                return round(avg / 100.0, 4)  # percentage -> fraction
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Live helpers
    # ------------------------------------------------------------------

    def _discover_live(self) -> list[str]:
        from energy_audit.pro import check_dependency
        check_dependency("boto3", "pip install boto3")

        import boto3  # type: ignore[import-untyped]

        results: list[str] = []
        session = boto3.Session(region_name=self._region)
        ec2 = session.client("ec2")
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate(Filters=[{"Name": "instance-state-name", "Values": ["running"]}]):
            for res in page["Reservations"]:
                for inst in res["Instances"]:
                    iid = inst["InstanceId"]
                    itype = inst["InstanceType"]
                    name = ""
                    for tag in inst.get("Tags", []):
                        if tag["Key"] == "Name":
                            name = tag["Value"]
                    label = f"{name} ({iid})" if name else iid
                    results.append(f"{label}: {itype}")
        return results

    def _test_live(self) -> bool:
        from energy_audit.pro import check_dependency
        check_dependency("boto3", "pip install boto3")

        import boto3  # type: ignore[import-untyped]

        try:
            session = boto3.Session(region_name=self._region)
            sts = session.client("sts")
            sts.get_caller_identity()
            return True
        except Exception:
            return False


# Self-register
register_collector("aws", AWSCollector)
