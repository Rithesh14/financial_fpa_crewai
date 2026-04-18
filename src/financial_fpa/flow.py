"""
Financial Analysis Flow — Production Orchestration (Phase 4).

Uses CrewAI Flows with:
  - @start / @listen / @router decorators for event-driven pipeline
  - @persist for SQLite-backed state persistence (crash recovery)
  - FPAFlowState (Pydantic) for typed, validated state throughout

Pipeline:
    validate_input
        ↓ valid ──────────────────────────────────────────────────────┐
        ↓ invalid → handle_invalid_input (stop)                       │
    run_analysis_crew                                                  │
        ↓                                                             │
    check_quality                                                      │
        ↓ quality_pass ────────────────────────────────────── generate_reports
        ↓ quality_retry → retry_with_feedback → run_analysis_crew     │
        ↓ (after 2 retries, accept)                                   │
    deliver_results ←─────────────────────────────────────────────────┘
"""

import re
import time
import pandas as pd
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

try:
    from crewai.flow.flow import Flow, listen, start, router
    from crewai.flow.persistence import persist
    FLOW_PERSIST_AVAILABLE = True
except ImportError:
    try:
        from crewai.flow.flow import Flow, listen, start, router
        persist = lambda cls: cls   # no-op decorator if persist not available
        FLOW_PERSIST_AVAILABLE = False
    except ImportError:
        raise ImportError(
            "CrewAI Flows not available. Please upgrade: pip install 'crewai>=0.86.0'"
        )

from financial_fpa.models import (
    PerformanceAnalysisOutput,
    ScenarioPlanningOutput,
    RiskAssessmentOutput,
    MarketResearchOutput,
    CFOAdvisoryOutput,
)
from fpa_tools.logger import fpa_logger, log_flow_state


# ── Flow State ────────────────────────────────────────────────────────────────

class FPAFlowState(BaseModel):
    """
    Typed state that flows through the entire FP&A pipeline.
    All fields have sensible defaults so the flow can always be instantiated.
    """
    # ── Inputs ──
    csv_path: str = ""
    company_name: str = ""
    sector: str = ""

    # ── Validation ──
    is_valid: bool = False
    validation_errors: List[str] = []
    available_companies: List[str] = []

    # ── Crew results (populated after crew run) ──
    performance_result: Optional[Dict[str, Any]] = None
    scenario_result:    Optional[Dict[str, Any]] = None
    risk_result:        Optional[Dict[str, Any]] = None
    market_result:      Optional[Dict[str, Any]] = None
    cfo_result:         Optional[Dict[str, Any]] = None

    # ── Quality gate ──
    quality_passed: bool = False
    quality_issues: List[str] = []
    retry_count: int = 0
    # Set to True when crew failed due to rate limits (skip quality retry)
    rate_limit_exhausted: bool = False

    # ── Outputs ──
    pdf_path:         Optional[str] = None
    excel_path:       Optional[str] = None
    charts_generated: List[str] = []

    # ── Status ──
    current_step:  str = "initialized"
    error_message: Optional[str] = None


# ── Flow Definition ───────────────────────────────────────────────────────────

@persist
class FinancialAnalysisFlow(Flow[FPAFlowState]):
    """
    Production orchestration flow for Financial FP&A.

    Wraps the CrewAI crew in a reliable pipeline with:
    - Input validation before any expensive LLM calls
    - Quality gates on crew outputs
    - Automatic retry with feedback (up to 2 retries)
    - PDF report generation from typed Pydantic state
    - State persistence to SQLite (survives crashes)
    """

    # ── Step 1: Validate Input ────────────────────────────────────────────────

    @start()
    def validate_input(self):
        """
        Validate the CSV file and company selection before starting analysis.
        Returns 'valid' or 'invalid' for the router.
        """
        log_flow_state("validate_input", f"csv={self.state.csv_path}, company={self.state.company_name}")
        self.state.current_step = "validating"

        # Try to load the CSV
        try:
            df = pd.read_csv(self.state.csv_path)
        except FileNotFoundError:
            self.state.is_valid = False
            self.state.validation_errors = [f"File not found: {self.state.csv_path}"]
            self.state.error_message = f"File not found: {self.state.csv_path}"
            return "invalid"
        except Exception as e:
            self.state.is_valid = False
            self.state.validation_errors = [f"Cannot read CSV: {str(e)}"]
            self.state.error_message = str(e)
            return "invalid"

        # Check required columns
        required = ['Period', 'Revenue', 'EBITDA', 'Operating_Cash_Flow',
                    'Debt/Equity Ratio', 'Current Ratio']
        actual = [c.strip() for c in df.columns]
        missing = [c for c in required if c not in actual]
        if missing:
            self.state.validation_errors.append(f"Missing columns: {missing}")

        # Validate company selection
        company_col = next((c for c in df.columns if c.strip() == 'Company'), None)
        if company_col:
            df[company_col] = df[company_col].str.strip()
            self.state.available_companies = sorted(df[company_col].unique().tolist())
            if self.state.company_name and self.state.company_name not in self.state.available_companies:
                self.state.validation_errors.append(
                    f"Company '{self.state.company_name}' not found. "
                    f"Available: {self.state.available_companies}"
                )
            elif not self.state.company_name and self.state.available_companies:
                # Auto-select first company if none specified
                self.state.company_name = self.state.available_companies[0]
                fpa_logger.info(f"Auto-selected company: {self.state.company_name}")

        self.state.is_valid = len(self.state.validation_errors) == 0
        log_flow_state(
            "validate_input_result",
            f"valid={self.state.is_valid}, errors={self.state.validation_errors}"
        )
        return "valid" if self.state.is_valid else "invalid"

    # ── Router: validation ────────────────────────────────────────────────────

    @router(validate_input)
    def route_validation(self):
        """Route to analysis or error handling based on validation result."""
        return "valid" if self.state.is_valid else "invalid"

    # ── Step 1b: Handle Invalid ───────────────────────────────────────────────

    @listen("invalid")
    def handle_invalid_input(self):
        """Gracefully handle invalid input — stop the flow with an error state."""
        self.state.current_step = "failed_validation"
        self.state.error_message = (
            f"Input validation failed: {'; '.join(self.state.validation_errors)}"
        )
        fpa_logger.error(f"[Flow] Validation failed: {self.state.error_message}")
        return self.state

    # ── Step 2: Run Analysis Crew ─────────────────────────────────────────────

    # ── Rate-limit helpers ────────────────────────────────────────────────────

    @staticmethod
    def _parse_retry_after(error_msg: str) -> float:
        """
        Extract the recommended wait time from a Groq RateLimitError message.
        Falls back to a sensible default if not parseable.

        Example message:
          "...Please try again in 13.86s..."
        """
        match = re.search(r'try again in\s+([\d.]+)s', str(error_msg), re.IGNORECASE)
        if match:
            return float(match.group(1)) + 2.0   # add 2s safety buffer
        return 20.0                               # safe default

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        """Return True if the exception is a Groq 429 / RateLimitError."""
        err_str = str(exc).lower()
        return (
            "ratelimit" in err_str
            or "rate_limit_exceeded" in err_str
            or "429" in err_str
            or "try again in" in err_str
        )

    @listen("valid")
    def run_analysis_crew(self):
        """
        Kick off the CrewAI analysis crew with validated inputs.

        Includes automatic retry with backoff for Groq TPM rate-limit errors
        (HTTP 429). The wait time is parsed from the error message so we
        only sleep as long as Groq tells us to, rather than a fixed delay.

        Token-pacing strategy:
        - A 15s pre-flight sleep lets the TPM window partially refill when retrying
        - MAX_RATE_LIMIT_RETRIES is kept at 3 to avoid burning the entire TPM budget
          on retries and leaving no capacity for downstream quality retries
        """
        from financial_fpa.crew import FinancialFpa

        self.state.current_step = "analyzing"
        self.state.rate_limit_exhausted = False
        log_flow_state(
            "run_analysis_crew",
            f"company={self.state.company_name}, retry={self.state.retry_count}"
        )

        # If this is a quality-gate retry, pause to let the TPM window refill
        if self.state.retry_count > 0:
            preflight_wait = 60.0
            fpa_logger.info(
                f"[Flow] Quality retry #{self.state.retry_count} — waiting {preflight_wait}s "
                "for Groq TPM window to refill before re-running crew…"
            )
            time.sleep(preflight_wait)

        MAX_RATE_LIMIT_RETRIES = 3  # Reduced: save TPM budget for later tasks

        for attempt in range(1, MAX_RATE_LIMIT_RETRIES + 1):
            try:
                crew_instance = FinancialFpa()
                # !! IMPORTANT: store the crew object in a variable and reuse it.
                # Calling crew_instance.crew() twice creates TWO separate Crew objects.
                # The second call (used below for task extraction) would return a brand-new
                # empty crew, so all task outputs would be None. One variable = one crew.
                active_crew = crew_instance.crew()
                result = active_crew.kickoff(inputs={
                    'csv_path':         self.state.csv_path,
                    'company_name':     self.state.company_name,
                    'benchmark_sector': self.state.sector or 'IT',
                })

                # ── Extract structured Pydantic results from each completed task ──
                # CrewAI stores task outputs on the crew object after kickoff.
                # We iterate the tasks list and pull .output.pydantic if present.
                for task_obj in active_crew.tasks:
                    raw_output = getattr(task_obj, 'output', None)
                    if raw_output is None:
                        continue
                    pydantic_out = getattr(raw_output, 'pydantic', None)
                    if pydantic_out is None:
                        # Fallback: try to coerce raw JSON output to Pydantic model
                        json_dict = getattr(raw_output, 'json_dict', None)
                        if json_dict and isinstance(json_dict, dict):
                            try:
                                if 'revenue' in json_dict and 'top_3_positives' in json_dict:
                                    pydantic_out = PerformanceAnalysisOutput(**json_dict)
                                elif 'overall_risk_level' in json_dict:
                                    pydantic_out = RiskAssessmentOutput(**json_dict)
                                elif 'executive_summary' in json_dict and 'recommendations' in json_dict:
                                    pydantic_out = CFOAdvisoryOutput(**json_dict)
                                elif 'scenarios' in json_dict and 'sensitivity_drivers' in json_dict:
                                    pydantic_out = ScenarioPlanningOutput(**json_dict)
                                elif 'benchmarks' in json_dict and 'market_trends' in json_dict:
                                    pydantic_out = MarketResearchOutput(**json_dict)
                            except Exception:
                                pass  # Coercion failed — skip this task output

                    if pydantic_out is None:
                        continue

                    if isinstance(pydantic_out, PerformanceAnalysisOutput):
                        self.state.performance_result = pydantic_out.model_dump()
                    elif isinstance(pydantic_out, ScenarioPlanningOutput):
                        self.state.scenario_result = pydantic_out.model_dump()
                    elif isinstance(pydantic_out, RiskAssessmentOutput):
                        self.state.risk_result = pydantic_out.model_dump()
                    elif isinstance(pydantic_out, MarketResearchOutput):
                        self.state.market_result = pydantic_out.model_dump()
                    elif isinstance(pydantic_out, CFOAdvisoryOutput):
                        self.state.cfo_result = pydantic_out.model_dump()

                fpa_logger.info(
                    f"[Flow] Crew analysis complete. "
                    f"Structured outputs captured: "
                    f"performance={'✓' if self.state.performance_result else '✗'}, "
                    f"risk={'✓' if self.state.risk_result else '✗'}, "
                    f"cfo={'✓' if self.state.cfo_result else '✗'}"
                )
                return result

            except Exception as e:
                is_rl = self._is_rate_limit_error(e)
                if is_rl and attempt < MAX_RATE_LIMIT_RETRIES:
                    wait_secs = self._parse_retry_after(str(e))
                    # Use exponential backoff on top of the Groq-suggested wait
                    backoff = wait_secs * (1.5 ** (attempt - 1))
                    fpa_logger.warning(
                        f"[Flow] Groq rate limit hit (attempt {attempt}/{MAX_RATE_LIMIT_RETRIES}). "
                        f"Waiting {backoff:.1f}s before retry…"
                    )
                    self.state.current_step = f"rate_limit_wait_{attempt}"
                    time.sleep(backoff)
                    # continue → next loop iteration
                elif is_rl:
                    # Rate limit exhausted all retries — mark flag so quality gate
                    # skips another crew retry and goes straight to report generation
                    self.state.rate_limit_exhausted = True
                    self.state.error_message = (
                        "Groq TPM limit exhausted after all retries. "
                        "Partial results will be used for report generation."
                    )
                    self.state.current_step = "rate_limit_exhausted"
                    fpa_logger.error(
                        f"[Flow] Rate limit exhausted after {MAX_RATE_LIMIT_RETRIES} attempts. "
                        "Proceeding with any partial results captured so far."
                    )
                    return None
                else:
                    # Non-rate-limit error
                    self.state.error_message = f"Crew execution failed: {str(e)}"
                    self.state.current_step = "crew_error"
                    fpa_logger.error(f"[Flow] Crew error: {str(e)}", exc_info=True)
                    return None

    # ── Step 3: Quality Gate ───────────────────────────────────────────────────

    @listen(run_analysis_crew)
    def check_quality(self):
        """
        Quality gate — verify core outputs were produced before generating reports.

        Relaxed criteria (v2):
        - PASS if performance_result is present (the primary deliverable)
        - PASS always if rate_limit_exhausted=True (retrying would burn more tokens)
        - WARN (not FAIL) on missing secondary outputs (cfo, risk)
        - Critical risk flag is informational only — does not block delivery
        """
        self.state.current_step = "quality_check"
        issues = []

        # If we hit a rate limit wall, skip retry — proceed with whatever we have
        if self.state.rate_limit_exhausted:
            fpa_logger.warning(
                "[Flow] Rate limit exhausted flag set — skipping quality retry, "
                "proceeding to report generation with partial results."
            )
            self.state.quality_passed = True
            self.state.quality_issues = ["Rate limit exhausted — partial results only"]
            log_flow_state("check_quality", "passed=True (rate_limit bypass)")
            return

        # Primary gate: performance analysis is the core deliverable
        if not self.state.performance_result:
            issues.append("Performance analysis returned no structured results")

        # Secondary warnings (logged but do not block delivery after 1 retry)
        if not self.state.cfo_result:
            fpa_logger.warning("[Flow] CFO advisory output missing — will use text fallback")
        if not self.state.risk_result:
            fpa_logger.warning("[Flow] Risk assessment output missing — will use text fallback")

        # Informational: log critical risk but do not add to blocking issues
        if self.state.risk_result:
            overall_risk = self.state.risk_result.get('overall_risk_level', '')
            if overall_risk == 'critical':
                fpa_logger.warning(
                    "[Flow] CRITICAL risk level detected — flagging in report"
                )

        self.state.quality_issues = issues
        self.state.quality_passed = len(issues) == 0
        log_flow_state("check_quality", f"passed={self.state.quality_passed}, issues={issues}")

    @router(check_quality)
    def route_quality(self):
        """Route to report generation, retry, or forced accept."""
        if self.state.quality_passed:
            return "quality_pass"
        elif self.state.rate_limit_exhausted:
            # Never retry if we already burned all TPM retries
            fpa_logger.warning("[Flow] Rate limit exhausted — forcing quality_pass")
            return "quality_pass"
        elif self.state.retry_count < 1:
            # Allow only 1 quality retry (not 2) to preserve TPM budget
            return "quality_retry"
        else:
            # Accept after 1 retry to prevent infinite loops
            fpa_logger.warning("[Flow] Quality issues persist after retry — accepting")
            return "quality_pass"

    # ── Step 3b: Retry ────────────────────────────────────────────────────────

    @listen("quality_retry")
    def retry_with_feedback(self):
        """
        Retry the crew with quality feedback injected.
        Emits "valid" to directly re-trigger run_analysis_crew.
        """
        self.state.retry_count += 1
        self.state.current_step = f"retry_{self.state.retry_count}"
        fpa_logger.warning(
            f"[Flow] Quality retry {self.state.retry_count}/1: {self.state.quality_issues}"
        )
        # Reset is_valid so the "valid" emission re-triggers run_analysis_crew
        self.state.is_valid = True
        return "valid"

    # ── Step 4: Generate Reports ──────────────────────────────────────────────

    @listen("quality_pass")
    def generate_reports(self):
        """
        Generate PDF report using the typed Pydantic state.
        Uses extracting text from structured outputs — no text parsing needed.
        """
        import os
        self.state.current_step = "generating_reports"
        log_flow_state("generate_reports", f"company={self.state.company_name}")

        os.makedirs("reports", exist_ok=True)

        # Build text summaries from structured state
        performance_text = ""
        if self.state.performance_result:
            pr = self.state.performance_result
            performance_text = (
                # BUG FIX: values are stored as plain percentages (e.g. 18.61 means 18.61%).
                # Using :.1% would multiply by 100 again → "1861.0%". Use :.2f% instead.
                f"Revenue CAGR: {pr.get('revenue', {}).get('cagr', 0):.2f}% | "
                f"EBITDA Margin: {pr.get('profitability', {}).get('current_ebitda_margin', 0):.2f}% | "
                f"Positives: {', '.join(pr.get('top_3_positives', [])[:3])} | "
                f"Concerns: {', '.join(pr.get('top_3_concerns', [])[:3])}"
            )

        market_text = ""
        if self.state.market_result:
            mr = self.state.market_result
            market_text = (
                f"Sector: {mr.get('sector', '')} | "
                f"Competitive position: {mr.get('competitive_position_summary', '')} | "
                f"Trends: {', '.join(mr.get('market_trends', [])[:3])}"
            )

        scenario_text = ""
        if self.state.scenario_result:
            sr = self.state.scenario_result
            scenarios = sr.get('scenarios', [])
            scenario_lines = []
            for s in scenarios:
                scenario_lines.append(
                    f"{s.get('scenario_name')}: Y1=${s.get('year_1_revenue', 0):,.0f}M "
                    # BUG FIX: growth_rate is a plain percentage (e.g. 8.79).
                    # :.1% would display it as 879.0%. Use :.2f% instead.
                    f"({s.get('growth_rate', 0):.2f}% growth)"
                )
            scenario_text = " | ".join(scenario_lines)

        risk_text = ""
        if self.state.risk_result:
            rr = self.state.risk_result
            risk_text = (
                f"Overall Risk: {rr.get('overall_risk_level', 'unknown').upper()} | "
                f"Flags: {', '.join(rr.get('risk_flags', [])[:3])} | "
                f"Mitigations: {', '.join(rr.get('mitigation_recommendations', [])[:3])}"
            )

        cfo_text = ""
        if self.state.cfo_result:
            cr = self.state.cfo_result
            cfo_text = cr.get('executive_summary', '')

        # Generate PDF
        # NOTE: Import build_pdf_report (plain Python function), NOT generate_pdf_report.
        # generate_pdf_report is decorated with @tool which turns it into a CrewAI Tool
        # *object* — calling it as a function raises "Tool object is not callable".
        # build_pdf_report is the identical logic without the decorator, safe to call directly.
        try:
            from fpa_tools.pdf_generator import build_pdf_report as _gen_pdf
            pdf_output_path = f"reports/{self.state.company_name}_analysis.pdf"
            _gen_pdf(
                performance_insights=performance_text,
                market_insights=market_text,
                scenario_insights=scenario_text,
                risk_insights=risk_text,
                cfo_summary=cfo_text,
                output_path=pdf_output_path,
            )
            self.state.pdf_path = pdf_output_path
            fpa_logger.info(f"[Flow] PDF generated: {pdf_output_path}")
        except Exception as e:
            fpa_logger.error(f"[Flow] PDF generation failed: {str(e)}")
            self.state.error_message = f"PDF generation failed: {str(e)}"

        # Track generated charts
        import os
        chart_files = [
            'charts/revenue_trend.png',
            'charts/profitability_analysis.png',
            'charts/scenario_comparison.png',
            'charts/risk_dashboard.png',
            'charts/waterfall_revenue.png',
            'charts/radar_metrics.png',
        ]
        self.state.charts_generated = [f for f in chart_files if os.path.exists(f)]

        return self.state

    # ── Step 5: Deliver Results ────────────────────────────────────────────────

    @listen(generate_reports)
    def deliver_results(self):
        """Final step — mark pipeline complete and return final state."""
        self.state.current_step = "completed"
        log_flow_state("deliver_results", f"pdf={self.state.pdf_path}, charts={len(self.state.charts_generated)}")
        fpa_logger.info(
            f"[Flow] ✅ Analysis complete for {self.state.company_name}. "
            f"PDF: {self.state.pdf_path}"
        )
        return self.state