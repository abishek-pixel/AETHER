from typing import Any
import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from src.agents.base import BaseAgent
from src.core.state import AetherState
from src.schemas.outputs import ResearcherOutput, ResearchFinding
from src.tools.search import TavilySearch, SerperSearch
from datetime import datetime

logger = logging.getLogger(__name__)


RESEARCHER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are the Researcher Agent for Aether, a multi-agent research system.

Your role is to:
1. Execute thorough research on assigned sub-queries
2. Find relevant sources and extract key information
3. Assess the credibility of sources
4. Organize findings with proper attribution
5. Report confidence levels for each finding

Guidelines:
- Use multiple search strategies (broad, specific, academic)
- Verify facts against multiple sources when possible
- Include source URLs and titles in your findings
- Assign confidence scores (0-1) based on source quality and consistency
- Extract direct quotes from sources when relevant
- Flag potential misinformation or contradictions

You MUST return a JSON object with EXACTLY this structure:
{{
  "sub_query": "<the exact sub-query text>",
  "findings": [
    {{
      "claim": "<factual statement>",
      "source_url": "<url or null>",
      "source_title": "<title or null>",
      "confidence": <float 0-1>,
      "raw_excerpt": "<direct quote from source or null>"
    }}
  ],
  "search_queries_used": ["<query1>", "<query2>"],
  "sources_consulted": <integer count of sources>
}}

Return only the JSON object. Do not wrap in markdown fences or add any commentary."""),
    ("human", "Research sub-query: {sub_query}\n\nContext from previous findings:\n{context}")
])


class ResearcherAgent(BaseAgent):
    """Agent that conducts research on decomposed sub-queries."""
    
    def __init__(self):
        super().__init__(name="researcher")
        self.tavily_search = TavilySearch(api_key=self.settings.tavily_api_key)
        self.serper_search = SerperSearch(api_key=self.settings.serper_api_key)
        self.chain = RESEARCHER_PROMPT | self._structured_output(ResearcherOutput)
    
    async def process(self, state: AetherState) -> dict[str, Any]:
        """Research a specific sub-query."""
        logger.info("[AGENT] Researcher started")
        try:
            # Get the next sub-query from decomposition
            if not state.get("decomposition") or not state["decomposition"].sub_queries:
                return {
                    "errors": ["No sub-queries available for research"],
                    "status": "error",
                }

            sub_queries = state["decomposition"].sub_queries

            # Cap sub-queries based on depth setting to control cost/quality.
            # fast: 2 sub-queries, max 2 results each
            # balanced: 3 sub-queries, max 3 results each (default)
            # deep: 5 sub-queries, max 5 results each
            current_iteration = state.get("current_iteration", 0)
            depth = state.get("depth", "balanced")
            if depth == "fast":
                sq_cap = 2
                self._max_results = 2
            elif depth == "deep":
                sq_cap = 5
                self._max_results = 5
            else:  # balanced
                sq_cap = 3
                self._max_results = 3

            # On refinement iterations only re-research fewer sub-queries
            if current_iteration > 0:
                sq_cap = max(1, sq_cap - 1)
            sub_queries = sub_queries[:sq_cap]

            # Process each sub-query
            research_outputs = []
            # Carry forward any findings already in state on refinement runs
            existing_outputs = state.get("research_outputs") or []
            context = ""

            for idx, sub_query in enumerate(sub_queries):
                # Execute searches — limit results based on depth setting
                max_r = getattr(self, "_max_results", 3)
                tavily_results = await self._search_tavily(sub_query, max_results=max_r)
                serper_results = await self._search_serper(sub_query, max_results=max_r)

                # Combine results for context
                search_context = self._format_search_results(
                    tavily_results, serper_results
                )

                # Generate findings using LLM
                output = await self.chain.ainvoke({
                    "sub_query": sub_query,
                    "context": f"{context}\n\n{search_context}".strip()
                })

                # Add search metadata
                output.search_queries_used = [sub_query]
                output.sources_consulted = len(tavily_results) + len(serper_results)

                research_outputs.append(output)
                context += f"\n\nFindings for '{sub_query}':\n{output.model_dump_json()}"

            # On refinement passes merge new outputs with existing ones
            if current_iteration > 0 and existing_outputs:
                merged = {o.sub_query: o for o in existing_outputs}
                for o in research_outputs:
                    merged[o.sub_query] = o
                research_outputs = list(merged.values())

            logger.info(f"[AGENT] Researcher completed ({len(research_outputs)} outputs)")
            return {
                "research_outputs": research_outputs,
                "status": "research_complete",
            }

        except Exception as e:
            logger.exception("[AGENT] Researcher failed")
            return {
                "errors": [f"Researcher error: {str(e)}"],
                "status": "error",
            }
    
    async def _search_tavily(self, query: str, max_results: int = 3) -> list[dict]:
        """Execute search using Tavily API."""
        try:
            results = await self.tavily_search.search(query, max_results=max_results)
            return results
        except Exception as e:
            return []

    async def _search_serper(self, query: str, max_results: int = 3) -> list[dict]:
        """Execute search using Serper API."""
        try:
            results = await self.serper_search.search(query, max_results=max_results)
            return results
        except Exception as e:
            return []
    
    def _format_search_results(self, tavily_results: list, serper_results: list) -> str:
        """Format search results into context string."""
        formatted = "Search Results:\n"
        
        for i, result in enumerate(tavily_results[:3]):
            formatted += f"\n{i+1}. {result.get('title', 'No title')}\n"
            formatted += f"   URL: {result.get('url', 'N/A')}\n"
            formatted += f"   Content: {result.get('content', 'N/A')[:500]}...\n"
        
        for i, result in enumerate(serper_results[:3]):
            formatted += f"\n{len(tavily_results)+i+1}. {result.get('title', 'No title')}\n"
            formatted += f"   URL: {result.get('link', 'N/A')}\n"
            formatted += f"   Snippet: {result.get('snippet', 'N/A')[:500]}...\n"
        
        return formatted
