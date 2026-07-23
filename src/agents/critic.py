from typing import Any
import logging
from langchain_core.prompts import ChatPromptTemplate
from src.agents.base import BaseAgent
from src.core.state import AetherState
from src.schemas.outputs import CriticOutput, CriticFeedback

logger = logging.getLogger(__name__)


CRITIC_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are the Critic Agent for Aether, a quality assurance specialist.

Your role is to:
1. Evaluate research findings for logical consistency
2. Identify potential biases or unsupported claims
3. Assess source credibility and methodology
4. Flag contradictions between findings
5. Suggest improvements and additional research

Evaluation Criteria:
- **Logic**: Are conclusions logically derived from evidence?
- **Bias**: Are claims presented objectively? Any cherry-picking?
- **Evidence**: Is evidence sufficient and properly attributed?
- **Contradictions**: Do findings conflict with each other?
- **Completeness**: Are there gaps in the research?
- **Recency**: Are sources current and relevant?

Severity Levels:
- minor: Typos, formatting, non-critical details
- moderate: Weak evidence, potential bias, incomplete sourcing
- critical: False claims, major logical fallacies, unsupported conclusions

Provide structured feedback for each finding with specific issues and suggestions.

Return only valid JSON that matches the requested structured schema.
Do not include markdown fences, prose, or commentary outside the JSON object."""),
    ("human", "Research Findings to Critique:\n{findings}\n\nDecomposition Context:\n{decomposition}")
])


class CriticAgent(BaseAgent):
    """Agent that critiques research findings for quality and consistency."""
    
    def __init__(self):
        super().__init__(name="critic")
        self.chain = CRITIC_PROMPT | self._structured_output(CriticOutput)
    
    async def process(self, state: AetherState) -> dict[str, Any]:
        """Critique the research outputs."""
        logger.info("[AGENT] Critic started")
        try:
            if not state.get("research_outputs"):
                return {
                    "errors": ["No research outputs to critique"],
                    "status": "error",
                }
            
            # Format findings for critique
            findings_text = self._format_findings(state["research_outputs"])
            decomposition_text = self._format_decomposition(state.get("decomposition"))
            
            # Generate critique
            critique = await self.chain.ainvoke({
                "findings": findings_text,
                "decomposition": decomposition_text
            })
            
            # Determine if major revisions needed
            red_flag_count = len(critique.red_flags)
            critical_feedback = sum(
                1 for item in critique.feedback_items 
                if item.severity == "critical"
            )
            
            status = "needs_revision" if critical_feedback > 0 else "critique_complete"
            logger.info(f"[AGENT] Critic completed assessment={critique.overall_assessment}")
            return {
                "critic_output": critique,
                "status": status,
                "critique_severity_level": "critical" if critical_feedback > 0 else "moderate" if red_flag_count > 0 else "minor",
            }
        
        except Exception as e:
            logger.exception("[AGENT] Critic failed")
            return {
                "errors": [f"Critic error: {str(e)}"],
                "status": "error",
            }
    
    def _format_findings(self, research_outputs: list) -> str:
        """Format research outputs for critique."""
        formatted = "Research Findings:\n"
        
        for idx, output in enumerate(research_outputs):
            formatted += f"\n{idx+1}. Sub-query: {output.sub_query}\n"
            formatted += f"   Sources consulted: {output.sources_consulted}\n"
            formatted += "   Findings:\n"
            
            for fidx, finding in enumerate(output.findings):
                formatted += f"      {fidx+1}. Claim: {finding.claim}\n"
                formatted += f"         Confidence: {finding.confidence}\n"
                formatted += f"         Source: {finding.source_title} ({finding.source_url})\n"
        
        return formatted
    
    def _format_decomposition(self, decomposition) -> str:
        """Format decomposition for context."""
        if not decomposition:
            return ""
        
        formatted = f"Original Query: {decomposition.original_query}\n"
        formatted += f"Research Type: {decomposition.research_type}\n"
        formatted += f"Complexity: {decomposition.estimated_complexity}\n"
        formatted += "Sub-queries:\n"
        
        for idx, sq in enumerate(decomposition.sub_queries):
            formatted += f"  {idx+1}. {sq}\n"
        
        return formatted
