from sentence_transformers import SentenceTransformer
from typing import List, Union
import logging

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings for research content."""

    # Singleton: only load the heavy model once across all agents
    _instance: "EmbeddingService | None" = None

    def __new__(cls, model_name: str = "all-MiniLM-L6-v2"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if getattr(self, "_initialized", False):
            return  # Already loaded — skip
        self.model = SentenceTransformer(model_name)
        # Support both old and new API names
        if hasattr(self.model, "get_embedding_dimension"):
            self.embedding_dim = self.model.get_embedding_dimension()
        else:
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
        self._initialized = True
        logger.info(f"Loaded embedding model: {model_name} (dim={self.embedding_dim})")
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a text.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector
        """
        embedding = self.model.encode(text, convert_to_tensor=False)
        return embedding.tolist()
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
        
        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(texts, convert_to_tensor=False)
        return embeddings.tolist()
    
    def similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
        
        Returns:
            Similarity score (0-1)
        """
        embeddings = self.model.encode([text1, text2])
        from sklearn.metrics.pairwise import cosine_similarity
        
        similarity_matrix = cosine_similarity([embeddings[0]], [embeddings[1]])
        return float(similarity_matrix[0][0])
