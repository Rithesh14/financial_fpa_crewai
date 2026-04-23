"""
Financial FP&A Crew — Production Architecture v4 (2-Stage Pipeline).

ARCHITECTURE CHANGE from v3:
  - FinancialFpa crew class REMOVED (entire ReAct agent loop eliminated)
  - run_tools_directly() KEPT — Stage 1 of the new 2-stage pipeline
  - FPAAnalysisCache KEPT — disk cache prevents redundant analysis runs
  - APICallTracker KEPT — lightweight call counter for monitoring
  - validate_tool_args() KEPT — used inside run_tools_directly()

The LLM is now called ONCE in flow.py (generate_llm_report step),
NOT via CrewAI agents. This eliminates:
  - Empty/None LLM responses caused by ReAct tool-call loops
  - Redundant tool calls (tools were being called by both run_direct_tools
    AND again by the crew agents)
  - Over-constrained prompts (Thought/Action/Observation format)
  - Unnecessary agent retries consuming API quota
"""

import os
import json
import time as _time
import hashlib
from typing import Tuple, Any, Dict, Optional

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

from fpa_tools.logger import fpa_logger


# ══════════════════════════════════════════════════════════════════════════════
# CACHING LAYER
# ══════════════════════════════════════════════════════════════════════════════

class FPAAnalysisCache:
    """
    Disk-backed JSON cache for fpa_analysis_tool results.

    Cache key = hash(company + csv_path + csv_mtime).
    Same company + same file → returns cached result, skips computation.
    """

    CACHE_DIR = "cache"
    CACHE_FILE = os.path.join(CACHE_DIR, "fpa_analysis_cache.json")

    @classmethod
    def _ensure_dir(cls):
        os.makedirs(cls.CACHE_DIR, exist_ok=True)

    @classmethod
    def _cache_key(cls, company: str, csv_path: str) -> str:
        try:
            mtime = str(os.path.getmtime(csv_path))
        except OSError:
            mtime = "unknown"
        raw = f"{company.strip().upper()}|{os.path.abspath(csv_path)}|{mtime}"
        return hashlib.md5(raw.encode()).hexdigest()

    @classmethod
    def get(cls, company: str, csv_path: str) -> Optional[str]:
        """Return cached analysis result or None."""
        cls._ensure_dir()
        key = cls._cache_key(company, csv_path)
        try:
            if os.path.exists(cls.CACHE_FILE):
                with open(cls.CACHE_FILE, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                if key in cache:
                    fpa_logger.info(f"[Cache] HIT for {company} (key={key[:8]}…)")
                    return cache[key]
        except (json.JSONDecodeError, OSError) as e:
            fpa_logger.warning(f"[Cache] Read error: {e}")
        return None

    @classmethod
    def put(cls, company: str, csv_path: str, result: str) -> None:
        """Store analysis result in cache."""
        cls._ensure_dir()
        key = cls._cache_key(company, csv_path)
        try:
            cache = {}
            if os.path.exists(cls.CACHE_FILE):
                with open(cls.CACHE_FILE, "r", encoding="utf-8") as f:
                    cache = json.load(f)
            cache[key] = result
            with open(cls.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)
            fpa_logger.info(f"[Cache] STORED for {company} (key={key[:8]}…)")
        except (json.JSONDecodeError, OSError) as e:
            fpa_logger.warning(f"[Cache] Write error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# API CALL TRACKER
# ══════════════════════════════════════════════════════════════════════════════

class APICallTracker:
    """Lightweight call counter for monitoring LLM usage per run."""

    def __init__(self, max_calls: int = 5):
        self.max_calls = max_calls
        self.call_count = 0
        self.rate_limit_hits = 0
        self.skipped_steps = []

    def can_call(self) -> bool:
        return self.call_count < self.max_calls

    def record_call(self, description: str = ""):
        self.call_count += 1
        fpa_logger.info(
            f"[APITracker] Call #{self.call_count}/{self.max_calls}: {description}"
        )

    def record_rate_limit(self, description: str = ""):
        self.rate_limit_hits += 1
        fpa_logger.warning(
            f"[APITracker] Rate limit hit #{self.rate_limit_hits}: {description}"
        )

    def record_skip(self, step: str, reason: str = ""):
        self.skipped_steps.append(step)
        fpa_logger.warning(f"[APITracker] SKIPPED '{step}': {reason}")

    def summary(self) -> str:
        return (
            f"[APITracker] Run summary: "
            f"calls={self.call_count}/{self.max_calls}, "
            f"rate_limits={self.rate_limit_hits}, "
            f"skipped={self.skipped_steps}"
        )


# Module-level tracker — reset per flow run
api_tracker = APICallTracker(max_calls=5)


def reset_api_tracker() -> APICallTracker:
    """Reset the global API tracker for a new run."""
    global api_tracker
    api_tracker = APICallTracker(max_calls=5)
    return api_tracker


# ══════════════════════════════════════════════════════════════════════════════
# TOOL ARGUMENT VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def validate_tool_args(
    tool_name: str,
    args: Dict[str, Any],
    company: str = "",
) -> Dict[str, Any]:
    """
    Validate and auto-fill required arguments before calling any chart tool.

    - output_path: auto-filled with sensible default if missing
    - company: auto-filled from context if missing
    - csv_path: raises if missing or not found
    """
    validated = dict(args)

    chart_defaults = {
        "generate_revenue_trend_chart":         "charts/revenue_trend.png",
        "generate_profitability_analysis_chart": "charts/profitability_analysis.png",
        "generate_scenario_comparison_chart":    "charts/scenario_comparison.png",
        "generate_risk_dashboard":               "charts/risk_dashboard.png",
        "generate_waterfall_chart":              "charts/waterfall_revenue.png",
        "generate_radar_chart":                  "charts/radar_metrics.png",
        "generate_metrics_heatmap":              "charts/metrics_heatmap.png",
    }

    if tool_name in chart_defaults:
        if "output_path" not in validated or not validated["output_path"]:
            validated["output_path"] = chart_defaults[tool_name]
            fpa_logger.info(
                f"[Validation] Auto-filled output_path for {tool_name}: "
                f"{validated['output_path']}"
            )

    if "company" not in validated or not validated["company"]:
        if company:
            validated["company"] = company

    if "csv_path" in validated:
        csv = validated["csv_path"]
        if not csv:
            raise ValueError(f"[Validation] csv_path is empty for {tool_name}")
        if not os.path.exists(csv):
            raise FileNotFoundError(
                f"[Validation] csv_path not found for {tool_name}: {csv}"
            )

    return validated


# ══════════════════════════════════════════════════════════════════════════════
# STAGE 1: DIRECT TOOL EXECUTION (no LLM — pure Python computation)
# ══════════════════════════════════════════════════════════════════════════════

def run_tools_directly(csv_path: str, company: str, sector: str = "IT") -> Dict[str, Any]:
    """
    Stage 1 of the 2-stage pipeline.

    Run FPA analysis + all 6 charts as direct Python calls — ZERO LLM usage.
    These are pure computation: CSV → numbers + PNGs.

    Returns:
        dict with keys:
          - analysis_result: str  (compact metrics summary, ~120 tokens)
          - charts:          list[str]  (paths to successfully generated PNGs)
          - errors:          list[str]  (non-fatal errors encountered)
    """
    results: Dict[str, Any] = {
        "analysis_result": None,
        "charts": [],
        "errors": [],
    }

    os.makedirs("charts", exist_ok=True)

    # ── 1. FPA Analysis (with caching) ─────────────────────────────────
    fpa_logger.info(f"[DirectExec] Step 1/2: Running FPA analysis for {company}…")
    try:
        cached = FPAAnalysisCache.get(company, csv_path)
        if cached:
            results["analysis_result"] = cached
        else:
            analysis = run_fpa_analysis(csv_path=csv_path, company=company, sector=sector)
            results["analysis_result"] = analysis
            FPAAnalysisCache.put(company, csv_path, analysis)
    except Exception as e:
        err = f"FPA analysis failed: {e}"
        fpa_logger.error(f"[DirectExec] {err}")
        results["errors"].append(err)

    # ── 2. Charts (all 6, best-effort) ─────────────────────────────────
    fpa_logger.info(f"[DirectExec] Step 2/2: Generating charts for {company}…")

    chart_calls = [
        ("generate_revenue_trend_chart",         generate_revenue_trend_chart,
         {"csv_path": csv_path, "company": company, "output_path": "charts/revenue_trend.png"}),
        ("generate_profitability_analysis_chart", generate_profitability_analysis_chart,
         {"csv_path": csv_path, "company": company, "output_path": "charts/profitability_analysis.png"}),
        ("generate_scenario_comparison_chart",    generate_scenario_comparison_chart,
         {"csv_path": csv_path, "company": company, "output_path": "charts/scenario_comparison.png"}),
        ("generate_risk_dashboard",               generate_risk_dashboard,
         {"csv_path": csv_path, "company": company, "output_path": "charts/risk_dashboard.png"}),
        ("generate_waterfall_chart",              generate_waterfall_chart,
         {"csv_path": csv_path, "company": company, "output_path": "charts/waterfall_revenue.png"}),
        ("generate_radar_chart",                  generate_radar_chart,
         {"csv_path": csv_path, "company": company, "output_path": "charts/radar_metrics.png"}),
    ]

    for tool_name, tool_fn, tool_args in chart_calls:
        try:
            validated = validate_tool_args(tool_name, tool_args, company)
            result = tool_fn.run(**validated)
            if isinstance(result, dict):
                if result.get("status") == "success":
                    results["charts"].append(result.get("chart_path", validated["output_path"]))
                    fpa_logger.info(f"[DirectExec] ✓ {tool_name}")
                else:
                    msg = result.get("message", "unknown error")
                    results["errors"].append(f"{tool_name}: {msg}")
                    fpa_logger.warning(f"[DirectExec] ✗ {tool_name}: {msg}")
            else:
                # String result — still treat as success
                results["charts"].append(validated.get("output_path", ""))
                fpa_logger.info(f"[DirectExec] ✓ {tool_name}: done")
        except Exception as e:
            err = f"{tool_name} failed: {e}"
            fpa_logger.warning(f"[DirectExec] {err}")
            results["errors"].append(err)
            # Continue — chart failures are non-fatal

    fpa_logger.info(
        f"[DirectExec] Complete: "
        f"analysis={'✓' if results['analysis_result'] else '✗'}, "
        f"charts={len(results['charts'])}, "
        f"errors={len(results['errors'])}"
    )
    return results