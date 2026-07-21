import asyncio
from src.memory.knowledge_graph import KnowledgeGraph
from src.memory.vector_store import VectorStore
from src.memory.memory_manager import MemoryManager
from src.core.embeddings import EmbeddingService
from src.core.config import get_settings


async def test_memory_system():
    """Test the complete memory system."""
    
    settings = get_settings()
    
    # Initialize components
    kg = KnowledgeGraph(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password
    )
    
    vs = VectorStore(
        host=settings.qdrant_host,
        port=settings.qdrant_port
    )
    
    embedding_service = EmbeddingService()
    memory_manager = MemoryManager(kg, vs)
    
    print("\n📊 Testing Memory System")
    print("=" * 60)
    
    try:
        # Connect to databases
        await kg.connect()
        await vs.initialize()
        print("✅ Connected to knowledge graph and vector store")
        
        # Test embedding generation
        test_text = "Quantum computing uses quantum bits for processing"
        embedding = embedding_service.embed_text(test_text)
        print(f"✅ Generated embedding with {len(embedding)} dimensions")
        
        # Test storing findings
        finding1 = {
            "claim": "Quantum computers can solve certain problems exponentially faster",
            "source_url": "https://example.com/1",
            "source_title": "Quantum Computing Basics",
            "confidence": 0.9,
            "embedding": embedding,
            "tags": ["quantum", "computing"]
        }
        
        await memory_manager.store_research_finding(
            finding_text=finding1["claim"],
            source_url=finding1["source_url"],
            source_title=finding1["source_title"],
            confidence=finding1["confidence"],
            embedding=finding1["embedding"],
            tags=finding1["tags"]
        )
        print("✅ Stored research finding")
        
        # Test similarity search
        similar_findings = await memory_manager.retrieve_similar_findings(
            query_embedding=embedding,
            max_results=5
        )
        print(f"✅ Found {len(similar_findings)} similar findings")
        
        # Get collection stats
        stats = await vs.get_collection_stats()
        print(f"✅ Vector store stats: {stats}")
        
        print("\n✅ All memory tests passed!")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    finally:
        await kg.disconnect()


if __name__ == "__main__":
    asyncio.run(test_memory_system())