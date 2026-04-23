"""
Financial Analysis Flow — Production v4 (2-Stage Pipeline).

ARCHITECTURE CHANGE from v3:
  BEFORE: validate → direct_tools → run_analysis_crew (5-agent ReAct loop)
                   → check_quality → generate_reports → deliver_results
  AFTER:  validate → run_direct_tools → generate_llm_report → deliver_results

Key benefits:
  - ZERO empty-LLM-response errors (no ReAct tool-call loop)
  - Max 1 LLM call per run (for the final report only)
  - Deterministic fallback: if LLM fails, report is built from raw numbers
  - ~10x fewer API calls vs v3
  - Token-efficient: only summary metrics sent to LLM, not full logs

Pipeline:
    validate_input
        ↓ valid   → run_direct_tools → generate_llm_report → deliver_results
        ↓ invalid → handle_invalid_input (stop)
"""

import re
import time
import os
import json
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
        persist = lambda cls: cls
        FLOW_PERSIST_AVAILABLE = False
    except ImportError:
        raise ImportError(
            "CrewAI Flows not available. Please upgrade: pip install 'crewai>=0.86.0'"
        )

from fpa_tools.logger import fpa_logger, log_flow_state


# ── Flow State ────────────────────────────────────────────────────────────────

class FPAFlowState(BaseModel):
    """Typed state flowing through the 2-stage FP&A pipeline."""
    # ── Inputs ──
    csv_path: str = ""
    company_name: str = ""
    sector: str = ""

    # ── Validation ──
    is_valid: bool = False
    validation_errors: List[str] = []
    available_companies: List[str] = []

    # ── Stage 1: Direct tool results (no LLM) ──
    direct_analysis_result: Optional[str] = None
    direct_charts: List[str] = []
    direct_errors: List[str] = []

    # ── Stage 2: LLM report (single call) ──
    llm_report: Optional[str] = None
    llm_report_source: str = "none"   # "llm" | "fallback" | "none"

    # ── Structured metrics extracted for Streamlit display ──
    performance_result: Optional[Dict[str, Any]] = None

    # ── API tracking ──
    api_calls_made: int = 0
    rate_limit_hits: int = 0
    skipped_steps: List[str] = []

    # ── Outputs ──
    pdf_path: Optional[str] = None
    charts_generated: List[str] = []

    # ── Status ──
    current_step: str = "initialized"
    error_message: Optional[str] = None


# ── Flow Definition ───────────────────────────────────────────────────────────

@persist
class FinancialAnalysisFlow(Flow[FPAFlowState]):
    """
    Production orchestration v4 — 2-stage pipeline.

    Stage 1 (no LLM): run_direct_tools
      - FPA analysis (pure Python computation)
      - All 6 charts (pure Python + matplotlib)
      - Results cached on disk

    Stage 2 (1 LLM call): generate_llm_report
      - Builds a concise prompt from summary metrics
      - Calls LLM ONCE for structured report text
      - On failure/empty response → deterministic fallback from raw numbers
    """

    # ── Step 1: Validate Input ────────────────────────────────────────────

    @start()
    def validate_input(self):
        """Validate CSV file and company selection."""
        log_flow_state("validate_input",
                       f"csv={self.state.csv_path}, company={self.state.company_name}")
        self.state.current_step = "validating"

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

        required = ['Period', 'Revenue', 'EBITDA', 'Operating_Cash_Flow',
                    'Debt/Equity Ratio', 'Current Ratio']
        actual = [c.strip() for c in df.columns]
        missing = [c for c in required if c not in actual]
        if missing:
            self.state.validation_errors.append(f"Missing columns: {missing}")

        company_col = next((c for c in df.columns if c.strip() == 'Company'), None)
        if company_col:
            df[company_col] = df[company_col].str.strip()
            self.state.available_companies = sorted(df[company_col].unique().tolist())
            if (self.state.company_name and
                    self.state.company_name not in self.state.available_companies):
                self.state.validation_errors.append(
                    f"Company '{self.state.company_name}' not found. "
                    f"Available: {self.state.available_companies}"
                )
            elif not self.state.company_name and self.state.available_companies:
                self.state.company_name = self.state.available_companies[0]
                fpa_logger.info(f"Auto-selected company: {self.state.company_name}")

        self.state.is_valid = len(self.state.validation_errors) == 0
        log_flow_state("validate_input_result",
                       f"valid={self.state.is_valid}, errors={self.state.validation_errors}")
        return "valid" if self.state.is_valid else "invalid"

    @router(validate_input)
    def route_validation(self):
        return "valid" if self.state.is_valid else "invalid"

    @listen("invalid")
    def handle_invalid_input(self):
        self.state.current_step = "failed_validation"
        self.state.error_message = (
            f"Input validation failed: {'; '.join(self.state.validation_errors)}"
        )
        fpa_logger.error(f"[Flow] Validation failed: {self.state.error_message}")
        return self.state

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        err_str = str(exc).lower()
        return (
            "ratelimit" in err_str
            or "rate_limit_exceeded" in err_str
            or "429" in err_str
            or "try again in" in err_str
            or "resource_exhausted" in err_str
            or "quota exceeded" in err_str
            or "please retry in" in err_str
        )

    @staticmethod
    def _parse_retry_after(error_msg: str) -> float:
        match = re.search(
            r'(?:try again|retry)\s+in\s+([\d.]+)s', str(error_msg), re.IGNORECASE
        )
        if match:
            return float(match.group(1)) + 2.0
        return 30.0

    # ── Stage 1: Run Direct Tools (NO LLM) ───────────────────────────────

    @listen("valid")
    def run_direct_tools(self):
        """
        Stage 1: Run FPA analysis + all charts as direct Python calls.

        Zero LLM usage. These are pure computation — CSV → numbers/PNGs.
        Results are cached on disk so re-runs for the same company skip this.
        """
        self.state.current_step = "running_direct_tools"
        log_flow_state("run_direct_tools", f"company={self.state.company_name}")

        # Skip if already have results (cached state from prior run)
        if self.state.direct_analysis_result:
            fpa_logger.info("[Flow] Direct tool results already in state — skipping")
            return

        try:
            from financial_fpa.crew import run_tools_directly
            results = run_tools_directly(
                csv_path=self.state.csv_path,
                company=self.state.company_name,
                sector=self.state.sector or "IT",
            )
            self.state.direct_analysis_result = results.get("analysis_result")
            self.state.direct_charts = results.get("charts", [])
            self.state.direct_errors = results.get("errors", [])

            fpa_logger.info(
                f"[Flow] Stage 1 complete: "
                f"analysis={'✓' if self.state.direct_analysis_result else '✗'}, "
                f"charts={len(self.state.direct_charts)}, "
                f"errors={len(self.state.direct_errors)}"
            )
        except Exception as e:
            fpa_logger.error(f"[Flow] Stage 1 (direct tools) failed: {e}")
            self.state.direct_errors.append(str(e))

    # ── Stage 2: Single LLM Call for Report Generation ───────────────────

    @listen(run_direct_tools)
    def generate_llm_report(self):
        """
        Stage 2: Call LLM ONCE to generate a structured FP&A report.

        Input:  compact summary metrics from Stage 1 (not raw logs)
        Output: structured text report stored in self.state.llm_report

        If the LLM returns an empty/None response or fails with a rate-limit
        error, a deterministic fallback report is built from the raw numbers —
        so the pipeline NEVER returns an empty output.
        """
        self.state.current_step = "generating_report"
        log_flow_state("generate_llm_report", f"company={self.state.company_name}")

        company = self.state.company_name
        analysis_text = self.state.direct_analysis_result or ""
        chart_paths = self.state.direct_charts or []

        # ── Build chart insights summary (not raw paths) ──
        chart_insights = self._summarise_charts(chart_paths)

        # ── Build concise prompt ──
        prompt = self._build_report_prompt(company, analysis_text, chart_insights)

        # ── Attempt single LLM call ──
        llm_response = self._call_llm_once(prompt)

        if llm_response:
            self.state.llm_report = llm_response
            self.state.llm_report_source = "llm"
            self.state.api_calls_made += 1
            fpa_logger.info(
                f"[Flow] Stage 2 LLM report generated "
                f"({len(llm_response)} chars)"
            )
        else:
            # Fallback: deterministic report from raw analysis data
            fpa_logger.warning(
                "[Flow] LLM returned empty/None — using deterministic fallback"
            )
            self.state.llm_report = self._build_fallback_report(
                company, analysis_text, chart_paths
            )
            self.state.llm_report_source = "fallback"
            self.state.skipped_steps.append("llm_report_generation")

        # ── Extract structured metrics for Streamlit display ──
        self._extract_performance_metrics(analysis_text, company)

        # ── Generate PDF from the report ──
        self._generate_pdf(company)

        # ── Track charts ──
        chart_files = [
            'charts/revenue_trend.png',
            'charts/profitability_analysis.png',
            'charts/scenario_comparison.png',
            'charts/risk_dashboard.png',
            'charts/waterfall_revenue.png',
            'charts/radar_metrics.png',
        ]
        self.state.charts_generated = [f for f in chart_files if os.path.exists(f)]

        fpa_logger.info(
            f"[Flow] Report generation complete: "
            f"source={self.state.llm_report_source}, "
            f"charts={len(self.state.charts_generated)}, "
            f"pdf={'✓' if self.state.pdf_path else '✗'}"
        )

    # ── Step 3: Deliver Results ───────────────────────────────────────────

    @listen(generate_llm_report)
    def deliver_results(self):
        """Final step — mark pipeline complete and return final state."""
        self.state.current_step = "completed"
        log_flow_state("deliver_results",
                       f"pdf={self.state.pdf_path}, charts={len(self.state.charts_generated)}")
        fpa_logger.info(
            f"[Flow] ✅ Analysis complete for {self.state.company_name}. "
            f"Report source: {self.state.llm_report_source}. "
            f"PDF: {self.state.pdf_path}"
        )
        return self.state

    # ── Private helpers ───────────────────────────────────────────────────

    def _summarise_charts(self, chart_paths: List[str]) -> str:
        """
        Convert chart file paths into human-readable insight strings.
        Keeps the LLM prompt small — no raw file paths injected.
        """
        if not chart_paths:
            return "No charts generated."
        labels = {
            "revenue_trend":       "Revenue trend over time",
            "profitability":       "EBITDA margin and profitability trend",
            "scenario_comparison": "Best/Base/Worst case revenue scenarios",
            "risk_dashboard":      "Risk metrics and financial stability dashboard",
            "waterfall":           "Revenue waterfall (year-over-year bridges)",
            "radar":               "Multi-metric financial radar chart",
        }
        found = []
        for path in chart_paths:
            base = os.path.basename(str(path)).replace(".png", "").lower()
            for key, label in labels.items():
                if key in base:
                    found.append(f"- {label} (generated: {os.path.basename(str(path))})")
                    break
            else:
                if path:
                    found.append(f"- Chart generated: {os.path.basename(str(path))}")
        return "\n".join(found) if found else "Charts generated (see charts/ directory)."

    def _build_report_prompt(
        self, company: str, analysis_text: str, chart_insights: str
    ) -> str:
        """
        Build the prompt for the single LLM call.
        Covers 10 clearly-numbered sections so section-parsing is reliable.
        Trimmed to ~900 chars of analysis data to stay within token budget.
        """
        trimmed_analysis = analysis_text[:900] if len(analysis_text) > 900 else analysis_text

        return (
            f"Generate a structured FP&A report for {company} using the financial data below.\n"
            f"Write in full sentences. Each section must have at least 2-3 sentences of analysis.\n\n"
            f"Financial Analysis Data:\n{trimmed_analysis}\n\n"
            f"Charts available: {chart_insights}\n\n"
            f"Output EXACTLY these 10 numbered sections with their headings as shown:\n"
            f"1. Revenue CAGR\n"
            f"   Analyse the CAGR value, what it means for the company, and the revenue trend direction.\n\n"
            f"2. YoY Growth (last 5 years)\n"
            f"   Summarise year-over-year growth pattern, acceleration or deceleration.\n\n"
            f"3. EBITDA Margin\n"
            f"   State the current margin, compare to typical industry levels, describe the trend.\n\n"
            f"4. Operating Cash Flow\n"
            f"   Describe the latest OCF figure and what it implies about cash generation quality.\n\n"
            f"5. Cash Conversion Ratio\n"
            f"   Explain the ratio and its implication for earnings quality.\n\n"
            f"6. Top 3 Positives\n"
            f"   List exactly 3 strengths as bullet points (start each with '- ').\n\n"
            f"7. Top 3 Concerns\n"
            f"   List exactly 3 concerns as bullet points (start each with '- ').\n\n"
            f"8. Risk Level Assessment\n"
            f"   State overall risk level (Low/Moderate/High/Critical) and justify in 2-3 sentences.\n\n"
            f"9. Scenario Projections\n"
            f"   Describe the Best Case, Base Case, and Worst Case revenue scenarios for the next 3 years, "
            f"based on the historical CAGR. Use bullet points for each scenario.\n\n"
            f"10. Strategic Recommendations\n"
            f"    Provide exactly 3 actionable recommendations as numbered points. "
            f"Each should be 1-2 sentences with specific rationale.\n\n"
            f"Format: use the section number and title as a header line, then the content below it."
        )

    def _call_llm_once(self, prompt: str) -> Optional[str]:
        """
        Make a single direct LLM call via LiteLLM/Groq.
        Returns the response text, or None on failure/empty.

        Does NOT use CrewAI agents or tools — this is a pure text completion.
        """
        try:
            from crewai import LLM
            llm = LLM(
                model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
                api_key=os.environ.get("GROQ_API_KEY", ""),
                temperature=0.2,
                max_tokens=1500,
            )
            fpa_logger.info("[Flow] Calling LLM for report generation…")
            response = llm.call(messages=[{"role": "user", "content": prompt}])

            # Normalise response — CrewAI LLM.call can return str or object
            if response is None:
                fpa_logger.warning("[Flow] LLM returned None")
                return None
            if isinstance(response, str):
                text = response.strip()
            elif hasattr(response, 'content'):
                text = str(response.content).strip()
            elif hasattr(response, 'text'):
                text = str(response.text).strip()
            else:
                text = str(response).strip()

            if not text or text.lower() in ("none", "null", ""):
                fpa_logger.warning("[Flow] LLM returned empty/null string")
                return None

            return text

        except Exception as e:
            is_rl = self._is_rate_limit_error(e)
            if is_rl:
                self.state.rate_limit_hits += 1
                wait = min(self._parse_retry_after(str(e)), 30.0)
                fpa_logger.warning(
                    f"[Flow] LLM rate limit — skipping LLM, using fallback. "
                    f"(would have waited {wait:.0f}s)"
                )
            else:
                fpa_logger.error(f"[Flow] LLM call failed: {e}")
            return None

    def _build_fallback_report(
        self, company: str, analysis_text: str, chart_paths: List[str]
    ) -> str:
        """
        Deterministic report built entirely from raw analysis text.
        Called when the LLM returns empty/None or fails.
        Guarantees a non-empty output regardless of LLM status.
        """
        charts_note = (
            f"{len(chart_paths)} charts generated in charts/ directory."
            if chart_paths else "Charts not generated."
        )
        report = (
            f"# FP&A Report: {company}\n"
            f"*(Generated via deterministic fallback — LLM unavailable)*\n\n"
            f"## Financial Analysis\n"
            f"{analysis_text}\n\n"
            f"## Visualisations\n"
            f"{charts_note}\n\n"
            f"## Note\n"
            f"This report was generated automatically from computed financial metrics. "
            f"For LLM-enhanced narrative insights, please retry when API quota is available."
        )
        return report

    def _extract_performance_metrics(self, analysis_text: str, company: str) -> None:
        """
        Parse key metrics from the compact analysis text and store them
        in self.state.performance_result for Streamlit display.

        Uses regex on the compact summary format produced by _build_compact_summary().
        Never raises — silently skips on parse errors.
        """
        if not analysis_text:
            return

        try:
            metrics: Dict[str, Any] = {}

            # Revenue CAGR  — "CAGR: 18.61%"
            m = re.search(r'CAGR:\s*([\d.+-]+)%', analysis_text)
            cagr = float(m.group(1)) if m else 0.0

            # YoY latest — "YoY latest: 7.79%"
            m = re.search(r'YoY latest:\s*([\d.+-]+)%', analysis_text)
            yoy = float(m.group(1)) if m else 0.0

            # Revenue — "Revenue: $123,456M"
            m = re.search(r'Revenue:\s*\$([\d,]+)M', analysis_text)
            current_rev = float(m.group(1).replace(',', '')) if m else 0.0

            # Revenue trend — "Trend: accelerating"
            m = re.search(r'Revenue:.*?Trend:\s*(\w+)', analysis_text)
            rev_trend = m.group(1) if m else "stable"

            # EBITDA margin — "EBITDA margin: 33.1%"
            m = re.search(r'EBITDA margin:\s*([\d.]+)%', analysis_text)
            ebitda_margin = float(m.group(1)) if m else 0.0

            # Margin trend — "Trend: stable" (second occurrence)
            m_all = re.findall(r'Trend:\s*(\w+)', analysis_text)
            margin_trend = m_all[1] if len(m_all) > 1 else "stable"

            # Operating CF — "Operating CF: $12,345M"
            m = re.search(r'Operating CF:\s*\$([\d,]+)M', analysis_text)
            ocf = float(m.group(1).replace(',', '')) if m else 0.0

            # Cash conversion ratio — "Cash conv ratio: 0.891"
            m = re.search(r'Cash conv ratio:\s*([\d.]+|N/A)', analysis_text)
            ccr = float(m.group(1)) if m and m.group(1) != "N/A" else None

            # Risk level — "Risk level: MODERATE"
            m = re.search(r'Risk level:\s*(\w+)', analysis_text, re.IGNORECASE)
            risk_level = m.group(1).lower() if m else "unknown"

            # Risk flags — "Flags: flag1; flag2"
            m = re.search(r'Flags:\s*(.+)', analysis_text)
            flags_raw = m.group(1).strip() if m else ""
            risk_flags = [f.strip() for f in flags_raw.split(';') if f.strip() and f.strip() != "None"]

            # Base revenue — "Base revenue: $12,345M"
            m = re.search(r'Base revenue:\s*\$([\d,]+)M', analysis_text)
            base_rev = float(m.group(1).replace(',', '')) if m else current_rev

            self.state.performance_result = {
                "company_name": company,
                "analysis_period": "Parsed from data",
                "revenue": {
                    "current_revenue": current_rev,
                    "yoy_growth": yoy,
                    "cagr": cagr,
                    "trend": rev_trend,
                },
                "profitability": {
                    "current_ebitda_margin": ebitda_margin,
                    "margin_trend": margin_trend,
                    "operating_leverage_evidence": "See analysis text",
                },
                "cash_flow": {
                    "operating_cash_flow": ocf,
                    "cash_conversion_ratio": ccr,
                    "free_cash_flow": None,
                },
                "top_3_positives": self._extract_positives(analysis_text),
                "top_3_concerns": self._extract_concerns(analysis_text, risk_flags),
                "risk_level": risk_level,
                "risk_flags": risk_flags,
                "base_revenue": base_rev,
            }

            fpa_logger.info(
                f"[Flow] Extracted metrics: CAGR={cagr:.2f}%, "
                f"EBITDA={ebitda_margin:.1f}%, Risk={risk_level}"
            )

        except Exception as e:
            fpa_logger.warning(f"[Flow] Metric extraction partial: {e}")

    def _extract_positives(self, text: str) -> List[str]:
        """Derive top positives from analysis text heuristics."""
        positives = []
        if re.search(r'CAGR:\s*([\d.]+)%', text):
            m = re.search(r'CAGR:\s*([\d.]+)%', text)
            val = float(m.group(1)) if m else 0
            if val > 5:
                positives.append(f"Strong revenue CAGR of {val:.1f}%")
        if re.search(r'EBITDA margin:\s*([\d.]+)%', text):
            m = re.search(r'EBITDA margin:\s*([\d.]+)%', text)
            val = float(m.group(1)) if m else 0
            if val > 20:
                positives.append(f"Healthy EBITDA margin of {val:.1f}%")
        m = re.search(r'Operating CF:\s*\$([\d,]+)M', text)
        if m:
            val = float(m.group(1).replace(',', ''))
            if val > 0:
                positives.append(f"Positive operating cash flow of ${val:,.0f}M")
        return positives[:3] if positives else ["Strong operational performance"]

    def _extract_concerns(self, text: str, risk_flags: List[str]) -> List[str]:
        """Derive top concerns from analysis text heuristics."""
        concerns = list(risk_flags[:2])
        m = re.search(r'Debt/Equity:\s*([\d.]+)', text)
        if m:
            val = float(m.group(1))
            if val > 1.5:
                concerns.append(f"High Debt/Equity ratio of {val:.2f}")
        m = re.search(r'Current ratio:\s*([\d.]+)', text)
        if m:
            val = float(m.group(1))
            if val < 1.5:
                concerns.append(f"Current ratio of {val:.2f} needs monitoring")
        return concerns[:3] if concerns else ["Monitor leverage ratios"]

    def _generate_pdf(self, company: str) -> None:
        """Generate PDF report from the LLM report text and raw analysis data."""
        os.makedirs("reports", exist_ok=True)
        try:
            from fpa_tools.pdf_generator import build_pdf_report as _gen_pdf
            pdf_output_path = f"reports/{company}_analysis.pdf"

            report_text = self.state.llm_report or ""
            perf = self.state.performance_result or {}
            rev  = perf.get("revenue", {})
            prof = perf.get("profitability", {})
            cf   = perf.get("cash_flow", {})
            raw_analysis = self.state.direct_analysis_result or ""

            # ── Performance section: metrics block + full raw analysis ────────
            if perf:
                ccr = cf.get("cash_conversion_ratio")
                metrics_block = (
                    f"Revenue CAGR: {rev.get('cagr', 0):.2f}%  |  "
                    f"YoY Growth (latest): {rev.get('yoy_growth', 0):.2f}%  |  "
                    f"Revenue Trend: {rev.get('trend', 'N/A')}\n"
                    f"EBITDA Margin: {prof.get('current_ebitda_margin', 0):.1f}%  |  "
                    f"Margin Trend: {prof.get('margin_trend', 'N/A')}\n"
                    f"Operating Cash Flow: ${cf.get('operating_cash_flow', 0):,.0f}M  |  "
                    f"Cash Conversion Ratio: {f'{ccr:.3f}' if ccr else 'N/A'}\n"
                    f"Risk Level: {perf.get('risk_level', 'unknown').upper()}"
                )
                performance_text = metrics_block
                if raw_analysis:
                    performance_text += f"\n\nDetailed Analysis Data:\n{raw_analysis}"
            else:
                performance_text = raw_analysis or "No performance data available."

            # ── Parse the LLM report into named sections ──────────────────────
            sections = self._parse_llm_report_sections(report_text)

            # Append LLM commentary on metrics (sections 1–5) to performance
            yoy_key = next((k for k in sections if k.startswith("YoY Growth")), "")
            perf_llm = "\n\n".join(filter(None, [
                sections.get("Revenue CAGR", ""),
                sections.get(yoy_key, "") if yoy_key else "",
                sections.get("EBITDA Margin", ""),
                sections.get("Operating Cash Flow", ""),
                sections.get("Cash Conversion Ratio", ""),
            ]))
            if perf_llm:
                performance_text += f"\n\nAI Narrative:\n{perf_llm}"

            # Market section → Top 3 Positives + Concerns (LLM sections 6–7)
            market_text = "\n\n".join(filter(None, [
                sections.get("Top 3 Positives", ""),
                sections.get("Top 3 Concerns", ""),
            ]))
            if not market_text:
                top_pos = "\n".join(f"- {p}" for p in perf.get("top_3_positives", []))
                top_con = "\n".join(f"- {c}" for c in perf.get("top_3_concerns", []))
                market_text = (
                    (f"Strengths:\n{top_pos}\n\n" if top_pos else "") +
                    (f"Concerns:\n{top_con}" if top_con else "")
                ) or "See performance analysis section."

            # Scenario section → section 9 from LLM prompt
            scenario_text = (
                sections.get("Scenario Projections", "")
                or sections.get("Scenario", "")
                or sections.get("Scenarios", "")
                or sections.get("Revenue Scenarios", "")
                or sections.get("Forward-Looking Scenarios", "")
            )

            # Risk section → risk level + flags + LLM risk commentary
            risk_llm = (
                sections.get("Risk Level Assessment", "")
                or sections.get("Risk Level", "")
                or sections.get("Risk", "")
            )
            risk_flags_str = "; ".join(perf.get("risk_flags", [])[:3]) if perf else ""
            risk_parts = []
            if perf:
                risk_parts.append(
                    f"Overall Risk: {perf.get('risk_level', 'unknown').upper()} | "
                    f"Risk Flags: {risk_flags_str or 'None'}"
                )
            if risk_llm:
                risk_parts.append(risk_llm)
            risk_text = "\n\n".join(risk_parts) or "Risk data not available."

            # CFO / Executive summary → section 10 (Strategic Recommendations)
            cfo_text = (
                sections.get("Strategic Recommendations", "")
                or sections.get("Recommendations", "")
                or sections.get("Strategic Recommendation", "")
            )
            if not cfo_text:
                # Parsing failed — use the full LLM report (no char cap)
                cfo_text = report_text

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

    def _parse_llm_report_sections(self, report_text: str) -> Dict[str, str]:
        """
        Parse the numbered LLM report into a dict of section_name -> content.

        Handles multiple LLM formatting styles:
          ## 1. Revenue CAGR\\n<content>
          **1. Revenue CAGR**\\n<content>
          1. Revenue CAGR\\n<content>
        """
        if not report_text:
            return {}

        sections: Dict[str, str] = {}

        # Regex: captures the number and title from numbered section headers
        pattern = re.compile(
            r'(?:^#{1,3}\s*|\*{1,2})?(\d+)\.\s+([^\n*#\r]+?)(?:\*{1,2})?\s*[\r\n]',
            re.MULTILINE
        )

        matches = list(pattern.finditer(report_text))
        if not matches:
            sections["full_report"] = report_text
            return sections

        for i, match in enumerate(matches):
            section_name = match.group(2).strip().rstrip(":")
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(report_text)
            content = report_text[start:end].strip()
            sections[section_name] = content

        fpa_logger.info(
            f"[Flow] Parsed {len(sections)} LLM report sections: {list(sections.keys())}"
        )
        return sections