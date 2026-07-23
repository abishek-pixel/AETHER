"""Fact-checker agent — all langchain imports deferred to __init__."""
from __future__ import annotations

from typing import Any
import asyncio
import logging
import httpx

from src.agents.base import BaseAgent

logger = logging.getLogger(__name__)

_FACT_CHECKER_SYSTEM = """You are the Fact-Checker Agent for Aether, responsible for citation validation.

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
Do not include markdown fences, prose, or commentary outside the JSON object."""


class FactCheckerAgent(BaseAgent):
    """Agent that validates citations and checks factual accuracy."""

    def __init__(self):
        super().__init__(name="fact_checker")
        # Deferred imports — langchain_core takes ~11 s on cold start
        from langchain_core.prompts import ChatPromptTemplate
        from src.schemas.outputs import FactCheckerOutput
        from src.tools.scraper import WebScraper
        logger.info("[INIT] Creating WebScraper...")
        self.scraper = WebScraper()
        logger.info("[INIT] WebScraper created")
        prompt = ChatPromptTemplate.from_messages([
            ("system", _FACT_CHECKER_SYSTEM),
            ("human", "Citations to Check:\n{citations}\n\nClaims:\n{claims}"),
        ])
        self.chain = prompt | self._structured_output(FactCheckerOutput)

    async def process(self, state: Any) -> dict[str, Any]:
        """Check factual accuracy of research findings."""
        logger.info("[AGENT] FactChecker ENTER")
        try:
            if not state.get("research_outputs"):
                return {
                    "errors": ["No research outputs to fact-check"],
                    "status": "error",
                }

            citations = self._extract_citations(state["research_outputs"])
            claims = self._extract_claims_text(state["research_outputs"])

            citation_checks = await self._validate_citations(citations)

            from src.schemas.outputs import FactCheckerOutput
            fact_check = await self.chain.ainvoke({
                "citations": self._format_citations(citations),
                "claims": claims,
            })

            fact_check.citation_checks = citation_checks

            accuracy_score = self._calculate_accuracy_score(citation_checks)
            fact_check.factual_accuracy_score = accuracy_score

            status = "fact_checked" if accuracy_score >= 80 else "fact_check_issues"
            logger.info(f"[AGENT] FactChecker EXIT accuracy={accuracy_score:.1f}")
            return {
                "fact_checker_output": fact_check,
                "status": status,
                "accuracy_score": accuracy_score,
            }

        except Exception as e:
            logger.exception("[AGENT] FactChecker failed")
            return {
                "errors": [f"Fact-checker error: {str(e)}"],
                "status": "error",
            }

    async def _validate_citations(self, citations: list) -> list:
        """Validate citation URLs concurrently (max 5 at once, 8 s per URL)."""
        from src.schemas.outputs import CitationCheck

        async def _check_one(url: str):
            try:
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    response = await client.get(url, timeout=8.0)
                    is_accessible = response.status_code < 400
                    content_matches = len(response.text) > 100 if is_accessible else None
                    return CitationCheck(
                        citation_url=url,
                        is_accessible=is_accessible,
                        content_matches_claim=content_matches,
                        source_credibility=self._assess_credibility(url),
                    )
            except Exception:
                return CitationCheck(
                    citation_url=url,
                    is_accessible=False,
                    content_matches_claim=False,
                    source_credibility="unknown",
                )

        MAX_CONCURRENT = 5
        checks = []
        for i in range(0, len(citations), MAX_CONCURRENT):
            batch = citations[i : i + MAX_CONCURRENT]
            checks.extend(await asyncio.gather(*[_check_one(u) for u in batch]))
        return checks

    def _assess_credibility(self, url: str) -> str:
        high = [".edu", ".gov", "academic", "scholar", "journal",
                "nature.com", "science.org", "arxiv.org"]
        low  = ["reddit.com", "medium.com", "quora.com", "blogspot"]
        u = url.lower()
        if any(d in u for d in high):
            return "high"
        if any(d in u for d in low):
            return "low"
        return "medium"

    def _extract_citations(self, research_outputs: list) -> list[str]:
        seen: set[str] = set()
        for output in research_outputs:
            for finding in output.findings:
                if finding.source_url:
                    seen.add(finding.source_url)
        return list(seen)

    def _extract_claims_text(self, research_outputs: list) -> str:
        lines = ["Claims:"]
        for i, output in enumerate(research_outputs):
            for j, finding in enumerate(output.findings):
                lines.append(f"{i+1}.{j+1} {finding.claim}")
        return "\n".join(lines)

    def _format_citations(self, citations: list) -> str:
        lines = ["Citations to Check:"]
        for i, url in enumerate(citations):
            lines.append(f"{i+1}. {url}")
        return "\n".join(lines)

    def _calculate_accuracy_score(self, citation_checks: list) -> float:
        if not citation_checks:
            return 100.0
        n = len(citation_checks)
        accessible = sum(1 for c in citation_checks if c.is_accessible)
        credible   = sum(1 for c in citation_checks if c.source_credibility in ("high", "medium"))
        return ((accessible / n) + (credible / n)) / 2 * 100
