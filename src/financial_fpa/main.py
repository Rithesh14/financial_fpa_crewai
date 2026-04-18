#!/usr/bin/env python
"""
Financial FP&A Analysis — CLI entry point.
Uses the FinancialAnalysisFlow for production-grade orchestration.
"""
import sys
import os
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def run():
    """Run the FP&A analysis pipeline via the Flow."""
    csv_path     = os.path.abspath("src/data/modified_financial_data.csv")
    company_name = os.environ.get("FPA_COMPANY", "AAPL")
    sector       = os.environ.get("FPA_SECTOR", "IT")

    print(f"\n{'='*60}")
    print("🚀 Financial FP&A Analysis — Production Pipeline")
    print(f"{'='*60}")
    print(f"📊 Dataset: {csv_path}")
    print(f"🏢 Company: {company_name}")
    print(f"🏭 Sector:  {sector}")
    print(f"{'='*60}\n")

    from financial_fpa.flow import FinancialAnalysisFlow

    flow   = FinancialAnalysisFlow()
    result = flow.kickoff(inputs={
        "csv_path":     csv_path,
        "company_name": company_name,
        "sector":       sector,
    })

    final = flow.state
    print(f"\n{'='*60}")
    print("✅ Analysis Complete!")
    print(f"{'='*60}")
    print(f"📌 Step:    {final.current_step}")
    if final.pdf_path:
        print(f"📄 PDF:     {final.pdf_path}")
    if final.charts_generated:
        print(f"📊 Charts:  {len(final.charts_generated)} generated")
    if final.error_message:
        print(f"⚠️  Warning: {final.error_message}")
    print(f"{'='*60}\n")
    return result


def train():
    """Train the crew."""
    csv_path = os.path.abspath("src/data/modified_financial_data.csv")
    inputs   = {"csv_path": csv_path, "company_name": "AAPL", "benchmark_sector": "IT"}
    try:
        from financial_fpa.crew import FinancialFpa
        FinancialFpa().crew().train(
            n_iterations=int(sys.argv[1]),
            filename=sys.argv[2],
            inputs=inputs
        )
    except Exception as e:
        raise Exception(f"Training failed: {e}")


def replay():
    """Replay crew execution from a specific task."""
    try:
        from financial_fpa.crew import FinancialFpa
        FinancialFpa().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"Replay failed: {e}")


def test():
    """Test the crew execution."""
    csv_path = os.path.abspath("src/data/modified_financial_data.csv")
    inputs   = {"csv_path": csv_path, "company_name": "AAPL", "benchmark_sector": "IT"}
    try:
        from financial_fpa.crew import FinancialFpa
        FinancialFpa().crew().test(
            n_iterations=int(sys.argv[1]),
            openai_model_name=sys.argv[2],
            inputs=inputs
        )
    except Exception as e:
        raise Exception(f"Test failed: {e}")
