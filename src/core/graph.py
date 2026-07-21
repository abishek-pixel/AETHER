import asyncio
from langgraph.graph import StateGraph, START, END
from langgraph.types import StreamWriter
from src.core.state import AetherState
from src.agents.supervisor import SupervisorAgent
from src.agents.researcher import ResearcherAgent
from src.agents.critic import CriticAgent
from src.agents.verifier import VerifierAgent
from src.agents.fact_checker import FactCheckerAgent
from src.agents.writer import WriterAgent
from src.core.communication import CommunicationBroker
from src.core.cost_tracker import CostTracker


class AetherWorkflow:
    """Advanced orchestration for the Aether multi-agent system."""
    
    def __init__(self):
        self.supervisor = SupervisorAgent()
        self.researcher = ResearcherAgent()
        self.critic = CriticAgent()
        self.verifier = VerifierAgent()
        self.fact_checker = FactCheckerAgent()
        self.writer = WriterAgent()
        self.communication_broker = CommunicationBroker()
        self.cost_tracker = CostTracker()
        
        # Set communication broker for all agents
        for agent in [self.supervisor, self.researcher, self.critic, 
                     self.verifier, self.fact_checker, self.writer]:
            agent.communication_broker = self.communication_broker
    
    def create_graph(self) -> StateGraph:
        """Create the advanced Aether workflow graph."""
        
        graph = StateGraph(AetherState)
        
        # Add all nodes
        graph.add_node("supervisor", self._supervisor_node)
        graph.add_node("researcher", self._researcher_node)
        graph.add_node("critic", self._critic_node)
        graph.add_node("verification_choice", self._verification_decision)
        graph.add_node("verifier", self._verifier_node)
        graph.add_node("fact_checker", self._fact_checker_node)
        graph.add_node("refinement_loop", self._refinement_loop)
        graph.add_node("quality_check", self._quality_assessment)
        graph.add_node("writer", self._writer_node)
        
        # Define edges with conditional routing
        graph.add_edge(START, "supervisor")
        graph.add_edge("supervisor", "researcher")
        graph.add_edge("researcher", "critic")
        
        # Conditional: Route based on critic assessment
        graph.add_conditional_edges(
            "critic",
            self._route_after_critique,
            {
                "needs_revision": "refinement_loop",
                "proceed": "verification_choice",
            }
        )
        
        # Conditional: Skip verification if high confidence
        graph.add_conditional_edges(
            "verification_choice",
            self._route_verification,
            {
                "verify": "verifier",
                "skip_to_fact_check": "fact_checker",
            }
        )
        
        graph.add_edge("verifier", "fact_checker")
        
        # Conditional: Route based on fact-check results
        graph.add_conditional_edges(
            "fact_checker",
            self._route_after_fact_check,
            {
                "needs_refinement": "refinement_loop",
                "quality_check": "quality_check",
            }
        )
        
        graph.add_edge("refinement_loop", "researcher")
        graph.add_edge("quality_check", "writer")
        graph.add_edge("writer", END)
        
        return graph.compile()
    
    async def _supervisor_node(self, state: AetherState) -> dict:
        """Execute supervisor agent."""
        result = await self.supervisor.process(state)
        
        # Track cost
        self.cost_tracker.track_agent_execution(
            agent_name="supervisor",
            tokens_used=result.get("token_usage", {})
        )
        
        decomposition = result.get("decomposition") or state.get("decomposition")

        # Send message to researcher
        if decomposition:
            await self.communication_broker.send_message(
                sender="supervisor",
                receiver="researcher",
                message_type="task",
                content={"sub_queries": decomposition.sub_queries}
            )
        
        return result
    
    async def _researcher_node(self, state: AetherState) -> dict:
        """Execute researcher agent."""
        result = await self.researcher.process(state)
        
        self.cost_tracker.track_agent_execution(
            agent_name="researcher",
            tokens_used=result.get("token_usage", {})
        )
        
        research_outputs = result.get("research_outputs") or state.get("research_outputs")

        # Send findings to critic
        if research_outputs:
            await self.communication_broker.send_message(
                sender="researcher",
                receiver="critic",
                message_type="result",
                content={"findings_count": len(research_outputs)}
            )
        
        return result
    
    async def _critic_node(self, state: AetherState) -> dict:
        """Execute critic agent."""
        result = await self.critic.process(state)
        
        self.cost_tracker.track_agent_execution(
            agent_name="critic",
            tokens_used=result.get("token_usage", {})
        )
        
        return result
    
    async def _verification_decision(self, state: AetherState) -> dict:
        """Decide whether verification is needed."""
        # If research has high confidence, skip verification
        avg_confidence = self._calculate_avg_confidence(state)
        
        return {
            "verification_required": avg_confidence < 0.85
        }
    
    async def _verifier_node(self, state: AetherState) -> dict:
        """Execute verifier agent."""
        result = await self.verifier.process(state)
        
        self.cost_tracker.track_agent_execution(
            agent_name="verifier",
            tokens_used=result.get("token_usage", {})
        )
        
        return result
    
    async def _fact_checker_node(self, state: AetherState) -> dict:
        """Execute fact-checker agent."""
        result = await self.fact_checker.process(state)
        
        self.cost_tracker.track_agent_execution(
            agent_name="fact_checker",
            tokens_used=result.get("token_usage", {})
        )
        
        return result
    
    async def _refinement_loop(self, state: AetherState) -> dict:
        """Handle iterative refinement of research."""
        current_iteration = state.get("current_iteration", 0)
        max_iterations = state.get("max_iterations", 5)
        
        if current_iteration >= max_iterations:
            return {
                "errors": [f"Max iterations ({max_iterations}) reached"],
                "status": "max_iterations_exceeded",
                "current_iteration": current_iteration,
            }
        
        # Log refinement iteration
        await self.communication_broker.send_message(
            sender="system",
            receiver="researcher",
            message_type="feedback",
            content={
                "iteration": current_iteration + 1,
                "max_iterations": max_iterations,
                "action": "refine_research"
            }
        )
        
        return {
            "current_iteration": current_iteration + 1,
            "status": "refining",
        }
    
    async def _quality_assessment(self, state: AetherState) -> dict:
        """Assess overall quality before final writing."""
        
        scores = {}
        
        # Research quality
        if state.get("research_outputs"):
            avg_confidence = self._calculate_avg_confidence(state)
            scores["research_quality"] = avg_confidence
        
        # Verification quality
        if state.get("verifier_output"):
            scores["verification_quality"] = state["verifier_output"].cross_reference_score / 100
        
        # Fact-check quality
        if state.get("fact_checker_output"):
            scores["accuracy_quality"] = state["fact_checker_output"].factual_accuracy_score / 100
        
        # Overall quality
        if scores:
            overall_quality = sum(scores.values()) / len(scores)
            
            quality_status = "high_quality" if overall_quality >= 0.7 else "acceptable_quality"
            
            return {
                "quality_scores": scores,
                "overall_quality": overall_quality,
                "quality_status": quality_status,
            }
        
        return {"overall_quality": 0.5, "quality_status": "unknown"}
    
    async def _writer_node(self, state: AetherState) -> dict:
        """Execute writer agent."""
        result = await self.writer.process(state)
        
        self.cost_tracker.track_agent_execution(
            agent_name="writer",
            tokens_used=result.get("token_usage", {})
        )
        
        # Calculate final metrics
        total_cost = self.cost_tracker.get_total_cost()
        
        return {
            **result,
            "total_cost": total_cost,
            "cost_breakdown": self.cost_tracker.get_cost_breakdown(),
        }
    
    def _route_after_critique(self, state: AetherState) -> str:
        """Route based on critique assessment.
        
        Only send back for refinement on truly critical issues AND only if
        we haven't already iterated — avoids expensive re-research loops.
        """
        if not state.get("critic_output"):
            return "proceed"

        # Never refine if we've already done at least one iteration
        if state.get("current_iteration", 0) > 0:
            return "proceed"

        assessment = state["critic_output"].overall_assessment
        red_flags = len(state["critic_output"].red_flags)

        # Only route back for revision on major issues with many red flags
        if assessment == "major_issues" and red_flags >= 5:
            return "needs_revision"

        return "proceed"

    def _route_verification(self, state: AetherState) -> str:
        """Route based on whether verification is needed."""
        avg_confidence = self._calculate_avg_confidence(state)

        # Skip verification for high-confidence results
        if avg_confidence > 0.75:
            return "skip_to_fact_check"

        return "verify"

    def _route_after_fact_check(self, state: AetherState) -> str:
        """Route based on fact-check results.
        
        Only refine if accuracy is very poor AND we haven't hit max iterations.
        Prefer proceeding to writer over expensive re-research.
        """
        if not state.get("fact_checker_output"):
            return "quality_check"

        accuracy = state["fact_checker_output"].factual_accuracy_score
        flagged = len(state["fact_checker_output"].flagged_claims)
        current_iteration = state.get("current_iteration", 0)
        max_iterations = state.get("max_iterations", 5)

        # Only refine on critically low accuracy, and never more than once
        if accuracy < 50 and flagged >= 5 and current_iteration < 1:
            return "needs_refinement"
        
        return "quality_check"
    
    def _calculate_avg_confidence(self, state: AetherState) -> float:
        """Calculate average confidence across findings."""
        if not state.get("research_outputs"):
            return 0.0
        
        total_confidence = 0
        total_findings = 0
        
        for output in state["research_outputs"]:
            for finding in output.findings:
                total_confidence += finding.confidence
                total_findings += 1
        
        return total_confidence / total_findings if total_findings > 0 else 0.0


def create_aether_graph() -> StateGraph:
    """Create and return compiled Aether workflow graph."""
    workflow = AetherWorkflow()
    return workflow.create_graph()


# Singleton instance
aether_workflow = create_aether_graph()

# Exposed for test utilities that need direct access to agent instances (e.g. cost_tracker)
aether_workflow_instance = AetherWorkflow()
