"""
PDF Report Generator for Financial FP&A Analysis
Creates professional board-ready PDF reports with charts and insights
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime
import os
from crewai.tools import tool  # Use crewai.tools instead of crewai_tools


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
    
    Args:
        performance_insights: Insights from FPA Analyst
        market_insights: Insights from Market Researcher
        scenario_insights: Insights from Scenario Analyst
        risk_insights: Insights from Risk Analyst
        cfo_summary: Executive summary from CFO Advisor
        chart_dir: Directory containing generated charts
        output_path: Where to save the PDF
        
    Returns:
        dict: PDF path and status
    """
    ensure_reports_dir()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )
    
    # Container for PDF elements
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
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
        fontSize=14,
        textColor=colors.HexColor('#118AB2'),
        spaceAfter=10,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=12,
        leading=14
    )
    
    # ===== COVER PAGE =====
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("Financial FP&A Analysis Report", title_style))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"<b>Report Date:</b> {datetime.now().strftime('%B %d, %Y')}", 
                          ParagraphStyle('center', parent=body_style, alignment=TA_CENTER)))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("<b>Prepared by:</b> CrewAI Financial Analysis Team", 
                          ParagraphStyle('center', parent=body_style, alignment=TA_CENTER)))
    story.append(Spacer(1, 1*inch))
    
    # Executive summary box
    summary_data = [
        ['EXECUTIVE SUMMARY'],
        [Paragraph(cfo_summary if cfo_summary else "Comprehensive financial analysis including performance metrics, scenario planning, risk assessment, and market context.", body_style)]
    ]
    summary_table = Table(summary_data, colWidths=[6.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 1), (-1, -1), 12),
        ('RIGHTPADDING', (0, 1), (-1, -1), 12),
        ('TOPPADDING', (0, 1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 12),
    ]))
    story.append(summary_table)
    
    story.append(PageBreak())
    
    # ===== TABLE OF CONTENTS =====
    story.append(Paragraph("Table of Contents", heading1_style))
    story.append(Spacer(1, 0.2*inch))
    
    toc_items = [
        "1. Performance Analysis",
        "2. Market Context & Benchmarks",
        "3. Scenario Planning",
        "4. Risk Assessment",
        "5. Strategic Recommendations"
    ]
    
    for item in toc_items:
        story.append(Paragraph(item, body_style))
        story.append(Spacer(1, 0.1*inch))
    
    story.append(PageBreak())
    
    # ===== PERFORMANCE ANALYSIS =====
    story.append(Paragraph("1. Performance Analysis", heading1_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph(performance_insights if performance_insights else 
                          "Detailed analysis of historical and current financial performance including revenue growth, profitability metrics, and operational efficiency.",
                          body_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Revenue trend chart
    revenue_chart_path = os.path.join(chart_dir, "revenue_trend.png")
    if os.path.exists(revenue_chart_path):
        story.append(Paragraph("Revenue Trend Analysis", heading2_style))
        img = Image(revenue_chart_path, width=6*inch, height=3*inch)
        story.append(img)
        story.append(Spacer(1, 0.2*inch))
    
    # Profitability chart
    profit_chart_path = os.path.join(chart_dir, "profitability_analysis.png")
    if os.path.exists(profit_chart_path):
        story.append(Paragraph("Profitability Analysis", heading2_style))
        img = Image(profit_chart_path, width=6*inch, height=3*inch)
        story.append(img)
        story.append(Spacer(1, 0.2*inch))
    
    story.append(PageBreak())
    
    # ===== MARKET CONTEXT =====
    story.append(Paragraph("2. Market Context & Benchmarks", heading1_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph(market_insights if market_insights else 
                          "Industry benchmarks, competitive positioning, and market trends provide context for financial performance evaluation.",
                          body_style))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(PageBreak())
    
    # ===== SCENARIO PLANNING =====
    story.append(Paragraph("3. Scenario Planning", heading1_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph(scenario_insights if scenario_insights else 
                          "Forward-looking scenario analysis examining best-case, base-case, and worst-case revenue projections based on historical trends.",
                          body_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Scenario chart
    scenario_chart_path = os.path.join(chart_dir, "scenario_comparison.png")
    if os.path.exists(scenario_chart_path):
        story.append(Paragraph("Scenario Comparison", heading2_style))
        img = Image(scenario_chart_path, width=5*inch, height=3*inch)
        story.append(img)
        story.append(Spacer(1, 0.2*inch))
    
    story.append(PageBreak())
    
    # ===== RISK ASSESSMENT =====
    story.append(Paragraph("4. Risk Assessment", heading1_style))
    story.append(Spacer(1, 0.2*inch))
    
    story.append(Paragraph(risk_insights if risk_insights else 
                          "Comprehensive risk evaluation covering liquidity position, leverage ratios, and cash flow sustainability.",
                          body_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Risk dashboard
    risk_chart_path = os.path.join(chart_dir, "risk_dashboard.png")
    if os.path.exists(risk_chart_path):
        story.append(Paragraph("Risk Metrics Dashboard", heading2_style))
        img = Image(risk_chart_path, width=6.5*inch, height=4.5*inch)
        story.append(img)
        story.append(Spacer(1, 0.2*inch))
    
    story.append(PageBreak())
    
    # ===== STRATEGIC RECOMMENDATIONS =====
    story.append(Paragraph("5. Strategic Recommendations", heading1_style))
    story.append(Spacer(1, 0.2*inch))
    
    recommendations = [
        "Continue monitoring revenue growth trends and adjust strategies accordingly",
        "Maintain focus on profitability margins while pursuing growth",
        "Monitor liquidity ratios and ensure adequate cash reserves",
        "Prepare contingency plans for worst-case scenario outcomes",
        "Leverage market opportunities identified in competitive analysis"
    ]
    
    for i, rec in enumerate(recommendations, 1):
        story.append(Paragraph(f"<b>{i}.</b> {rec}", body_style))
        story.append(Spacer(1, 0.1*inch))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Disclaimer
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=body_style,
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_JUSTIFY
    )
    
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("<b>Disclaimer:</b> This report is generated by AI agents for analytical purposes. "
                          "All projections and scenarios are based on historical data and should be validated "
                          "by financial professionals before making business decisions.",
                          disclaimer_style))
    
    # Build PDF
    doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    
    return {
        "pdf_path": output_path,
        "status": "success",
        "message": f"PDF report generated successfully at {output_path}"
    }
