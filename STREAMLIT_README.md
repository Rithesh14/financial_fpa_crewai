# Financial FP&A Analysis - Streamlit Application

## Quick Start

### 1. Install Dependencies
```bash
pip install streamlit
```

### 2. Run the Application
```bash
streamlit run streamlit_app.py
```

### 3. Access the Application
The app will open automatically in your browser at `http://localhost:8501`

## Features

### 📤 Upload & Analyze Tab
- Upload CSV file with financial data
- Preview data before analysis
- View column information
- Start analysis with one click

### 📊 Results & Charts Tab
- View 4 professional charts:
  - Revenue Trend
  - Scenario Comparison
  - Risk Dashboard
  - Profitability Analysis
- Read executive insights
- Interactive chart display

### 📄 Download Report Tab
- Download comprehensive PDF report
- Download individual charts
- View report metadata

## Usage Instructions

1. **Upload Your Data**
   - Click "Browse files" in the Upload & Analyze tab
   - Select your CSV file
   - Preview the data to ensure it's correct

2. **Run Analysis**
   - Click "🚀 Start Analysis" button
   - Wait for AI agents to complete analysis (2-5 minutes)
   - Progress bar shows current status

3. **View Results**
   - Switch to "Results & Charts" tab
   - View all generated visualizations
   - Read insights from AI agents

4. **Download Report**
   - Switch to "Download Report" tab
   - Click "📥 Download PDF Report"
   - Optionally download individual charts

## CSV Format Requirements

Your CSV should include columns like:
- `Period` - Time period (e.g., 2020, 2021, etc.)
- `Revenue` - Revenue figures
- `EBITDA` - EBITDA values
- `Operating_Cash_Flow` - Operating cash flow
- `Debt/Equity Ratio` - Debt to equity ratio
- `Current Ratio` - Current ratio
- `Company` (optional) - Company name

## Configuration

Ensure your `.env` file contains:
```bash
OPENAI_API_KEY=your_openai_api_key
SERPER_API_KEY=your_serper_api_key  # Optional
```

## Troubleshooting

### Issue: "OpenAI API Key missing"
**Solution:** Add `OPENAI_API_KEY` to your `.env` file

### Issue: Charts not displaying
**Solution:** Ensure the analysis completed successfully and check the `charts/` directory

### Issue: PDF download not working
**Solution:** Verify the `reports/` directory exists and contains `fpa_analysis.pdf`

## Advanced Options

### Custom Styling
Edit the CSS in `streamlit_app.py` to customize colors and layout

### Session Management
The app uses Streamlit session state to maintain analysis results across tab switches

## Tips

- 💡 Use the sidebar to check API key status
- 💡 Preview your data before running analysis
- 💡 Analysis takes 2-5 minutes depending on data size
- 💡 You can download charts individually or as part of the PDF
