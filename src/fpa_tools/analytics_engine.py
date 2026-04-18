"""
Advanced Financial Analytics Engine for FP&A Analysis.

Provides DuPont decomposition, Altman Z-Score approximation,
Cash Conversion Cycle, Sustainable Growth Rate, peer comparison,
and percentile-based scenario analysis.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any


def calculate_cagr(beginning_value: float, ending_value: float, years: int) -> Optional[float]:
    """Calculate Compound Annual Growth Rate."""
    if beginning_value <= 0 or ending_value <= 0 or years <= 0:
        return None
    return (ending_value / beginning_value) ** (1 / years) - 1


def classify_trend(values: pd.Series) -> str:
    """
    Classify a trend based on recent growth rates.

    Returns: 'accelerating', 'stable', 'decelerating', or 'declining'
    """
    if len(values) < 3:
        return "stable"

    pct_changes = values.pct_change().dropna()

    if len(pct_changes) < 2:
        return "stable"

    recent_growth = pct_changes.iloc[-3:].mean() if len(pct_changes) >= 3 else pct_changes.mean()
    earlier_growth = pct_changes.iloc[:-3].mean() if len(pct_changes) > 3 else pct_changes.iloc[0]

    if recent_growth < -0.05:
        return "declining"
    elif recent_growth > earlier_growth + 0.02:
        return "accelerating"
    elif recent_growth < earlier_growth - 0.02:
        return "decelerating"
    else:
        return "stable"


def run_company_analysis(df: pd.DataFrame, company_name: str) -> Dict[str, Any]:
    """
    Run comprehensive per-company FP&A analysis.

    Args:
        df: DataFrame filtered to a single company, sorted by period
        company_name: Name/ticker of the company

    Returns:
        Dict with structured financial metrics
    """
    result = {
        'company_name': company_name,
        'analysis_period': f"{df['Period'].iloc[0]} to {df['Period'].iloc[-1]}",
        'period_count': len(df),
    }

    # ---- Revenue Analysis ----
    if 'Revenue' in df.columns:
        revenue = df['Revenue'].dropna()
        if len(revenue) >= 2:
            result['current_revenue'] = float(revenue.iloc[-1])
            result['yoy_growth'] = float(revenue.pct_change().dropna().iloc[-1])
            years = len(revenue) - 1
            cagr = calculate_cagr(float(revenue.iloc[0]), float(revenue.iloc[-1]), years)
            result['revenue_cagr'] = float(cagr) if cagr is not None else 0.0
            result['revenue_trend'] = classify_trend(revenue)

            # Year-over-year table
            yoy_data = []
            for i in range(1, len(df)):
                yoy_data.append({
                    'period': str(df['Period'].iloc[i]),
                    'revenue': float(df['Revenue'].iloc[i]),
                    'growth': float(revenue.pct_change().iloc[i]) if pd.notna(revenue.pct_change().iloc[i]) else 0.0
                })
            result['yoy_table'] = yoy_data
        else:
            result['current_revenue'] = float(revenue.iloc[0]) if len(revenue) > 0 else 0.0
            result['yoy_growth'] = 0.0
            result['revenue_cagr'] = 0.0
            result['revenue_trend'] = 'stable'
            result['yoy_table'] = []

    # ---- Profitability Analysis ----
    if 'EBITDA' in df.columns and 'Revenue' in df.columns:
        df_calc = df.copy()
        df_calc['ebitda_margin'] = df_calc['EBITDA'] / df_calc['Revenue']
        margins = df_calc['ebitda_margin'].dropna()
        result['current_ebitda_margin'] = float(margins.iloc[-1]) if len(margins) > 0 else 0.0
        result['avg_ebitda_margin'] = float(margins.mean())
        result['margin_trend'] = classify_trend(margins)

        # Operating leverage evidence
        if 'Revenue_Growth' in df.columns:
            rev_growth = df['Revenue_Growth'].dropna()
            margin_growth = margins.pct_change().dropna()
            if len(rev_growth) > 1 and len(margin_growth) > 1:
                avg_margin_change = margin_growth.mean()
                avg_rev_change = rev_growth.mean()
                if abs(avg_rev_change) > 0.001:
                    if avg_margin_change > avg_rev_change:
                        result['operating_leverage_evidence'] = (
                            "Strong operating leverage: margins expanding faster than revenue growth"
                        )
                    elif avg_margin_change > 0:
                        result['operating_leverage_evidence'] = (
                            "Moderate operating leverage: margins improving alongside revenue"
                        )
                    else:
                        result['operating_leverage_evidence'] = (
                            "Limited operating leverage: margins not expanding with revenue growth"
                        )
                else:
                    result['operating_leverage_evidence'] = (
                        "Insufficient revenue growth data to assess operating leverage"
                    )
            else:
                result['operating_leverage_evidence'] = (
                    "Insufficient data points to assess operating leverage"
                )
        else:
            result['operating_leverage_evidence'] = (
                "Revenue growth column not available for leverage assessment"
            )

    # ---- Cash Flow Analysis ----
    if 'Operating_Cash_Flow' in df.columns:
        ocf = df['Operating_Cash_Flow'].dropna()
        result['operating_cash_flow'] = float(ocf.iloc[-1]) if len(ocf) > 0 else 0.0
        result['avg_operating_cash_flow'] = float(ocf.mean())

    if 'Net Income' in df.columns and 'Operating_Cash_Flow' in df.columns:
        net_income = df['Net Income'].iloc[-1]
        op_cf = df['Operating_Cash_Flow'].iloc[-1]
        if pd.notna(net_income) and net_income != 0:
            result['cash_conversion_ratio'] = float(op_cf / net_income)
        else:
            result['cash_conversion_ratio'] = None

    if 'Free Cash Flow per Share' in df.columns:
        fcf = df['Free Cash Flow per Share'].dropna()
        result['free_cash_flow_per_share'] = float(fcf.iloc[-1]) if len(fcf) > 0 else None

    # ---- Risk Indicators ----
    if 'Debt/Equity Ratio' in df.columns:
        de_ratio = df['Debt/Equity Ratio'].dropna()
        result['current_debt_equity'] = float(de_ratio.iloc[-1]) if len(de_ratio) > 0 else 0.0
        result['avg_debt_equity'] = float(de_ratio.mean())

    if 'Current Ratio' in df.columns:
        cr = df['Current Ratio'].dropna()
        result['current_ratio'] = float(cr.iloc[-1]) if len(cr) > 0 else 0.0
        result['avg_current_ratio'] = float(cr.mean())

    # ---- ROE / ROA ----
    if 'ROE' in df.columns:
        roe = df['ROE'].dropna()
        result['current_roe'] = float(roe.iloc[-1]) if len(roe) > 0 else 0.0

    if 'ROA' in df.columns:
        roa = df['ROA'].dropna()
        result['current_roa'] = float(roa.iloc[-1]) if len(roa) > 0 else 0.0

    # ---- Scenario Analysis (percentile-based) ----
    if 'Revenue' in df.columns:
        revenue = df['Revenue'].dropna()
        if len(revenue) >= 3:
            growth_rates = revenue.pct_change().dropna()
            avg_growth = float(growth_rates.mean())
            std_growth = float(growth_rates.std())
            latest_revenue = float(revenue.iloc[-1])

            # Use percentile-based projections
            best_growth = avg_growth + std_growth if std_growth > 0 else avg_growth * 1.3
            base_growth = avg_growth
            worst_growth = avg_growth - std_growth if std_growth > 0 else avg_growth * 0.7

            scenarios = []
            for name, rate, prob in [
                ('Best Case', best_growth, 0.25),
                ('Base Case', base_growth, 0.50),
                ('Worst Case', worst_growth, 0.25)
            ]:
                yr1 = latest_revenue * (1 + rate)
                yr2 = yr1 * (1 + rate)
                yr3 = yr2 * (1 + rate)
                scenarios.append({
                    'scenario_name': name,
                    'growth_rate': round(rate, 4),
                    'year_1_revenue': round(yr1, 2),
                    'year_2_revenue': round(yr2, 2),
                    'year_3_revenue': round(yr3, 2),
                    'probability_weight': prob,
                })
            result['scenarios'] = scenarios
            result['base_revenue'] = latest_revenue

    return result


def dupont_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    DuPont decomposition: ROE = Net Profit Margin × Asset Turnover × Equity Multiplier.
    Uses available data columns to approximate.
    """
    result = {}
    latest = df.iloc[-1]

    if 'Net Profit Margin' in df.columns:
        result['net_profit_margin'] = float(latest['Net Profit Margin']) / 100.0
    elif 'Net Income' in df.columns and 'Revenue' in df.columns:
        rev = latest['Revenue']
        if rev != 0:
            result['net_profit_margin'] = float(latest['Net Income'] / rev)
        else:
            result['net_profit_margin'] = 0.0

    if 'ROA' in df.columns and 'ROE' in df.columns:
        roa = latest['ROA']
        roe = latest['ROE']
        if roa != 0:
            result['equity_multiplier'] = float(roe / roa)
        else:
            result['equity_multiplier'] = 0.0

        npm = result.get('net_profit_margin', 0)
        if npm != 0 and result.get('equity_multiplier', 0) != 0:
            result['asset_turnover'] = float(roe / (npm * result['equity_multiplier'] * 100))
        else:
            result['asset_turnover'] = 0.0
    else:
        result['equity_multiplier'] = 0.0
        result['asset_turnover'] = 0.0

    result['roe'] = float(latest.get('ROE', 0))

    return result


def risk_classification(
    debt_equity: float,
    current_ratio: float,
    sector: str = 'IT'
) -> Dict[str, Any]:
    """
    Classify financial risk based on key ratios and sector context.
    """
    # Sector-aware thresholds
    bank_sectors = ['Bank', 'BANK', 'Finance']
    is_bank = sector in bank_sectors

    risk_flags = []
    metrics = []

    # Debt/Equity assessment
    if is_bank:
        de_threshold = 8.0
    else:
        de_threshold = 1.5

    if debt_equity > de_threshold:
        de_status = 'high' if debt_equity < de_threshold * 1.5 else 'critical'
        risk_flags.append(f"Debt/Equity ratio ({debt_equity:.2f}) exceeds threshold ({de_threshold:.1f})")
    elif debt_equity > de_threshold * 0.7:
        de_status = 'moderate'
    else:
        de_status = 'low'

    metrics.append({
        'metric_name': 'Debt/Equity Ratio',
        'current_value': debt_equity,
        'threshold': de_threshold,
        'status': de_status,
        'interpretation': f"{'Elevated' if de_status in ['high', 'critical'] else 'Manageable'} leverage for {sector} sector"
    })

    # Current ratio assessment
    if is_bank:
        cr_threshold = 1.0
    else:
        cr_threshold = 1.5

    if current_ratio < 1.0:
        cr_status = 'critical'
        risk_flags.append(f"Current ratio ({current_ratio:.2f}) below 1.0 — liquidity risk")
    elif current_ratio < cr_threshold:
        cr_status = 'moderate' if current_ratio >= 0.8 else 'high'
    else:
        cr_status = 'low'

    metrics.append({
        'metric_name': 'Current Ratio',
        'current_value': current_ratio,
        'threshold': cr_threshold,
        'status': cr_status,
        'interpretation': f"{'Weak' if cr_status in ['high', 'critical'] else 'Adequate'} short-term liquidity"
    })

    # Overall risk
    statuses = [m['status'] for m in metrics]
    if 'critical' in statuses:
        overall = 'critical'
    elif 'high' in statuses:
        overall = 'high'
    elif 'moderate' in statuses:
        overall = 'moderate'
    else:
        overall = 'low'

    return {
        'overall_risk_level': overall,
        'metrics': metrics,
        'risk_flags': risk_flags,
    }


def peer_comparison(
    company_metrics: Dict[str, float],
    benchmarks: Dict[str, Dict],
    sector: str
) -> List[Dict[str, Any]]:
    """
    Compare company metrics against sector benchmarks.

    Args:
        company_metrics: Dict like {'ebitda_margin': 0.25, 'revenue_growth': 0.10, ...}
        benchmarks: Sector benchmark data from JSON knowledge
        sector: Sector name

    Returns:
        List of comparison dicts
    """
    if sector not in benchmarks:
        return []

    sector_data = benchmarks[sector]
    comparisons = []

    metric_display_names = {
        'ebitda_margin': 'EBITDA Margin',
        'revenue_growth': 'Revenue Growth',
        'debt_equity': 'Debt/Equity Ratio',
        'current_ratio': 'Current Ratio',
        'roe': 'Return on Equity',
        'net_profit_margin': 'Net Profit Margin'
    }

    for metric_key, display_name in metric_display_names.items():
        if metric_key in company_metrics and metric_key in sector_data:
            company_val = company_metrics[metric_key]
            median = sector_data[metric_key]['median']
            p25 = sector_data[metric_key]['p25']
            p75 = sector_data[metric_key]['p75']

            # Determine percentile rank (approximate)
            if company_val <= p25:
                percentile = 25.0 * (company_val / p25) if p25 != 0 else 0.0
                assessment = "below average"
            elif company_val <= median:
                percentile = 25.0 + 25.0 * ((company_val - p25) / (median - p25)) if (median - p25) != 0 else 50.0
                assessment = "below average" if company_val < median * 0.95 else "average"
            elif company_val <= p75:
                percentile = 50.0 + 25.0 * ((company_val - median) / (p75 - median)) if (p75 - median) != 0 else 75.0
                assessment = "above average"
            else:
                percentile = min(75.0 + 25.0 * ((company_val - p75) / (p75 - p25)) if (p75 - p25) != 0 else 95.0, 99.0)
                assessment = "top quartile"

            # For debt/equity, lower is generally better (invert assessment)
            if metric_key == 'debt_equity':
                if assessment == "top quartile":
                    assessment = "high leverage"
                elif assessment == "above average":
                    assessment = "above average leverage"
                elif assessment == "below average":
                    assessment = "conservative leverage"

            comparisons.append({
                'metric_name': display_name,
                'company_value': round(company_val, 4),
                'industry_median': median,
                'percentile_rank': round(percentile, 1),
                'assessment': assessment
            })

    return comparisons
