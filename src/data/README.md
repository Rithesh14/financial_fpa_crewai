# Sample CSV files removed

The sample CSV file `modified_financial_data.csv` has been removed from the `src/data/` directory.

Users will now upload their own CSV files through the Streamlit interface.

## CSV Format Requirements

Your uploaded CSV should contain columns like:
- `Period` - Time period (e.g., 2020, 2021, Q1 2023, etc.)
- `Revenue` - Revenue figures
- `EBITDA` - EBITDA values  
- `Operating_Cash_Flow` - Operating cash flow
- `Debt/Equity Ratio` - Debt to equity ratio
- `Current Ratio` - Current ratio
- `Company` (optional) - Company name

## Example CSV Structure

```csv
Period,Revenue,EBITDA,Operating_Cash_Flow,Debt/Equity Ratio,Current Ratio
2020,500,120,85,0.8,1.5
2021,550,135,92,0.75,1.6
2022,600,145,98,0.7,1.7
```

All data will be provided by users via the Streamlit upload interface.
