"""
Financial FP&A Analysis - Streamlit Application
Interactive web interface for enterprise financial analysis
"""

import streamlit as st
import pandas as pd
import os
import sys
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Force Ollama configuration if not already set
if not os.getenv('OPENAI_API_BASE'):
    os.environ['OPENAI_API_BASE'] = 'http://localhost:11434/v1'
if not os.getenv('OPENAI_MODEL_NAME'):
    os.environ['OPENAI_MODEL_NAME'] = 'llama3.1'
if not os.getenv('OPENAI_API_KEY'):
    os.environ['OPENAI_API_KEY'] = 'NA'

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from financial_fpa.crew import FinancialFpa

# Page configuration
st.set_page_config(
    page_title="Financial FP&A Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define run_analysis function early so it can be called later
def run_analysis(csv_path):
    """Run the complete FP&A analysis pipeline"""
    
    # Create progress container
    progress_container = st.container()
    
    with progress_container:
        st.markdown("### 🔄 Analysis in Progress")
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Create directories
        os.makedirs("charts", exist_ok=True)
        os.makedirs("reports", exist_ok=True)
        
        try:
            # Step 1: Initialize
            status_text.text("Initializing AI agents...")
            progress_bar.progress(10)
            
            # Prepare inputs
            inputs = {'csv_path': csv_path}
            
            # Step 2: Run analysis
            status_text.text("Running financial analysis (this may take a few minutes)...")
            progress_bar.progress(20)
            
            # Execute crew
            with st.spinner("AI agents are analyzing your data..."):
                result = FinancialFpa().crew().kickoff(inputs=inputs)
            
            progress_bar.progress(90)
            status_text.text("Finalizing report...")
            
            # Check for PDF
            pdf_path = "reports/fpa_analysis.pdf"
            if os.path.exists(pdf_path):
                st.session_state.pdf_path = pdf_path
            
            # Mark as complete
            st.session_state.analysis_complete = True
            st.session_state.charts_generated = True
            
            progress_bar.progress(100)
            status_text.text("✅ Analysis complete!")
            
            st.success("🎉 Analysis completed successfully! Check the 'Results & Charts' and 'Download Report' tabs.")
            st.balloons()
            
        except Exception as e:
            st.error(f"❌ Error during analysis: {str(e)}")
            st.exception(e)
            progress_bar.progress(0)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E86AB;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-left: 5px solid #28a745;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        background-color: #d1ecf1;
        border-left: 5px solid #17a2b8;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'analysis_complete' not in st.session_state:
    st.session_state.analysis_complete = False
if 'charts_generated' not in st.session_state:
    st.session_state.charts_generated = False
if 'pdf_path' not in st.session_state:
    st.session_state.pdf_path = None
if 'uploaded_file_path' not in st.session_state:
    st.session_state.uploaded_file_path = None

# Header
st.markdown('<div class="main-header">📊 Financial FP&A Analysis</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Enterprise-Grade Financial Analysis with AI Agents</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("🔧 Configuration")
    
    st.markdown("### Analysis Pipeline")
    st.markdown("""
    1. **Performance Analysis** - Historical metrics
    2. **Market Research** - Industry benchmarks
    3. **Scenario Planning** - Future projections
    4. **Risk Assessment** - Financial stability
    5. **Chart Generation** - Visual insights
    6. **CFO Advisory** - Executive summary
    7. **PDF Report** - Comprehensive output
    """)
    
    st.markdown("---")
    
    st.markdown("### 🤖 AI Agents")
    st.markdown("""
    - FP&A Analyst
    - Market Researcher
    - Scenario Analyst
    - Risk Analyst
    - CFO Advisor
    """)
    
    st.markdown("---")
    
    # API Key / LLM Configuration status
    st.markdown("### 🤖 LLM Configuration")
    
    # Check for Ollama or OpenAI configuration
    openai_base = os.getenv('OPENAI_API_BASE')
    openai_key = os.getenv('OPENAI_API_KEY')
    model_name = os.getenv('OPENAI_MODEL_NAME')
    
    if openai_base and 'localhost' in openai_base:
        # Using Ollama
        st.success("✅ Ollama (Local LLM)")
        if model_name:
            st.info(f"📦 Model: {model_name}")
        else:
            st.warning("⚠️ OPENAI_MODEL_NAME not set")
    elif openai_key and openai_key != 'NA':
        # Using OpenAI
        st.success("✅ OpenAI API configured")
    else:
        st.error("❌ LLM not configured")
        st.markdown("Set up either Ollama or OpenAI in `.env`")
    
    st.markdown("---")
    st.markdown("### 🌐 Internet Search")

    if os.getenv('SERPER_API_KEY'):
        st.success("✅ Serper API Key configured")
    else:
        st.warning("⚠️ Serper API Key missing (optional)")

# Main content
tab1, tab2, tab3 = st.tabs(["📤 Upload & Analyze", "📊 Results & Charts", "📄 Download Report"])

with tab1:
    st.header("Upload Financial Data")
    
    st.markdown("""
    <div class="info-box">
    <strong>📋 Required CSV Format:</strong><br>
    Your CSV should contain financial data with columns like: Period, Revenue, EBITDA, 
    Operating_Cash_Flow, Debt/Equity Ratio, Current Ratio, etc.
    </div>
    """, unsafe_allow_html=True)
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=['csv'],
        help="Upload your financial data in CSV format"
    )
    
    if uploaded_file is not None:
        # Display file info
        st.success(f"✅ File uploaded: {uploaded_file.name}")
        
        # Preview data
        try:
            df = pd.read_csv(uploaded_file)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Rows", len(df))
            with col2:
                st.metric("Columns", len(df.columns))
            with col3:
                st.metric("Companies", df['Company'].nunique() if 'Company' in df.columns else 'N/A')
            
            with st.expander("📊 Preview Data (First 10 rows)"):
                st.dataframe(df.head(10), use_container_width=True)
            
            with st.expander("📋 Column Information"):
                st.write("**Available Columns:**")
                st.write(", ".join(df.columns.tolist()))
            
            # Save uploaded file temporarily
            temp_dir = tempfile.mkdtemp()
            temp_file_path = os.path.join(temp_dir, "uploaded_data.csv")
            df.to_csv(temp_file_path, index=False)
            st.session_state.uploaded_file_path = temp_file_path
            
            st.markdown("---")
            
            # Analysis button
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚀 Start Analysis", type="primary", use_container_width=True):
                    run_analysis(temp_file_path)
        
        except Exception as e:
            st.error(f"❌ Error reading CSV file: {str(e)}")
    
    else:
        st.info("👆 Please upload a CSV file to begin analysis")

with tab2:
    st.header("Analysis Results")
    
    if st.session_state.analysis_complete:
        st.markdown('<div class="success-box"><strong>✅ Analysis Complete!</strong> View your results below.</div>', unsafe_allow_html=True)
        
        # Display charts
        st.subheader("📊 Generated Charts")
        
        chart_files = {
            "Revenue Trend": "charts/revenue_trend.png",
            "Scenario Comparison": "charts/scenario_comparison.png",
            "Risk Dashboard": "charts/risk_dashboard.png",
            "Profitability Analysis": "charts/profitability_analysis.png"
        }
        
        # Display charts in 2x2 grid
        col1, col2 = st.columns(2)
        
        chart_items = list(chart_files.items())
        
        with col1:
            for i in [0, 2]:
                if i < len(chart_items):
                    title, path = chart_items[i]
                    if os.path.exists(path):
                        st.markdown(f"**{title}**")
                        st.image(path, use_container_width=True)
                    else:
                        st.warning(f"Chart not found: {title}")
        
        with col2:
            for i in [1, 3]:
                if i < len(chart_items):
                    title, path = chart_items[i]
                    if os.path.exists(path):
                        st.markdown(f"**{title}**")
                        st.image(path, use_container_width=True)
                    else:
                        st.warning(f"Chart not found: {title}")
        
        # Display insights
        st.markdown("---")
        st.subheader("💡 Key Insights")
        
        # Check for output files
        if os.path.exists("reports/fpa_analysis_summary.md"):
            with open("reports/fpa_analysis_summary.md", "r") as f:
                summary = f.read()
                st.markdown(summary)
        else:
            st.info("Executive summary will appear here after analysis completes.")
    
    else:
        st.info("📊 Results will appear here after running the analysis")
        st.markdown("""
        The analysis will generate:
        - 📈 Revenue trend visualization
        - 📊 Scenario comparison chart
        - ⚠️ Risk metrics dashboard
        - 💰 Profitability analysis
        - 📝 Executive insights
        """)

with tab3:
    st.header("Download Report")
    
    if st.session_state.analysis_complete and st.session_state.pdf_path:
        st.markdown('<div class="success-box"><strong>✅ PDF Report Ready!</strong></div>', unsafe_allow_html=True)
        
        # Report info
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Report Date", datetime.now().strftime("%Y-%m-%d"))
        with col2:
            if os.path.exists(st.session_state.pdf_path):
                file_size = os.path.getsize(st.session_state.pdf_path) / 1024  # KB
                st.metric("File Size", f"{file_size:.1f} KB")
        
        st.markdown("### 📄 Report Contents")
        st.markdown("""
        - **Cover Page** - Title and date
        - **Executive Summary** - Key findings
        - **Performance Analysis** - Historical metrics with charts
        - **Market Context** - Industry benchmarks
        - **Scenario Planning** - Future projections with visualizations
        - **Risk Assessment** - Financial stability analysis
        - **Strategic Recommendations** - Actionable insights
        """)
        
        # Download button
        if os.path.exists(st.session_state.pdf_path):
            with open(st.session_state.pdf_path, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()
                
                st.download_button(
                    label="📥 Download PDF Report",
                    data=pdf_bytes,
                    file_name=f"FPA_Analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )
        
        # Download individual charts
        st.markdown("---")
        st.markdown("### 📊 Download Individual Charts")
        
        chart_cols = st.columns(4)
        chart_files = {
            "Revenue Trend": "charts/revenue_trend.png",
            "Scenarios": "charts/scenario_comparison.png",
            "Risk Dashboard": "charts/risk_dashboard.png",
            "Profitability": "charts/profitability_analysis.png"
        }
        
        for idx, (name, path) in enumerate(chart_files.items()):
            with chart_cols[idx]:
                if os.path.exists(path):
                    with open(path, "rb") as img_file:
                        st.download_button(
                            label=f"📊 {name}",
                            data=img_file.read(),
                            file_name=os.path.basename(path),
                            mime="image/png",
                            use_container_width=True
                        )
    
    else:
        st.info("📄 PDF report will be available here after analysis completes")
        st.markdown("""
        The comprehensive PDF report will include:
        - All generated charts
        - Insights from all AI agents
        - Executive summary
        - Strategic recommendations
        - Professional formatting
        """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <strong>Financial FP&A Analysis System</strong><br>
    Powered by CrewAI | Enterprise-Grade Financial Intelligence
</div>
""", unsafe_allow_html=True)


if __name__ == "__main__":
    # Ensure required directories exist
    os.makedirs("charts", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
