from datetime import datetime
from typing import Optional
from src.schemas.outputs import ResearchFinding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import hashlib
import json


class ResearchMemory:
    """Memory system for storing and retrieving research findings."""
    
    def __init__(self, qdrant_host: str = "localhost", qdrant_port: int = 6333):
        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.collection_name = "research_findings"
        self.embedding_dim = 384  # For sentence-transformers
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Ensure collection exists, create if not."""
        try:
            self.client.get_collection(self.collection_name)
        except:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
    
    def store_finding(self, finding: ResearchFinding, query_embedding: list[float]):
        """Store a research finding in vector memory."""
        
        # Create unique ID from content hash
        finding_hash = hashlib.md5(
            f"{finding.claim}_{finding.source_url}".encode()
        ).hexdigest()
        point_id = int(finding_hash, 16) % (2**31)
        
        # Create point with metadata
        point = PointStruct(
            id=point_id,
            vector=query_embedding,
            payload={
                "claim": finding.claim,
                "source_url": finding.source_url,
                "source_title": finding.source_title,
                "confidence": finding.confidence,
                "raw_excerpt": finding.raw_excerpt,
                "retrieved_at": finding.retrieved_at.isoformat(),
            }
        )
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point],
        )
    
    def search_similar_findings(
        self,
        query_embedding: list[float],
        limit: int = 5,
        min_confidence: float = 0.5
    ) -> list[dict]:
        """Search for similar findings in memory."""
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
        )
        
        findings = []
        for result in results:
            if result.payload.get("confidence", 0) >= min_confidence:
                findings.append({
                    "score": result.score,
                    "claim": result.payload.get("claim"),
                    "source": result.payload.get("source_title"),
                    "url": result.payload.get("source_url"),
                    "confidence": result.payload.get("confidence"),
                })
        
        return findings
    
    def get_research_history(self, query: str) -> list[dict]:
        """Get research history for a query."""
        # In production, implement semantic search here
        return []