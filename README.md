# 📊 Financial FP&A Intelligence

Enterprise-Grade AI Financial Analysis pipeline featuring a robust 2-stage architecture for stable, rate-limit-resistant performance.

![Financial FP&A Dashboard](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![CrewAI](https://img.shields.io/badge/CrewAI-Powered-orange?style=for-the-badge)

## 🚀 Overview

The Financial FP&A Intelligence project is a powerful AI-driven financial analysis application. To guarantee stability and prevent API rate limit exhaustion (such as Groq TPM or Gemini free-tier limits), the architecture transitioned from a multi-agent ReAct loop to a highly optimized **2-Stage Pipeline**. This approach minimizes LLM calls while maximizing computational accuracy and delivering rich visual outputs.

## ✨ Key Features

- **Streamlit Web Dashboard**: Interactive UI with file uploading, configuration, and a detailed results viewer.
- **2-Stage Pipeline Architecture**:
  - **Stage 1 (Pure Python Computation)**: Conducts data validation, FP&A calculations, and generates 6 insightful charts—without a single LLM API call.
  - **Stage 2 (Single LLM Call)**: Synthesizes the computed data into an executive-level narrative report, saving API tokens and ensuring high reliability.
- **Deterministic Fallbacks**: Generates an automated, structured report even if the LLM API is unavailable or rate limits are hit.
- **Intelligent Caching**: Disk-backed caching (`FPAAnalysisCache`) skips redundant data processing for previously analyzed datasets.
- **Comprehensive Visualizations**: Automatically generates Revenue Trend, Profitability, Scenario Comparison, Risk Dashboard, Revenue Waterfall, and Financial Radar charts.
- **Exportable Reports**: Downloads analysis results as comprehensive PDF documents, individual PNG charts, or structured JSON data.

## 🧠 AI Agents & Conceptual Roles

While the orchestration is heavily optimized to reduce unnecessary LLM loops, the underlying analysis structure models the expertise of the following roles:
- **FP&A Analyst**: Evaluates historical performance, CAGR, and profitability.
- **Scenario Planning Analyst**: Creates best, base, and worst-case probability-weighted projections.
- **Financial Risk Analyst**: Evaluates liquidity, leverage, and flags potential risks.
- **Market Researcher**: Compares company metrics against sector-specific industry benchmarks.
- **CFO Advisor**: Synthesizes all findings into a board-ready executive memo.

## 🛠️ Tech Stack

- **Web Framework**: [Streamlit](https://streamlit.io/)
- **AI / LLM Orchestration**: [CrewAI](https://crewai.com) (Flows, Knowledge Sources), Groq / Google Gemini APIs
- **Data Processing**: Pandas, NumPy
- **Visualizations**: Matplotlib, Seaborn
- **Reporting**: ReportLab (PDF generation)

## 📦 Installation

Ensure you have Python >=3.10 <=3.13 installed on your system.

1. **Clone the repository:**
   ```bash
   git clone <your-repository-url>
   cd financial_fpa
   ```

2. **Install dependencies:**
   This project uses `uv` for fast dependency management, but `pip` works perfectly too.
   ```bash
   pip install -r requirements.txt
   ```
   *(Alternatively, you can use `crewai install` to lock and install dependencies).*

3. **Set up environment variables:**
   Create a `.env` file in the root directory and add your API keys:
   ```env
   GROQ_API_KEY=your_groq_api_key
   # or
   OPENAI_API_KEY=your_openai_api_key
   ```

## 💻 Usage

Run the interactive Streamlit application from the root folder:

```bash
streamlit run streamlit_app.py
```

### Steps to Run an Analysis:
1. Navigate to the **Upload & Configure** tab.
2. Upload your financial CSV dataset. 
   *(Required columns: `Period`, `Company`, `Revenue`, `EBITDA`, `Operating_Cash_Flow`, `Debt/Equity Ratio`, `Current Ratio`)*
   > **Note:** A built-in demo dataset is available to test the application immediately.
3. Select the target **Company** and **Industry Sector**.
4. Click **Run Analysis** to execute the pipeline.
5. Review the generated visualizations and structured data across the **Results & Charts** and **Detailed Analysis** tabs.
6. Download the comprehensive PDF report or raw JSON data from the **Download Report** tab.

## 📊 Outputs & Artifacts

All generated assets are automatically saved to their respective directories for easy access and auditability:
- `charts/`: PNG files of all financial visualizations.
- `reports/`: Final synthesized PDF reports.
- `cache/`: Hashes of previous analyses to optimize execution speed on re-runs.
- `logs/`: Application execution and tracking logs.

## 🤝 Support & Contribution

- Reach out via issues or pull requests.
- Built using the power and simplicity of [crewAI](https://crewai.com).
