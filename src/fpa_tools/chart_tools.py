"""
Chart Generation Tools for Financial FP&A Analysis
Creates professional visualizations for financial insights
"""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to avoid async issues

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import os
import numpy as np
from crewai.tools import tool  # Use crewai.tools instead of crewai_tools


# Set style for professional charts
plt.style.use('seaborn-v0_8-darkgrid')

def ensure_chart_dir():
    """Ensure charts directory exists"""
    os.makedirs("charts", exist_ok=True)


@tool
def generate_revenue_trend_chart(csv_path: str, output_path: str = "charts/revenue_trend.png"):
    """
    Generate revenue trend visualization showing revenue growth over time.
    
    Args:
        csv_path: Path to the CSV file containing financial data
        output_path: Where to save the chart
        
    Returns:
        dict: Chart path and key insights
    """
    ensure_chart_dir()
    
    # Load data
    df = pd.read_csv(csv_path)
    
    # Sort by period
    df = df.sort_values('Period')
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot revenue trend
    ax.plot(df['Period'], df['Revenue'], marker='o', linewidth=2, 
            markersize=6, color='#2E86AB', label='Revenue')
    
    # Add trend line
    z = np.polyfit(range(len(df)), df['Revenue'], 1)
    p = np.poly1d(z)
    ax.plot(df['Period'], p(range(len(df))), "--", 
            color='#A23B72', alpha=0.7, label='Trend')
    
    # Formatting
    ax.set_xlabel('Period', fontsize=12, fontweight='bold')
    ax.set_ylabel('Revenue (Millions)', fontsize=12, fontweight='bold')
    ax.set_title('Revenue Trend Analysis', fontsize=14, fontweight='bold', pad=20)
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Rotate x-axis labels for readability
    plt.xticks(rotation=45, ha='right')
    
    # Add value annotations for key points
    max_idx = df['Revenue'].idxmax()
    min_idx = df['Revenue'].idxmin()
    
    ax.annotate(f'Peak: ${df.loc[max_idx, "Revenue"]:,.0f}M',
                xy=(df.loc[max_idx, 'Period'], df.loc[max_idx, 'Revenue']),
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    # Calculate insights
    avg_revenue = df['Revenue'].mean()
    growth_rate = df['Revenue'].pct_change().mean()
    
    insights = f"Average revenue: ${avg_revenue:,.2f}M. Average growth rate: {growth_rate:.1%}. Peak revenue in {df.loc[max_idx, 'Period']}."
    
    return {
        "chart_path": output_path,
        "insights": insights,
        "status": "success"
    }


@tool
def generate_scenario_comparison_chart(csv_path: str, output_path: str = "charts/scenario_comparison.png"):
    """
    Generate scenario comparison chart showing best/base/worst case revenue projections.
    
    Args:
        csv_path: Path to the CSV file containing financial data
        output_path: Where to save the chart
        
    Returns:
        dict: Chart path and key insights
    """
    ensure_chart_dir()
    
    # Load data and calculate scenarios
    df = pd.read_csv(csv_path)
    avg_revenue = df['Revenue'].mean()
    
    scenarios = {
        'Best Case\n(+15%)': avg_revenue * 1.15,
        'Base Case': avg_revenue,
        'Worst Case\n(-15%)': avg_revenue * 0.85
    }
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create bars
    colors = ['#06D6A0', '#118AB2', '#EF476F']
    bars = ax.bar(scenarios.keys(), scenarios.values(), color=colors, 
                   edgecolor='black', linewidth=1.5, alpha=0.8)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'${height:,.0f}M',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # Add reference line for base case
    ax.axhline(y=avg_revenue, color='gray', linestyle='--', 
               linewidth=1, alpha=0.5, label='Base Case Reference')
    
    # Formatting
    ax.set_ylabel('Revenue (Millions)', fontsize=12, fontweight='bold')
    ax.set_title('Revenue Scenario Analysis', fontsize=14, fontweight='bold', pad=20)
    ax.grid(True, axis='y', alpha=0.3)
    
    # Add percentage labels
    ax.text(0, scenarios['Best Case\n(+15%)'] * 0.5, '+15%', 
            ha='center', fontsize=10, color='white', fontweight='bold')
    ax.text(2, scenarios['Worst Case\n(-15%)'] * 0.5, '-15%', 
            ha='center', fontsize=10, color='white', fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    upside = scenarios['Best Case\n(+15%)'] - scenarios['Base Case']
    downside = scenarios['Base Case'] - scenarios['Worst Case\n(-15%)']
    
    insights = f"Base case: ${avg_revenue:,.0f}M. Upside potential: ${upside:,.0f}M. Downside risk: ${downside:,.0f}M."
    
    return {
        "chart_path": output_path,
        "insights": insights,
        "status": "success"
    }


@tool
def generate_risk_dashboard(csv_path: str, output_path: str = "charts/risk_dashboard.png"):
    """
    Generate risk metrics dashboard showing debt/equity, current ratio, and cash flow trends.
    
    Args:
        csv_path: Path to the CSV file containing financial data
        output_path: Where to save the chart
        
    Returns:
        dict: Chart path and key insights
    """
    ensure_chart_dir()
    
    # Load data
    df = pd.read_csv(csv_path)
    df = df.sort_values('Period')
    
    # Create figure with subplots
    fig = plt.figure(figsize=(14, 10))
    gs = GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
    
    # 1. Debt/Equity Ratio
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(df['Period'], df['Debt/Equity Ratio'], marker='o', 
             linewidth=2, color='#EF476F', label='Debt/Equity')
    ax1.axhline(y=1.0, color='orange', linestyle='--', 
                linewidth=1, alpha=0.7, label='Threshold (1.0)')
    ax1.set_title('Debt/Equity Ratio Trend', fontweight='bold')
    ax1.set_ylabel('Ratio', fontweight='bold')
    ax1.legend(loc='best')
    ax1.grid(True, alpha=0.3)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 2. Current Ratio
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(df['Period'], df['Current Ratio'], marker='s', 
             linewidth=2, color='#06D6A0', label='Current Ratio')
    ax2.axhline(y=1.0, color='red', linestyle='--', 
                linewidth=1, alpha=0.7, label='Min Threshold (1.0)')
    ax2.axhline(y=2.0, color='green', linestyle='--', 
                linewidth=1, alpha=0.7, label='Healthy (2.0)')
    ax2.set_title('Current Ratio (Liquidity)', fontweight='bold')
    ax2.set_ylabel('Ratio', fontweight='bold')
    ax2.legend(loc='best')
    ax2.grid(True, alpha=0.3)
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 3. Operating Cash Flow
    ax3 = fig.add_subplot(gs[1, :])
    ax3.bar(df['Period'], df['Operating_Cash_Flow'], 
            color=['#06D6A0' if x > 0 else '#EF476F' for x in df['Operating_Cash_Flow']],
            edgecolor='black', linewidth=0.5, alpha=0.8)
    ax3.axhline(y=0, color='black', linewidth=1)
    ax3.set_title('Operating Cash Flow Trend', fontweight='bold')
    ax3.set_ylabel('Cash Flow (Millions)', fontweight='bold')
    ax3.set_xlabel('Period', fontweight='bold')
    ax3.grid(True, axis='y', alpha=0.3)
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # Overall title
    fig.suptitle('Financial Risk Metrics Dashboard', 
                 fontsize=16, fontweight='bold', y=0.98)
    
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    # Calculate insights
    avg_debt_equity = df['Debt/Equity Ratio'].mean()
    avg_current_ratio = df['Current Ratio'].mean()
    avg_cash_flow = df['Operating_Cash_Flow'].mean()
    
    insights = f"Avg Debt/Equity: {avg_debt_equity:.2f}. Avg Current Ratio: {avg_current_ratio:.2f}. Avg Operating CF: ${avg_cash_flow:,.0f}M."
    
    return {
        "chart_path": output_path,
        "insights": insights,
        "status": "success"
    }


@tool
def generate_profitability_analysis_chart(csv_path: str, output_path: str = "charts/profitability_analysis.png"):
    """
    Generate profitability analysis chart showing EBITDA margin and revenue relationship.
    
    Args:
        csv_path: Path to the CSV file containing financial data
        output_path: Where to save the chart
        
    Returns:
        dict: Chart path and key insights
    """
    ensure_chart_dir()
    
    # Load data
    df = pd.read_csv(csv_path)
    df = df.sort_values('Period')
    
    # Calculate EBITDA margin
    df['EBITDA_Margin_Calc'] = (df['EBITDA'] / df['Revenue']) * 100
    
    # Create figure with dual axis
    fig, ax1 = plt.subplots(figsize=(12, 6))
    
    # Revenue bars
    color1 = '#118AB2'
    ax1.bar(df['Period'], df['Revenue'], color=color1, alpha=0.6, 
            label='Revenue', edgecolor='black', linewidth=0.5)
    ax1.set_xlabel('Period', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Revenue (Millions)', fontsize=12, fontweight='bold', color=color1)
    ax1.tick_params(axis='y', labelcolor=color1)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # EBITDA margin line
    ax2 = ax1.twinx()
    color2 = '#EF476F'
    ax2.plot(df['Period'], df['EBITDA_Margin_Calc'], marker='o', 
             linewidth=2.5, color=color2, label='EBITDA Margin %', markersize=6)
    ax2.set_ylabel('EBITDA Margin (%)', fontsize=12, fontweight='bold', color=color2)
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.axhline(y=df['EBITDA_Margin_Calc'].mean(), color=color2, 
                linestyle='--', linewidth=1, alpha=0.5, label='Avg Margin')
    
    # Title and legends
    ax1.set_title('Profitability Analysis: Revenue vs EBITDA Margin', 
                  fontsize=14, fontweight='bold', pad=20)
    
    # Combine legends
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    ax1.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    # Calculate insights
    avg_margin = df['EBITDA_Margin_Calc'].mean()
    margin_trend = "improving" if df['EBITDA_Margin_Calc'].iloc[-1] > df['EBITDA_Margin_Calc'].iloc[0] else "declining"
    
    insights = f"Average EBITDA margin: {avg_margin:.1f}%. Margin trend: {margin_trend}. Revenue and profitability correlation analyzed."
    
    return {
        "chart_path": output_path,
        "insights": insights,
        "status": "success"
    }

