from typing import Dict, List, Callable, Any
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TuningParameter:
    """A tunable agent parameter."""
    
    name: str
    current_value: float
    min_value: float
    max_value: float
    improvement_target: float
    
    def should_adjust(self, current_performance: float) -> bool:
        """Check if parameter should be adjusted.
        
        Args:
            current_performance: Current performance metric
        
        Returns:
            Whether to adjust
        """
        return current_performance < self.improvement_target


class AgentFineTuner:
    """Fine-tune agent parameters."""
    
    def __init__(self):
        """Initialize fine-tuner."""
        self.parameters = {
            "researcher_depth": TuningParameter(
                name="research_depth",
                current_value=0.7,
                min_value=0.3,
                max_value=1.0,
                improvement_target=0.85,
            ),
            "critic_threshold": TuningParameter(
                name="critic_threshold",
                current_value=0.6,
                min_value=0.4,
                max_value=0.9,
                improvement_target=0.75,
            ),
            "fact_check_strictness": TuningParameter(
                name="fact_check_strictness",
                current_value=0.5,
                min_value=0.3,
                max_value=0.95,
                improvement_target=0.8,
            ),
            "temperature": TuningParameter(
                name="temperature",
                current_value=0.1,
                min_value=0.0,
                max_value=1.0,
                improvement_target=0.15,
            ),
        }
    
    async def optimize_parameters(
        self,
        metrics: Dict[str, float],
        adjustment_rate: float = 0.1
    ) -> Dict[str, float]:
        """Optimize parameters based on metrics.
        
        Args:
            metrics: Current performance metrics
            adjustment_rate: How much to adjust per iteration
        
        Returns:
            Updated parameter values
        """
        updated = {}
        
        for param_name, param in self.parameters.items():
            metric_key = f"{param_name}_score"
            
            if metric_key not in metrics:
                updated[param_name] = param.current_value
                continue
            
            current_perf = metrics[metric_key]
            
            if param.should_adjust(current_perf):
                # Adjust parameter
                gap = param.improvement_target - current_perf
                direction = 1 if gap > 0 else -1
                adjustment = adjustment_rate * direction
                
                new_value = param.current_value + adjustment
                new_value = max(param.min_value, min(param.max_value, new_value))
                
                param.current_value = new_value
                updated[param_name] = new_value
                
                logger.info(
                    f"Adjusted {param_name}: {param.current_value:.3f} "
                    f"(performance: {current_perf:.2%})"
                )
            else:
                updated[param_name] = param.current_value
        
        return updated
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """Get optimized config for agent.
        
        Args:
            agent_name: Name of agent
        
        Returns:
            Agent configuration
        """
        config = {}
        
        if agent_name == "researcher":
            config["research_depth"] = self.parameters["researcher_depth"].current_value
        
        elif agent_name == "critic":
            config["threshold"] = self.parameters["critic_threshold"].current_value
        
        elif agent_name == "fact_checker":
            config["strictness"] = self.parameters["fact_check_strictness"].current_value
        
        config["temperature"] = self.parameters["temperature"].current_value
        
        return config


class CostOptimizer:
    """Optimize for cost efficiency."""
    
    @staticmethod
    def analyze_cost_breakdown(
        execution_log: Dict[str, Any]
    ) -> Dict[str, float]:
        """Analyze where costs are highest.
        
        Args:
            execution_log: Execution log with costs
        
        Returns:
            Cost breakdown by agent
        """
        breakdown = {}
        
        for event in execution_log.get("events", []):
            if event.get("type") == "agent_complete":
                agent = event.get("agent")
                cost = event.get("cost", 0)
                
                if agent not in breakdown:
                    breakdown[agent] = 0
                
                breakdown[agent] += cost
        
        return breakdown
    
    @staticmethod
    def suggest_optimizations(
        cost_breakdown: Dict[str, float],
        total_cost: float
    ) -> List[str]:
        """Suggest cost optimizations.
        
        Args:
            cost_breakdown: Cost per agent
            total_cost: Total cost
        
        Returns:
            List of optimization suggestions
        """
        suggestions = []
        
        for agent, cost in cost_breakdown.items():
            percentage = cost / total_cost * 100
            
            if percentage > 40:
                suggestions.append(
                    f"Agent '{agent}' uses {percentage:.1f}% of costs. "
                    f"Consider reducing research depth or increasing batch size."
                )
            
            if agent == "researcher" and percentage > 30:
                suggestions.append(
                    f"Researcher costs are high. Consider: "
                    f"1) Limiting search results, "
                    f"2) Using cheaper search APIs, "
                    f"3) Enabling caching."
                )
        
        return suggestions