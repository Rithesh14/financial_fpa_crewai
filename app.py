#!/usr/bin/env python
"""
Financial FP&A Analysis - Main Execution Script
Enterprise-grade financial analysis using CrewAI
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from financial_fpa.crew import FinancialFpa

def main():
    """
    Main execution function for Financial FP&A Analysis
    
    This script runs a comprehensive financial analysis including:
    - Performance Analysis (FPA Analyst)
    - Scenario Planning (Scenario Analyst)
    - Risk Assessment (Risk Analyst)
    - CFO Advisory Summary (CFO Advisor)
    """
    
    # Define the path to the financial dataset
    csv_path = os.path.abspath("src/data/modified_financial_data.csv")
    
    # Validate dataset exists
    if not os.path.exists(csv_path):
        print(f"❌ Error: Dataset not found at {csv_path}")
        sys.exit(1)
    
    print("\n" + "="*70)
    print("🚀 FINANCIAL FP&A ANALYSIS - ENTERPRISE PIPELINE")
    print("="*70)
    print(f"📊 Dataset: {csv_path}")
    print(f"📈 Analysis Pipeline:")
    print(f"   1. Performance Analysis (Historical & Current)")
    print(f"   2. Scenario Planning (Best/Base/Worst Case)")
    print(f"   3. Risk Assessment (Liquidity & Leverage)")
    print(f"   4. CFO Executive Summary (Board-Ready)")
    print("="*70 + "\n")
    
    # Prepare inputs
    inputs = {
        'csv_path': csv_path
    }
    
    try:
        # Execute the crew
        result = FinancialFpa().crew().kickoff(inputs=inputs)
        
        print("\n" + "="*70)
        print("✅ ANALYSIS COMPLETE!")
        print("="*70)
        print(f"📄 CFO Executive Summary: cfo_executive_summary.md")
        print("="*70 + "\n")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error during analysis: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
