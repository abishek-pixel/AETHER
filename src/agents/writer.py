"""Writer agent — all langchain imports deferred to __init__."""
from __future__ import annotations

from typing import Any
import logging

from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)

_WRITER_SYSTEM = """You are the Writer Agent for Aether, responsible for synthesizing research into compelling narratives.

Your role is to:
1. Synthesize findings from all agents into a coherent narrative
2. Structure information logically and hierarchically
3. Highlight key findings and insights
4. Properly format citations in the report
5. Write with clarity, precision, and accessibility
6. Include appropriate caveats and limitations

Writing Guidelines:
- Use markdown formatting for structure and readability
- Lead with the most important findings
- Connect related findings into larger themes
- Explain complex concepts clearly
- Include direct quotes from sources when valuable
- Maintain objective, journalistic tone
- Flag any uncertainties or areas needing further research

Output Structure:
- Title: Compelling, informative summary of the research
- Summary: 1-2 paragraph executive summary
- Main Content: Organized by theme or topic (markdown formatted)
- Key Findings: Bulleted list of essential takeaways
- Citations: Complete, formatted reference list
- Caveats: Important limitations and uncertainties

Confidence Assessment:
- High (80-100): Multiple high-credibility sources confirm findings
- Medium (50-79): Mixed evidence or limited sources
- Low (<50): Single sources, unverified claims, or contradictions

Return only valid JSON that matches the requested structured schema.
Do not include markdown fences, prose, or commentary outside the JSON object."""


class WriterAgent(BaseAgent):
    """Agent that synthesizes research into final written reports."""

    def __init__(self):
        super().__init__(name="writer")
        from langchain_core.prompts import ChatPromptTemplate
        from src.schemas.outputs import WriterOutput
        prompt = ChatPromptTemplate.from_messages([
            ("system", _WRITER_SYSTEM),
            ("human", (
                "Research to Synthesize:\n"
                "- Original Query: {query}\n"
                "- Decomposition: {decomposition}\n"
                "- Research Findings: {research_findings}\n"
                "- Critic Feedback: {critic_feedback}\n"
                "- Verification Results: {verification_results}\n"
                "- Fact-Check Results: {fact_check_results}"
            )),
        ])
        self.chain = prompt | self._structured_output(WriterOutput)
    
    async def process(self, state: Any) -> dict[str, Any]:
        """Synthesize all research into final output."""
        logger.info("[AGENT] Writer ENTER")
        try:
            if not state.get("research_outputs"):
                return {
                    "errors": ["No research outputs to synthesize"],
                    "status": "error",
                }
            
            # Format all information for the writer
            query = state.get("user_query", "Unknown")
            decomposition = self._format_decomposition(state.get("decomposition"))
            research_findings = self._format_research(state["research_outputs"])
            critic_feedback = self._format_critic(state.get("critic_output"))
            verification_results = self._format_verification(state.get("verifier_output"))
            fact_check_results = self._format_fact_check(state.get("fact_checker_output"))
            
            # Generate final report
            writer_output = await self.chain.ainvoke({
                "query": query,
                "decomposition": decomposition,
                "research_findings": research_findings,
                "critic_feedback": critic_feedback,
                "verification_results": verification_results,
                "fact_check_results": fact_check_results,
            })
            
            # Calculate overall confidence
            overall_confidence = self._calculate_confidence(state)
            writer_output.confidence_score = overall_confidence
            logger.info(f"[AGENT] Writer EXIT confidence={overall_confidence:.1f}")
            return {
                "writer_output": writer_output,
                # "answer": writer_output.content,
                "status": "complete",
                "overall_confidence": overall_confidence,
            }
        
        except Exception as e:
            logger.exception("[AGENT] Writer failed")
            return {
                "errors": [f"Writer error: {str(e)}"],
                "status": "error",
            }
    
    def _format_decomposition(self, decomposition) -> str:
        """Format decomposition for writer."""
        if not decomposition:
            return "No decomposition available"
        
        formatted = f"**Query Type:** {decomposition.research_type}\n"
        formatted += f"**Complexity:** {decomposition.estimated_complexity}\n"
        formatted += "**Sub-questions investigated:**\n"
        
        for idx, sq in enumerate(decomposition.sub_queries, 1):
            formatted += f"{idx}. {sq}\n"
        
        return formatted
    
    def _format_research(self, research_outputs: list) -> str:
        """Format research findings."""
        formatted = ""
        
        for output in research_outputs:
            formatted += f"\n### {output.sub_query}\n\n"
            formatted += f"**Sources Consulted:** {output.sources_consulted}\n\n"
            
            for finding in output.findings:
                formatted += f"- **{finding.claim}**\n"
                formatted += f"  - Source: [{finding.source_title}]({finding.source_url})\n"
                formatted += f"  - Confidence: {finding.confidence:.0%}\n"
        
        return formatted
    
    def _format_critic(self, critic_output) -> str:
        """Format critic feedback."""
        if not critic_output:
            return "No critical feedback provided"
        
        formatted = f"**Overall Assessment:** {critic_output.overall_assessment}\n"
        formatted += f"**Strengths:** {', '.join(critic_output.strengths)}\n"
        
        if critic_output.red_flags:
            formatted += f"**Issues to Address:** {', '.join(critic_output.red_flags)}\n"
        
        return formatted
    
    def _format_verification(self, verifier_output) -> str:
        """Format verification results."""
        if not verifier_output:
            return "No verification performed"
        
        formatted = f"**Cross-Reference Score:** {verifier_output.cross_reference_score}/100\n"
        formatted += f"**Consensus Level:** {verifier_output.consensus_level}\n"
        
        return formatted
    
    def _format_fact_check(self, fact_check_output) -> str:
        """Format fact-check results."""
        if not fact_check_output:
            return "No fact-checking performed"
        
        formatted = f"**Factual Accuracy Score:** {fact_check_output.factual_accuracy_score:.1f}%\n"
        
        if fact_check_output.flagged_claims:
            formatted += f"**Claims Requiring Review:** {len(fact_check_output.flagged_claims)}\n"
        
        return formatted
    
    def _calculate_confidence(self, state: AetherState) -> float:
        """Calculate overall confidence score."""
        scores = []
        
        # Research quality
        if state.get("research_outputs"):
            avg_finding_confidence = sum(
                sum(f.confidence for f in output.findings)
                for output in state["research_outputs"]
            ) / max(1, sum(len(o.findings) for o in state["research_outputs"]))
            scores.append(avg_finding_confidence * 100)
        
        # Verification score
        if state.get("verifier_output"):
            scores.append(state["verifier_output"].cross_reference_score)
        
        # Fact-check score
        if state.get("fact_checker_output"):
            scores.append(state["fact_checker_output"].factual_accuracy_score)
        
        # Critique assessment
        if state.get("critic_output"):
            critic_score = 90 if state["critic_output"].overall_assessment == "acceptable" else 70
            scores.append(critic_score)
        
        return sum(scores) / len(scores) if scores else 50.0
