"""
FP&A Operations Module — Per-Company Financial Analysis.

Enhanced from v1 to support:
- Per-company filtering (stops averaging across all companies)
- CAGR and trend classification
- Year-over-year tables
- Percentile-based scenario analysis
- Integration with analytics engine

v2 fix — compact_summary:
  The tool return value is injected directly into the LLM's message history
  as an "Observation". When the raw dict is returned (~600 tokens of nested
  Python dicts and lists), the Llama 4 Scout model on Groq sometimes returns
  a blank/None completion on the NEXT turn — because the observation token
  count plus the conversation history exhausts the model's output budget.

  Fix: `run_fpa_analysis` now returns a compact plain-text summary (~120 tokens)
  that contains every number the agent needs to populate PerformanceAnalysisOutput,
  without the verbose nested structure.  The full raw dict is still available
  via `run_fpa_analysis_raw()` for internal use by flow.py / PDF generator.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

from fpa_tools.analytics_engine import (
    run_company_analysis,
    risk_classification,
    calculate_cagr,
    classify_trend,
)
from fpa_tools.data_validator import get_company_data, validate_company_selection


# ── Internal helper ────────────────────────────────────────────────────────────

def _load_and_filter(
    csv_path: str,
    company: Optional[str],
    sector: Optional[str],
) -> tuple:
    """
    Load the CSV, resolve company column, filter to the requested company,
    and detect sector.  Returns (company_df, resolved_company, resolved_sector).
    """
    if not csv_path:
        raise ValueError("CSV path cannot be empty")

    df = pd.read_csv(csv_path)

    # Find company column (handle trailing whitespace in header)
    company_col = None
    for col in df.columns:
        if col.strip() == 'Company':
            company_col = col
            break

    if company_col:
        df[company_col] = df[company_col].str.strip()

    # Auto-select first company if none specified
    if company is None and company_col:
        company = df[company_col].unique()[0]

    # Filter to selected company
    if company and company_col:
        company_df = df[df[company_col] == company.strip()].copy()
        if len(company_df) == 0:
            available = df[company_col].unique().tolist()
            raise ValueError(
                f"Company '{company}' not found. Available: {available}"
            )
    else:
        company_df = df.copy()

    company_df = company_df.sort_values('Period').reset_index(drop=True)

    # Detect sector from data if not provided
    if sector is None and 'Category' in company_df.columns:
        sector = str(company_df['Category'].iloc[0]).strip()

    return company_df, company or "Unknown", sector or 'IT'


def _build_compact_summary(analysis: Dict[str, Any]) -> str:
    """
    Convert the full analysis dict into a compact ~120-token plain-text
    summary suitable for LLM consumption as a tool Observation.

    Every number an agent needs to fill PerformanceAnalysisOutput is present.
    The verbose nested arrays (full yoy list, scenario objects) are condensed
    to single lines so the model does not hit its output-token budget.
    """
    # --- YoY last-5 condensed to one line ---
    yoy_table = analysis.get('yoy_table', [])
    yoy_last5 = yoy_table[-5:] if yoy_table else []
    yoy_str = ", ".join(
        f"{y['period']}:{y['growth']*100:+.1f}%"
        for y in yoy_last5
    ) if yoy_last5 else "N/A"

    # --- Scenarios condensed to one line each ---
    scenarios = analysis.get('scenarios', [])
    scen_lines = []
    for s in scenarios:
        scen_lines.append(
            f"  {s['scenario_name']}: growth={s['growth_rate']*100:.1f}% "
            f"Y1=${s['year_1_revenue']:,.0f}M Y3=${s['year_3_revenue']:,.0f}M "
            f"prob={s['probability_weight']}"
        )
    scen_str = "\n".join(scen_lines) if scen_lines else "  N/A"

    # --- Risk flags condensed ---
    risk = analysis.get('risk', {})
    flags_str = "; ".join(risk.get('risk_flags', [])) or "None"

    # --- Handle possible None values ---
    ccr = analysis.get('cash_conversion_ratio')
    ccr_str = f"{ccr:.3f}" if ccr is not None else "N/A"
    roe = analysis.get('current_roe')
    roe_str = f"{roe:.1f}%" if roe is not None else "N/A"
    roa = analysis.get('current_roa')
    roa_str = f"{roa:.1f}%" if roa is not None else "N/A"

    summary = (
        f"[FP&A Analysis: {analysis.get('company_name', 'N/A')} | "
        f"Period: {analysis.get('analysis_period', 'N/A')}]\n"
        f"Revenue: ${analysis.get('current_revenue', 0):,.0f}M | "
        f"CAGR: {analysis.get('revenue_cagr', 0)*100:.2f}% | "
        f"YoY latest: {analysis.get('yoy_growth', 0)*100:.2f}% | "
        f"Trend: {analysis.get('revenue_trend', 'N/A')}\n"
        f"YoY last 5: {yoy_str}\n"
        f"EBITDA margin: {analysis.get('current_ebitda_margin', 0)*100:.1f}% | "
        f"5yr avg: {analysis.get('avg_ebitda_margin', 0)*100:.1f}% | "
        f"Trend: {analysis.get('margin_trend', 'N/A')}\n"
        f"Operating CF: ${analysis.get('operating_cash_flow', 0):,.0f}M | "
        f"Avg CF: ${analysis.get('avg_operating_cash_flow', 0):,.0f}M | "
        f"Cash conv ratio: {ccr_str}\n"
        f"Debt/Equity: {analysis.get('current_debt_equity', 0):.2f} | "
        f"Current ratio: {analysis.get('current_ratio', 0):.2f} | "
        f"ROE: {roe_str} | ROA: {roa_str}\n"
        f"Operating leverage: {analysis.get('operating_leverage_evidence', 'N/A')}\n"
        f"Base revenue: ${analysis.get('base_revenue', 0):,.0f}M\n"
        f"Scenarios:\n{scen_str}\n"
        f"Risk level: {risk.get('overall_risk_level', 'N/A').upper()} | "
        f"Flags: {flags_str}\n"
        f"Sector: {analysis.get('sector', 'N/A')}"
    )
    return summary


# ── Public API ─────────────────────────────────────────────────────────────────

def run_fpa_analysis(
    csv_path: str,
    company: Optional[str] = None,
    sector: Optional[str] = None,
) -> str:
    """
    Run comprehensive FP&A analysis on financial data.

    Returns a COMPACT PLAIN-TEXT SUMMARY (~120 tokens) instead of a raw dict.

    Rationale: This function's return value is injected into the LLM context as
    a tool Observation.  Returning the full raw analysis dict (~600 tokens of
    nested Python objects) caused Llama 4 Scout on Groq to produce an empty/None
    completion on the very next turn — crashing the agent with
    "Invalid response from LLM call - None or empty".

    The compact summary preserves every number the agent needs while keeping
    the Observation short enough that the model has ample budget for its reply.

    Args:
        csv_path: Path to the CSV file containing financial data
        company:  Company name/ticker to analyze (required for accurate results)
        sector:   Industry sector for risk context (e.g. 'IT', 'FinTech', 'Bank')

    Returns:
        str: Compact plain-text financial metrics summary
    """
    company_df, resolved_company, resolved_sector = _load_and_filter(
        csv_path, company, sector
    )

    # Run the comprehensive per-company analysis
    analysis = run_company_analysis(company_df, resolved_company)

    # Add risk classification
    debt_equity = analysis.get('current_debt_equity', analysis.get('debt_equity', 0.0))
    current_ratio = analysis.get('current_ratio', 0.0)
    risk_info = risk_classification(debt_equity, current_ratio, resolved_sector)
    analysis['risk'] = risk_info
    analysis['sector'] = resolved_sector

    return _build_compact_summary(analysis)


def run_fpa_analysis_raw(
    csv_path: str,
    company: Optional[str] = None,
    sector: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Same as run_fpa_analysis but returns the FULL raw dict.

    Use this from Python code (flow.py, pdf_generator, tests) where you need
    structured access to nested keys.  Do NOT use as a CrewAI tool return value
    — it will produce the "None or empty LLM response" crash described above.

    Args:
        csv_path: Path to the CSV file containing financial data
        company:  Company name/ticker to analyze
        sector:   Industry sector for risk context

    Returns:
        dict: Full structured financial metrics including all nested arrays
    """
    company_df, resolved_company, resolved_sector = _load_and_filter(
        csv_path, company, sector
    )

    analysis = run_company_analysis(company_df, resolved_company)

    debt_equity = analysis.get('current_debt_equity', analysis.get('debt_equity', 0.0))
    current_ratio = analysis.get('current_ratio', 0.0)
    risk_info = risk_classification(debt_equity, current_ratio, resolved_sector)
    analysis['risk'] = risk_info
    analysis['sector'] = resolved_sector

    return analysis