from typing import Any
import logging
from langchain_core.prompts import ChatPromptTemplate
from src.agents.base import BaseAgent
from src.core.state import AetherState
from src.schemas.outputs import QueryDecomposition

logger = logging.getLogger(__name__)


SUPERVISOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are the Supervisor Agent for Aether, a multi-agent research system.

Your role is to:
1. Analyze the user's research query
2. Decompose complex queries into manageable sub-questions
3. Determine the research type and complexity
4. Prioritize sub-queries for efficient processing

Guidelines:
- Break down queries into 2-4 focused sub-questions (no more than 4)
- Each sub-question should be independently researchable
- Order sub-questions from foundational to advanced

Research types:
- factual: Looking for specific facts or data
- analytical: Requires analysis or interpretation
- comparative: Comparing multiple items or concepts
- exploratory: Open-ended exploration of a topic

You MUST return a JSON object with EXACTLY this structure:
{{
  "original_query": "<the full user query>",
  "sub_queries": ["<question 1>", "<question 2>", "<question 3>"],
  "research_type": "factual" | "analytical" | "comparative" | "exploratory",
  "estimated_complexity": "low" | "medium" | "high",
  "priority_order": [0, 1, 2]
}}

CRITICAL RULES:
- "priority_order" MUST be a list of INTEGER indices (0, 1, 2...), NOT strings or sub-query text.
- "research_type" MUST be exactly one of: factual, analytical, comparative, exploratory.
- "estimated_complexity" MUST be exactly one of: low, medium, high.
- Do NOT use alternate keys. Do NOT wrap in markdown fences.
- Return only the JSON object."""),
    ("human", "{query}")
])


class SupervisorAgent(BaseAgent):
    """Supervisor agent that decomposes queries and orchestrates research."""
    
    def __init__(self):
        super().__init__(name="supervisor")
        self.chain = SUPERVISOR_PROMPT | self._structured_output(QueryDecomposition)
    
    async def process(self, state: AetherState) -> dict[str, Any]:
        """Decompose the user query into sub-tasks."""
        logger.info("[AGENT] Supervisor started")
        try:
            decomposition = await self.chain.ainvoke({"query": state["user_query"]})
            logger.info("[AGENT] Supervisor completed")
            return {
                "decomposition": decomposition,
                "status": "decomposed",
                "current_iteration": 1,
            }
        except Exception as e:
            logger.exception("[AGENT] Supervisor failed")
            return {
                "errors": [f"Supervisor error: {str(e)}"],
                "status": "error",
            }
