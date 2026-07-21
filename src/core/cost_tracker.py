from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict
import json


@dataclass
class TokenUsage:
    """Track token usage per agent."""
    agent_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    def estimate_cost(self, model: str = "groq/llama-3.1-70b") -> float:
        """Estimate cost based on model."""
        # Groq pricing (very cheap)
        if "groq" in model.lower():
            input_cost = (self.input_tokens / 1_000_000) * 0.59
            output_cost = (self.output_tokens / 1_000_000) * 0.79
            return input_cost + output_cost
        
        # Default fallback
        return (self.total_tokens / 1_000_000) * 0.10


class CostTracker:
    """Track costs and token usage across agents."""
    
    def __init__(self, cost_limit_per_session: float = 1.0):
        self.cost_limit = cost_limit_per_session
        self.token_usage: Dict[str, TokenUsage] = {}
        self.execution_times: Dict[str, float] = {}
        self.start_time = datetime.utcnow()
    
    def track_agent_execution(
        self,
        agent_name: str,
        tokens_used: Dict[str, int] | None = None,
        execution_time: float = 0.0
    ) -> None:
        """Track execution metrics for an agent."""
        
        if tokens_used:
            usage = TokenUsage(
                agent_name=agent_name,
                input_tokens=tokens_used.get("input", 0),
                output_tokens=tokens_used.get("output", 0),
            )
            self.token_usage[agent_name] = usage
        
        if execution_time > 0:
            self.execution_times[agent_name] = execution_time
    
    def get_agent_cost(self, agent_name: str) -> float:
        """Get estimated cost for a specific agent."""
        if agent_name not in self.token_usage:
            return 0.0
        
        return self.token_usage[agent_name].estimate_cost()
    
    def get_total_cost(self) -> float:
        """Get total estimated cost for all agents."""
        return sum(self.get_agent_cost(agent) for agent in self.token_usage)
    
    def get_total_tokens(self) -> Dict[str, int]:
        """Get total token usage."""
        return {
            "input": sum(u.input_tokens for u in self.token_usage.values()),
            "output": sum(u.output_tokens for u in self.token_usage.values()),
            "total": sum(u.total_tokens for u in self.token_usage.values()),
        }
    
    def get_cost_breakdown(self) -> Dict[str, float]:
        """Get cost breakdown by agent."""
        return {
            agent: self.get_agent_cost(agent)
            for agent in self.token_usage
        }
    
    def get_performance_metrics(self) -> Dict[str, any]:
        """Get performance metrics."""
        return {
            "total_agents_executed": len(self.token_usage),
            "total_tokens": self.get_total_tokens(),
            "total_cost": self.get_total_cost(),
            "cost_limit": self.cost_limit,
            "under_budget": self.get_total_cost() < self.cost_limit,
            "execution_times": self.execution_times,
            "session_duration": (datetime.utcnow() - self.start_time).total_seconds(),
        }
    
    def is_within_budget(self) -> bool:
        """Check if total cost is within budget."""
        return self.get_total_cost() < self.cost_limit
    
    def export_report(self) -> Dict[str, any]:
        """Export comprehensive cost and usage report."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "session_metrics": self.get_performance_metrics(),
            "token_usage_by_agent": {
                agent: {
                    "input": usage.input_tokens,
                    "output": usage.output_tokens,
                    "total": usage.total_tokens,
                }
                for agent, usage in self.token_usage.items()
            },
            "cost_breakdown": self.get_cost_breakdown(),
            "total_cost": self.get_total_cost(),
        }