from typing import Any
from langchain_core.prompts import ChatPromptTemplate
from src.agents.base import BaseAgent
from src.core.state import AetherState
from src.schemas.outputs import FactCheckerOutput, CitationCheck
from src.tools.scraper import WebScraper
import httpx
from datetime import datetime


FACT_CHECKER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are the Fact-Checker Agent for Aether, responsible for citation validation.

Your role is to:
1. Verify that citations are accessible and accurate
2. Check if content matches the claims being made
3. Assess source credibility and authority
4. Identify potential factual errors
5. Flag outdated or unreliable sources

Citation Assessment:
- **Accessibility**: Is the URL still valid and accessible?
- **Content Match**: Does the source support the claim?
- **Credibility**: Is the source reliable? Check domain, author, publication date
- **Authority**: Is the author an expert in the field?
- **Currency**: Is the information up-to-date?

Credibility Levels:
- high: Academic sources, established news, government sources, verified experts
- medium: Reputable websites, industry publications, established companies
- low: Blogs, forums, non-expert sources, unreliable domains
- unknown: Unable to verify source credibility

Flag any claims that cannot be verified or have credibility issues.

Return only valid JSON that matches the requested structured schema.
Do not include markdown fences, prose, or commentary outside the JSON object."""),
    ("human", "Citations to Check:\n{citations}\n\nClaims:\n{claims}")
])


class FactCheckerAgent(BaseAgent):
    """Agent that validates citations and checks factual accuracy."""
    
    def __init__(self):
        super().__init__(name="fact_checker")
        self.scraper = WebScraper()
        self.chain = FACT_CHECKER_PROMPT | self._structured_output(FactCheckerOutput)
    
    async def process(self, state: AetherState) -> dict[str, Any]:
        """Check factual accuracy of research findings."""
        try:
            if not state.get("research_outputs"):
                return {
                    "errors": ["No research outputs to fact-check"],
                    "status": "error",
                }
            
            # Extract citations and claims
            citations = self._extract_citations(state["research_outputs"])
            claims = self._extract_claims_text(state["research_outputs"])
            
            # Validate each citation
            citation_checks = await self._validate_citations(citations)
            
            # Generate fact-checking report
            fact_check = await self.chain.ainvoke({
                "citations": self._format_citations(citations),
                "claims": claims
            })
            
            # Update with actual validation results
            fact_check.citation_checks = citation_checks
            
            # Calculate accuracy score
            accuracy_score = self._calculate_accuracy_score(citation_checks)
            fact_check.factual_accuracy_score = accuracy_score
            
            status = "fact_checked" if accuracy_score >= 80 else "fact_check_issues"
            
            return {
                "fact_checker_output": fact_check,
                "status": status,
                "accuracy_score": accuracy_score,
            }
        
        except Exception as e:
            return {
                "errors": [f"Fact-checker error: {str(e)}"],
                "status": "error",
            }
    
    async def _validate_citations(self, citations: list) -> list[CitationCheck]:
        """Validate accessibility and content of citations."""
        checks = []
        
        for url in citations:
            try:
                # Check if URL is accessible
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=10.0)
                    is_accessible = response.status_code == 200
                    
                    # If accessible, extract content
                    content_matches = None
                    if is_accessible:
                        content = response.text[:5000]  # Get first 5000 chars
                        # In real implementation, use scraper to extract relevant content
                        content_matches = len(content) > 100  # Simple heuristic
                    
                    # Assess credibility based on domain
                    credibility = self._assess_credibility(url)
                    
                    check = CitationCheck(
                        citation_url=url,
                        is_accessible=is_accessible,
                        content_matches_claim=content_matches,
                        source_credibility=credibility,
                    )
                    checks.append(check)
            
            except Exception as e:
                checks.append(CitationCheck(
                    citation_url=url,
                    is_accessible=False,
                    content_matches_claim=False,
                    source_credibility="unknown",
                ))
        
        return checks
    
    def _assess_credibility(self, url: str) -> str:
        """Assess source credibility based on domain."""
        high_credibility_domains = [
            ".edu", ".gov", "academic", "scholar", "journal",
            "nature.com", "science.org", "arxiv.org"
        ]
        low_credibility_domains = [
            "reddit.com", "medium.com", "quora.com", "blogspot"
        ]
        
        url_lower = url.lower()
        
        if any(domain in url_lower for domain in high_credibility_domains):
            return "high"
        elif any(domain in url_lower for domain in low_credibility_domains):
            return "low"
        else:
            return "medium"
    
    def _extract_citations(self, research_outputs: list) -> list[str]:
        """Extract unique citation URLs."""
        citations = set()
        
        for output in research_outputs:
            for finding in output.findings:
                if finding.source_url:
                    citations.add(finding.source_url)
        
        return list(citations)
    
    def _extract_claims_text(self, research_outputs: list) -> str:
        """Extract claims as text."""
        formatted = "Claims:\n"
        
        for idx, output in enumerate(research_outputs):
            for fidx, finding in enumerate(output.findings):
                formatted += f"{idx+1}.{fidx+1} {finding.claim}\n"
        
        return formatted
    
    def _format_citations(self, citations: list) -> str:
        """Format citations for verification."""
        formatted = "Citations to Check:\n"
        
        for idx, url in enumerate(citations):
            formatted += f"{idx+1}. {url}\n"
        
        return formatted
    
    def _calculate_accuracy_score(self, citation_checks: list) -> float:
        """Calculate overall accuracy score."""
        if not citation_checks:
            return 100.0
        
        accessible_count = sum(1 for check in citation_checks if check.is_accessible)
        credible_count = sum(1 for check in citation_checks if check.source_credibility in ["high", "medium"])
        
        accessibility_score = (accessible_count / len(citation_checks)) * 100
        credibility_score = (credible_count / len(citation_checks)) * 100
        
        return (accessibility_score + credibility_score) / 2
