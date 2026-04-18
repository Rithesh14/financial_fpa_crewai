#!/usr/bin/env python
"""
Financial FP&A Analysis — Root CLI entry point (app.py).
Delegates to the Flow-based pipeline.
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Load env
from dotenv import load_dotenv
load_dotenv()

# Force Groq config if not already set
if not os.getenv('OPENAI_API_BASE'):
    os.environ['OPENAI_API_BASE'] = 'https://api.groq.com/openai/v1'
if not os.getenv('OPENAI_MODEL_NAME'):
    os.environ['OPENAI_MODEL_NAME'] = 'llama-3.1-8b-instant'
if not os.getenv('OPENAI_API_KEY') and os.getenv('GROQ_API_KEY'):
    os.environ['OPENAI_API_KEY'] = os.getenv('GROQ_API_KEY')


def main():
    csv_path     = os.path.abspath("src/data/modified_financial_data.csv")
    company_name = os.environ.get("FPA_COMPANY", "AAPL")
    sector       = os.environ.get("FPA_SECTOR", "IT")

    if not os.path.exists(csv_path):
        print(f"❌ Error: Dataset not found at {csv_path}")
        sys.exit(1)

    print("\n" + "="*70)
    print("🚀 FINANCIAL FP&A ANALYSIS — ENTERPRISE PIPELINE v2")
    print("="*70)
    print(f"📊 Dataset:  {csv_path}")
    print(f"🏢 Company:  {company_name}")
    print(f"🏭 Sector:   {sector}")
    print("="*70 + "\n")

    os.makedirs("charts",  exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    os.makedirs("logs",    exist_ok=True)

    try:
        from financial_fpa.flow import FinancialAnalysisFlow

        flow   = FinancialAnalysisFlow()
        result = flow.kickoff(inputs={
            "csv_path":     csv_path,
            "company_name": company_name,
            "sector":       sector,
        })

        final = flow.state
        print("\n" + "="*70)
        if final.current_step == "completed":
            print("✅ ANALYSIS COMPLETE!")
        else:
            print(f"⚠️  ANALYSIS ENDED: step={final.current_step}")
        print("="*70)
        if final.pdf_path:
            print(f"📄 PDF Report:  {final.pdf_path}")
        if final.charts_generated:
            print(f"📊 Charts:      {len(final.charts_generated)} files in charts/")
        if final.error_message:
            print(f"⚠️  Message:     {final.error_message}")
        print("="*70 + "\n")
        return result

    except Exception as e:
        print(f"\n❌ Error during analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
