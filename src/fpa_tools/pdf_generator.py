"""
PDF Report Generator for Financial FP&A Analysis
Creates professional board-ready PDF reports with charts and insights.

v2 changes:
  - _render_text_block(): converts raw text (newlines, bullet dashes, **bold**)
    into properly formatted ReportLab Paragraph elements — no more wall-of-text dumps
  - Strategic Recommendations section now renders cfo_summary content
    instead of hardcoded boilerplate bullets
  - Performance Analysis section renders each sub-section (metrics, analysis,
    AI narrative) as separate formatted blocks
  - All sections have graceful non-empty fallbacks
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle, ListFlowable, ListItem
from reportlab.lib import colors
from datetime import datetime
import os
import re
from crewai.tools import tool


def ensure_reports_dir():
    """Ensure reports directory exists"""
    os.makedirs("reports", exist_ok=True)


def add_header_footer(canvas, doc):
    """Add header and footer to each page"""
    canvas.saveState()

    # Footer
    canvas.setFont('Helvetica', 9)
    canvas.drawString(inch, 0.5 * inch, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    canvas.drawRightString(7.5 * inch, 0.5 * inch, f"Page {doc.page}")

    # Header (except first page)
    if doc.page > 1:
        canvas.setFont('Helvetica-Bold', 10)
        canvas.drawString(inch, 10.5 * inch, "Financial FP&A Analysis Report")
        canvas.line(inch, 10.4 * inch, 7.5 * inch, 10.4 * inch)

    canvas.restoreState()


def _render_text_block(text: str, story: list, body_style, bullet_style, heading2_style):
    """
    Convert a raw text string into properly formatted ReportLab elements.

    Handles:
      - Blank input → adds a placeholder paragraph
      - Lines starting with '-' or '*' → rendered as bullet points
      - Lines starting with '##' or '**text**' → rendered as sub-headings
      - Lines with '**bold**' inline → preserved as ReportLab <b> tags
      - Plain paragraphs → separated at blank lines, rendered as body text
      - Newlines within a paragraph → collapsed into spaces (PDF reflows text)
    """
    if not text or not text.strip():
        return  # caller adds fallback

    # Normalise line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Replace markdown **bold** with ReportLab XML bold
    def md_to_rl_bold(s):
        return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)

    # Escape XML-special chars that ReportLab can't handle (except our own tags)
    def safe(s):
        s = s.replace('&', '&amp;')
        # Restore our own tags after escaping
        s = s.replace('&amp;lt;b&amp;gt;', '<b>').replace('&amp;lt;/b&amp;gt;', '</b>')
        return s

    lines = text.split('\n')
    current_para_lines = []

    def flush_para():
        """Emit the buffered plain-text paragraph."""
        if current_para_lines:
            combined = ' '.join(current_para_lines).strip()
            if combined:
                combined = md_to_rl_bold(safe(combined))
                story.append(Paragraph(combined, body_style))
                story.append(Spacer(1, 0.05 * inch))
            current_para_lines.clear()

    for line in lines:
        stripped = line.strip()

        # Blank line → paragraph break
        if not stripped:
            flush_para()
            continue

        # Sub-heading: lines starting with ## or ### 
        if stripped.startswith('##'):
            flush_para()
            heading_text = stripped.lstrip('#').strip()
            heading_text = md_to_rl_bold(safe(heading_text))
            story.append(Paragraph(heading_text, heading2_style))
            story.append(Spacer(1, 0.05 * inch))
            continue

        # Bullet point: lines starting with - or * (but not **)
        if re.match(r'^[-*]\s+', stripped) and not stripped.startswith('**'):
            flush_para()
            bullet_text = re.sub(r'^[-*]\s+', '', stripped)
            bullet_text = md_to_rl_bold(safe(bullet_text))
            story.append(Paragraph(f"• {bullet_text}", bullet_style))
            story.append(Spacer(1, 0.04 * inch))
            continue

        # Numbered list: lines starting with "1." "2." etc.
        if re.match(r'^\d+\.\s+', stripped):
            flush_para()
            num_text = re.sub(r'^\d+\.\s+', '', stripped)
            num_text = md_to_rl_bold(safe(num_text))
            match = re.match(r'^(\d+)\.', stripped)
            num = match.group(1) if match else '•'
            story.append(Paragraph(f"<b>{num}.</b> {num_text}", bullet_style))
            story.append(Spacer(1, 0.04 * inch))
            continue

        # Metric line (contains | separator) — render as monospace-style body
        if '|' in stripped and not stripped.startswith('<'):
            flush_para()
            safe_line = md_to_rl_bold(safe(stripped))
            story.append(Paragraph(safe_line, body_style))
            story.append(Spacer(1, 0.04 * inch))
            continue

        # Regular text → accumulate into paragraph
        current_para_lines.append(stripped)

    flush_para()


def build_pdf_report(
    performance_insights: str = "",
    market_insights: str = "",
    scenario_insights: str = "",
    risk_insights: str = "",
    cfo_summary: str = "",
    chart_dir: str = "charts",
    output_path: str = "reports/fpa_analysis.pdf"
):
    """
    Plain Python function — build and write the PDF report.
    Called directly by flow.py (avoids CrewAI Tool wrapper TypeError).

    Args:
        performance_insights: Metrics + AI narrative from Stage 1 + LLM
        market_insights:      Strengths & concerns (Top 3 each)
        scenario_insights:    Forward-looking scenario projections
        risk_insights:        Risk level + flags + LLM risk commentary
        cfo_summary:          Strategic Recommendations from LLM (or full report)
        chart_dir:            Directory containing generated charts
        output_path:          Where to save the PDF

    Returns:
        dict: PDF path and status
    """
    ensure_reports_dir()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )

    story = []
    styles = getSampleStyleSheet()

    # ── Style definitions ─────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    heading1_style = ParagraphStyle(
        'CustomHeading1',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2E86AB'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=colors.HexColor('#118AB2'),
        spaceAfter=8,
        spaceBefore=8,
        fontName='Helvetica-Bold'
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        leading=15
    )

    bullet_style = ParagraphStyle(
        'BulletBody',
        parent=styles['BodyText'],
        fontSize=11,
        leftIndent=18,
        spaceAfter=4,
        leading=15
    )

    # ── COVER PAGE ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph("Financial FP&amp;A Analysis Report", title_style))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        f"<b>Report Date:</b> {datetime.now().strftime('%B %d, %Y')}",
        ParagraphStyle('center', parent=body_style, alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(
        "<b>Prepared by:</b> AI Financial Analysis Pipeline",
        ParagraphStyle('center', parent=body_style, alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 1 * inch))

    # Executive summary box on cover — short excerpt from cfo_summary or fallback
    exec_summary_text = (cfo_summary[:600] + "…" if len(cfo_summary) > 600 else cfo_summary) \
        if cfo_summary else \
        "Comprehensive financial analysis including performance metrics, scenario planning, risk assessment, and strategic recommendations."

    summary_data = [
        ['EXECUTIVE SUMMARY'],
        [Paragraph(exec_summary_text, body_style)]
    ]
    summary_table = Table(summary_data, colWidths=[6.5 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0),  colors.HexColor('#2E86AB')),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.whitesmoke),
        ('ALIGN',         (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0),  14),
        ('BOTTOMPADDING', (0, 0), (-1, 0),  12),
        ('BACKGROUND',    (0, 1), (-1, -1), colors.HexColor('#F0F8FF')),
        ('GRID',          (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 1), (-1, -1), 12),
        ('RIGHTPADDING',  (0, 1), (-1, -1), 12),
        ('TOPPADDING',    (0, 1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 12),
    ]))
    story.append(summary_table)
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ─────────────────────────────────────────────────────
    story.append(Paragraph("Table of Contents", heading1_style))
    story.append(Spacer(1, 0.2 * inch))
    toc_items = [
        "1. Performance Analysis",
        "2. Market Context &amp; Strengths / Concerns",
        "3. Scenario Planning",
        "4. Risk Assessment",
        "5. Strategic Recommendations",
    ]
    for item in toc_items:
        story.append(Paragraph(item, body_style))
        story.append(Spacer(1, 0.08 * inch))
    story.append(PageBreak())

    # ── 1. PERFORMANCE ANALYSIS ───────────────────────────────────────────────
    story.append(Paragraph("1. Performance Analysis", heading1_style))
    story.append(Spacer(1, 0.15 * inch))

    if performance_insights:
        _render_text_block(performance_insights, story, body_style, bullet_style, heading2_style)
    else:
        story.append(Paragraph(
            "Detailed analysis of historical and current financial performance including "
            "revenue growth, profitability metrics, and operational efficiency.",
            body_style
        ))

    story.append(Spacer(1, 0.2 * inch))

    revenue_chart_path = os.path.join(chart_dir, "revenue_trend.png")
    if os.path.exists(revenue_chart_path):
        story.append(Paragraph("Revenue Trend Analysis", heading2_style))
        story.append(Image(revenue_chart_path, width=6 * inch, height=3 * inch))
        story.append(Spacer(1, 0.15 * inch))

    profit_chart_path = os.path.join(chart_dir, "profitability_analysis.png")
    if os.path.exists(profit_chart_path):
        story.append(Paragraph("Profitability Analysis", heading2_style))
        story.append(Image(profit_chart_path, width=6 * inch, height=3 * inch))
        story.append(Spacer(1, 0.15 * inch))

    waterfall_path = os.path.join(chart_dir, "waterfall_revenue.png")
    if os.path.exists(waterfall_path):
        story.append(Paragraph("Revenue Waterfall (YoY)", heading2_style))
        story.append(Image(waterfall_path, width=6 * inch, height=3 * inch))
        story.append(Spacer(1, 0.15 * inch))

    story.append(PageBreak())

    # ── 2. MARKET CONTEXT & STRENGTHS / CONCERNS ──────────────────────────────
    story.append(Paragraph("2. Market Context &amp; Strengths / Concerns", heading1_style))
    story.append(Spacer(1, 0.15 * inch))

    if market_insights:
        _render_text_block(market_insights, story, body_style, bullet_style, heading2_style)
    else:
        story.append(Paragraph(
            "Industry benchmarks, competitive positioning, strengths, and key concerns "
            "provide context for evaluating overall financial performance.",
            body_style
        ))

    story.append(Spacer(1, 0.15 * inch))
    radar_path = os.path.join(chart_dir, "radar_metrics.png")
    if os.path.exists(radar_path):
        story.append(Paragraph("Financial Metrics Radar", heading2_style))
        story.append(Image(radar_path, width=5 * inch, height=3.5 * inch))
        story.append(Spacer(1, 0.15 * inch))

    story.append(PageBreak())

    # ── 3. SCENARIO PLANNING ──────────────────────────────────────────────────
    story.append(Paragraph("3. Scenario Planning", heading1_style))
    story.append(Spacer(1, 0.15 * inch))

    if scenario_insights:
        _render_text_block(scenario_insights, story, body_style, bullet_style, heading2_style)
    else:
        story.append(Paragraph(
            "Forward-looking scenario analysis examines best-case, base-case, and worst-case "
            "revenue projections based on historical CAGR and market conditions. "
            "The scenario comparison chart below illustrates the projected revenue trajectories "
            "across each scenario over a three-year horizon.",
            body_style
        ))

    story.append(Spacer(1, 0.15 * inch))
    scenario_chart_path = os.path.join(chart_dir, "scenario_comparison.png")
    if os.path.exists(scenario_chart_path):
        story.append(Paragraph("Scenario Comparison Chart", heading2_style))
        story.append(Image(scenario_chart_path, width=6 * inch, height=3.5 * inch))
        story.append(Spacer(1, 0.15 * inch))

    story.append(PageBreak())

    # ── 4. RISK ASSESSMENT ────────────────────────────────────────────────────
    story.append(Paragraph("4. Risk Assessment", heading1_style))
    story.append(Spacer(1, 0.15 * inch))

    if risk_insights:
        _render_text_block(risk_insights, story, body_style, bullet_style, heading2_style)
    else:
        story.append(Paragraph(
            "Comprehensive risk evaluation covering liquidity position, leverage ratios, "
            "and cash flow sustainability.",
            body_style
        ))

    story.append(Spacer(1, 0.15 * inch))
    risk_chart_path = os.path.join(chart_dir, "risk_dashboard.png")
    if os.path.exists(risk_chart_path):
        story.append(Paragraph("Risk Metrics Dashboard", heading2_style))
        story.append(Image(risk_chart_path, width=6.5 * inch, height=4 * inch))
        story.append(Spacer(1, 0.15 * inch))

    story.append(PageBreak())

    # ── 5. STRATEGIC RECOMMENDATIONS ──────────────────────────────────────────
    story.append(Paragraph("5. Strategic Recommendations", heading1_style))
    story.append(Spacer(1, 0.15 * inch))

    if cfo_summary:
        # Render the actual LLM-generated recommendations (properly formatted)
        _render_text_block(cfo_summary, story, body_style, bullet_style, heading2_style)
    else:
        # Fallback generic recommendations
        fallback_recs = [
            "Continue monitoring revenue growth trends and adjust capital allocation strategies accordingly.",
            "Maintain focus on profitability margins while pursuing sustainable growth initiatives.",
            "Monitor liquidity ratios and ensure adequate cash reserves for operational continuity.",
            "Prepare contingency plans for adverse scenario outcomes identified in the scenario analysis.",
            "Leverage competitive strengths identified in the market context to deepen market position.",
        ]
        for i, rec in enumerate(fallback_recs, 1):
            story.append(Paragraph(f"<b>{i}.</b> {rec}", bullet_style))
            story.append(Spacer(1, 0.08 * inch))

    story.append(Spacer(1, 0.4 * inch))

    # ── DISCLAIMER ────────────────────────────────────────────────────────────
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=body_style,
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_JUSTIFY
    )
    story.append(Paragraph(
        "<b>Disclaimer:</b> This report is generated by an AI pipeline for analytical purposes. "
        "All projections and scenarios are based on historical data and should be validated "
        "by qualified financial professionals before making business decisions.",
        disclaimer_style
    ))

    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)

    return {
        "pdf_path": output_path,
        "status": "success",
        "message": f"PDF report generated successfully at {output_path}"
    }


# ── CrewAI Tool Wrapper ────────────────────────────────────────────────────────
@tool
def generate_pdf_report(
    performance_insights: str = "",
    market_insights: str = "",
    scenario_insights: str = "",
    risk_insights: str = "",
    cfo_summary: str = "",
    chart_dir: str = "charts",
    output_path: str = "reports/fpa_analysis.pdf"
):
    """
    Generate comprehensive PDF report with all insights and charts.
    Thin @tool wrapper around build_pdf_report() for use by CrewAI agents.
    """
    return build_pdf_report(
        performance_insights=performance_insights,
        market_insights=market_insights,
        scenario_insights=scenario_insights,
        risk_insights=risk_insights,
        cfo_summary=cfo_summary,
        chart_dir=chart_dir,
        output_path=output_path,
    )