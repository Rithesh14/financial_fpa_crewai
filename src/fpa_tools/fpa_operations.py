import pandas as pd

def run_fpa_analysis(csv_path: str):
    """
    Run comprehensive FP&A analysis on financial data.
    
    Args:
        csv_path: Path to the CSV file containing financial data
        
    Returns:
        dict: Structured financial metrics including growth, profitability, 
              cash flow, risk indicators, and scenario analysis
    """
    # Validate input
    if not csv_path:
        raise ValueError("CSV path cannot be empty")
    
    # Load data from provided path
    df = pd.read_csv(csv_path)

    # ---- Core FP&A Metrics ----

    # Growth
    df["Revenue_Growth"] = df["Revenue"].pct_change()

    # Profitability
    df["EBITDA_Margin"] = df["EBITDA"] / df["Revenue"]

    # Cash health
    avg_operating_cf = df["Operating_Cash_Flow"].mean()

    # Risk indicators
    avg_debt_equity = df["Debt/Equity Ratio"].mean()
    avg_current_ratio = df["Current Ratio"].mean()

    # Scenario analysis
    avg_revenue = df["Revenue"].mean()
    scenarios = {
        "best_case": round(avg_revenue * 1.15, 2),
        "base_case": round(avg_revenue, 2),
        "worst_case": round(avg_revenue * 0.85, 2)
    }

    return {
        "avg_revenue_growth": round(df["Revenue_Growth"].mean(), 3),
        "avg_ebitda_margin": round(df["EBITDA_Margin"].mean(), 3),
        "avg_operating_cash_flow": round(avg_operating_cf, 2),
        "avg_debt_equity": round(avg_debt_equity, 2),
        "avg_current_ratio": round(avg_current_ratio, 2),
        "scenarios": scenarios
    }
