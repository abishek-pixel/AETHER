from src.memory.knowledge_graph import KnowledgeGraph
from src.memory.vector_store import VectorStore
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manage all research memory operations."""
    
    def __init__(
        self,
        kg: KnowledgeGraph,
        vs: VectorStore
    ):
        """Initialize memory manager.
        
        Args:
            kg: Knowledge graph instance
            vs: Vector store instance
        """
        self.knowledge_graph = kg
        self.vector_store = vs
    
    async def store_research_finding(
        self,
        finding_text: str,
        source_url: str,
        source_title: str,
        confidence: float,
        embedding: List[float],
        tags: List[str] = None
    ):
        """Store finding in both knowledge graph and vector store.
        
        Args:
            finding_text: The research finding
            source_url: Source URL
            source_title: Source title
            confidence: Confidence score
            embedding: Vector embedding
            tags: Optional tags
        """
        # Store in knowledge graph
        finding_id = await self.knowledge_graph.add_research_finding(
            claim=finding_text,
            source_url=source_url,
            source_title=source_title,
            confidence=confidence,
            tags=tags
        )
        
        # Store in vector database
        await self.vector_store.store_finding(
            finding_text=finding_text,
            embedding=embedding,
            metadata={
                "source_url": source_url,
                "source_title": source_title,
                "confidence": confidence,
                "kg_id": finding_id,
                "tags": tags or []
            }
        )
        
        logger.info(f"Stored finding: {finding_text[:100]}...")
    
    async def retrieve_similar_findings(
        self,
        query_embedding: List[float],
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve similar past findings using vector search.
        
        Args:
            query_embedding: Query vector
            max_results: Maximum results
        
        Returns:
            List of similar findings
        """
        return await self.vector_store.search_similar(
            query_embedding=query_embedding,
            limit=max_results,
            score_threshold=0.5
        )
    
    async def get_topic_context(
        self,
        topic: str,
        max_findings: int = 10
    ) -> Dict[str, Any]:
        """Get comprehensive context for a topic.
        
        Args:
            topic: Topic to analyze
            max_findings: Maximum findings to retrieve
        
        Returns:
            Topic context including findings and authorities
        """
        # Get related findings from knowledge graph
        related = await self.knowledge_graph.find_related_findings(
            concept=topic,
            limit=max_findings
        )
        
        # Get authority scores
        authorities = await self.knowledge_graph.calculate_topic_authority(
            topic=topic
        )
        
        return {
            "topic": topic,
            "related_findings": related,
            "source_authorities": authorities,
            "total_findings": len(related),
        }
    
    async def track_research_session(
        self,
        query: str,
        findings: List[Dict[str, Any]],
        tags: List[str] = None
    ):
        """Track a complete research session.
        
        Args:
            query: Research query
            findings: List of findings from session
            tags: Session tags
        """
        # Add query node
        query_id = await self.knowledge_graph.add_research_query(
            query=query,
            tags=tags
        )
        
        # Link each finding to the query
        for finding in findings:
            finding_id = await self.knowledge_graph.add_research_finding(
                claim=finding.get("claim"),
                source_url=finding.get("source_url"),
                source_title=finding.get("source_title"),
                confidence=finding.get("confidence", 0.5),
                tags=finding.get("tags")
            )
            
            await self.knowledge_graph.link_finding_to_query(
                query_id=str(query_id),
                finding_id=str(finding_id),
                relationship_type="FOUND_IN"
            )