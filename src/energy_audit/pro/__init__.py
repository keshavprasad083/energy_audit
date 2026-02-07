# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Energy Audit Pro — premium data ingestion and analysis module."""

__version__ = "0.1.0"

_PRO_AVAILABLE = True


def check_dependency(package: str, install_hint: str) -> None:
    """Raise *ImportError* with a helpful message if *package* is missing."""
    try:
        __import__(package)
    except ImportError:
        raise ImportError(
            f"Pro feature requires '{package}'. Install with: {install_hint}"
        ) from None
