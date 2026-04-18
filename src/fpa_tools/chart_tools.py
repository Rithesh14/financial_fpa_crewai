"""
Chart Generation Tools for Financial FP&A Analysis.
Enhanced v2: Per-company filtering + 3 new chart types.

All chart tools accept an optional 'company' parameter to scope
the visualization to a specific company instead of averaging all.
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend — avoids async issues

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import numpy as np
import os
from typing import Optional
from crewai.tools import tool


# ── Professional style ──────────────────────────────────────────────────────
plt.style.use('seaborn-v0_8-darkgrid')

COLORS = {
    'primary':   '#2E86AB',
    'secondary': '#A23B72',
    'success':   '#06D6A0',
    'danger':    '#EF476F',
    'neutral':   '#118AB2',
    'warning':   '#FFB703',
    'dark':      '#1A1A2E',
}


def ensure_chart_dir():
    """Ensure charts directory exists."""
    os.makedirs("charts", exist_ok=True)


def _load_company_data(csv_path: str, company: Optional[str]) -> pd.DataFrame:
    """Load and optionally filter to a single company."""
    df = pd.read_csv(csv_path)
    # Normalise company column (trailing space in header)
    company_col = next((c for c in df.columns if c.strip() == 'Company'), None)
    if company_col:
        df[company_col] = df[company_col].str.strip()
        if company:
            df = df[df[company_col] == company.strip()]
    df = df.sort_values('Period').reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════════════════════════════════
# Tool 1 — Revenue Trend Chart
# ═══════════════════════════════════════════════════════════════════════════

@tool
def generate_revenue_trend_chart(
    csv_path: str,
    company: str = "",
    output_path: str = "charts/revenue_trend.png"
):
    """
    Generate a revenue trend chart for a specific company.

    Args:
        csv_path: Path to the CSV file containing financial data
        company: Company name/ticker to analyze (empty = first company found)
        output_path: Where to save the chart

    Returns:
        dict with chart_path, insights, and status
    """
    ensure_chart_dir()
    df = _load_company_data(csv_path, company or None)

    if df.empty:
        return {"status": "error", "message": f"No data for company '{company}'"}

    company_label = company or str(df.get('Company ', df.columns[0]))

    fig, ax = plt.subplots(figsize=(12, 6))

    # Revenue bars + line overlay
    bar_colors = [COLORS['primary'] if v >= 0 else COLORS['danger']
                  for v in df['Revenue']]
    ax.bar(df['Period'], df['Revenue'], color=bar_colors, alpha=0.35,
           label='Revenue (bars)', edgecolor='none')
    ax.plot(df['Period'], df['Revenue'], marker='o', linewidth=2.5,
            markersize=6, color=COLORS['primary'], label='Revenue', zorder=3)

    # Trend line
    x_num = np.arange(len(df))
    z = np.polyfit(x_num, df['Revenue'], 1)
    trend_vals = np.poly1d(z)(x_num)
    ax.plot(df['Period'], trend_vals, '--', color=COLORS['secondary'],
            alpha=0.8, linewidth=1.5, label='Trend')

    # Annotate peak
    max_idx = df['Revenue'].idxmax()
    ax.annotate(
        f"Peak: ${df.loc[max_idx, 'Revenue']:,.0f}M",
        xy=(df.loc[max_idx, 'Period'], df.loc[max_idx, 'Revenue']),
        xytext=(10, 12), textcoords='offset points',
        bbox=dict(boxstyle='round,pad=0.4', fc=COLORS['warning'], alpha=0.85),
        arrowprops=dict(arrowstyle='->', color='black'), fontsize=9
    )

    ax.set_xlabel('Period', fontsize=12, fontweight='bold')
    ax.set_ylabel('Revenue (Millions)', fontsize=12, fontweight='bold')
    ax.set_title(f'Revenue Trend — {company_label}', fontsize=14, fontweight='bold', pad=15)
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    avg_rev    = df['Revenue'].mean()
    growth_avg = df['Revenue'].pct_change().dropna().mean()
    insights   = (
        f"{company_label} — Avg revenue: ${avg_rev:,.0f}M | "
        f"Avg YoY growth: {growth_avg:.1%} | "
        f"Peak: ${df['Revenue'].max():,.0f}M ({df.loc[df['Revenue'].idxmax(), 'Period']})"
    )
    return {"chart_path": output_path, "insights": insights, "status": "success"}


# ═══════════════════════════════════════════════════════════════════════════
# Tool 2 — Scenario Comparison Chart
# ═══════════════════════════════════════════════════════════════════════════

@tool
def generate_scenario_comparison_chart(
    csv_path: str,
    company: str = "",
    output_path: str = "charts/scenario_comparison.png"
):
    """
    Generate a scenario comparison chart for a specific company using
    percentile-based projections derived from historical growth rates.

    Args:
        csv_path: Path to the CSV file
        company: Company name/ticker (empty = first company found)
        output_path: Where to save the chart

    Returns:
        dict with chart_path, insights, and status
    """
    ensure_chart_dir()
    df = _load_company_data(csv_path, company or None)

    if df.empty:
        return {"status": "error", "message": f"No data for company '{company}'"}

    company_label = company or "Company"

    revenue     = df['Revenue'].dropna()
    latest_rev  = float(revenue.iloc[-1])
    growth_rates = revenue.pct_change().dropna()
    avg_g   = float(growth_rates.mean())
    std_g   = float(growth_rates.std()) if len(growth_rates) > 1 else abs(avg_g) * 0.3

    # Percentile-based growth assumptions
    best_g  = avg_g + std_g
    base_g  = avg_g
    worst_g = avg_g - std_g

    scenarios = {
        f'Best\n(+{best_g:.0%})':  latest_rev * (1 + best_g),
        f'Base\n({base_g:.0%})':   latest_rev * (1 + base_g),
        f'Worst\n({worst_g:.0%})': latest_rev * (1 + worst_g),
    }

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = [COLORS['success'], COLORS['neutral'], COLORS['danger']]
    bars   = ax.bar(list(scenarios.keys()), list(scenarios.values()),
                    color=colors, edgecolor='black', linewidth=1.2, alpha=0.85)

    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2., h + 0.01 * max(scenarios.values()),
                f'${h:,.0f}M', ha='center', va='bottom', fontsize=11, fontweight='bold')

    ax.axhline(y=latest_rev, color='gray', linestyle='--',
               linewidth=1.2, alpha=0.6, label=f'Current: ${latest_rev:,.0f}M')
    ax.set_ylabel('Projected Revenue (Millions)', fontsize=12, fontweight='bold')
    ax.set_title(f'3-Scenario Revenue Projection — {company_label}',
                 fontsize=14, fontweight='bold', pad=15)
    ax.legend(fontsize=9)
    ax.grid(True, axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    upside   = list(scenarios.values())[0] - latest_rev
    downside = latest_rev - list(scenarios.values())[2]
    insights = (
        f"{company_label} — Base: ${latest_rev:,.0f}M | "
        f"Upside potential: ${upside:,.0f}M | Downside risk: ${downside:,.0f}M"
    )
    return {"chart_path": output_path, "insights": insights, "status": "success"}


# ═══════════════════════════════════════════════════════════════════════════
# Tool 3 — Risk Dashboard
# ═══════════════════════════════════════════════════════════════════════════

@tool
def generate_risk_dashboard(
    csv_path: str,
    company: str = "",
    output_path: str = "charts/risk_dashboard.png"
):
    """
    Generate a risk metrics dashboard for a specific company showing
    debt/equity, current ratio, and operating cash flow trends.

    Args:
        csv_path: Path to the CSV file
        company: Company name/ticker (empty = first company found)
        output_path: Where to save the chart

    Returns:
        dict with chart_path, insights, and status
    """
    ensure_chart_dir()
    df = _load_company_data(csv_path, company or None)

    if df.empty:
        return {"status": "error", "message": f"No data for company '{company}'"}

    company_label = company or "Company"

    fig = plt.figure(figsize=(14, 10))
    gs  = GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3)
    fig.suptitle(f'Financial Risk Dashboard — {company_label}',
                 fontsize=15, fontweight='bold', y=0.98)

    # 1. Debt/Equity
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(df['Period'], df['Debt/Equity Ratio'], marker='o',
             linewidth=2, color=COLORS['danger'], label='D/E Ratio')
    ax1.axhline(y=1.0, color='orange', linestyle='--', linewidth=1.2,
                alpha=0.7, label='Threshold 1.0')
    ax1.set_title('Debt/Equity Ratio', fontweight='bold')
    ax1.set_ylabel('Ratio')
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 2. Current Ratio
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(df['Period'], df['Current Ratio'], marker='s',
             linewidth=2, color=COLORS['success'], label='Current Ratio')
    ax2.axhline(y=1.0, color='red',   linestyle='--', linewidth=1, alpha=0.7, label='Min (1.0)')
    ax2.axhline(y=2.0, color='green', linestyle='--', linewidth=1, alpha=0.7, label='Healthy (2.0)')
    ax2.set_title('Current Ratio (Liquidity)', fontweight='bold')
    ax2.set_ylabel('Ratio')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # 3. Operating Cash Flow
    ax3 = fig.add_subplot(gs[1, :])
    ocf_colors = [COLORS['success'] if v >= 0 else COLORS['danger']
                  for v in df['Operating_Cash_Flow']]
    ax3.bar(df['Period'], df['Operating_Cash_Flow'], color=ocf_colors,
            edgecolor='black', linewidth=0.5, alpha=0.85)
    ax3.axhline(y=0, color='black', linewidth=1.2)
    ax3.set_title('Operating Cash Flow', fontweight='bold')
    ax3.set_ylabel('Cash Flow (Millions)')
    ax3.set_xlabel('Period')
    ax3.grid(True, axis='y', alpha=0.3)
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    avg_de = df['Debt/Equity Ratio'].mean()
    avg_cr = df['Current Ratio'].mean()
    avg_cf = df['Operating_Cash_Flow'].mean()
    insights = (
        f"{company_label} — Avg D/E: {avg_de:.2f} | "
        f"Avg Current Ratio: {avg_cr:.2f} | "
        f"Avg Operating CF: ${avg_cf:,.0f}M"
    )
    return {"chart_path": output_path, "insights": insights, "status": "success"}


# ═══════════════════════════════════════════════════════════════════════════
# Tool 4 — Profitability Analysis
# ═══════════════════════════════════════════════════════════════════════════

@tool
def generate_profitability_analysis_chart(
    csv_path: str,
    company: str = "",
    output_path: str = "charts/profitability_analysis.png"
):
    """
    Generate a dual-axis profitability chart (Revenue bars + EBITDA margin line)
    for a specific company.

    Args:
        csv_path: Path to the CSV file
        company: Company name/ticker (empty = first company found)
        output_path: Where to save the chart

    Returns:
        dict with chart_path, insights, and status
    """
    ensure_chart_dir()
    df = _load_company_data(csv_path, company or None)

    if df.empty:
        return {"status": "error", "message": f"No data for company '{company}'"}

    company_label = company or "Company"
    df['EBITDA_Margin_Pct'] = (df['EBITDA'] / df['Revenue']) * 100

    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.bar(df['Period'], df['Revenue'], color=COLORS['neutral'],
            alpha=0.55, label='Revenue', edgecolor='black', linewidth=0.5)
    ax1.set_xlabel('Period', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Revenue (Millions)', fontsize=12, fontweight='bold',
                   color=COLORS['neutral'])
    ax1.tick_params(axis='y', labelcolor=COLORS['neutral'])
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')

    ax2 = ax1.twinx()
    ax2.plot(df['Period'], df['EBITDA_Margin_Pct'], marker='o',
             linewidth=2.5, color=COLORS['danger'], label='EBITDA Margin %', markersize=6)
    avg_margin = df['EBITDA_Margin_Pct'].mean()
    ax2.axhline(y=avg_margin, color=COLORS['danger'], linestyle='--',
                linewidth=1.2, alpha=0.6, label=f'Avg {avg_margin:.1f}%')
    ax2.set_ylabel('EBITDA Margin (%)', fontsize=12, fontweight='bold',
                   color=COLORS['danger'])
    ax2.tick_params(axis='y', labelcolor=COLORS['danger'])

    ax1.set_title(f'Profitability: Revenue vs EBITDA Margin — {company_label}',
                  fontsize=14, fontweight='bold', pad=15)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    trend = ("improving"
             if df['EBITDA_Margin_Pct'].iloc[-1] > df['EBITDA_Margin_Pct'].iloc[0]
             else "declining")
    insights = (
        f"{company_label} — Avg EBITDA margin: {avg_margin:.1f}% | "
        f"Trend: {trend} | "
        f"Latest margin: {df['EBITDA_Margin_Pct'].iloc[-1]:.1f}%"
    )
    return {"chart_path": output_path, "insights": insights, "status": "success"}


# ═══════════════════════════════════════════════════════════════════════════
# Tool 5 — Waterfall Chart (NEW)
# ═══════════════════════════════════════════════════════════════════════════

@tool
def generate_waterfall_chart(
    csv_path: str,
    company: str = "",
    output_path: str = "charts/waterfall_revenue.png"
):
    """
    Generate a revenue waterfall chart showing period-over-period revenue changes.

    Args:
        csv_path: Path to the CSV file
        company: Company name/ticker
        output_path: Where to save the chart

    Returns:
        dict with chart_path, insights, and status
    """
    ensure_chart_dir()
    df = _load_company_data(csv_path, company or None)

    if df.empty or len(df) < 2:
        return {"status": "error", "message": "Need at least 2 data points for waterfall"}

    company_label = company or "Company"

    # Calculate period-over-period changes
    periods = df['Period'].tolist()
    revenues = df['Revenue'].tolist()
    changes = [revenues[0]] + [revenues[i] - revenues[i-1] for i in range(1, len(revenues))]
    labels = [str(periods[0])] + [f'Δ{periods[i]}' for i in range(1, len(periods))]

    # Build cumulative for stacked bars
    fig, ax = plt.subplots(figsize=(max(12, len(periods) * 0.9), 6))

    running = 0
    for i, (label, change) in enumerate(zip(labels, changes)):
        if i == 0:
            bar_color = COLORS['primary']
            bottom = 0
        else:
            bar_color = COLORS['success'] if change >= 0 else COLORS['danger']
            bottom = running

        ax.bar(label, abs(change), bottom=bottom if change >= 0 else running + change,
               color=bar_color, edgecolor='black', linewidth=0.8, alpha=0.85)

        # Connector line
        if i > 0:
            end_prev = running
            ax.plot([i - 0.4, i - 0.4 + 0.8], [end_prev, end_prev],
                    color='gray', linewidth=0.8, linestyle='--')

        # Value label
        val_y = (bottom if change >= 0 else running + change) + abs(change) / 2
        ax.text(i, val_y, f'${change:+,.0f}M' if i > 0 else f'${change:,.0f}M',
                ha='center', va='center', fontsize=8, fontweight='bold',
                color='white' if abs(change) > max(revenues) * 0.05 else 'black')

        running += change

    ax.set_title(f'Revenue Waterfall — {company_label}', fontsize=14, fontweight='bold', pad=15)
    ax.set_ylabel('Revenue (Millions)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Period', fontsize=12, fontweight='bold')
    ax.grid(True, axis='y', alpha=0.3)
    plt.xticks(rotation=45, ha='right')

    legend_patches = [
        mpatches.Patch(color=COLORS['primary'], label='Base'),
        mpatches.Patch(color=COLORS['success'], label='Increase'),
        mpatches.Patch(color=COLORS['danger'],  label='Decrease'),
    ]
    ax.legend(handles=legend_patches, loc='upper left', fontsize=9)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    total_change = revenues[-1] - revenues[0]
    insights = (
        f"{company_label} — Total revenue change: ${total_change:+,.0f}M | "
        f"Start: ${revenues[0]:,.0f}M | End: ${revenues[-1]:,.0f}M"
    )
    return {"chart_path": output_path, "insights": insights, "status": "success"}


# ═══════════════════════════════════════════════════════════════════════════
# Tool 6 — Radar Chart (NEW)
# ═══════════════════════════════════════════════════════════════════════════

@tool
def generate_radar_chart(
    csv_path: str,
    company: str = "",
    output_path: str = "charts/radar_metrics.png"
):
    """
    Generate a radar/spider chart of key financial metrics vs industry averages.

    Args:
        csv_path: Path to the CSV file
        company: Company name/ticker
        output_path: Where to save the chart

    Returns:
        dict with chart_path, insights, and status
    """
    ensure_chart_dir()
    df = _load_company_data(csv_path, company or None)

    if df.empty:
        return {"status": "error", "message": f"No data for company '{company}'"}

    company_label = company or "Company"
    latest = df.iloc[-1]

    # Metrics to plot (normalized 0-1 scale for radar)
    metrics_raw = {}
    if 'ROE' in df.columns and pd.notna(latest.get('ROE')):
        metrics_raw['ROE'] = float(latest['ROE'])
    if 'ROA' in df.columns and pd.notna(latest.get('ROA')):
        metrics_raw['ROA'] = float(latest['ROA'])
    if 'EBITDA' in df.columns and 'Revenue' in df.columns:
        margin = float(latest['EBITDA'] / latest['Revenue']) * 100
        metrics_raw['EBITDA Margin'] = margin
    if 'Current Ratio' in df.columns:
        metrics_raw['Current Ratio'] = float(latest['Current Ratio'])
    if 'Net Profit Margin' in df.columns and pd.notna(latest.get('Net Profit Margin')):
        metrics_raw['Net Margin'] = float(latest['Net Profit Margin'])
    if 'Revenue_Growth' in df.columns:
        growth = df['Revenue_Growth'].dropna()
        if len(growth) > 0:
            metrics_raw['Rev Growth'] = float(growth.iloc[-1]) * 100

    if not metrics_raw:
        return {"status": "error", "message": "Insufficient metric data for radar chart"}

    categories = list(metrics_raw.keys())
    values     = list(metrics_raw.values())
    N = len(categories)

    # Normalize: clip then scale 0–100
    norm_vals = []
    for v in values:
        clipped = max(min(v, 100), -50)
        normalized = (clipped + 50) / 150 * 100  # Maps [-50, 100] → [0, 100]
        norm_vals.append(normalized)

    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    norm_vals_plot = norm_vals + norm_vals[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    ax.plot(angles, norm_vals_plot, 'o-', linewidth=2, color=COLORS['primary'])
    ax.fill(angles, norm_vals_plot, alpha=0.25, color=COLORS['primary'])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, size=11)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], size=8)
    ax.set_title(f'Financial Health Radar — {company_label}',
                 size=14, fontweight='bold', y=1.08)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    insights = (
        f"{company_label} — Radar covers: {', '.join(categories)} | "
        f"Best metric: {categories[norm_vals.index(max(norm_vals))]}"
    )
    return {"chart_path": output_path, "insights": insights, "status": "success"}


# ═══════════════════════════════════════════════════════════════════════════
# Tool 7 — Heatmap (NEW)
# ═══════════════════════════════════════════════════════════════════════════

@tool
def generate_metrics_heatmap(
    csv_path: str,
    company: str = "",
    output_path: str = "charts/metrics_heatmap.png"
):
    """
    Generate a heatmap showing metric performance across years for a company.

    Args:
        csv_path: Path to the CSV file
        company: Company name/ticker
        output_path: Where to save the chart

    Returns:
        dict with chart_path, insights, and status
    """
    ensure_chart_dir()
    df = _load_company_data(csv_path, company or None)

    if df.empty:
        return {"status": "error", "message": f"No data for company '{company}'"}

    company_label = company or "Company"

    # Select numeric metrics that exist
    candidate_cols = ['Revenue', 'EBITDA', 'Operating_Cash_Flow',
                      'Current Ratio', 'Debt/Equity Ratio', 'ROE', 'ROA']
    available_cols = [c for c in candidate_cols if c in df.columns]

    if not available_cols:
        return {"status": "error", "message": "No numeric columns for heatmap"}

    # Build pivot: periods × metrics (normalized per column)
    heatmap_df = df[['Period'] + available_cols].set_index('Period')[available_cols].copy()

    # Normalize each column 0–1 so colours are comparable
    for col in heatmap_df.columns:
        col_min = heatmap_df[col].min()
        col_max = heatmap_df[col].max()
        if col_max != col_min:
            heatmap_df[col] = (heatmap_df[col] - col_min) / (col_max - col_min)
        else:
            heatmap_df[col] = 0.5  # uniform column

    fig, ax = plt.subplots(figsize=(max(10, len(available_cols) * 1.5),
                                    max(6, len(heatmap_df) * 0.5)))
    data = heatmap_df.values
    im   = ax.imshow(data, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)

    ax.set_xticks(range(len(available_cols)))
    ax.set_xticklabels(available_cols, rotation=45, ha='right', fontsize=10)
    ax.set_yticks(range(len(heatmap_df)))
    ax.set_yticklabels(heatmap_df.index, fontsize=9)

    # Annotate cells
    for i in range(len(heatmap_df)):
        for j, col in enumerate(available_cols):
            raw_val = df.iloc[i][col] if col in df.columns else 0
            ax.text(j, i, f'{raw_val:.1f}' if abs(raw_val) < 1000 else f'{raw_val/1000:.0f}K',
                    ha='center', va='center', fontsize=7,
                    color='black' if 0.2 < data[i, j] < 0.8 else 'white')

    plt.colorbar(im, ax=ax, label='Normalized Performance (0=Low, 1=High)')
    ax.set_title(f'Metric Performance Heatmap — {company_label}',
                 fontsize=14, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    insights = (
        f"{company_label} — Heatmap across {len(heatmap_df)} periods | "
        f"Metrics: {', '.join(available_cols)}"
    )
    return {"chart_path": output_path, "insights": insights, "status": "success"}
