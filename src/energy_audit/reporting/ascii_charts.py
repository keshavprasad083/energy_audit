# Copyright (c) 2025 Keshav
# Licensed under the GNU Affero General Public License v3.0
# See LICENSE file for details.
"""Terminal-friendly visualizations using Unicode characters.

These functions return Rich-markup strings that render as bar charts,
sparklines, and score gauges in the terminal via the Rich library.
"""

from __future__ import annotations


def horizontal_bar(
    label: str,
    value: float,
    max_value: float,
    width: int = 40,
    color: str = "green",
) -> str:
    """Render a horizontal bar chart line using Unicode block characters.

    Returns a Rich-markup string like:
        PUE Score.............. [green]████████████░░░░░░░░[/] 65.0/100
    """
    if max_value <= 0:
        return f"  {label:.<30} [dim]no data[/]"
    ratio = min(value / max_value, 1.0)
    filled = int(ratio * width)
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    return f"  {label:.<30} [{color}]{bar}[/] {value:>6.1f}/{max_value:.0f}"


def score_gauge(score: float, width: int = 20) -> str:
    """Large visual gauge with color coding.

    Returns something like: [green]████████████░░░░░░░░[/] 78/100 [green]B[/]
    """
    clamped = max(0.0, min(100.0, score))
    filled = int(clamped / 100 * width)
    empty = width - filled

    if clamped >= 80:
        color = "green"
    elif clamped >= 50:
        color = "yellow"
    else:
        color = "red"

    bar = "\u2588" * filled + "\u2591" * empty
    grade = _score_to_letter(clamped)
    return f"[{color}]{bar}[/] {clamped:.0f}/100 [{color}]{grade}[/]"


def mini_gauge(score: float, width: int = 10) -> str:
    """Compact gauge for inline use in tables."""
    clamped = max(0.0, min(100.0, score))
    filled = int(clamped / 100 * width)
    empty = width - filled

    if clamped >= 80:
        color = "green"
    elif clamped >= 50:
        color = "yellow"
    else:
        color = "red"

    bar = "\u2588" * filled + "\u2591" * empty
    return f"[{color}]{bar}[/] {clamped:.0f}"


def sparkline(values: list[float], width: int | None = None) -> str:
    """Render a sparkline using Unicode block characters.

    Each value maps to one of 9 block heights: \" ▁▂▃▄▅▆▇█\"
    If width is given and len(values) > width, values are downsampled.
    """
    if not values:
        return ""

    blocks = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"

    # Downsample if needed
    if width and len(values) > width:
        step = len(values) / width
        sampled = []
        for i in range(width):
            start = int(i * step)
            end = int((i + 1) * step)
            sampled.append(sum(values[start:end]) / (end - start))
        values = sampled

    min_v = min(values)
    max_v = max(values)
    range_v = max_v - min_v or 1

    return "".join(
        blocks[int((v - min_v) / range_v * 8)] for v in values
    )


def colored_sparkline(values: list[float], width: int | None = None) -> str:
    """Sparkline with color gradient (green=high, red=low)."""
    if not values:
        return ""

    blocks = " \u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"

    if width and len(values) > width:
        step = len(values) / width
        sampled = []
        for i in range(width):
            start = int(i * step)
            end = int((i + 1) * step)
            sampled.append(sum(values[start:end]) / (end - start))
        values = sampled

    min_v = min(values)
    max_v = max(values)
    range_v = max_v - min_v or 1

    parts = []
    for v in values:
        idx = int((v - min_v) / range_v * 8)
        ratio = (v - min_v) / range_v
        if ratio >= 0.66:
            color = "green"
        elif ratio >= 0.33:
            color = "yellow"
        else:
            color = "red"
        parts.append(f"[{color}]{blocks[idx]}[/]")

    return "".join(parts)


def percentage_bar(
    label: str,
    pct: float,
    width: int = 20,
) -> str:
    """Simple percentage bar: [label] ████░░░░ 45%"""
    clamped = max(0.0, min(100.0, pct))
    filled = int(clamped / 100 * width)
    empty = width - filled

    if clamped >= 80:
        color = "green"
    elif clamped >= 50:
        color = "yellow"
    else:
        color = "red"

    bar = "\u2588" * filled + "\u2591" * empty
    return f"{label} [{color}]{bar}[/] {clamped:.0f}%"


def box_score_display(
    box_number: int,
    box_name: str,
    score: float,
    grade_letter: str,
) -> str:
    """Format a single box score for the dashboard header.

    Returns Rich markup like:
        ┌─ BOX 1 ──────────────┐
        │ CURRENT OPERATIONS    │
        │ ████████████░░░░ 72/100 B │
        └───────────────────────┘
    """
    color = "green" if score >= 80 else "yellow" if score >= 50 else "red"
    gauge = score_gauge(score)

    return (
        f"[bold]BOX {box_number}[/bold] | "
        f"[dim]{box_name}[/dim] | "
        f"{gauge}"
    )


def _score_to_letter(score: float) -> str:
    """Convert 0-100 score to letter grade."""
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"
