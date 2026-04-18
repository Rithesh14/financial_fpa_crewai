"""
Event Listener for Financial FP&A Analysis.

Tracks agent progress in real-time for Streamlit progress updates
and structured logging. Uses CrewAI's event bus.
"""

import datetime
from typing import List, Dict, Any

try:
    from crewai.utilities.events import (
        BaseEventListener,
        AgentExecutionStartedEvent,
        AgentExecutionCompletedEvent,
        TaskStartedEvent,
        TaskCompletedEvent,
    )
    CREWAI_EVENTS_AVAILABLE = True
except ImportError:
    # Graceful fallback if event bus API changes in a future version
    CREWAI_EVENTS_AVAILABLE = False
    BaseEventListener = object

from fpa_tools.logger import fpa_logger


class FPAProgressListener(BaseEventListener if CREWAI_EVENTS_AVAILABLE else object):
    """
    Tracks agent and task progress for real-time Streamlit updates.

    Usage:
        listener = FPAProgressListener()
        # After crew runs, check listener.events for progress data
    """

    def __init__(self):
        if CREWAI_EVENTS_AVAILABLE:
            super().__init__()
        self.events: List[Dict[str, Any]] = []
        self.task_count: int = 0
        self.completed_tasks: int = 0
        self.current_agent: str = ""
        self.start_time: datetime.datetime = datetime.datetime.now()

    def setup_listeners(self, crewai_event_bus):
        """Register event handlers with the CrewAI event bus."""
        if not CREWAI_EVENTS_AVAILABLE:
            return

        @crewai_event_bus.on(AgentExecutionStartedEvent)
        def on_agent_start(source, event):
            agent_role = ""
            try:
                agent_role = event.agent.role if hasattr(event, 'agent') else "Unknown Agent"
            except Exception:
                agent_role = "Unknown Agent"

            self.current_agent = agent_role
            event_data = {
                "type": "agent_start",
                "agent": agent_role,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            self.events.append(event_data)
            fpa_logger.info(f"🤖 Agent started: {agent_role}")

        @crewai_event_bus.on(AgentExecutionCompletedEvent)
        def on_agent_complete(source, event):
            agent_role = ""
            try:
                agent_role = event.agent.role if hasattr(event, 'agent') else "Unknown Agent"
            except Exception:
                agent_role = "Unknown Agent"

            event_data = {
                "type": "agent_complete",
                "agent": agent_role,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            self.events.append(event_data)
            fpa_logger.info(f"✅ Agent completed: {agent_role}")

        @crewai_event_bus.on(TaskStartedEvent)
        def on_task_start(source, event):
            desc = ""
            try:
                desc = event.task.description[:80] if hasattr(event, 'task') else ""
            except Exception:
                desc = ""

            event_data = {
                "type": "task_start",
                "task": desc,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            self.events.append(event_data)
            self.task_count += 1
            fpa_logger.info(f"📋 Task started: {desc[:60]}...")

        @crewai_event_bus.on(TaskCompletedEvent)
        def on_task_complete(source, event):
            desc = ""
            agent_role = ""
            try:
                desc = event.task.description[:80] if hasattr(event, 'task') else ""
                agent_role = event.task.agent.role if (
                    hasattr(event, 'task') and event.task.agent
                ) else "unknown"
            except Exception:
                pass

            self.completed_tasks += 1
            event_data = {
                "type": "task_complete",
                "task": desc,
                "agent": agent_role,
                "completed_count": self.completed_tasks,
                "timestamp": datetime.datetime.now().isoformat(),
            }
            self.events.append(event_data)
            fpa_logger.info(f"✅ Task completed by {agent_role}: {desc[:50]}...")

    def get_progress_percentage(self, total_tasks: int = 5) -> float:
        """Return estimated progress (0–100) based on completed tasks."""
        if total_tasks == 0:
            return 0.0
        return min(100.0, (self.completed_tasks / total_tasks) * 100)

    def get_latest_event_description(self) -> str:
        """Return a human-readable description of the most recent event."""
        if not self.events:
            return "Initializing..."
        latest = self.events[-1]
        event_type = latest.get("type", "")
        if event_type == "agent_start":
            return f"🤖 {latest.get('agent')} is analyzing..."
        elif event_type == "agent_complete":
            return f"✅ {latest.get('agent')} completed"
        elif event_type == "task_start":
            task = latest.get("task", "")[:50]
            return f"📋 Running: {task}..."
        elif event_type == "task_complete":
            agent = latest.get("agent", "")
            return f"✅ {agent} finished task {latest.get('completed_count', '')}"
        return "Processing..."

    def reset(self):
        """Reset listener state for a new run."""
        self.events.clear()
        self.task_count = 0
        self.completed_tasks = 0
        self.current_agent = ""
        self.start_time = datetime.datetime.now()


# Module-level instance — used by Streamlit app
progress_listener = FPAProgressListener()
