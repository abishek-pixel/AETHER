"""Embedding service with full lazy loading.

sentence_transformers eagerly imports torch, which takes 30+ seconds on
Render's free tier (slow CPU, 512 MB RAM) and causes the workflow to hang.

This module imports NOTHING heavy at the top level.  The SentenceTransformer
model is loaded the first time embed_text() / embed_texts() is called, which
only happens when memory_manager is set (Neo4j/Qdrant available).  Since
both are unavailable on the current production instance, the model is never
loaded and the zero-vector fallback is used throughout.
"""
from __future__ import annotations

from typing import List
import logging

logger = logging.getLogger(__name__)

# sentinel — set to True once we've attempted the import (success or fail)
_ST_IMPORT_ATTEMPTED = False
_ST_AVAILABLE = False
_SentenceTransformer = None


def _ensure_st_imported() -> bool:
    """Try to import sentence_transformers on first call; return availability."""
    global _ST_IMPORT_ATTEMPTED, _ST_AVAILABLE, _SentenceTransformer
    if _ST_IMPORT_ATTEMPTED:
        return _ST_AVAILABLE
    _ST_IMPORT_ATTEMPTED = True
    try:
        from sentence_transformers import SentenceTransformer as _ST
        _SentenceTransformer = _ST
        _ST_AVAILABLE = True
        logger.info("[INIT] sentence_transformers imported successfully")
    except Exception as exc:
        logger.warning(
            f"[INIT] sentence_transformers not available ({type(exc).__name__}: {exc}). "
            "Falling back to zero-vector embeddings."
        )
        _ST_AVAILABLE = False
    return _ST_AVAILABLE


class EmbeddingService:
    """Generate text embeddings, with graceful zero-vector fallback.

    The singleton pattern ensures the heavy SentenceTransformer model is
    loaded at most once across all agents.
    """

    _instance: EmbeddingService | None = None
    EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 output dimension

    def __new__(cls, model_name: str = "all-MiniLM-L6-v2"):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._initialized = False
            cls._instance = inst
        return cls._instance

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if getattr(self, "_initialized", False):
            return
        self._model_name = model_name
        self.model = None
        self.embedding_dim = self.EMBEDDING_DIM
        self._model_load_attempted = False
        self._initialized = True
        logger.info("[INIT] EmbeddingService created (model load deferred)")

    def _ensure_model(self) -> None:
        """Load the SentenceTransformer model on first encode call."""
        if self._model_load_attempted:
            return
        self._model_load_attempted = True

        if not _ensure_st_imported():
            return  # sentence_transformers unavailable — stay in zero-vector mode

        try:
            logger.info(f"[INIT] Loading SentenceTransformer '{self._model_name}'...")
            self.model = _SentenceTransformer(self._model_name)
            if hasattr(self.model, "get_embedding_dimension"):
                self.embedding_dim = self.model.get_embedding_dimension()
            else:
                self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(
                f"[INIT] SentenceTransformer loaded (dim={self.embedding_dim})"
            )
        except Exception as exc:
            logger.warning(
                f"[INIT] SentenceTransformer load failed "
                f"({type(exc).__name__}: {exc}). "
                "Using zero-vector fallback."
            )
            self.model = None

    # ── Public API ────────────────────────────────────────────────────────

    def embed_text(self, text: str) -> List[float]:
        """Return embedding for text, or a zero-vector if model unavailable."""
        self._ensure_model()
        if self.model is not None:
            try:
                return self.model.encode(text, convert_to_tensor=False).tolist()
            except Exception as exc:
                logger.warning(f"embed_text failed ({exc}); using zero-vector")
        return [0.0] * self.embedding_dim

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Return embeddings for multiple texts, or zero-vectors."""
        self._ensure_model()
        if self.model is not None:
            try:
                return self.model.encode(texts, convert_to_tensor=False).tolist()
            except Exception as exc:
                logger.warning(f"embed_texts failed ({exc}); using zero-vectors")
        return [[0.0] * self.embedding_dim for _ in texts]

    def similarity(self, text1: str, text2: str) -> float:
        """Cosine similarity between two texts, or 0.0 if model unavailable."""
        self._ensure_model()
        if self.model is not None:
            try:
                import numpy as _np
                from sklearn.metrics.pairwise import cosine_similarity as _cos
                embs = self.model.encode([text1, text2], convert_to_tensor=False)
                return float(_cos([embs[0]], [embs[1]])[0][0])
            except Exception as exc:
                logger.warning(f"similarity() failed ({exc}); returning 0.0")
        return 0.0
