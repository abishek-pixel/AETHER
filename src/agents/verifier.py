from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from src.agents.base import BaseAgent
from src.core.state import AetherState
from src.schemas.outputs import VerifierOutput, VerificationResult
from src.tools.search import TavilySearch


VERIFIER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are the Verifier Agent for Aether, specializing in cross-reference validation.

Your role is to:
1. Cross-reference claims against multiple independent sources
2. Identify supporting and contradicting evidence
3. Assess source consensus on claims
4. Determine confidence levels for verification
5. Flag unverifiable claims

Verification Process:
- For each claim, search for supporting AND contradicting sources
- Assess the quality and credibility of each source
- Look for expert consensus or academic support
- Note if claims are disputed or controversial
- Assign confidence scores based on source agreement

Consensus Levels:
- strong: Multiple high-quality sources agree (3+ sources)
- moderate: Multiple sources agree with some variation (2+ sources)
- weak: Limited evidence, single source or weak sources (1 source)
- conflicting: Sources contradict each other

Output detailed verification results with cross-reference score (0-100).

Return only valid JSON that matches the requested structured schema.
Do not include markdown fences, prose, or commentary outside the JSON object."""),
    ("human", "Claims to Verify:\n{claims}\n\nOriginal Research Sources:\n{research_sources}")
])


class VerifierAgent(BaseAgent):
    """Agent that verifies claims through cross-referencing."""
    
    def __init__(self):
        super().__init__(name="verifier")
        self.search_tool = TavilySearch(api_key=self.settings.tavily_api_key)
        self.chain = VERIFIER_PROMPT | self._structured_output(VerifierOutput)
    
    async def process(self, state: AetherState) -> dict[str, Any]:
        """Verify research findings through cross-referencing."""
        try:
            if not state.get("research_outputs"):
                return {
                    "errors": ["No research outputs to verify"],
                    "status": "error",
                }
            
            # Extract claims to verify
            claims_to_verify = self._extract_claims(state["research_outputs"])
            research_sources = self._format_research_sources(state["research_outputs"])
            
            # Generate verification
            verification = await self.chain.ainvoke({
                "claims": claims_to_verify,
                "research_sources": research_sources
            })
            
            # Determine if verification passed
            status = "verified" if verification.cross_reference_score >= 70 else "partial_verification"
            
            return {
                "verifier_output": verification,
                "status": status,
                "verification_confidence": verification.cross_reference_score,
            }
        
        except Exception as e:
            return {
                "errors": [f"Verifier error: {str(e)}"],
                "status": "error",
            }
    
    def _extract_claims(self, research_outputs: list) -> str:
        """Extract claims from research findings."""
        claims = []
        
        for output in research_outputs:
            for finding in output.findings:
                claims.append({
                    "claim": finding.claim,
                    "original_source": finding.source_url,
                    "confidence": finding.confidence,
                })
        
        formatted = "Claims to Verify:\n"
        for idx, claim in enumerate(claims):
            formatted += f"\n{idx+1}. {claim['claim']}\n"
            formatted += f"   Original Source: {claim['original_source']}\n"
            formatted += f"   Original Confidence: {claim['confidence']}\n"
        
        return formatted
    
    def _format_research_sources(self, research_outputs: list) -> str:
        """Format research sources for reference."""
        formatted = "Research Sources:\n"
        
        sources_set = set()
        for output in research_outputs:
            for finding in output.findings:
                sources_set.add((finding.source_title, finding.source_url))
        
        for idx, (title, url) in enumerate(sources_set):
            formatted += f"\n{idx+1}. {title}\n"
            formatted += f"   URL: {url}\n"
        
        return formatted
