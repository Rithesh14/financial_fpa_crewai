"""
Financial FP&A Analysis — Streamlit Application v3.
Powered by a 2-stage pipeline: direct tool execution (Stage 1)
+ single LLM report generation (Stage 2). No ReAct agent loop.
"""

import streamlit as st
import pandas as pd
import os
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime

# ── Path & env setup ───────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv
load_dotenv()

if not os.getenv('GROQ_API_KEY') and os.getenv('OPENAI_API_KEY'):
    os.environ['GROQ_API_KEY'] = os.getenv('OPENAI_API_KEY')

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Financial FP&A Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main-header {
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(135deg, #2E86AB 0%, #A23B72 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    padding: 1rem 0 0.3rem 0;
    letter-spacing: -0.5px;
}
.sub-header {
    font-size: 1rem;
    color: #888;
    text-align: center;
    margin-bottom: 2rem;
    font-weight: 400;
}
.metric-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #2E86AB33;
    border-radius: 12px;
    padding: 1.2rem;
    margin: 0.3rem 0;
}
.status-badge-success {
    display: inline-block;
    background: #06D6A022;
    color: #06D6A0;
    border: 1px solid #06D6A055;
    border-radius: 20px;
    padding: 0.2rem 0.8rem;
    font-size: 0.85rem;
    font-weight: 500;
}
.status-badge-warning {
    display: inline-block;
    background: #FFB70322;
    color: #FFB703;
    border: 1px solid #FFB70355;
    border-radius: 20px;
    padding: 0.2rem 0.8rem;
    font-size: 0.85rem;
    font-weight: 500;
}
.status-badge-error {
    display: inline-block;
    background: #EF476F22;
    color: #EF476F;
    border: 1px solid #EF476F55;
    border-radius: 20px;
    padding: 0.2rem 0.8rem;
    font-size: 0.85rem;
    font-weight: 500;
}
.section-divider {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, #2E86AB44, transparent);
    margin: 1.5rem 0;
}
.risk-low      { color: #06D6A0; font-weight: 600; }
.risk-moderate { color: #FFB703; font-weight: 600; }
.risk-high     { color: #EF476F; font-weight: 600; }
.risk-critical { color: #FF0000; font-weight: 700; animation: pulse 1s infinite; }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────────────────────
defaults = {
    'analysis_complete': False,
    'flow_state':        None,
    'uploaded_file_path': None,
    'selected_company':  None,
    'selected_sector':   None,
    'run_history':       [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">📊 Financial FP&A Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Enterprise-Grade AI Financial Analysis · 2-Stage Pipeline · Max 1 LLM Call</div>', unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")

    # LLM Status
    groq_key = os.getenv('GROQ_API_KEY', '')

    if groq_key:
        st.success(f"✅ Groq · `meta-llama/llama-4-scout-17b-16e-instruct`")
    else:
        st.error("❌ LLM not configured")

    st.markdown("---")
    st.markdown("### 📋 Pipeline Stages")
    pipeline_steps = [
        "**Stage 1 — No LLM**",
        "1. Input Validation",
        "2. FP&A Analysis (Python)",
        "3. Chart Generation (6 charts)",
        "**Stage 2 — 1 LLM Call**",
        "4. Report Generation",
        "5. PDF Export",
    ]
    for step in pipeline_steps:
        st.markdown(f"<small>{step}</small>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ⚡ LLM Usage")
    st.markdown("<small>Max **1 API call** per run</small>", unsafe_allow_html=True)
    st.markdown("<small>Fallback: deterministic report if LLM unavailable</small>", unsafe_allow_html=True)

    st.markdown("---")
    # Quick run with default dataset
    if st.button("⚡ Demo Run (AAPL)", use_container_width=True):
        st.session_state.uploaded_file_path = os.path.abspath(
            "src/data/modified_financial_data.csv"
        )
        st.session_state.selected_company = "AAPL"
        st.session_state.selected_sector  = "IT"
        st.rerun()

# ── Main tabs ─────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    ["📤 Upload & Configure", "📊 Results & Charts", "📋 Detailed Analysis", "📄 Download Report"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Upload & Configure
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Financial Data Setup")

    col_upload, col_config = st.columns([3, 2])

    with col_upload:
        st.markdown("#### 📂 Upload Financial CSV")

        # Option A: Upload
        uploaded = st.file_uploader(
            "Choose CSV file",
            type=['csv'],
            help="Required columns: Period, Company, Revenue, EBITDA, Operating_Cash_Flow, Debt/Equity Ratio, Current Ratio"
        )

        # Option B: Use built-in demo data
        use_demo = st.checkbox(
            "Use built-in demo dataset (10 companies, 2009–2023)",
            value=st.session_state.uploaded_file_path is not None
                  and 'modified_financial_data' in str(st.session_state.uploaded_file_path)
        )

        if use_demo and not uploaded:
            demo_path = os.path.abspath("src/data/modified_financial_data.csv")
            if os.path.exists(demo_path):
                st.session_state.uploaded_file_path = demo_path
                st.success(f"✅ Demo dataset loaded")
            else:
                st.error("Demo dataset not found at src/data/modified_financial_data.csv")

        if uploaded:
            temp_dir  = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, "uploaded_data.csv")
            with open(temp_path, 'wb') as f:
                f.write(uploaded.getbuffer())
            st.session_state.uploaded_file_path = temp_path
            st.success(f"✅ Uploaded: {uploaded.name}")

    with col_config:
        st.markdown("#### 🏢 Company Selection")

        if st.session_state.uploaded_file_path and os.path.exists(
            st.session_state.uploaded_file_path
        ):
            try:
                df_preview = pd.read_csv(st.session_state.uploaded_file_path)
                company_col = next(
                    (c for c in df_preview.columns if c.strip() == 'Company'), None
                )
                if company_col:
                    df_preview[company_col] = df_preview[company_col].str.strip()
                    companies = sorted(df_preview[company_col].unique().tolist())
                    selected_company = st.selectbox(
                        "Select Company",
                        companies,
                        index=companies.index(st.session_state.selected_company)
                              if st.session_state.selected_company in companies else 0
                    )
                    st.session_state.selected_company = selected_company

                    # Auto-detect sector
                    if 'Category' in df_preview.columns:
                        co_data = df_preview[df_preview[company_col] == selected_company]
                        auto_sector = str(co_data['Category'].iloc[0]).strip() if len(co_data) > 0 else "IT"
                    else:
                        auto_sector = "IT"

                    st.text_input("Industry Sector", value=auto_sector, disabled=True)
                    st.session_state.selected_sector = auto_sector

            except Exception as e:
                st.error(f"Cannot read file: {e}")

    # Show data preview
    if st.session_state.uploaded_file_path and os.path.exists(
        st.session_state.uploaded_file_path
    ):
        df_prev = pd.read_csv(st.session_state.uploaded_file_path)
        company_col = next((c for c in df_prev.columns if c.strip() == 'Company'), None)

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Rows", len(df_prev))
        with c2:
            st.metric("Columns", len(df_prev.columns))
        with c3:
            n_co = df_prev[company_col].nunique() if company_col else "N/A"
            st.metric("Companies", n_co)
        with c4:
            years = sorted(df_prev['Period'].unique()) if 'Period' in df_prev.columns else []
            period_str = f"{years[0]}–{years[-1]}" if len(years) >= 2 else "–"
            st.metric("Period", period_str)

        with st.expander("📋 Data Preview (first 10 rows)"):
            st.dataframe(df_prev.head(10), use_container_width=True)

        # ── RUN BUTTON ────────────────────────────────────────────────────────
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        _, btn_col, _ = st.columns([1, 2, 1])
        with btn_col:
            run_clicked = st.button(
                "🚀 Run Analysis",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.analysis_complete
            )

        if run_clicked:
            if not st.session_state.selected_company:
                st.error("Please select a company first.")
                st.stop()

            # Reset previous state
            st.session_state.analysis_complete = False
            st.session_state.flow_state        = None

            # ── Progress UI ────────────────────────────────────────────────
            progress_bar = st.progress(0, text="Initializing pipeline...")
            status_ph    = st.empty()
            log_ph       = st.empty()

            os.makedirs("charts",  exist_ok=True)
            os.makedirs("reports", exist_ok=True)
            os.makedirs("logs",    exist_ok=True)
            os.makedirs("cache",   exist_ok=True)

            try:
                from financial_fpa.flow import FinancialAnalysisFlow

                progress_bar.progress(5, text="🔍 Validating input data...")
                status_ph.info(f"Starting analysis for **{st.session_state.selected_company}**...")

                flow = FinancialAnalysisFlow()
                result = flow.kickoff(inputs={
                    "csv_path":     st.session_state.uploaded_file_path,
                    "company_name": st.session_state.selected_company,
                    "sector":       st.session_state.selected_sector or "IT",
                })

                final = flow.state
                step = final.current_step

                progress_bar.progress(100, text="✅ Complete!")

                if step == "completed":
                    st.session_state.analysis_complete = True
                    st.session_state.flow_state        = final
                    status_ph.success(
                        f"🎉 Analysis complete for **{st.session_state.selected_company}**! "
                        f"Check Results & Download tabs."
                    )
                    # Save to history
                    st.session_state.run_history.append({
                        "company":   st.session_state.selected_company,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "pdf_path":  final.pdf_path,
                        "api_calls": getattr(final, 'api_calls_made', 0),
                        "rate_limits": getattr(final, 'rate_limit_hits', 0),
                    })
                else:
                    status_ph.warning(
                        f"⚠️ Analysis ended at step: {step}. "
                        f"{final.error_message or ''}"
                    )
                    # Accept partial results if we have at least the analysis text or report
                    if final.direct_analysis_result or final.llm_report:
                        st.session_state.analysis_complete = True
                        st.session_state.flow_state        = final

            except Exception as e:
                progress_bar.progress(0)
                st.error(f"❌ Pipeline error: {str(e)}")
                with st.expander("🔍 Full Error"):
                    import traceback
                    st.code(traceback.format_exc())

    else:
        st.info("👆 Upload a CSV file or enable the demo dataset to get started.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Results & Charts
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Analysis Results")

    if not st.session_state.analysis_complete or not st.session_state.flow_state:
        st.info("📊 Run the analysis to see results here.")
        st.markdown("""
        **What you'll see after analysis:**
        - 📈 Revenue trend chart
        - 📊 Scenario comparison
        - ⚠️ Risk dashboard
        - 💰 Profitability analysis
        - 🌊 Waterfall chart
        - 🕸️ Financial radar
        """)
    else:
        state = st.session_state.flow_state
        company = state.company_name

        # Status banner
        perf = state.performance_result or {}
        risk_level = perf.get('risk_level', 'unknown')
        report_source = getattr(state, 'llm_report_source', 'unknown')

        banner_col1, banner_col2, banner_col3 = st.columns(3)
        with banner_col1:
            st.metric("Company", company)
        with banner_col2:
            source_label = {"llm": "✅ LLM Report", "fallback": "⚡ Auto Report", "none": "⚠️ No Report"}.get(report_source, report_source)
            st.metric("Report Source", source_label)
        with banner_col3:
            risk_color = {
                'low': '🟢', 'moderate': '🟡', 'high': '🔴', 'critical': '💀'
            }.get(risk_level, '⚪')
            st.metric("Risk Level", f"{risk_color} {risk_level.upper()}")

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        # Key metrics summary
        st.subheader("⚡ Key Metrics Summary")

        if perf:
            rev  = perf.get('revenue', {})
            prof = perf.get('profitability', {})
            cf   = perf.get('cash_flow', {})

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                cagr = rev.get('cagr', 0)
                st.metric("Revenue CAGR", f"{cagr:.1f}%" if cagr else "N/A")
            with m2:
                yoy = rev.get('yoy_growth', 0)
                st.metric("Latest YoY Growth", f"{yoy:.1f}%" if yoy is not None else "N/A",
                          delta=f"{yoy:.1f}%" if yoy else None)
            with m3:
                margin = prof.get('current_ebitda_margin', 0)
                st.metric("EBITDA Margin", f"{margin:.1f}%" if margin else "N/A")
            with m4:
                ocf = cf.get('operating_cash_flow', 0)
                st.metric("Operating CF", f"${ocf:,.0f}M" if ocf else "N/A")

            pos_col, neg_col = st.columns(2)
            with pos_col:
                st.markdown("**✅ Top Strengths**")
                for p in perf.get('top_3_positives', []):
                    st.markdown(f"- {p}")
            with neg_col:
                st.markdown("**⚠️ Top Concerns**")
                for c in perf.get('top_3_concerns', []):
                    st.markdown(f"- {c}")

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        # Charts grid
        st.subheader("📊 Generated Charts")
        chart_map = {
            "Revenue Trend":         "charts/revenue_trend.png",
            "Profitability":         "charts/profitability_analysis.png",
            "Scenario Comparison":   "charts/scenario_comparison.png",
            "Risk Dashboard":        "charts/risk_dashboard.png",
            "Revenue Waterfall":     "charts/waterfall_revenue.png",
            "Financial Radar":       "charts/radar_metrics.png",
        }

        existing = {k: v for k, v in chart_map.items() if os.path.exists(v)}
        if existing:
            chart_items = list(existing.items())
            for i in range(0, len(chart_items), 2):
                cols = st.columns(2)
                for j, col in enumerate(cols):
                    if i + j < len(chart_items):
                        title, path = chart_items[i + j]
                        with col:
                            st.markdown(f"**{title}**")
                            st.image(path, use_column_width=True)
        else:
            st.warning("Charts not found — they may still be generating.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Detailed Analysis
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Detailed Structured Analysis")

    if not st.session_state.analysis_complete or not st.session_state.flow_state:
        st.info("Run the analysis to see detailed structured outputs here.")
    else:
        state = st.session_state.flow_state

        # LLM Report
        if state.llm_report:
            report_source = getattr(state, 'llm_report_source', 'unknown')
            source_badge = {
                "llm":      "🤖 AI-Generated Report",
                "fallback": "⚡ Auto-Generated Report (LLM unavailable)",
            }.get(report_source, "📋 Report")
            st.subheader(f"📄 {source_badge}")
            st.markdown(state.llm_report)
            st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        # Structured performance metrics from Stage 1
        perf = state.performance_result or {}
        if perf:
            st.subheader("📊 Structured Metrics (Computed)")
            rev  = perf.get('revenue', {})
            prof = perf.get('profitability', {})
            cf   = perf.get('cash_flow', {})

            metrics_data = [
                {"Metric": "Revenue CAGR",        "Value": f"{rev.get('cagr', 0):.2f}%",              "Trend": rev.get('trend', 'N/A')},
                {"Metric": "Latest YoY Growth",   "Value": f"{rev.get('yoy_growth', 0):.2f}%",        "Trend": ""},
                {"Metric": "Current Revenue",      "Value": f"${rev.get('current_revenue', 0):,.0f}M",  "Trend": ""},
                {"Metric": "EBITDA Margin",        "Value": f"{prof.get('current_ebitda_margin', 0):.1f}%", "Trend": prof.get('margin_trend', 'N/A')},
                {"Metric": "Operating Cash Flow",  "Value": f"${cf.get('operating_cash_flow', 0):,.0f}M", "Trend": ""},
                {"Metric": "Cash Conv. Ratio",     "Value": f"{cf.get('cash_conversion_ratio', 0):.3f}" if cf.get('cash_conversion_ratio') else "N/A", "Trend": ""},
                {"Metric": "Risk Level",           "Value": perf.get('risk_level', 'unknown').upper(),  "Trend": ""},
            ]
            st.dataframe(pd.DataFrame(metrics_data), use_container_width=True)

            if perf.get('risk_flags'):
                st.markdown("**🚩 Risk Flags:**")
                for flag in perf.get('risk_flags', []):
                    st.warning(flag)

        # Raw analysis text (expandable)
        if state.direct_analysis_result:
            with st.expander("🔍 Raw FP&A Metrics (Stage 1 Output)"):
                st.code(state.direct_analysis_result, language="text")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Download Report
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("Download Reports")

    if not st.session_state.analysis_complete or not st.session_state.flow_state:
        st.info("📄 Reports will become available after running the analysis.")
    else:
        state = st.session_state.flow_state

        # PDF Download
        pdf_path = state.pdf_path
        if pdf_path and os.path.exists(pdf_path):
            st.markdown("### 📄 PDF Report")
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Report Date", datetime.now().strftime("%Y-%m-%d"))
            with c2:
                size_kb = os.path.getsize(pdf_path) / 1024
                st.metric("File Size", f"{size_kb:.1f} KB")

            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()

            st.download_button(
                label="📥 Download PDF Report",
                data=pdf_bytes,
                file_name=f"FPA_{state.company_name}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
        else:
            st.warning("PDF report not available (generation may have failed).")

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

        # Chart Downloads
        st.markdown("### 📊 Individual Charts")
        chart_map = {
            "Revenue Trend":       "charts/revenue_trend.png",
            "Profitability":       "charts/profitability_analysis.png",
            "Scenarios":           "charts/scenario_comparison.png",
            "Risk Dashboard":      "charts/risk_dashboard.png",
            "Revenue Waterfall":   "charts/waterfall_revenue.png",
            "Financial Radar":     "charts/radar_metrics.png",
        }
        existing_charts = {k: v for k, v in chart_map.items() if os.path.exists(v)}
        if existing_charts:
            chart_cols = st.columns(min(3, len(existing_charts)))
            for idx, (name, path) in enumerate(existing_charts.items()):
                with chart_cols[idx % 3]:
                    with open(path, 'rb') as img_file:
                        st.download_button(
                            label=f"📊 {name}",
                            data=img_file.read(),
                            file_name=os.path.basename(path),
                            mime="image/png",
                            use_container_width=True,
                        )

        # JSON Export
        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        st.markdown("### 📋 Structured Data Export")
        structured_data = {
            "company":            state.company_name,
            "sector":             state.sector,
            "timestamp":          datetime.now().isoformat(),
            "report_source":      getattr(state, 'llm_report_source', 'unknown'),
            "performance":        state.performance_result,
            "llm_report":         state.llm_report,
            "direct_analysis":    state.direct_analysis_result,
            "api_calls_made":     getattr(state, 'api_calls_made', 0),
            "rate_limit_hits":    getattr(state, 'rate_limit_hits', 0),
        }
        json_str = json.dumps(
            {k: v for k, v in structured_data.items() if v is not None},
            indent=2
        )
        st.download_button(
            label="📋 Download JSON (Structured Data)",
            data=json_str,
            file_name=f"FPA_{state.company_name}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json",
            use_container_width=True,
        )

        # Run history
        if st.session_state.run_history:
            st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
            st.markdown("### 🕒 Analysis History")
            hist_df = pd.DataFrame(st.session_state.run_history)
            st.dataframe(hist_df, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#555;padding:0.5rem;font-size:0.85rem;'>"
    "<strong>Financial FP&A Intelligence v3</strong> · "
    "2-Stage Pipeline · Max 1 LLM Call · Deterministic Fallback"
    "</div>",
    unsafe_allow_html=True
)

if __name__ == "__main__":
    os.makedirs("charts",  exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    os.makedirs("logs",    exist_ok=True)
    os.makedirs("cache",   exist_ok=True)
