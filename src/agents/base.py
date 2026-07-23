"""Base agent — all heavy imports are deferred to __init__ so that importing
this module does NOT trigger langchain_groq / sentence_transformers loading.

On Render's 512 MB free tier those imports alone can take 20-60 s and cause
the "[WORKFLOW] Constructing agents" hang observed in production logs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any
import logging

if TYPE_CHECKING:
    # Only used for type hints — never executed at runtime
    from langchain_core.language_models import BaseChatModel
    from src.core.state import AetherState

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all Aether agents."""

    def __init__(self, name: str, llm=None):
        self.name = name

        # Defer heavy imports — importing langchain_groq alone takes ~10 s
        logger.info(f"[INIT] Creating LLM client for {name}...")
        from src.core.config import get_settings
        self.settings = get_settings()
        self.llm = llm or self._get_default_llm()
        logger.info(f"[INIT] LLM client created for {name}")

        self.communication_broker = None  # set by AetherWorkflow
        self.memory_manager = None        # set by AetherWorkflow

        # ── EmbeddingService is NOT created here ──────────────────────────
        # sentence_transformers import takes 30+ s (eager torch load).
        # embeddings are only needed when memory_manager is available
        # (i.e. Neo4j/Qdrant running).  Since both are unavailable on the
        # current Render free instance, we never reach that code path.
        # Defer to first access via the property below.
        self._embedding_service = None

    @property
    def embedding_service(self):
        """Return EmbeddingService, loading it lazily on first access."""
        if self._embedding_service is None:
            logger.info(f"[INIT] Loading EmbeddingService for {self.name}...")
            from src.core.embeddings import EmbeddingService
            self._embedding_service = EmbeddingService()
            logger.info(f"[INIT] EmbeddingService ready for {self.name}")
        return self._embedding_service

    def _get_default_llm(self):
        """Construct the default LLM client (Groq).

        ChatGroq() is pure object construction — no network call is made here.
        The first actual API call happens inside ainvoke() during graph execution.
        """
        # Inline import so this module-level import never blocks startup
        from langchain_groq import ChatGroq

        groq_key = self.settings.groq_api_key
        is_configured = bool(
            groq_key
            and groq_key.strip()
            and not groq_key.startswith("REPLACE_")
            and not groq_key.startswith("gsk_REPLACE")
        )
        logger.info(f"[INIT] GROQ_API_KEY configured: {is_configured}")
        if not is_configured:
            raise RuntimeError(
                "GROQ_API_KEY is not set or is still a placeholder value. "
                "Set it in the Render dashboard → Environment Variables."
            )
        return ChatGroq(
            api_key=groq_key,
            model=self.settings.default_text_model,
            temperature=0.1,
        )

    def _structured_output(self, schema):
        """Return the LLM bound to a Pydantic schema via json_mode."""
        return self.llm.with_structured_output(schema, method="json_mode")

    async def retrieve_relevant_findings(
        self,
        query: str,
        max_results: int = 5,
    ) -> list:
        """Retrieve relevant past findings from vector memory (optional)."""
        if not self.memory_manager:
            return []
        # embedding_service is lazy — only loads sentence_transformers here
        query_embedding = self.embedding_service.embed_text(query)
        return await self.memory_manager.retrieve_similar_findings(
            query_embedding=query_embedding,
            max_results=max_results,
        )

    @abstractmethod
    async def process(self, state: Any) -> dict[str, Any]:
        """Process the current graph state and return updates."""
        pass

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for Groq models (late-2024 pricing)."""
        return (input_tokens / 1_000_000) * 0.59 + (output_tokens / 1_000_000) * 0.79
