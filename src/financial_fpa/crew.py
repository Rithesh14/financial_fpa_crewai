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


# ── LLM — GEMINI Model Setup ───
# gemini-2.0-flash: 1,500 req/day free (vs. 20/day for gemini-2.5-flash-lite)
# This is the most cost-effective free-tier model for multi-agent pipelines.
_gemini_llm = LLM(
    model="gemini/gemini-2.0-flash",
    api_key=os.environ.get("GEMINI_API_KEY", ""),
    temperature=0.1,
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

# Inter-task pacing: Gemini's quota is DAILY (not per-minute like Groq TPM).
# A short 3s courtesy sleep is enough — long sleeps waste time without helping
# the daily quota at all. The pipeline now runs ~3 minutes faster as a result.
_INTER_TASK_SLEEP_SECS = 3

def log_task_completion(task_output):
    """Called after each task completes — logs structured output and pace-sleeps."""
    from fpa_tools.logger import fpa_logger
    agent_role = task_output.agent if hasattr(task_output, 'agent') else "Unknown"
    desc = task_output.description[:60] if hasattr(task_output, 'description') else ""
    fpa_logger.info(f"[Task Complete] {agent_role}: {desc}...")
    if hasattr(task_output, 'pydantic') and task_output.pydantic:
        fpa_logger.info(f"  → Structured output: {type(task_output.pydantic).__name__}")
    # Brief courtesy pause — Gemini daily quota is not affected by sleep duration
    fpa_logger.info(f"[Task Pacing] Brief {_INTER_TASK_SLEEP_SECS}s pause (Gemini daily quota model)...")
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
            llm=_gemini_llm,
            tools=[
                fpa_analysis_tool,
                generate_revenue_trend_chart,
                generate_profitability_analysis_chart,
                generate_waterfall_chart,
                generate_radar_chart,
                generate_metrics_heatmap,
            ],
            verbose=True,
            max_iter=8,             # Was 3 — gives breathing room for tool calls
            max_retry_limit=3,      # Keep low: each retry uses ~2500 tokens of 30K TPM
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
            llm=_gemini_llm,
            tools=[generate_scenario_comparison_chart],
            verbose=True,
            max_iter=8,             # Was 3
            max_retry_limit=3,      # Keep low: each retry uses ~2500 tokens of 30K TPM
            respect_context_window=True,
        )

    @agent
    def risk_analyst(self) -> Agent:
        """Risk Analyst — financial stability and risk assessment."""
        return Agent(
            config=self.agents_config['risk_analyst'],
            llm=_gemini_llm,
            tools=[generate_risk_dashboard],
            verbose=True,
            max_iter=8,             # Was 3
            max_retry_limit=3,      # Keep low: each retry uses ~2500 tokens of 30K TPM
            respect_context_window=True,
        )

    @agent
    def market_researcher(self) -> Agent:
        """Market Researcher — grounded benchmark comparisons via knowledge base."""
        agent_kwargs = dict(
            config=self.agents_config['market_researcher'],
            llm=_gemini_llm,
            tools=[],  # Uses knowledge sources instead of live search
            verbose=True,
            max_iter=8,             # Was 3
            max_retry_limit=3,      # Keep low: each retry uses ~2500 tokens of 30K TPM
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
            llm=_gemini_llm,
            tools=[generate_pdf_report],
            verbose=True,
            max_iter=8,             # Was 3
            max_retry_limit=3,      # Keep low: each retry uses ~2500 tokens of 30K TPM
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
            guardrail_max_retries=2,                         # Increased from 1
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
            guardrail_max_retries=2,                         # Increased from 1
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