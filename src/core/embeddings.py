from typing import List
import logging
import numpy as np

logger = logging.getLogger(__name__)

# ── Lazy torch / sentence_transformers import ─────────────────────────────
# torch is NOT imported at module level.
# On Render the CPU wheel may fail to install or conflict with the default
# index, making `torch` unavailable even when sentence_transformers is present.
# We guard every call so a missing torch never crashes the research pipeline.

try:
    from sentence_transformers import SentenceTransformer as _SentenceTransformer
    _ST_AVAILABLE = True
except Exception:  # ImportError, or torch NameError at import time
    _SentenceTransformer = None  # type: ignore[assignment,misc]
    _ST_AVAILABLE = False


class EmbeddingService:
    """Generate embeddings for research content.

    Falls back to zero-vectors when sentence_transformers / torch is
    unavailable, so the research pipeline can still run without local
    ML dependencies.  On Render this avoids the:
        NameError: name 'torch' is not defined
    crash that sentence_transformers 5.x triggers when torch is not
    properly installed.
    """

    # Singleton: only load the heavy model once across all agents
    _instance: "EmbeddingService | None" = None

    EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output size

    def __new__(cls, model_name: str = "all-MiniLM-L6-v2"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if getattr(self, "_initialized", False):
            return  # Already loaded — skip
        self.model = None
        self.embedding_dim = self.EMBEDDING_DIM
        if _ST_AVAILABLE:
            try:
                self.model = _SentenceTransformer(model_name)
                # Support both old and new API names
                if hasattr(self.model, "get_embedding_dimension"):
                    self.embedding_dim = self.model.get_embedding_dimension()
                else:
                    self.embedding_dim = self.model.get_sentence_embedding_dimension()
                logger.info(
                    f"✅ Loaded embedding model: {model_name} (dim={self.embedding_dim})"
                )
            except Exception as exc:
                # torch or CUDA error at model-load time — degrade gracefully
                logger.warning(
                    f"⚠️  EmbeddingService: failed to load '{model_name}' "
                    f"({type(exc).__name__}: {exc}). "
                    "Falling back to zero-vector embeddings."
                )
                self.model = None
        else:
            logger.warning(
                "⚠️  EmbeddingService: sentence_transformers not available. "
                "Falling back to zero-vector embeddings. "
                "Install sentence-transformers and torch[cpu] for full functionality."
            )
        self._initialized = True

    # ── Public API ────────────────────────────────────────────────────────

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a text, or return a zero-vector fallback."""
        if self.model is not None:
            try:
                embedding = self.model.encode(text, convert_to_tensor=False)
                return embedding.tolist()
            except Exception as exc:
                logger.warning(f"embed_text failed ({exc}); using zero-vector fallback")
        return [0.0] * self.embedding_dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts, or return zero-vector fallbacks."""
        if self.model is not None:
            try:
                embeddings = self.model.encode(texts, convert_to_tensor=False)
                return embeddings.tolist()
            except Exception as exc:
                logger.warning(f"embed_texts failed ({exc}); using zero-vector fallbacks")
        return [[0.0] * self.embedding_dim for _ in texts]

    def similarity(self, text1: str, text2: str) -> float:
        """Calculate cosine similarity between two texts."""
        if self.model is not None:
            try:
                # Always use convert_to_tensor=False to get a numpy array —
                # this avoids the torch.Tensor path that requires torch at call-time
                embeddings = self.model.encode(
                    [text1, text2], convert_to_tensor=False
                )
                from sklearn.metrics.pairwise import cosine_similarity as _cos_sim
                matrix = _cos_sim([embeddings[0]], [embeddings[1]])
                return float(matrix[0][0])
            except Exception as exc:
                logger.warning(f"similarity() failed ({exc}); returning 0.0")
        return 0.0
