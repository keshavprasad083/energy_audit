"""ReportLab-based PDF report generator for energy audit results.

Produces an 8-page professional PDF report covering the complete energy
audit, including embedded Matplotlib charts, scoring tables,
recommendations, and methodology appendix.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import tempfile
from typing import Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from energy_audit.data.models import (
    AuditResult,
    BoxScore,
    DataCenter,
    Grade,
    Recommendation,
)
from energy_audit.reporting.charts import ChartGenerator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
DARK_BLUE = colors.HexColor('#1565C0')
GRADE_GREEN = colors.HexColor('#4CAF50')
GRADE_ORANGE = colors.HexColor('#FF9800')
GRADE_RED = colors.HexColor('#F44336')
LIGHT_GRAY = colors.HexColor('#F5F5F5')
WHITE = colors.white
BLACK = colors.black


def _grade_color(grade: Grade) -> colors.Color:
    """Return the display color for a given letter grade."""
    if grade in (Grade.A, Grade.B):
        return GRADE_GREEN
    if grade is Grade.C:
        return GRADE_ORANGE
    return GRADE_RED


def _strip_rich_tags(text: str) -> str:
    """Remove Rich console markup tags such as [green] or [/bold]."""
    return re.sub(r'\[/?[^\]]+\]', '', text)


class PDFReportGenerator:
    """Generates a multi-page PDF report from an :class:`AuditResult`."""

    def __init__(self) -> None:
        self._styles = getSampleStyleSheet()
        self._register_custom_styles()

    # ------------------------------------------------------------------
    # Custom paragraph styles
    # ------------------------------------------------------------------

    def _register_custom_styles(self) -> None:
        """Add project-specific paragraph styles to the stylesheet."""
        self._styles.add(ParagraphStyle(
            'CoverTitle',
            parent=self._styles['Title'],
            fontSize=28,
            leading=34,
            textColor=DARK_BLUE,
            spaceAfter=12,
            alignment=1,  # center
        ))
        self._styles.add(ParagraphStyle(
            'CoverSubtitle',
            parent=self._styles['Normal'],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#333333'),
            spaceAfter=8,
            alignment=1,
        ))
        self._styles.add(ParagraphStyle(
            'CoverDate',
            parent=self._styles['Normal'],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#666666'),
            spaceAfter=24,
            alignment=1,
        ))
        self._styles.add(ParagraphStyle(
            'SectionTitle',
            parent=self._styles['Heading1'],
            fontSize=20,
            leading=24,
            textColor=DARK_BLUE,
            spaceAfter=12,
            spaceBefore=6,
        ))
        self._styles.add(ParagraphStyle(
            'SubSection',
            parent=self._styles['Heading2'],
            fontSize=14,
            leading=18,
            textColor=DARK_BLUE,
            spaceAfter=8,
        ))
        self._styles.add(ParagraphStyle(
            'BodyText2',
            parent=self._styles['Normal'],
            fontSize=10,
            leading=14,
            spaceAfter=6,
        ))
        self._styles.add(ParagraphStyle(
            'Finding',
            parent=self._styles['Normal'],
            fontSize=10,
            leading=13,
            leftIndent=18,
            bulletIndent=6,
            spaceAfter=3,
        ))
        self._styles.add(ParagraphStyle(
            'FooterStyle',
            parent=self._styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#999999'),
            alignment=1,
        ))
        self._styles.add(ParagraphStyle(
            'GradeLarge',
            parent=self._styles['Normal'],
            fontSize=48,
            leading=52,
            alignment=1,
            spaceAfter=4,
        ))
        self._styles.add(ParagraphStyle(
            'ScoreLabel',
            parent=self._styles['Normal'],
            fontSize=12,
            leading=14,
            alignment=1,
            textColor=colors.HexColor('#444444'),
            spaceAfter=4,
        ))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, result: AuditResult, output_path: str) -> None:
        """Generate a complete PDF report and save to *output_path*."""
        # Generate charts into a temporary directory
        chart_paths: Dict[str, str] = {}
        tmpdir: Optional[str] = None
        try:
            tmpdir = tempfile.mkdtemp(prefix='energy_audit_charts_')
            try:
                chart_gen = ChartGenerator(result)
                chart_paths = chart_gen.save_all(tmpdir)
            except Exception:
                logger.warning(
                    "Chart generation failed; PDF will be produced without charts.",
                    exc_info=True,
                )

            # Build the PDF
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                topMargin=0.75 * inch,
                bottomMargin=0.75 * inch,
                leftMargin=0.75 * inch,
                rightMargin=0.75 * inch,
            )

            elements = []
            elements.extend(self._build_cover(result))
            elements.append(PageBreak())
            elements.extend(self._build_executive_summary(result, chart_paths))
            elements.append(PageBreak())
            elements.extend(self._build_box1(result, chart_paths))
            elements.append(PageBreak())
            elements.extend(self._build_box2(result, chart_paths))
            elements.append(PageBreak())
            elements.extend(self._build_box3(result, chart_paths))
            elements.append(PageBreak())
            elements.extend(self._build_recommendations(result, chart_paths))
            # Recommendations may span two pages; page break inserted within
            elements.append(PageBreak())
            elements.extend(self._build_appendix())

            doc.build(elements, onFirstPage=self._add_page_number,
                      onLaterPages=self._add_page_number)

        finally:
            # Clean up temporary chart files
            if tmpdir and os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Page number footer callback
    # ------------------------------------------------------------------

    @staticmethod
    def _add_page_number(canvas, doc) -> None:
        """Draw the page number in the footer of every page."""
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#999999'))
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.drawCentredString(letter[0] / 2.0, 0.5 * inch, text)
        canvas.restoreState()

    # ------------------------------------------------------------------
    # Page 1: Cover
    # ------------------------------------------------------------------

    def _build_cover(self, result: AuditResult) -> list:
        elements: list = []

        elements.append(Spacer(1, 1.5 * inch))
        elements.append(Paragraph("Energy Audit Report", self._styles['CoverTitle']))
        elements.append(Spacer(1, 0.25 * inch))

        dc_name = result.data_center.config.name
        dc_location = result.data_center.config.location
        elements.append(Paragraph(dc_name, self._styles['CoverSubtitle']))
        elements.append(Paragraph(dc_location, self._styles['CoverSubtitle']))
        elements.append(Spacer(1, 0.15 * inch))

        date_str = result.timestamp.strftime('%B %d, %Y')
        elements.append(Paragraph(date_str, self._styles['CoverDate']))
        elements.append(Spacer(1, 0.5 * inch))

        # Overall grade badge
        grade_clr = _grade_color(result.overall_grade)
        grade_hex = grade_clr.hexval() if hasattr(grade_clr, 'hexval') else str(grade_clr)
        elements.append(Paragraph(
            f'<font color="{grade_hex}" size="48"><b>{result.overall_grade.value}</b></font>',
            self._styles['GradeLarge'],
        ))
        elements.append(Paragraph(
            f"Overall Score: {result.overall_score:.1f} / 100",
            self._styles['ScoreLabel'],
        ))
        elements.append(Spacer(1, 0.5 * inch))

        # Three box score badges in a row
        boxes = [result.box1, result.box2, result.box3]
        box_labels = [
            "Box 1: Current Operations",
            "Box 2: Legacy & Waste",
            "Box 3: Future Readiness",
        ]
        badge_data = []
        for box, label in zip(boxes, box_labels):
            g_clr = _grade_color(box.grade)
            g_hex = g_clr.hexval() if hasattr(g_clr, 'hexval') else str(g_clr)
            badge_data.append([
                Paragraph(f'<font color="{g_hex}" size="24"><b>{box.grade.value}</b></font>',
                          self._styles['BodyText2']),
                Paragraph(f'<b>{box.overall_score:.1f}</b>', self._styles['BodyText2']),
                Paragraph(label, self._styles['BodyText2']),
            ])

        badge_table = Table(
            [[badge_data[0], badge_data[1], badge_data[2]]],
            colWidths=[2.2 * inch, 2.2 * inch, 2.2 * inch],
        )
        badge_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX', (0, 0), (0, 0), 0.5, DARK_BLUE),
            ('BOX', (1, 0), (1, 0), 0.5, DARK_BLUE),
            ('BOX', (2, 0), (2, 0), 0.5, DARK_BLUE),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(badge_table)

        return elements

    # ------------------------------------------------------------------
    # Page 2: Executive Summary
    # ------------------------------------------------------------------

    def _build_executive_summary(self, result: AuditResult,
                                  chart_paths: Dict[str, str]) -> list:
        elements: list = []

        elements.append(Paragraph("Executive Summary", self._styles['SectionTitle']))
        elements.append(Spacer(1, 0.15 * inch))

        summary_text = _strip_rich_tags(result.executive_summary)
        for paragraph in summary_text.split('\n'):
            paragraph = paragraph.strip()
            if paragraph:
                elements.append(Paragraph(paragraph, self._styles['BodyText2']))

        elements.append(Spacer(1, 0.25 * inch))

        # Pillar radar chart
        self._maybe_add_chart(elements, chart_paths, 'three_box_radar',
                              width=5 * inch, height=3.5 * inch)

        return elements

    # ------------------------------------------------------------------
    # Page 3: Box 1 - Current Operations
    # ------------------------------------------------------------------

    def _build_box1(self, result: AuditResult,
                    chart_paths: Dict[str, str]) -> list:
        elements: list = []
        box = result.box1

        elements.append(Paragraph("Box 1: Current Operations",
                                  self._styles['SectionTitle']))
        elements.extend(self._box_header(box))
        elements.extend(self._sub_metrics_table(box))
        elements.extend(self._findings_list(box))
        elements.append(Spacer(1, 0.2 * inch))
        self._maybe_add_chart(elements, chart_paths, 'energy_breakdown_pie',
                              width=5 * inch, height=3.5 * inch)

        return elements

    # ------------------------------------------------------------------
    # Page 4: Box 2 - Legacy & Waste
    # ------------------------------------------------------------------

    def _build_box2(self, result: AuditResult,
                    chart_paths: Dict[str, str]) -> list:
        elements: list = []
        box = result.box2

        elements.append(Paragraph("Box 2: Legacy & Waste",
                                  self._styles['SectionTitle']))
        elements.extend(self._box_header(box))
        elements.extend(self._sub_metrics_table(box))
        elements.extend(self._findings_list(box))
        elements.append(Spacer(1, 0.2 * inch))
        self._maybe_add_chart(elements, chart_paths, 'server_utilization_histogram',
                              width=5 * inch, height=3 * inch)
        elements.append(Spacer(1, 0.15 * inch))
        self._maybe_add_chart(elements, chart_paths, 'fleet_age_distribution',
                              width=5 * inch, height=3 * inch)

        return elements

    # ------------------------------------------------------------------
    # Page 5: Box 3 - Future Readiness
    # ------------------------------------------------------------------

    def _build_box3(self, result: AuditResult,
                    chart_paths: Dict[str, str]) -> list:
        elements: list = []
        box = result.box3

        elements.append(Paragraph("Box 3: Future Readiness",
                                  self._styles['SectionTitle']))
        elements.extend(self._box_header(box))
        elements.extend(self._sub_metrics_table(box))
        elements.extend(self._findings_list(box))
        elements.append(Spacer(1, 0.2 * inch))
        self._maybe_add_chart(elements, chart_paths, 'pue_trend_line',
                              width=5 * inch, height=3.5 * inch)

        return elements

    # ------------------------------------------------------------------
    # Pages 6-7: Recommendations
    # ------------------------------------------------------------------

    def _build_recommendations(self, result: AuditResult,
                                chart_paths: Dict[str, str]) -> list:
        elements: list = []

        elements.append(Paragraph("Recommendations", self._styles['SectionTitle']))
        elements.append(Spacer(1, 0.1 * inch))

        if result.recommendations:
            # Header row
            header = ['Rank', 'Box', 'Title', 'Monthly\nSavings ($)',
                      'Energy\nSaved (kWh)', 'Effort', 'Impact']
            data = [header]

            for rec in result.recommendations:
                data.append([
                    str(rec.rank),
                    str(rec.box_number),
                    Paragraph(rec.title, self._styles['BodyText2']),
                    f"${rec.monthly_savings_dollars:,.0f}",
                    f"{rec.monthly_energy_savings_kwh:,.0f}",
                    rec.effort.capitalize(),
                    rec.impact.capitalize(),
                ])

            # Totals row
            total_savings = sum(r.monthly_savings_dollars for r in result.recommendations)
            total_energy = sum(r.monthly_energy_savings_kwh for r in result.recommendations)
            data.append([
                '', '', Paragraph('<b>TOTAL</b>', self._styles['BodyText2']),
                f"${total_savings:,.0f}",
                f"{total_energy:,.0f}",
                '', '',
            ])

            col_widths = [
                0.45 * inch,   # Rank
                0.4 * inch,    # Box
                2.0 * inch,    # Title
                0.95 * inch,   # Savings
                0.95 * inch,   # Energy
                0.7 * inch,    # Effort
                0.7 * inch,    # Impact
            ]

            tbl = Table(data, colWidths=col_widths, repeatRows=1)
            style_commands = [
                # Header
                ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Body
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('ALIGN', (0, 1), (1, -1), 'CENTER'),
                ('ALIGN', (3, 1), (4, -1), 'RIGHT'),
                ('ALIGN', (5, 1), (6, -1), 'CENTER'),
                # Grid
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('LINEBELOW', (0, 0), (-1, 0), 1, DARK_BLUE),
                # Totals row bold line
                ('LINEABOVE', (0, -1), (-1, -1), 1.5, DARK_BLUE),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                # Padding
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ]

            # Alternating row colors (skip header row 0 and totals row -1)
            for i in range(1, len(data) - 1):
                if i % 2 == 0:
                    style_commands.append(
                        ('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY)
                    )

            tbl.setStyle(TableStyle(style_commands))
            elements.append(tbl)
        else:
            elements.append(Paragraph(
                "No recommendations generated.", self._styles['BodyText2']
            ))

        elements.append(Spacer(1, 0.3 * inch))

        # Charts
        self._maybe_add_chart(elements, chart_paths, 'cost_projection_bar',
                              width=5 * inch, height=3 * inch)
        elements.append(Spacer(1, 0.15 * inch))
        self._maybe_add_chart(elements, chart_paths, 'savings_waterfall',
                              width=5 * inch, height=3 * inch)

        return elements

    # ------------------------------------------------------------------
    # Page 8: Appendix
    # ------------------------------------------------------------------

    def _build_appendix(self) -> list:
        elements: list = []

        elements.append(Paragraph("Appendix: Methodology",
                                  self._styles['SectionTitle']))
        elements.append(Spacer(1, 0.15 * inch))

        # Assessment framework
        elements.append(Paragraph(
            "<b>Three-Pillar Assessment Framework</b>",
            self._styles['SubSection'],
        ))
        elements.append(Paragraph(
            "This energy audit organizes findings and recommendations into "
            "three strategic pillars that cover current operations, legacy "
            "burden, and future readiness:",
            self._styles['BodyText2'],
        ))
        elements.append(Spacer(1, 0.05 * inch))
        elements.append(Paragraph(
            "<b>Box 1 - Current Operations:</b> Evaluates current operational "
            "efficiency including PUE (Power Usage Effectiveness), server utilization "
            "rates, energy cost optimization, cooling efficiency, and carbon footprint.",
            self._styles['BodyText2'],
        ))
        elements.append(Paragraph(
            "<b>Box 2 - Legacy & Waste:</b> Identifies inefficiencies "
            "inherited from past decisions, such as zombie servers consuming power "
            "without useful work, overprovisioned resources, legacy hardware past "
            "warranty, and cooling waste from outdated infrastructure.",
            self._styles['BodyText2'],
        ))
        elements.append(Paragraph(
            "<b>Box 3 - Future Readiness:</b> Assesses readiness for future "
            "demands through capacity forecasting, hardware refresh planning, "
            "workload scheduling optimization, renewable energy adoption, and "
            "PUE improvement trends.",
            self._styles['BodyText2'],
        ))
        elements.append(Spacer(1, 0.2 * inch))

        # Scoring methodology
        elements.append(Paragraph(
            "<b>Scoring Methodology</b>",
            self._styles['SubSection'],
        ))
        elements.append(Paragraph(
            "Each sub-metric is scored on a 0-100 scale and assigned a letter "
            "grade. Sub-metrics are combined using weighted averages to produce "
            "box-level scores. The overall score is a weighted composite: "
            "Box 1 (40%) + Box 2 (30%) + Box 3 (30%).",
            self._styles['BodyText2'],
        ))
        elements.append(Spacer(1, 0.1 * inch))

        # Grading table
        grade_data = [
            ['Grade', 'Score Range', 'Assessment'],
            ['A', '85 - 100', 'Excellent'],
            ['B', '70 - 84', 'Good'],
            ['C', '55 - 69', 'Average'],
            ['D', '40 - 54', 'Below Average'],
            ['F', '0 - 39', 'Critical'],
        ]
        grade_tbl = Table(grade_data, colWidths=[1 * inch, 1.5 * inch, 2 * inch])
        grade_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#E8F5E9')),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#E8F5E9')),
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#FFF3E0')),
            ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#FFEBEE')),
            ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#FFEBEE')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(grade_tbl)
        elements.append(Spacer(1, 0.3 * inch))

        # Disclaimer
        elements.append(Paragraph(
            "<b>Data Disclaimer</b>",
            self._styles['SubSection'],
        ))
        elements.append(Paragraph(
            "This report uses simulated data for demonstration purposes. "
            "In a production deployment, data would be sourced from live "
            "monitoring systems, DCIM platforms, and utility metering.",
            self._styles['BodyText2'],
        ))
        elements.append(Spacer(1, 0.5 * inch))

        # Footer
        elements.append(Paragraph(
            "Generated by energy-audit v0.1.0",
            self._styles['FooterStyle'],
        ))

        return elements

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _box_header(self, box: BoxScore) -> list:
        """Return score/grade header elements for a box section."""
        elements: list = []
        g_clr = _grade_color(box.grade)
        g_hex = g_clr.hexval() if hasattr(g_clr, 'hexval') else str(g_clr)
        elements.append(Paragraph(
            f'Score: <b>{box.overall_score:.1f}</b> / 100 &nbsp;&nbsp; '
            f'Grade: <font color="{g_hex}"><b>{box.grade.value}</b></font>',
            self._styles['SubSection'],
        ))
        elements.append(Spacer(1, 0.1 * inch))
        return elements

    def _sub_metrics_table(self, box: BoxScore) -> list:
        """Build the sub-metrics table for a box section."""
        elements: list = []
        if not box.sub_metrics:
            return elements

        header = ['Metric', 'Value', 'Score', 'Weight', 'Grade']
        data = [header]

        for sm in box.sub_metrics:
            g_clr = _grade_color(sm.grade)
            g_hex = g_clr.hexval() if hasattr(g_clr, 'hexval') else str(g_clr)
            data.append([
                sm.name,
                f"{sm.value:.2f}",
                f"{sm.score:.1f}",
                f"{sm.weight:.0%}",
                Paragraph(
                    f'<font color="{g_hex}"><b>{sm.grade.value}</b></font>',
                    self._styles['BodyText2'],
                ),
            ])

        col_widths = [2.2 * inch, 1.0 * inch, 0.8 * inch, 0.8 * inch, 0.8 * inch]
        tbl = Table(data, colWidths=col_widths)

        style_commands = [
            ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]
        # Alternating row colors
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_commands.append(
                    ('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY)
                )

        tbl.setStyle(TableStyle(style_commands))
        elements.append(tbl)
        elements.append(Spacer(1, 0.15 * inch))
        return elements

    def _findings_list(self, box: BoxScore) -> list:
        """Render the findings as a bulleted list."""
        elements: list = []
        if not box.findings:
            return elements

        elements.append(Paragraph("<b>Key Findings</b>",
                                  self._styles['SubSection']))
        for finding in box.findings:
            clean = _strip_rich_tags(finding)
            elements.append(Paragraph(
                f"\u2022 {clean}",
                self._styles['Finding'],
            ))
        elements.append(Spacer(1, 0.1 * inch))
        return elements

    def _maybe_add_chart(self, elements: list, chart_paths: Dict[str, str],
                         chart_key: str, width: float, height: float) -> None:
        """Add a chart image if available, otherwise skip silently."""
        path = chart_paths.get(chart_key)
        if path and os.path.isfile(path):
            try:
                img = Image(path, width=width, height=height)
                elements.append(KeepTogether([img]))
            except Exception:
                logger.warning(
                    "Failed to embed chart '%s'; skipping.", chart_key,
                    exc_info=True,
                )
        else:
            if chart_key in chart_paths:
                logger.warning(
                    "Chart file for '%s' not found at '%s'; skipping.",
                    chart_key, path,
                )
