"""
Test script for chart generation tools
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from fpa_tools.chart_tools import (
    generate_revenue_trend_chart,
    generate_scenario_comparison_chart,
    generate_risk_dashboard,
    generate_profitability_analysis_chart
)

def test_chart_tools():
    """Test all chart generation tools"""
    
    csv_path = "src/data/modified_financial_data.csv"
    
    print("="*60)
    print("Testing Chart Generation Tools")
    print("="*60)
    print(f"Dataset: {csv_path}\n")
    
    try:
        # Test 1: Revenue Trend Chart
        print("1. Generating Revenue Trend Chart...")
        result1 = generate_revenue_trend_chart(csv_path)
        print(f"   ✅ {result1['status']}: {result1['chart_path']}")
        print(f"   📊 {result1['insights']}\n")
        
        # Test 2: Scenario Comparison Chart
        print("2. Generating Scenario Comparison Chart...")
        result2 = generate_scenario_comparison_chart(csv_path)
        print(f"   ✅ {result2['status']}: {result2['chart_path']}")
        print(f"   📊 {result2['insights']}\n")
        
        # Test 3: Risk Dashboard
        print("3. Generating Risk Dashboard...")
        result3 = generate_risk_dashboard(csv_path)
        print(f"   ✅ {result3['status']}: {result3['chart_path']}")
        print(f"   📊 {result3['insights']}\n")
        
        # Test 4: Profitability Analysis Chart
        print("4. Generating Profitability Analysis Chart...")
        result4 = generate_profitability_analysis_chart(csv_path)
        print(f"   ✅ {result4['status']}: {result4['chart_path']}")
        print(f"   📊 {result4['insights']}\n")
        
        print("="*60)
        print("✅ All charts generated successfully!")
        print("="*60)
        print(f"\nCharts saved to: charts/")
        print("  - revenue_trend.png")
        print("  - scenario_comparison.png")
        print("  - risk_dashboard.png")
        print("  - profitability_analysis.png")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_chart_tools()
    sys.exit(0 if success else 1)
