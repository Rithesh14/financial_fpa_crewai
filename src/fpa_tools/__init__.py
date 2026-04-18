"""
FPA Tools Package — Financial FP&A Analysis Utilities.

Provides:
  - fpa_operations: Per-company financial analysis
  - analytics_engine: DuPont, Z-Score, CAGR, peer comparison
  - data_validator: CSV validation
  - chart_tools: Matplotlib chart generation (7 chart types)
  - pdf_generator: PDF report generation
  - logger: Structured logging
"""

from fpa_tools.fpa_operations import run_fpa_analysis
from fpa_tools.chart_tools import (
    generate_revenue_trend_chart,
    generate_scenario_comparison_chart,
    generate_risk_dashboard,
    generate_profitability_analysis_chart,
    generate_waterfall_chart,
    generate_radar_chart,
    generate_metrics_heatmap,
)
from fpa_tools.pdf_generator import generate_pdf_report
from fpa_tools.logger import fpa_logger, log_analysis_start, log_analysis_complete

__all__ = [
    'run_fpa_analysis',
    'generate_revenue_trend_chart',
    'generate_scenario_comparison_chart',
    'generate_risk_dashboard',
    'generate_profitability_analysis_chart',
    'generate_waterfall_chart',
    'generate_radar_chart',
    'generate_metrics_heatmap',
    'generate_pdf_report',
    'fpa_logger',
    'log_analysis_start',
    'log_analysis_complete',
]
