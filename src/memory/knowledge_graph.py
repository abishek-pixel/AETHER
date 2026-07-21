from neo4j import AsyncDriver, AsyncSession
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """Manage research knowledge in Neo4j graph database."""
    
    def __init__(self, uri: str, user: str, password: str):
        """Initialize knowledge graph connection.
        
        Args:
            uri: Neo4j database URI
            user: Database username
            password: Database password
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.driver: Optional[AsyncDriver] = None
    
    async def connect(self):
        """Establish connection to Neo4j."""
        from neo4j import AsyncGraphDatabase
        
        self.driver = AsyncGraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )
        
        await self.driver.verify_connectivity()
        logger.info("Connected to Neo4j knowledge graph")
    
    async def disconnect(self):
        """Close connection to Neo4j."""
        if self.driver:
            await self.driver.close()
    
    async def add_research_finding(
        self,
        claim: str,
        source_url: str,
        source_title: str,
        confidence: float,
        tags: List[str] = None,
    ) -> str:
        """Add a research finding to the knowledge graph.
        
        Args:
            claim: The research finding/claim
            source_url: Source URL
            source_title: Source title
            confidence: Confidence score (0-1)
            tags: Optional tags for categorization
        
        Returns:
            Finding node ID
        """
        query = """
        CREATE (f:Finding {
            claim: $claim,
            source_url: $source_url,
            source_title: $source_title,
            confidence: $confidence,
            created_at: datetime(),
            tags: $tags
        })
        RETURN id(f) as finding_id
        """
        
        async with self.driver.session() as session:
            result = await session.run(
                query,
                claim=claim,
                source_url=source_url,
                source_title=source_title,
                confidence=confidence,
                tags=tags or []
            )
            record = await result.single()
            return record["finding_id"]
    
    async def add_research_query(self, query: str, tags: List[str] = None) -> str:
        """Add a research query node.
        
        Args:
            query: Research query
            tags: Optional tags
        
        Returns:
            Query node ID
        """
        cypher_query = """
        CREATE (q:Query {
            text: $text,
            created_at: datetime(),
            tags: $tags
        })
        RETURN id(q) as query_id
        """
        
        async with self.driver.session() as session:
            result = await session.run(
                cypher_query,
                text=query,
                tags=tags or []
            )
            record = await result.single()
            return record["query_id"]
    
    async def link_finding_to_query(
        self,
        query_id: str,
        finding_id: str,
        relationship_type: str = "FOUND_IN"
    ):
        """Link a finding to a query.
        
        Args:
            query_id: Query node ID
            finding_id: Finding node ID
            relationship_type: Type of relationship
        """
        cypher_query = f"""
        MATCH (q) WHERE id(q) = $query_id
        MATCH (f) WHERE id(f) = $finding_id
        CREATE (q)-[r:{relationship_type}]->(f)
        RETURN r
        """
        
        async with self.driver.session() as session:
            await session.run(
                cypher_query,
                query_id=int(query_id),
                finding_id=int(finding_id)
            )
    
    async def create_concept_relationships(
        self,
        concept1: str,
        concept2: str,
        relationship: str
    ):
        """Create relationships between concepts.
        
        Args:
            concept1: First concept
            concept2: Second concept
            relationship: Type of relationship
        """
        cypher_query = f"""
        MERGE (c1:Concept {{name: $concept1}})
        MERGE (c2:Concept {{name: $concept2}})
        MERGE (c1)-[r:{relationship}]->(c2)
        RETURN r
        """
        
        async with self.driver.session() as session:
            await session.run(
                cypher_query,
                concept1=concept1,
                concept2=concept2
            )
    
    async def find_related_findings(
        self,
        concept: str,
        max_depth: int = 2,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Find related findings for a concept.
        
        Args:
            concept: Concept to search for
            max_depth: Maximum relationship depth
            limit: Maximum results
        
        Returns:
            List of related findings
        """
        cypher_query = f"""
        MATCH (c:Concept {{name: $concept}})
        MATCH (c)-[r*1..{max_depth}]->(finding:Finding)
        RETURN DISTINCT finding.claim as claim,
                         finding.source_url as url,
                         finding.confidence as confidence,
                         length(r) as hops
        LIMIT $limit
        """
        
        async with self.driver.session() as session:
            result = await session.run(
                cypher_query,
                concept=concept,
                limit=limit
            )
            
            findings = []
            async for record in result:
                findings.append({
                    "claim": record["claim"],
                    "url": record["url"],
                    "confidence": record["confidence"],
                    "relationship_depth": record["hops"]
                })
            
            return findings
    
    async def get_research_history(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get history of research on a topic.
        
        Args:
            query: Query to search for
            limit: Maximum results
        
        Returns:
            List of past research sessions
        """
        cypher_query = """
        MATCH (q:Query {text: $query})-[rel]->(f:Finding)
        RETURN q.created_at as query_time,
               f.claim as claim,
               f.confidence as confidence,
               f.source_title as source,
               count(*) as occurrences
        ORDER BY query_time DESC
        LIMIT $limit
        """
        
        async with self.driver.session() as session:
            result = await session.run(
                cypher_query,
                query=query,
                limit=limit
            )
            
            history = []
            async for record in result:
                history.append({
                    "query_time": record["query_time"],
                    "claim": record["claim"],
                    "confidence": record["confidence"],
                    "source": record["source"],
                    "occurrences": record["occurrences"]
                })
            
            return history
    
    async def calculate_topic_authority(
        self,
        topic: str
    ) -> Dict[str, float]:
        """Calculate authority scores for sources on a topic.
        
        Args:
            topic: Topic to analyze
        
        Returns:
            Dictionary of source authorities
        """
        cypher_query = """
        MATCH (f:Finding)-[:COVERS]->(t:Topic {name: $topic})
        WITH f.source_title as source,
             count(*) as frequency,
             avg(f.confidence) as avg_confidence
        RETURN source,
               (frequency * avg_confidence) as authority_score
        ORDER BY authority_score DESC
        """
        
        async with self.driver.session() as session:
            result = await session.run(
                cypher_query,
                topic=topic
            )
            
            authorities = {}
            async for record in result:
                authorities[record["source"]] = record["authority_score"]
            
            return authorities