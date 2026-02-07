"""Matplotlib chart generators for the energy audit PDF report.

This module provides a ``ChartGenerator`` class that transforms an
``AuditResult`` into a collection of publication-quality Matplotlib
figures suitable for embedding in a ReportLab PDF or saving as standalone
PNG images.

The Agg (Anti-Grain Geometry) backend is selected unconditionally so that
chart rendering works in headless / server environments without a display.
"""

from __future__ import annotations

import math
import os
from collections import defaultdict
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from energy_audit.data.models import AuditResult  # noqa: E402

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Style / palette constants
# ---------------------------------------------------------------------------

_STYLE_CANDIDATES = ["seaborn-v0_8-whitegrid", "seaborn-whitegrid"]

_BLUE = "#2196F3"
_GREEN = "#4CAF50"
_ORANGE = "#FF9800"
_RED = "#F44336"
_PURPLE = "#9C27B0"
_CYAN = "#00BCD4"

_PALETTE = [_BLUE, _GREEN, _ORANGE, _RED, _PURPLE, _CYAN]

_DPI = 150


def _apply_style() -> None:
    """Apply the best available Matplotlib style."""
    for style in _STYLE_CANDIDATES:
        if style in plt.style.available:
            plt.style.use(style)
            return
    # Fallback: use default style (no-op)


_apply_style()


# ---------------------------------------------------------------------------
# ChartGenerator
# ---------------------------------------------------------------------------


class ChartGenerator:
    """Generate all charts required by the energy audit PDF report.

    Each public method returns a :class:`matplotlib.figure.Figure` that can
    be saved to a file or rendered into a PDF page.

    Parameters
    ----------
    result:
        A fully populated ``AuditResult`` produced by the scoring engine.
    """

    def __init__(self, result: AuditResult) -> None:
        self.result = result

    # -- 1. Radar / spider chart for pillar scores --------------------------

    def three_box_radar(self) -> Figure:
        """Radar (spider) chart showing Box 1, Box 2, and Box 3 scores."""
        labels = ["Box 1: Operations", "Box 2: Legacy", "Box 3: Future"]
        scores = [
            self.result.box1.overall_score,
            self.result.box2.overall_score,
            self.result.box3.overall_score,
        ]

        # Compute angles for each axis (equally spaced around the circle)
        num_vars = len(labels)
        angles = [n / float(num_vars) * 2 * math.pi for n in range(num_vars)]
        # Close the polygon
        angles += angles[:1]
        scores_closed = scores + scores[:1]

        fig, ax = plt.subplots(figsize=(8, 8), dpi=_DPI, subplot_kw={"polar": True})

        ax.set_theta_offset(math.pi / 2)
        ax.set_theta_direction(-1)

        # Draw axis labels
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=12, fontweight="bold")

        # Set radial limits
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=8, color="grey")

        # Plot data
        ax.plot(angles, scores_closed, color=_BLUE, linewidth=2.5, linestyle="solid")
        ax.fill(angles, scores_closed, color=_BLUE, alpha=0.25)

        # Add score annotations at each vertex
        for angle, score in zip(angles[:-1], scores):
            ax.annotate(
                f"{score:.0f}",
                xy=(angle, score),
                fontsize=13,
                fontweight="bold",
                ha="center",
                va="bottom",
                color=_BLUE,
            )

        ax.set_title(
            "Assessment Pillar Scores",
            fontsize=16,
            fontweight="bold",
            pad=24,
        )

        fig.tight_layout()
        return fig

    # -- 2. Energy breakdown pie chart ------------------------------------

    def energy_breakdown_pie(self) -> Figure:
        """Pie chart of energy consumption grouped by workload type."""
        type_power: dict[str, float] = defaultdict(float)
        for wl in self.result.data_center.workloads:
            type_power[wl.workload_type.value] += wl.power_consumption_kw

        if not type_power:
            type_power["No Data"] = 1.0

        labels = list(type_power.keys())
        sizes = list(type_power.values())

        # Assign colors from the palette, cycling if needed
        colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels))]

        fig, ax = plt.subplots(figsize=(8, 8), dpi=_DPI)
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=140,
            pctdistance=0.80,
            wedgeprops={"edgecolor": "white", "linewidth": 1.5},
        )

        for text in texts:
            text.set_fontsize(10)
        for autotext in autotexts:
            autotext.set_fontsize(9)
            autotext.set_fontweight("bold")

        ax.set_title(
            "Energy Consumption by Workload Type",
            fontsize=16,
            fontweight="bold",
            pad=20,
        )

        fig.tight_layout()
        return fig

    # -- 3. Server utilization histogram ----------------------------------

    def server_utilization_histogram(self) -> Figure:
        """Histogram of CPU utilization across all servers (color-coded)."""
        utilizations = [s.cpu_utilization * 100 for s in self.result.data_center.servers]

        if not utilizations:
            utilizations = [0.0]

        fig, ax = plt.subplots(figsize=(10, 6), dpi=_DPI)

        # Create histogram data with 20 bins from 0-100
        bins = np.linspace(0, 100, 21)
        counts, edges, patches = ax.hist(
            utilizations, bins=bins, edgecolor="white", linewidth=0.8
        )

        # Color-code bins based on utilization bracket
        for patch, left_edge in zip(patches, edges[:-1]):
            if left_edge < 30:
                patch.set_facecolor(_RED)  # Underutilized
            elif left_edge < 70:
                patch.set_facecolor(_ORANGE)  # Moderate
            else:
                patch.set_facecolor(_GREEN)  # Well-utilized

        # Add vertical mean line
        mean_util = np.mean(utilizations)
        ax.axvline(
            mean_util,
            color=_PURPLE,
            linewidth=2,
            linestyle="--",
            label=f"Mean: {mean_util:.1f}%",
        )

        ax.set_xlabel("CPU Utilization (%)", fontsize=12)
        ax.set_ylabel("Number of Servers", fontsize=12)
        ax.set_title(
            "Server CPU Utilization Distribution",
            fontsize=16,
            fontweight="bold",
        )
        ax.legend(fontsize=11, loc="upper right")
        ax.set_xlim(0, 100)

        # Add color legend annotations
        legend_items = [
            (_RED, "Underutilized (0-30%)"),
            (_ORANGE, "Moderate (30-70%)"),
            (_GREEN, "Well-utilized (70-100%)"),
        ]
        for i, (color, label) in enumerate(legend_items):
            ax.annotate(
                label,
                xy=(0.02, 0.95 - i * 0.06),
                xycoords="axes fraction",
                fontsize=9,
                color=color,
                fontweight="bold",
            )

        fig.tight_layout()
        return fig

    # -- 4. PUE trend line ------------------------------------------------

    def pue_trend_line(self) -> Figure:
        """Line chart of PUE values over the 30-day readings window."""
        readings = self.result.data_center.energy_readings
        valid_readings = [r for r in readings if r.pue > 0]

        if not valid_readings:
            # Return an empty figure with a message
            fig, ax = plt.subplots(figsize=(10, 6), dpi=_DPI)
            ax.text(
                0.5, 0.5, "No energy readings available",
                ha="center", va="center", fontsize=14, transform=ax.transAxes,
            )
            ax.set_title("PUE Trend (30 Days)", fontsize=16, fontweight="bold")
            fig.tight_layout()
            return fig

        # Sort by timestamp
        valid_readings = sorted(valid_readings, key=lambda r: r.timestamp)

        # Downsample to daily averages for cleaner visualization
        daily_data: dict[str, list[float]] = defaultdict(list)
        for r in valid_readings:
            day_key = r.timestamp.strftime("%Y-%m-%d")
            daily_data[day_key].append(r.pue)

        days = sorted(daily_data.keys())
        daily_avg_pue = [np.mean(daily_data[d]) for d in days]

        # Use short date labels
        day_labels = [d[5:] for d in days]  # MM-DD format

        fig, ax = plt.subplots(figsize=(10, 6), dpi=_DPI)

        ax.plot(
            range(len(days)),
            daily_avg_pue,
            color=_BLUE,
            linewidth=2,
            marker="o",
            markersize=4,
            label="Daily Avg PUE",
        )

        # Target and ideal reference lines
        ax.axhline(
            y=1.2,
            color=_GREEN,
            linewidth=1.5,
            linestyle="--",
            label="Target PUE (1.2)",
        )
        ax.axhline(
            y=1.0,
            color=_CYAN,
            linewidth=1.5,
            linestyle=":",
            label="Ideal PUE (1.0)",
        )

        # Fill between current PUE and target to highlight gap
        ax.fill_between(
            range(len(days)),
            daily_avg_pue,
            1.2,
            where=[p > 1.2 for p in daily_avg_pue],
            alpha=0.15,
            color=_RED,
            label="Above Target",
        )

        ax.set_xticks(range(len(days)))
        ax.set_xticklabels(day_labels, rotation=45, ha="right", fontsize=8)
        ax.set_xlabel("Date", fontsize=12)
        ax.set_ylabel("PUE", fontsize=12)
        ax.set_title(
            "Power Usage Effectiveness (PUE) -- 30-Day Trend",
            fontsize=16,
            fontweight="bold",
        )
        ax.legend(fontsize=10, loc="upper right")

        # Set y-axis to reasonable range
        min_pue = min(daily_avg_pue)
        max_pue = max(daily_avg_pue)
        ax.set_ylim(max(0.9, min_pue - 0.1), max_pue + 0.2)

        fig.tight_layout()
        return fig

    # -- 5. Fleet age distribution ----------------------------------------

    def fleet_age_distribution(self) -> Figure:
        """Bar chart of server count by age bracket."""
        brackets = [
            ("0-12 mo", 0, 12),
            ("12-24 mo", 12, 24),
            ("24-36 mo", 24, 36),
            ("36-48 mo", 36, 48),
            ("48-60 mo", 48, 60),
            ("60+ mo", 60, float("inf")),
        ]
        bracket_colors = [_GREEN, _GREEN, _ORANGE, _ORANGE, _RED, _RED]

        counts = []
        labels = []
        for label, low, high in brackets:
            count = sum(
                1
                for s in self.result.data_center.servers
                if low <= s.age_months < high
            )
            counts.append(count)
            labels.append(label)

        fig, ax = plt.subplots(figsize=(10, 6), dpi=_DPI)

        bars = ax.bar(labels, counts, color=bracket_colors, edgecolor="white", linewidth=1.2)

        # Add count labels on bars
        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.3,
                    str(count),
                    ha="center",
                    va="bottom",
                    fontsize=11,
                    fontweight="bold",
                )

        ax.set_xlabel("Age Bracket", fontsize=12)
        ax.set_ylabel("Number of Servers", fontsize=12)
        ax.set_title(
            "Fleet Age Distribution",
            fontsize=16,
            fontweight="bold",
        )

        fig.tight_layout()
        return fig

    # -- 6. Cost projection bar chart -------------------------------------

    def cost_projection_bar(self) -> Figure:
        """Bar chart comparing current, optimized monthly, and annual costs."""
        monthly_cost = self.result.data_center.total_cost
        savings = self.result.total_monthly_savings
        optimized_monthly = monthly_cost - savings
        annual_projection = optimized_monthly * 12

        categories = ["Current\nMonthly Cost", "Optimized\nMonthly Cost", "Annual\nProjection"]
        values = [monthly_cost, optimized_monthly, annual_projection]
        colors = [_RED, _GREEN, _BLUE]

        fig, ax = plt.subplots(figsize=(10, 6), dpi=_DPI)

        bars = ax.bar(categories, values, color=colors, edgecolor="white", linewidth=1.2, width=0.5)

        # Add dollar amount labels on bars
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"${value:,.0f}",
                ha="center",
                va="bottom",
                fontsize=13,
                fontweight="bold",
            )

        # Add savings annotation
        if savings > 0:
            ax.annotate(
                f"Monthly Savings: ${savings:,.0f}",
                xy=(0.5, 0.92),
                xycoords="axes fraction",
                fontsize=12,
                fontweight="bold",
                color=_GREEN,
                ha="center",
                bbox={"boxstyle": "round,pad=0.4", "facecolor": "#E8F5E9", "edgecolor": _GREEN},
            )

        ax.set_ylabel("Cost (USD)", fontsize=12)
        ax.set_title(
            "Cost Projection: Current vs. Optimized",
            fontsize=16,
            fontweight="bold",
        )

        # Ensure y-axis starts at 0 with some headroom
        ax.set_ylim(0, max(values) * 1.18)

        fig.tight_layout()
        return fig

    # -- 7. Workload energy treemap (horizontal stacked bar) --------------

    def workload_energy_treemap(self) -> Figure:
        """Horizontal stacked bar showing energy share by workload type."""
        type_power: dict[str, float] = defaultdict(float)
        for wl in self.result.data_center.workloads:
            type_power[wl.workload_type.value] += wl.power_consumption_kw

        if not type_power:
            type_power["No Data"] = 1.0

        # Sort by power descending for visual clarity
        sorted_items = sorted(type_power.items(), key=lambda x: x[1], reverse=True)
        labels = [item[0] for item in sorted_items]
        sizes = [item[1] for item in sorted_items]
        total = sum(sizes)

        colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels))]

        fig, ax = plt.subplots(figsize=(10, 6), dpi=_DPI)

        # Draw stacked horizontal bar segments
        left = 0.0
        for i, (label, size) in enumerate(zip(labels, sizes)):
            pct = (size / total) * 100 if total > 0 else 0
            bar = ax.barh(
                0,
                size,
                left=left,
                color=colors[i],
                edgecolor="white",
                linewidth=1.5,
                height=0.5,
            )

            # Add label inside segment if wide enough
            segment_center = left + size / 2
            if pct >= 8:  # Only label segments >= 8% to avoid clutter
                ax.text(
                    segment_center,
                    0,
                    f"{label}\n{pct:.1f}%",
                    ha="center",
                    va="center",
                    fontsize=9,
                    fontweight="bold",
                    color="white",
                )
            left += size

        # Legend for all segments
        from matplotlib.patches import Patch

        legend_elements = [
            Patch(
                facecolor=colors[i],
                edgecolor="white",
                label=f"{labels[i]} ({(sizes[i] / total) * 100:.1f}%)",
            )
            for i in range(len(labels))
        ]
        ax.legend(
            handles=legend_elements,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.08),
            ncol=min(3, len(labels)),
            fontsize=9,
            frameon=True,
        )

        ax.set_yticks([])
        ax.set_xlabel("Power Consumption (kW)", fontsize=12)
        ax.set_title(
            "Energy Distribution by Workload Type",
            fontsize=16,
            fontweight="bold",
        )

        fig.tight_layout()
        return fig

    # -- 8. Savings waterfall chart ---------------------------------------

    def savings_waterfall(self) -> Figure:
        """Waterfall chart showing cumulative savings from each recommendation."""
        monthly_cost = self.result.data_center.total_cost
        recommendations = self.result.recommendations
        savings = self.result.total_monthly_savings
        optimized_cost = monthly_cost - savings

        # Build the waterfall data
        step_labels: list[str] = ["Current\nCost"]
        step_values: list[float] = [monthly_cost]
        step_colors: list[str] = ["#9E9E9E"]  # Gray for start
        bottoms: list[float] = [0.0]

        running = monthly_cost
        for rec in recommendations:
            s = rec.monthly_savings_dollars
            if s <= 0:
                continue
            title = rec.title[:20] + ("..." if len(rec.title) > 20 else "")
            step_labels.append(title)
            step_values.append(s)
            step_colors.append(_GREEN)
            running -= s
            bottoms.append(running)

        # Final bar: optimized cost
        step_labels.append("Optimized\nCost")
        step_values.append(optimized_cost)
        step_colors.append("#9E9E9E")  # Gray for end
        bottoms.append(0.0)

        fig, ax = plt.subplots(figsize=(10, 6), dpi=_DPI)

        x_pos = np.arange(len(step_labels))
        bars = ax.bar(
            x_pos,
            step_values,
            bottom=bottoms,
            color=step_colors,
            edgecolor="white",
            linewidth=1.2,
            width=0.6,
        )

        # Add dollar labels on each bar
        for i, (bar, val) in enumerate(zip(bars, step_values)):
            y_pos = bottoms[i] + val
            # For savings steps, show as negative
            if step_colors[i] == _GREEN:
                label_text = f"-${val:,.0f}"
            else:
                label_text = f"${val:,.0f}"
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                y_pos + monthly_cost * 0.01,
                label_text,
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color=step_colors[i] if step_colors[i] == _GREEN else "#424242",
            )

        # Draw connector lines between bars
        for i in range(len(step_labels) - 1):
            connector_y = bottoms[i] + step_values[i]
            # Skip connector from last savings step to "Optimized Cost"
            if i == len(step_labels) - 2:
                connector_y = optimized_cost
            ax.plot(
                [x_pos[i] + 0.3, x_pos[i + 1] - 0.3],
                [connector_y, connector_y],
                color="#BDBDBD",
                linewidth=1.0,
                linestyle="--",
            )

        ax.set_xticks(x_pos)
        ax.set_xticklabels(step_labels, fontsize=8, rotation=45, ha="right")
        ax.set_ylabel("Monthly Cost (USD)", fontsize=12)
        ax.set_title(
            "Savings Waterfall: Recommendation Impact Breakdown",
            fontsize=16,
            fontweight="bold",
        )

        # Ensure y starts at 0
        ax.set_ylim(0, monthly_cost * 1.15)

        fig.tight_layout()
        return fig

    # -- Convenience methods ----------------------------------------------

    def generate_all(self) -> dict[str, Figure]:
        """Generate all charts and return as a name -> figure dict."""
        return {
            "three_box_radar": self.three_box_radar(),
            "energy_breakdown_pie": self.energy_breakdown_pie(),
            "server_utilization_histogram": self.server_utilization_histogram(),
            "pue_trend_line": self.pue_trend_line(),
            "fleet_age_distribution": self.fleet_age_distribution(),
            "cost_projection_bar": self.cost_projection_bar(),
            "workload_energy_treemap": self.workload_energy_treemap(),
            "savings_waterfall": self.savings_waterfall(),
        }

    def save_all(self, output_dir: str) -> dict[str, str]:
        """Save all charts as PNG files.

        Parameters
        ----------
        output_dir:
            Directory where PNG files will be written. Created if it does
            not already exist.

        Returns
        -------
        dict[str, str]
            Mapping of chart name to the absolute file path of the saved PNG.
        """
        os.makedirs(output_dir, exist_ok=True)
        charts = self.generate_all()
        paths: dict[str, str] = {}
        for name, fig in charts.items():
            filepath = os.path.join(output_dir, f"{name}.png")
            fig.savefig(filepath, dpi=_DPI, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            paths[name] = os.path.abspath(filepath)
        return paths
