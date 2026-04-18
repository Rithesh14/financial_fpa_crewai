"""
Financial FP&A Crew — Production Architecture v2.

Features implemented:
  Phase 1: output_pydantic on all 5 analysis tasks (structured output)
  Phase 2: Knowledge Sources — JSONKnowledgeSource + TextFileKnowledgeSource
  Phase 3: memory=False (Groq has no embeddings API; disabled to avoid conflicts)
  Phase 5: Process.sequential with guardrails on performance + CFO tasks
  Phase 6: Task callbacks for progress tracking
"""

import os
import re
from typing import Tuple, Any

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task

# Knowledge sources
try:
    from crewai.knowledge.source.json_knowledge_source import JSONKnowledgeSource
    from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource
    KNOWLEDGE_AVAILABLE = True
except ImportError:
    KNOWLEDGE_AVAILABLE = False

from crewai.tools import tool

from fpa_tools.fpa_operations import run_fpa_analysis
from fpa_tools.chart_tools import (
    generate_revenue_trend_chart,
    generate_scenario_comparison_chart,
    generate_risk_dashboard,
    generate_profitability_analysis_chart,
    generate_waterfall_chart,
    generate_radar_chart,
    generate_metrics_heatmap,
)
from fpa_tools.pdf_generator import generate_pdf_report

from financial_fpa.models import (
    PerformanceAnalysisOutput,
    ScenarioPlanningOutput,
    RiskAssessmentOutput,
    MarketResearchOutput,
    CFOAdvisoryOutput,
)


# ── LLM — explicit groq/ prefix so LiteLLM resolves tool schemas correctly ───
# The OPENAI_API_BASE trick causes LiteLLM to return None for supported_params,
# which breaks tool-calling and produces empty responses. Using groq/ prefix
# lets LiteLLM use its native Groq route with proper tool schema support.
# llama-4-scout-17b-16e-instruct: 30K TPM / 30 RPM on Groq free tier.
# Replaces llama-3.1-8b-instant (6K TPM) — 5x more headroom eliminates rate-limit
# crashes across 7 sequential tasks. Better structured JSON output quality too.
_groq_llm = LLM(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=os.environ.get("GROQ_API_KEY", ""),
    temperature=0.1,
    max_tokens=2048,  # Structured JSON outputs don't need more than 2048
)


# ── Knowledge Sources (Phase 2) ─────────────────────────────────────────────
def _build_knowledge_sources():
    """Build knowledge source instances if the library supports them."""
    if not KNOWLEDGE_AVAILABLE:
        return None, None
    try:
        benchmarks_knowledge = JSONKnowledgeSource(
            file_paths=["knowledge/industry_benchmarks.json"]
        )
        fpa_knowledge = TextFileKnowledgeSource(
            file_paths=["knowledge/fpa_frameworks.txt"]
        )
        return benchmarks_knowledge, fpa_knowledge
    except Exception:
        return None, None


benchmarks_knowledge, fpa_knowledge = _build_knowledge_sources()


# ── FPA Analysis Tool (wraps per-company engine) ──────────────────────────────
@tool
def fpa_analysis_tool(csv_path: str, company: str = "", sector: str = ""):
    """
    Run comprehensive FP&A analysis for a specific company.

    Args:
        csv_path: Path to the CSV file containing financial data
        company: Company name/ticker to analyze (required for accurate results)
        sector: Industry sector for risk context (e.g. 'IT', 'FinTech', 'Bank')

    Returns:
        Compact financial metrics summary (token-efficient) including revenue CAGR,
        EBITDA margins, cash flow, risk indicators, and scenario projections.
    """
    return run_fpa_analysis(
        csv_path=csv_path,
        company=company if company else None,
        sector=sector if sector else None,
    )

    # ── Compress output to ~400 tokens (was ~3,500) ───────────────────────────
    # Keep only the fields agents actually need; summarize verbose sub-lists.
    yoy = raw.get('yoy_table', [])
    yoy_summary = [
        {"period": r["period"], "growth_pct": round(r["growth"] * 100, 1)}
        for r in yoy[-5:]   # Last 5 years only — enough for trend analysis
    ]

    scenarios = raw.get('scenarios', [])
    scenario_summary = [
        {
            "name": s["scenario_name"],
            "growth_rate_pct": round(s["growth_rate"] * 100, 1),
            "y1_revenue": round(s["year_1_revenue"]),
            "y3_revenue": round(s["year_3_revenue"]),
            "weight": s["probability_weight"],
        }
        for s in scenarios
    ]

    risk = raw.get('risk', {})
    risk_summary = {
        "overall": risk.get('overall_risk_level', 'unknown'),
        "flags": risk.get('risk_flags', []),
    }

    return {
        "company": raw.get('company_name'),
        "period": raw.get('analysis_period'),
        "current_revenue_M": raw.get('current_revenue'),
        "revenue_cagr_pct": round(raw.get('revenue_cagr', 0) * 100, 2),
        "yoy_growth_latest_pct": round(raw.get('yoy_growth', 0) * 100, 2),
        "revenue_trend": raw.get('revenue_trend'),
        "yoy_last5": yoy_summary,
        "full_period_yoy_count": len(yoy),
        "ebitda_margin_pct": round(raw.get('current_ebitda_margin', 0) * 100, 2),
        "avg_ebitda_margin_pct": round(raw.get('avg_ebitda_margin', 0) * 100, 2),
        "margin_trend": raw.get('margin_trend'),
        "operating_leverage": raw.get('operating_leverage_evidence'),
        "operating_cf_M": raw.get('operating_cash_flow'),
        "avg_operating_cf_M": round(raw.get('avg_operating_cash_flow', 0), 1),
        "cash_conversion_ratio": round(raw.get('cash_conversion_ratio', 0), 3),
        "fcf_per_share": raw.get('free_cash_flow_per_share'),
        "debt_equity": raw.get('current_debt_equity'),
        "current_ratio": raw.get('current_ratio'),
        "roe_pct": raw.get('current_roe'),
        "roa_pct": raw.get('current_roa'),
        "scenarios": scenario_summary,
        "base_revenue_M": raw.get('base_revenue'),
        "risk": risk_summary,
        "sector": raw.get('sector'),
    }


# ── Guardrail Functions (Phase 5) ────────────────────────────────────────────

def validate_performance_output(output) -> Tuple[bool, Any]:
    """
    Guardrail: Ensure performance analysis contains real numbers,
    references the correct company, and doesn't average across companies.
    """
    text = output.raw if hasattr(output, 'raw') else str(output)

    # Must contain actual numbers
    numbers = re.findall(r'\d+\.?\d*%?', text)
    if len(numbers) < 5:
        return (False, "Performance analysis must contain at least 5 specific numerical metrics.")

    # Guard against cross-company averages
    if "average across all companies" in text.lower():
        return (False, "Do NOT average across companies. Analyze the specific company only.")

    if "all companies" in text.lower() and "average" in text.lower():
        return (False, "Analysis must be scoped to the selected company only, not averaged.")

    return (True, "Output validated successfully")


def validate_cfo_output(output) -> Tuple[bool, Any]:
    """
    Guardrail: CFO advisory must be concise and have the right number of recommendations.
    """
    text = output.raw if hasattr(output, 'raw') else str(output)

    # Must mention recommendations
    rec_count = len(re.findall(
        r'(recommend|immediate|short-term|medium-term)', text, re.IGNORECASE
    ))
    if rec_count < 3:
        return (
            False,
            "CFO advisory must include at least 3 strategic recommendations with clear priorities."
        )

    return (True, "CFO output validated successfully")


# ── Task Callback (Phase 6) ────────────────────────────────────────────────────────

import time as _time

# Inter-task pacing: sleep between tasks to let the Groq TPM window partially
# refill. With 7 tasks at ~3,500 tokens each = ~24,500 tokens/run. Spacing them
# out keeps peak usage below the 30,000 TPM limit.
# llama-3.1-8b-instant has 131K TPM — no need for long sleeps between tasks.
# 5s spacing keeps us safely under the 30 RPM (requests per minute) limit instead.
_INTER_TASK_SLEEP_SECS = 8

def log_task_completion(task_output):
    """Called after each task completes — logs structured output and pace-sleeps."""
    from fpa_tools.logger import fpa_logger
    agent_role = task_output.agent if hasattr(task_output, 'agent') else "Unknown"
    desc = task_output.description[:60] if hasattr(task_output, 'description') else ""
    fpa_logger.info(f"[Task Complete] {agent_role}: {desc}...")
    if hasattr(task_output, 'pydantic') and task_output.pydantic:
        fpa_logger.info(f"  → Structured output: {type(task_output.pydantic).__name__}")
    # Pace token usage: sleep to let the 1-minute Groq TPM window partially refill
    fpa_logger.info(f"[Task Pacing] Sleeping {_INTER_TASK_SLEEP_SECS}s to manage Groq TPM...")
    _time.sleep(_INTER_TASK_SLEEP_SECS)


# ── Crew Definition ───────────────────────────────────────────────────────────

@CrewBase
class FinancialFpa():
    """
    FinancialFpa crew — Production Financial Analysis v2.

    Crew configuration:
    - Process: Sequential (reliable task ordering for LLM-based analysis)
    - Memory: Disabled (Groq has no embeddings API — stateless per-session)
    - Knowledge: JSON benchmarks + FPA frameworks text
    - Guardrails: Performance analysis + CFO advisory validation
    - Structured Output: Pydantic models on all 5 analysis tasks
    """

    agents_config = 'config/agents.yaml'
    tasks_config  = 'config/tasks.yaml'

    # ═══════════════════════════════════════════════════════════════════════
    # AGENTS
    # ═══════════════════════════════════════════════════════════════════════

    @agent
    def fpa_analyst(self) -> Agent:
        """FP&A Analyst — historical performance analysis with charts."""
        agent_kwargs = dict(
            config=self.agents_config['fpa_analyst'],
            llm=_groq_llm,
            tools=[
                fpa_analysis_tool,
                generate_revenue_trend_chart,
                generate_profitability_analysis_chart,
                generate_waterfall_chart,
                generate_radar_chart,
                generate_metrics_heatmap,
            ],
            verbose=True,
            max_iter=3,
            respect_context_window=True,
        )
        if fpa_knowledge is not None:
            agent_kwargs['knowledge_sources'] = [fpa_knowledge]
        return Agent(**agent_kwargs)

    @agent
    def scenario_analyst(self) -> Agent:
        """Scenario Analyst — forward-looking percentile-based projections."""
        return Agent(
            config=self.agents_config['scenario_analyst'],
            llm=_groq_llm,
            tools=[generate_scenario_comparison_chart],
            verbose=True,
            max_iter=3,
            respect_context_window=True,
        )

    @agent
    def risk_analyst(self) -> Agent:
        """Risk Analyst — financial stability and risk assessment."""
        return Agent(
            config=self.agents_config['risk_analyst'],
            llm=_groq_llm,
            tools=[generate_risk_dashboard],
            verbose=True,
            max_iter=3,
            respect_context_window=True,
        )

    @agent
    def market_researcher(self) -> Agent:
        """Market Researcher — grounded benchmark comparisons via knowledge base."""
        agent_kwargs = dict(
            config=self.agents_config['market_researcher'],
            llm=_groq_llm,
            tools=[],  # Uses knowledge sources instead of live search
            verbose=True,
            max_iter=3,
            respect_context_window=True,
        )
        # Inject benchmark knowledge so it never hallucates
        if benchmarks_knowledge is not None:
            agent_kwargs['knowledge_sources'] = [benchmarks_knowledge]
        return Agent(**agent_kwargs)

    @agent
    def cfo_advisor(self) -> Agent:
        """CFO Advisor — executive synthesis and PDF report generation."""
        return Agent(
            config=self.agents_config['cfo_advisor'],
            llm=_groq_llm,
            tools=[generate_pdf_report],
            verbose=True,
            max_iter=3,
            respect_context_window=True,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # TASKS
    # ═══════════════════════════════════════════════════════════════════════

    @task
    def performance_analysis_task(self) -> Task:
        """Analyze historical financial performance — returns PerformanceAnalysisOutput."""
        return Task(
            config=self.tasks_config['performance_analysis_task'],
            output_pydantic=PerformanceAnalysisOutput,       # Phase 1
            guardrail=validate_performance_output,           # Phase 5
            guardrail_max_retries=1,                         # Was 2; save TPM tokens
            callback=log_task_completion,                    # Phase 6
        )

    @task
    def market_research_task(self) -> Task:
        """Research industry benchmarks — returns MarketResearchOutput."""
        return Task(
            config=self.tasks_config['market_research_task'],
            output_pydantic=MarketResearchOutput,            # Phase 1
            callback=log_task_completion,                    # Phase 6
        )

    @task
    def scenario_planning_task(self) -> Task:
        """Create forward-looking scenarios — returns ScenarioPlanningOutput."""
        return Task(
            config=self.tasks_config['scenario_planning_task'],
            output_pydantic=ScenarioPlanningOutput,          # Phase 1
            callback=log_task_completion,                    # Phase 6
        )

    @task
    def risk_assessment_task(self) -> Task:
        """Assess financial risks — returns RiskAssessmentOutput."""
        return Task(
            config=self.tasks_config['risk_assessment_task'],
            output_pydantic=RiskAssessmentOutput,            # Phase 1
            callback=log_task_completion,                    # Phase 6
        )

    @task
    def chart_generation_task(self) -> Task:
        """Generate all visualizations."""
        return Task(
            config=self.tasks_config['chart_generation_task'],
            callback=log_task_completion,                    # Phase 6
        )

    @task
    def cfo_advisory_task(self) -> Task:
        """Synthesize executive advisory — returns CFOAdvisoryOutput."""
        return Task(
            config=self.tasks_config['cfo_advisory_task'],
            output_pydantic=CFOAdvisoryOutput,               # Phase 1
            guardrail=validate_cfo_output,                   # Phase 5
            guardrail_max_retries=1,                         # Was 2; save TPM tokens
            callback=log_task_completion,                    # Phase 6
        )



    # ═══════════════════════════════════════════════════════════════════════
    # CREW
    # ═══════════════════════════════════════════════════════════════════════

    @crew
    def crew(self) -> Crew:
        """
        Creates the FinancialFpa production crew.

        Process: Sequential — ensures reliable task ordering.
        Memory: Enabled — agents remember cross-session insights.
        Knowledge: Industry benchmarks + FPA frameworks.

        Task Order:
        1. performance_analysis_task  (FPA Analyst)
        2. market_research_task       (Market Researcher)
        3. scenario_planning_task     (Scenario Analyst)
        4. risk_assessment_task       (Risk Analyst)
        5. chart_generation_task      (FPA Analyst)
        6. cfo_advisory_task          (CFO Advisor)
        """
        crew_kwargs = dict(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )

        # Memory disabled: Groq has no embeddings API, and local embedder libraries
        # (sentence-transformers/fastembed) have version conflicts in this environment.
        # The full LLM pipeline runs fine without cross-session memory.
        crew_kwargs['memory'] = False

        return Crew(**crew_kwargs)