import logging
from datetime import datetime
from typing import Optional
import json


class ResearchLogger:
    """Comprehensive logging for research execution."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.logger = logging.getLogger(f"aether_{session_id}")
        self.events = []
    
    def log_agent_start(self, agent_name: str, input_data: dict):
        """Log agent execution start."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "agent_start",
            "agent": agent_name,
            "input_keys": list(input_data.keys()),
        }
        self.events.append(event)
        self.logger.info(f"Agent {agent_name} started")
    
    def log_agent_complete(self, agent_name: str, output_data: dict, duration: float):
        """Log agent completion."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "agent_complete",
            "agent": agent_name,
            "duration_seconds": duration,
            "output_keys": list(output_data.keys()),
        }
        self.events.append(event)
        self.logger.info(f"Agent {agent_name} completed in {duration:.2f}s")
    
    def log_routing_decision(self, current_node: str, next_node: str, reason: str):
        """Log routing decision."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "routing",
            "from": current_node,
            "to": next_node,
            "reason": reason,
        }
        self.events.append(event)
        self.logger.info(f"Routed from {current_node} to {next_node}: {reason}")
    
    def log_error(self, agent_name: str, error: str):
        """Log error."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "error",
            "agent": agent_name,
            "error": error,
        }
        self.events.append(event)
        self.logger.error(f"Agent {agent_name} error: {error}")
    
    def get_execution_log(self) -> dict:
        """Get complete execution log."""
        return {
            "session_id": self.session_id,
            "start_time": self.events[0]["timestamp"] if self.events else None,
            "end_time": self.events[-1]["timestamp"] if self.events else None,
            "total_events": len(self.events),
            "events": self.events,
        }