from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List, Dict, Any, Optional
import logging
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


class VectorStore:
    """Manage semantic vectors for research findings."""
    
    def __init__(self, host: str = "localhost", port: int = 6333, embedding_dim: int = 384):
        """Initialize vector store.
        
        Args:
            host: Qdrant host
            port: Qdrant port
            embedding_dim: Embedding dimension
        """
        self.client = AsyncQdrantClient(host=host, port=port)
        self.collection_name = "research_findings"
        self.embedding_dim = embedding_dim
    
    async def initialize(self):
        """Initialize vector store collections."""
        try:
            await self.client.get_collection(self.collection_name)
        except:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created collection: {self.collection_name}")
    
    async def store_finding(
        self,
        finding_text: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> str:
        """Store a finding with its embedding.
        
        Args:
            finding_text: Text of the finding
            embedding: Vector embedding
            metadata: Additional metadata
        
        Returns:
            Point ID
        """
        # Create deterministic ID from finding text
        point_id = int(hashlib.md5(finding_text.encode()).hexdigest(), 16) % (2**31)
        
        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "text": finding_text,
                "source": metadata.get("source_url"),
                "confidence": metadata.get("confidence", 0.0),
                "title": metadata.get("source_title"),
                "timestamp": datetime.utcnow().isoformat(),
                **metadata
            }
        )
        
        await self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        
        return str(point_id)
    
    async def search_similar(
        self,
        query_embedding: List[float],
        limit: int = 5,
        score_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Search for similar findings.
        
        Args:
            query_embedding: Query vector embedding
            limit: Maximum results
            score_threshold: Minimum similarity score
        
        Returns:
            List of similar findings
        """
        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            score_threshold=score_threshold
        )
        
        findings = []
        for result in results:
            findings.append({
                "score": result.score,
                "text": result.payload.get("text"),
                "source": result.payload.get("source"),
                "confidence": result.payload.get("confidence"),
                "title": result.payload.get("title"),
            })
        
        return findings
    
    async def batch_store_findings(
        self,
        findings: List[Dict[str, Any]]
    ):
        """Store multiple findings at once.
        
        Args:
            findings: List of finding dictionaries with 'text' and 'embedding'
        """
        points = []
        
        for finding in findings:
            point_id = int(
                hashlib.md5(finding["text"].encode()).hexdigest(), 16
            ) % (2**31)
            
            point = PointStruct(
                id=point_id,
                vector=finding.get("embedding", []),
                payload={
                    "text": finding.get("text"),
                    "source": finding.get("source_url"),
                    "confidence": finding.get("confidence", 0.0),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            points.append(point)
        
        if points:
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
    
    async def delete_old_findings(self, days_old: int = 30):
        """Delete findings older than specified days.
        
        Args:
            days_old: Delete findings older than this many days
        """
        from datetime import timedelta
        
        cutoff_date = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
        
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector={
                "filter": {
                    "range": {
                        "timestamp": {
                            "lt": cutoff_date
                        }
                    }
                }
            }
        )
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics.
        
        Returns:
            Collection statistics
        """
        collection_info = await self.client.get_collection(
            self.collection_name
        )
        
        return {
            "points_count": collection_info.points_count,
            "vector_size": self.embedding_dim,
            "distance_metric": "cosine",
        }