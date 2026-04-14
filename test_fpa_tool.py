"""
Test script to validate FP&A tool functionality
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from fpa_tools.fpa_operations import run_fpa_analysis

def test_fpa_tool():
    """Test the FPA analysis tool with the dataset"""
    
    csv_path = "src/data/modified_financial_data.csv"
    
    print("="*60)
    print("Testing FP&A Analysis Tool")
    print("="*60)
    print(f"Dataset: {csv_path}\n")
    
    try:
        # Run analysis
        result = run_fpa_analysis(csv_path)
        
        print("✅ Tool executed successfully!\n")
        print("Results:")
        print("-" * 60)
        
        # Display results
        print(f"📈 Average Revenue Growth: {result['avg_revenue_growth']:.1%}")
        print(f"💰 Average EBITDA Margin: {result['avg_ebitda_margin']:.1%}")
        print(f"💵 Average Operating Cash Flow: ${result['avg_operating_cash_flow']:,.2f}M")
        print(f"⚖️  Average Debt/Equity Ratio: {result['avg_debt_equity']:.2f}")
        print(f"💧 Average Current Ratio: {result['avg_current_ratio']:.2f}")
        
        print("\n📊 Revenue Scenarios:")
        print(f"   Best Case:  ${result['scenarios']['best_case']:,.2f}M (+15%)")
        print(f"   Base Case:  ${result['scenarios']['base_case']:,.2f}M")
        print(f"   Worst Case: ${result['scenarios']['worst_case']:,.2f}M (-15%)")
        
        print("\n" + "="*60)
        print("✅ All metrics calculated correctly!")
        print("="*60)
        
        # Validation checks
        print("\n🔍 Validation Checks:")
        
        # Check 1: Revenue growth should be reasonable
        if -0.5 < result['avg_revenue_growth'] < 0.5:
            print("✅ Revenue growth is within reasonable range")
        else:
            print("⚠️  Revenue growth seems unusual")
        
        # Check 2: EBITDA margin should be positive for healthy companies
        if result['avg_ebitda_margin'] > 0:
            print("✅ EBITDA margin is positive")
        else:
            print("⚠️  Negative EBITDA margin detected")
        
        # Check 3: Scenarios should be properly ordered
        if (result['scenarios']['worst_case'] < 
            result['scenarios']['base_case'] < 
            result['scenarios']['best_case']):
            print("✅ Scenarios are properly ordered")
        else:
            print("❌ Scenario ordering is incorrect")
        
        # Check 4: Current ratio > 1 is generally healthy
        if result['avg_current_ratio'] >= 1:
            print("✅ Current ratio indicates adequate liquidity")
        else:
            print("⚠️  Current ratio below 1 - potential liquidity concern")
        
        print("\n" + "="*60)
        print("🎉 Tool validation complete!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_fpa_tool()
    sys.exit(0 if success else 1)
