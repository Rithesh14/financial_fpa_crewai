"""
Pydantic Structured Output Models for Financial FP&A Analysis.

These models define typed, validated data contracts for all agent outputs.
Every inter-agent handoff uses these models — eliminating text-parsing roulette.

Changelog:
  v2 — BenchmarkComparison.company_value changed to Optional[float] (Bug fix:
       Groq rejects the tool call when the LLM outputs null for metrics that
       are genuinely unavailable at runtime, e.g. ROE when net-income data is
       missing. The Pydantic schema must accept null so validation passes on
       the first attempt instead of triggering 3 costly retry LLM calls.)
     — RiskMetric.current_value / threshold made Optional[float] for the same
       defensive reason.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any


# ---- Normalizers ----
# Groq validates tool-call JSON against the schema BEFORE Pydantic sees it.
# Enums cause Groq to reject capitalized/synonym values (e.g. "Stable",
# "Increasing"). Plain str fields bypass Groq's enum check; Pydantic
# field_validators normalize after acceptance.

_TREND_SYNONYMS = {
    'increasing': 'accelerating', 'growing': 'accelerating',
    'rising': 'accelerating', 'improving': 'accelerating',
    'decreasing': 'declining', 'shrinking': 'declining',
    'falling': 'declining', 'dropping': 'declining',
    'slowing': 'decelerating', 'weakening': 'decelerating',
}

def _normalize_trend(v):
    """Lowercase + map common LLM synonyms to canonical trend values."""
    if isinstance(v, str):
        v = v.lower().strip()
        return _TREND_SYNONYMS.get(v, v)
    return v

def _normalize_risk(v):
    """Lowercase risk level strings."""
    return v.lower().strip() if isinstance(v, str) else v


# ---- Performance Analysis Output ----

class RevenueAnalysis(BaseModel):
    """Revenue metrics and trend analysis."""
    current_revenue: float = Field(description="Latest period revenue in millions")
    yoy_growth: float = Field(description="Year-over-year growth rate as percentage (e.g. 7.79 means 7.79%)")
    cagr: float = Field(description="Compound annual growth rate over full period as percentage (e.g. 18.61 means 18.61%)")
    trend: str = Field(description="Revenue trend: accelerating, stable, decelerating, or declining")

    @field_validator('trend', mode='before')
    @classmethod
    def norm_trend(cls, v):
        return _normalize_trend(v)


class ProfitabilityAnalysis(BaseModel):
    """Profitability metrics and margin analysis."""
    current_ebitda_margin: float = Field(description="Current EBITDA margin as percentage (e.g. 33.1 means 33.1%)")
    margin_trend: str = Field(description="EBITDA margin trend: accelerating, stable, decelerating, or declining")

    @field_validator('margin_trend', mode='before')
    @classmethod
    def norm_margin_trend(cls, v):
        return _normalize_trend(v)
    operating_leverage_evidence: str = Field(
        description="Evidence of operating leverage in the business"
    )


class CashFlowAnalysis(BaseModel):
    """Cash flow health assessment."""
    operating_cash_flow: float = Field(description="Operating cash flow in millions")
    cash_conversion_ratio: Optional[float] = Field(
        default=None,
        description="Cash conversion ratio (OCF / Net Income)"
    )
    free_cash_flow: Optional[float] = Field(
        default=None,
        description="Free cash flow in millions"
    )


class PerformanceAnalysisOutput(BaseModel):
    """Structured output from the FPA Analyst agent."""
    company_name: str = Field(description="Name/ticker of the analyzed company")
    analysis_period: str = Field(description="Time period covered by the analysis")
    revenue: RevenueAnalysis
    profitability: ProfitabilityAnalysis
    cash_flow: CashFlowAnalysis
    top_3_positives: List[str] = Field(
        description="Top 3 positive findings from the analysis"
    )
    top_3_concerns: List[str] = Field(
        description="Top 3 concerns or risk areas identified"
    )
    data_quality_notes: List[str] = Field(
        default=[],
        description="Notes about data quality issues encountered"
    )


# ---- Scenario Planning Output ----

class ScenarioProjection(BaseModel):
    """A single scenario with projected financials."""
    scenario_name: str = Field(description="e.g. 'Best Case', 'Base Case', 'Worst Case'")
    growth_rate: float = Field(description="Annual growth rate as percentage (e.g. 8.79 means 8.79%)")
    assumptions: List[str] = Field(description="Key assumptions for this scenario")
    year_1_revenue: float = Field(description="Projected Year 1 revenue in millions")
    year_2_revenue: float = Field(description="Projected Year 2 revenue in millions")
    year_3_revenue: float = Field(description="Projected Year 3 revenue in millions")
    probability_weight: float = Field(
        description="Estimated probability (0-1), must sum to ~1 across scenarios"
    )


class ScenarioPlanningOutput(BaseModel):
    """Structured output from the Scenario Analyst agent."""
    company_name: str = Field(description="Name/ticker of the analyzed company")
    base_revenue: float = Field(description="Last known revenue used as base in millions")
    scenarios: List[ScenarioProjection] = Field(
        description="List of scenario projections (typically 3)"
    )
    sensitivity_drivers: List[str] = Field(
        description="Top 3 variables that most impact outcomes"
    )


# ---- Risk Assessment Output ----

class RiskMetric(BaseModel):
    """A single financial risk metric with threshold analysis."""
    metric_name: str = Field(description="Name of the risk metric")
    # BUG FIX: Made Optional[float] to prevent validation failures when the LLM
    # cannot determine the exact numerical value from context alone.
    current_value: Optional[float] = Field(
        default=None,
        description="Current value of the metric. Use 0.0 if genuinely unknown rather than null."
    )
    threshold: Optional[float] = Field(
        default=None,
        description="Risk threshold value. Use 0.0 if not applicable."
    )
    status: str = Field(description="Risk status: low, moderate, high, or critical")

    @field_validator('status', mode='before')
    @classmethod
    def norm_status(cls, v):
        return _normalize_risk(v)
    interpretation: str = Field(description="Business interpretation of this metric")


class RiskAssessmentOutput(BaseModel):
    """Structured output from the Risk Analyst agent."""
    company_name: str = Field(description="Name/ticker of the analyzed company")
    overall_risk_level: str = Field(description="Overall risk: low, moderate, high, or critical")

    @field_validator('overall_risk_level', mode='before')
    @classmethod
    def norm_risk(cls, v):
        return _normalize_risk(v)
    metrics: List[RiskMetric] = Field(description="Individual risk metrics assessed")
    risk_flags: List[str] = Field(description="Active risk warnings")
    mitigation_recommendations: List[str] = Field(
        description="Recommended actions to mitigate identified risks"
    )


# ---- Market Research Output ----

class BenchmarkComparison(BaseModel):
    """Comparison of company metric against industry benchmark."""
    metric_name: str = Field(description="Name of the compared metric")
    # BUG FIX (v2): Changed from `float` to `Optional[float]` with default=None.
    #
    # Root cause: When a metric (e.g. ROE) is not available in the performance
    # analysis context, the LLM correctly outputs null.  The previous `float`
    # type caused Groq's tool-call validator to reject the entire response with:
    #   "expected number, but got null"
    # This triggered 3 Pydantic retry attempts, each consuming ~2 K tokens and
    # pushing the pipeline into TPM rate-limit territory before downstream tasks
    # (risk_assessment, cfo_advisory) even started.
    #
    # Resolution: Accept null here.  The flow's generate_reports step already
    # uses .get() with defaults, so a None value is handled safely downstream.
    company_value: Optional[float] = Field(
        default=None,
        description=(
            "Company's value for this metric as a number. "
            "Use 0.0 if the metric is unknown rather than omitting the field."
        )
    )
    industry_median: float = Field(description="Industry median value")
    percentile_rank: Optional[float] = Field(
        default=None,
        description="Company's percentile rank within industry (0-100)"
    )
    assessment: str = Field(
        description="Performance assessment: 'Outperforms', 'Matches', or 'Underperforms'"
    )


class MarketResearchOutput(BaseModel):
    """Structured output from the Market Researcher agent."""
    company_name: str = Field(description="Name/ticker of the analyzed company")
    sector: str = Field(description="Industry sector of the company")
    benchmarks: List[BenchmarkComparison] = Field(
        description="List of benchmark comparisons"
    )
    market_trends: List[str] = Field(
        description="Key market trends affecting the sector"
    )
    competitive_position_summary: str = Field(
        description="Summary of competitive positioning"
    )


# ---- CFO Advisory Output ----

class StrategicRecommendation(BaseModel):
    """A single strategic recommendation for executive leadership."""
    title: str = Field(description="Brief title of the recommendation")
    rationale: str = Field(description="Supporting rationale for this recommendation")
    priority: str = Field(description="'immediate', 'short-term', or 'medium-term'")
    expected_impact: str = Field(description="Expected business impact if implemented")


class CFOAdvisoryOutput(BaseModel):
    """Structured output from the CFO Advisor agent."""
    company_name: str = Field(description="Name/ticker of the analyzed company")
    executive_summary: str = Field(
        description="2-3 sentence overview of key takeaways for the board"
    )
    performance_highlights: List[str] = Field(
        description="Top performance highlights from the analysis"
    )
    risk_considerations: List[str] = Field(
        description="Key risk factors to monitor"
    )
    future_outlook: str = Field(
        description="Forward-looking assessment of the company"
    )
    recommendations: List[StrategicRecommendation] = Field(
        description="3-5 strategic recommendations for executive action"
    )