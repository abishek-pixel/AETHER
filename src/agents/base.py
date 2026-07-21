from abc import ABC, abstractmethod
from typing import Any
from langchain_core.language_models import BaseChatModel
from langchain_groq import ChatGroq
from src.core.config import get_settings
from src.core.state import AetherState
from src.core.embeddings import EmbeddingService


class BaseAgent(ABC):
    """Abstract base class for all Aether agents."""
    
    def __init__(self, name: str, llm: BaseChatModel | None = None):
        self.name = name
        self.settings = get_settings()
        self.llm = llm or self._get_default_llm()
        self.communication_broker = None  # Will be set by graph
        self.memory_manager = None  # Will be set by graph
        self.embedding_service = EmbeddingService()
    
    def _get_default_llm(self) -> BaseChatModel:
        """Get the default LLM (Groq for speed and cost efficiency)."""
        return ChatGroq(
            api_key=self.settings.groq_api_key,
            model=self.settings.default_text_model,
            temperature=0.1,
        )

    def _structured_output(self, schema):
        """Return LLM bound to a Pydantic schema using json_mode.
        
        json_mode works reliably with llama-3.3-70b-versatile on Groq.
        The model returns valid JSON which is parsed into the Pydantic schema.
        """
        return self.llm.with_structured_output(schema, method="json_mode")
    
    async def retrieve_relevant_findings(
        self,
        query: str,
        max_results: int = 5
    ) -> list:
        """Retrieve relevant past findings from memory.
        
        Args:
            query: Query string
            max_results: Maximum findings to retrieve
        
        Returns:
            List of relevant findings
        """
        if not self.memory_manager:
            return []
        
        # Generate embedding for query
        query_embedding = self.embedding_service.embed_text(query)
        
        # Search vector store
        findings = await self.memory_manager.retrieve_similar_findings(
            query_embedding=query_embedding,
            max_results=max_results
        )
        
        return findings
    
    @abstractmethod
    async def process(self, state: AetherState) -> dict[str, Any]:
        """Process the current state and return updates."""
        pass
    
    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for Groq models."""
        # Groq pricing as of late 2024
        input_cost = (input_tokens / 1_000_000) * 0.59
        output_cost = (output_tokens / 1_000_000) * 0.79
        return input_cost + output_cost