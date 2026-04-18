"""
Structured Logging Module for Financial FP&A Analysis.

Provides consistent, structured logging across the entire pipeline
including file-based logging and console output.
"""

import logging
import os
from datetime import datetime


def setup_logger(
    name: str = "fpa",
    log_dir: str = "logs",
    level: int = logging.INFO
) -> logging.Logger:
    """
    Create a structured logger with file and console handlers.

    Args:
        name: Logger name
        log_dir: Directory to store log files
        level: Logging level

    Returns:
        Configured logger instance
    """
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on re-initialization
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # File handler — one file per day
    date_str = datetime.now().strftime("%Y-%m-%d")
    file_handler = logging.FileHandler(
        os.path.join(log_dir, f"fpa_{date_str}.log"),
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_format = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(levelname)s | %(message)s'
    )
    console_handler.setFormatter(console_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Module-level logger instance
fpa_logger = setup_logger()


def log_analysis_start(company: str, csv_path: str):
    """Log the start of an analysis run."""
    fpa_logger.info(f"=== ANALYSIS START === Company: {company} | File: {csv_path}")


def log_analysis_complete(company: str, status: str = "success"):
    """Log the completion of an analysis run."""
    fpa_logger.info(f"=== ANALYSIS COMPLETE === Company: {company} | Status: {status}")


def log_validation_result(csv_path: str, is_valid: bool, errors: list):
    """Log data validation results."""
    status = "PASSED" if is_valid else "FAILED"
    fpa_logger.info(f"Data Validation {status}: {csv_path}")
    for error in errors:
        fpa_logger.error(f"  Validation Error: {error}")


def log_crew_step(step_name: str, details: str = ""):
    """Log a crew execution step."""
    fpa_logger.info(f"[Crew Step] {step_name} | {details}")


def log_flow_state(step: str, state_summary: str):
    """Log flow state transitions."""
    fpa_logger.info(f"[Flow] Step: {step} | State: {state_summary}")


def log_error(context: str, error: Exception):
    """Log an error with context."""
    fpa_logger.error(f"[ERROR] {context}: {str(error)}", exc_info=True)
