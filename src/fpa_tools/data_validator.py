"""
Data Validation Module for Financial FP&A Analysis.

Validates CSV input files before they enter the analysis pipeline,
ensuring data quality and preventing garbage-in-garbage-out scenarios.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional


# Required columns that MUST exist in the CSV
REQUIRED_COLUMNS = [
    'Period', 'Company ', 'Revenue', 'EBITDA',
    'Operating_Cash_Flow', 'Debt/Equity Ratio', 'Current Ratio'
]

# Columns that should be numeric
NUMERIC_COLUMNS = [
    'Revenue', 'EBITDA', 'Operating_Cash_Flow',
    'Debt/Equity Ratio', 'Current Ratio', 'Net Income',
    'Gross Profit', 'Market_Cap', 'ROE', 'ROA'
]


def validate_csv_file(csv_path: str) -> Dict:
    """
    Perform comprehensive validation of a financial CSV file.

    Args:
        csv_path: Path to the CSV file

    Returns:
        dict with keys:
            - is_valid (bool): Whether the file passes validation
            - errors (list): Critical errors that block analysis
            - warnings (list): Non-critical issues to be aware of
            - available_companies (list): Companies found in the data
            - row_count (int): Total rows
            - column_count (int): Total columns
            - period_range (str): Date range of data
    """
    result = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'available_companies': [],
        'row_count': 0,
        'column_count': 0,
        'period_range': ''
    }

    # Step 1: Try to load the file
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        result['is_valid'] = False
        result['errors'].append(f"File not found: {csv_path}")
        return result
    except pd.errors.EmptyDataError:
        result['is_valid'] = False
        result['errors'].append("CSV file is empty")
        return result
    except Exception as e:
        result['is_valid'] = False
        result['errors'].append(f"Cannot read CSV: {str(e)}")
        return result

    result['row_count'] = len(df)
    result['column_count'] = len(df.columns)

    # Step 2: Check for required columns
    # Handle the trailing space in 'Company ' column name
    actual_columns = df.columns.tolist()
    for col in REQUIRED_COLUMNS:
        col_stripped = col.strip()
        matching = [c for c in actual_columns if c.strip() == col_stripped]
        if not matching:
            result['errors'].append(f"Missing required column: '{col_stripped}'")
            result['is_valid'] = False

    if not result['is_valid']:
        return result

    # Step 3: Check for empty dataset
    if len(df) == 0:
        result['is_valid'] = False
        result['errors'].append("Dataset contains no rows")
        return result

    # Step 4: Get available companies
    company_col = [c for c in actual_columns if c.strip() == 'Company'][0]
    df[company_col] = df[company_col].str.strip()
    result['available_companies'] = sorted(df[company_col].unique().tolist())

    # Step 5: Check for duplicates
    dup_count = df.duplicated(subset=['Period', company_col]).sum()
    if dup_count > 0:
        result['warnings'].append(
            f"Found {dup_count} duplicate rows (same Period + Company)"
        )

    # Step 6: Validate numeric columns
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            non_numeric = pd.to_numeric(df[col], errors='coerce').isna().sum()
            original_na = df[col].isna().sum()
            bad_values = non_numeric - original_na
            if bad_values > 0:
                result['warnings'].append(
                    f"Column '{col}' has {bad_values} non-numeric values"
                )

    # Step 7: Check for extreme outliers in key metrics
    if 'Revenue' in df.columns:
        revenue = pd.to_numeric(df['Revenue'], errors='coerce').dropna()
        if len(revenue) > 0:
            mean_rev = revenue.mean()
            std_rev = revenue.std()
            if std_rev > 0:
                outliers = ((revenue - mean_rev).abs() > 4 * std_rev).sum()
                if outliers > 0:
                    result['warnings'].append(
                        f"Revenue has {outliers} extreme outliers (>4 std from mean)"
                    )

    # Step 8: Check for negative values in typically positive columns
    for col in ['Revenue', 'Current Ratio']:
        if col in df.columns:
            neg_count = (pd.to_numeric(df[col], errors='coerce') < 0).sum()
            if neg_count > 0:
                result['warnings'].append(
                    f"Column '{col}' has {neg_count} negative values (unexpected)"
                )

    # Step 9: Get period range
    if 'Period' in df.columns:
        periods = sorted(df['Period'].unique())
        if len(periods) > 0:
            result['period_range'] = f"{periods[0]} to {periods[-1]}"

    # Step 10: Check minimum data requirement per company
    company_counts = df.groupby(company_col).size()
    small_companies = company_counts[company_counts < 3]
    if len(small_companies) > 0:
        result['warnings'].append(
            f"Companies with < 3 data points: "
            f"{small_companies.index.tolist()} (analysis may be limited)"
        )

    return result


def validate_company_selection(
    csv_path: str,
    company_name: str
) -> Tuple[bool, str, List[str]]:
    """
    Validate that the selected company exists in the dataset.

    Args:
        csv_path: Path to the CSV file
        company_name: Selected company name/ticker

    Returns:
        Tuple of (is_valid, error_message, available_companies)
    """
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return (False, f"Cannot read CSV: {str(e)}", [])

    # Find the company column (handle trailing space)
    company_col = None
    for col in df.columns:
        if col.strip() == 'Company':
            company_col = col
            break

    if company_col is None:
        return (False, "No 'Company' column found in dataset", [])

    df[company_col] = df[company_col].str.strip()
    available = sorted(df[company_col].unique().tolist())

    if company_name.strip() not in available:
        return (
            False,
            f"Company '{company_name}' not found. Available: {available}",
            available
        )

    return (True, "", available)


def get_company_data(csv_path: str, company_name: str) -> Optional[pd.DataFrame]:
    """
    Extract data for a specific company from the CSV.

    Args:
        csv_path: Path to the CSV file
        company_name: Company name/ticker to filter

    Returns:
        DataFrame filtered to the selected company, sorted by period
    """
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return None

    # Find company column
    company_col = None
    for col in df.columns:
        if col.strip() == 'Company':
            company_col = col
            break

    if company_col is None:
        return None

    df[company_col] = df[company_col].str.strip()
    company_df = df[df[company_col] == company_name.strip()].copy()

    if len(company_df) == 0:
        return None

    # Sort by period
    company_df = company_df.sort_values('Period').reset_index(drop=True)

    return company_df
