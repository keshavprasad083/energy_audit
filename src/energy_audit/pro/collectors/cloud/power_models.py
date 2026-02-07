# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Instance-type to estimated wattage lookup tables for cloud providers.

Power estimates are approximations based on publicly available TDP data,
benchmark results, and community research.  They represent *average*
draw at moderate utilisation — not peak or idle.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# AWS EC2 Instance Power Estimates (watts)
# ---------------------------------------------------------------------------

AWS_INSTANCE_POWER: dict[str, float] = {
    # --- t3 (burstable, Intel Xeon) ---
    "t3.nano": 3.0,
    "t3.micro": 5.0,
    "t3.small": 8.0,
    "t3.medium": 12.0,
    "t3.large": 18.0,
    "t3.xlarge": 30.0,
    "t3.2xlarge": 55.0,
    # --- m5 (general purpose, Intel Xeon Platinum) ---
    "m5.large": 25.0,
    "m5.xlarge": 50.0,
    "m5.2xlarge": 95.0,
    "m5.4xlarge": 180.0,
    "m5.8xlarge": 340.0,
    "m5.12xlarge": 500.0,
    "m5.16xlarge": 650.0,
    "m5.24xlarge": 950.0,
    # --- c5 (compute optimised, Intel Xeon Platinum) ---
    "c5.large": 28.0,
    "c5.xlarge": 55.0,
    "c5.2xlarge": 105.0,
    "c5.4xlarge": 200.0,
    "c5.9xlarge": 430.0,
    "c5.12xlarge": 570.0,
    "c5.18xlarge": 830.0,
    "c5.24xlarge": 1100.0,
    # --- r5 (memory optimised, Intel Xeon Platinum) ---
    "r5.large": 28.0,
    "r5.xlarge": 55.0,
    "r5.2xlarge": 100.0,
    "r5.4xlarge": 190.0,
    "r5.8xlarge": 370.0,
    "r5.12xlarge": 540.0,
    "r5.16xlarge": 700.0,
    "r5.24xlarge": 1020.0,
    # --- p3 (GPU, NVIDIA V100) ---
    "p3.2xlarge": 350.0,
    "p3.8xlarge": 1200.0,
    "p3.16xlarge": 2400.0,
    # --- p4d (GPU, NVIDIA A100) ---
    "p4d.24xlarge": 2500.0,
    # --- g4dn (GPU inference, NVIDIA T4) ---
    "g4dn.xlarge": 120.0,
    "g4dn.2xlarge": 180.0,
    "g4dn.4xlarge": 280.0,
    "g4dn.8xlarge": 450.0,
    "g4dn.12xlarge": 650.0,
    "g4dn.16xlarge": 800.0,
    "g4dn.metal": 1100.0,
    # --- g5 (GPU, NVIDIA A10G) ---
    "g5.xlarge": 160.0,
    "g5.2xlarge": 220.0,
    "g5.4xlarge": 340.0,
    "g5.8xlarge": 520.0,
    "g5.12xlarge": 750.0,
    "g5.16xlarge": 900.0,
    "g5.24xlarge": 1300.0,
    "g5.48xlarge": 2400.0,
    # --- i3 (storage optimised, NVMe SSD) ---
    "i3.large": 30.0,
    "i3.xlarge": 58.0,
    "i3.2xlarge": 110.0,
    "i3.4xlarge": 210.0,
    "i3.8xlarge": 400.0,
    "i3.16xlarge": 780.0,
    "i3.metal": 800.0,
    # --- d2 (dense storage, HDD) ---
    "d2.xlarge": 85.0,
    "d2.2xlarge": 160.0,
    "d2.4xlarge": 310.0,
    "d2.8xlarge": 600.0,
}


# ---------------------------------------------------------------------------
# Azure VM Power Estimates (watts)
# ---------------------------------------------------------------------------

AZURE_VM_POWER: dict[str, float] = {
    # --- Standard_B (burstable) ---
    "Standard_B1s": 4.0,
    "Standard_B1ms": 6.0,
    "Standard_B2s": 10.0,
    "Standard_B2ms": 15.0,
    "Standard_B4ms": 28.0,
    "Standard_B8ms": 55.0,
    "Standard_B12ms": 80.0,
    "Standard_B16ms": 105.0,
    "Standard_B20ms": 130.0,
    # --- Standard_D (general purpose) ---
    "Standard_D2s_v5": 20.0,
    "Standard_D4s_v5": 38.0,
    "Standard_D8s_v5": 75.0,
    "Standard_D16s_v5": 145.0,
    "Standard_D32s_v5": 280.0,
    "Standard_D48s_v5": 410.0,
    "Standard_D64s_v5": 540.0,
    "Standard_D96s_v5": 800.0,
    # --- Standard_E (memory optimised) ---
    "Standard_E2s_v5": 22.0,
    "Standard_E4s_v5": 42.0,
    "Standard_E8s_v5": 80.0,
    "Standard_E16s_v5": 155.0,
    "Standard_E20s_v5": 190.0,
    "Standard_E32s_v5": 300.0,
    "Standard_E48s_v5": 440.0,
    "Standard_E64s_v5": 580.0,
    "Standard_E96s_v5": 860.0,
    # --- Standard_F (compute optimised) ---
    "Standard_F2s_v2": 18.0,
    "Standard_F4s_v2": 35.0,
    "Standard_F8s_v2": 68.0,
    "Standard_F16s_v2": 130.0,
    "Standard_F32s_v2": 255.0,
    "Standard_F48s_v2": 375.0,
    "Standard_F64s_v2": 490.0,
    "Standard_F72s_v2": 550.0,
    # --- Standard_N (GPU) ---
    "Standard_NC6s_v3": 300.0,
    "Standard_NC12s_v3": 580.0,
    "Standard_NC24s_v3": 1100.0,
    "Standard_NC24rs_v3": 1150.0,
    "Standard_ND40rs_v2": 2200.0,
    "Standard_ND96asr_v4": 2600.0,
    "Standard_NC4as_T4_v3": 120.0,
    "Standard_NC8as_T4_v3": 180.0,
    "Standard_NC16as_T4_v3": 300.0,
    "Standard_NC64as_T4_v3": 800.0,
    "Standard_NV6": 180.0,
    "Standard_NV12": 320.0,
    "Standard_NV24": 600.0,
}


# ---------------------------------------------------------------------------
# GCP Compute Engine Power Estimates (watts)
# ---------------------------------------------------------------------------

GCP_INSTANCE_POWER: dict[str, float] = {
    # --- e2 (cost-optimised) ---
    "e2-micro": 4.0,
    "e2-small": 7.0,
    "e2-medium": 12.0,
    "e2-standard-2": 18.0,
    "e2-standard-4": 35.0,
    "e2-standard-8": 65.0,
    "e2-standard-16": 125.0,
    "e2-standard-32": 245.0,
    # --- n2 (general purpose, Intel) ---
    "n2-standard-2": 22.0,
    "n2-standard-4": 42.0,
    "n2-standard-8": 80.0,
    "n2-standard-16": 155.0,
    "n2-standard-32": 300.0,
    "n2-standard-48": 440.0,
    "n2-standard-64": 580.0,
    "n2-standard-80": 720.0,
    "n2-standard-96": 860.0,
    "n2-standard-128": 1140.0,
    # --- c2 (compute optimised) ---
    "c2-standard-4": 45.0,
    "c2-standard-8": 85.0,
    "c2-standard-16": 165.0,
    "c2-standard-30": 300.0,
    "c2-standard-60": 580.0,
    # --- a2 (GPU, NVIDIA A100) ---
    "a2-highgpu-1g": 400.0,
    "a2-highgpu-2g": 750.0,
    "a2-highgpu-4g": 1400.0,
    "a2-highgpu-8g": 2600.0,
    "a2-megagpu-16g": 5000.0,
    "a2-ultragpu-1g": 450.0,
    "a2-ultragpu-2g": 850.0,
    "a2-ultragpu-4g": 1600.0,
    "a2-ultragpu-8g": 3000.0,
    # --- g2 (GPU, NVIDIA L4) ---
    "g2-standard-4": 130.0,
    "g2-standard-8": 190.0,
    "g2-standard-12": 260.0,
    "g2-standard-16": 330.0,
    "g2-standard-24": 420.0,
    "g2-standard-32": 510.0,
    "g2-standard-48": 700.0,
    "g2-standard-96": 1300.0,
}

# Unified lookup mapping provider names to their respective tables
_PROVIDER_TABLES: dict[str, dict[str, float]] = {
    "aws": AWS_INSTANCE_POWER,
    "azure": AZURE_VM_POWER,
    "gcp": GCP_INSTANCE_POWER,
}

_DEFAULT_POWER_WATTS: float = 150.0


def estimate_power(provider: str, instance_type: str) -> float:
    """Return estimated power draw in watts for a given cloud instance.

    Parameters
    ----------
    provider:
        Cloud provider key — ``"aws"``, ``"azure"``, or ``"gcp"``.
    instance_type:
        Instance / VM / machine-type name, e.g. ``"m5.xlarge"``.

    Returns
    -------
    float
        Estimated watts.  Falls back to 150 W if the instance type is
        not found in the lookup table.
    """
    table = _PROVIDER_TABLES.get(provider.lower(), {})
    return table.get(instance_type, _DEFAULT_POWER_WATTS)
