import asyncio
import time
from src.core.state import AetherState
from src.core.graph import aether_workflow, aether_workflow_instance
from src.core.cost_tracker import CostTracker
from src.core.monitoring import ResearchLogger


async def test_full_workflow():
    """Test the complete advanced workflow with all features."""
    
    session_id = f"test_session_{int(time.time() * 1000)}"
    logger = ResearchLogger(session_id)
    cost_tracker = aether_workflow_instance.cost_tracker
    
    # Create initial state
    initial_state: AetherState = {
        "user_query": "What are the latest developments in quantum computing and how do they compare to classical computing for cryptography?",
        "decomposition": None,
        "research_outputs": [],
        "critic_output": None,
        "verifier_output": None,
        "fact_checker_output": None,
        "writer_output": None,
        "messages": [],
        "current_iteration": 0,
        "max_iterations": 3,
        "confidence_scores": {},
        "errors": [],
        "total_cost": 0.0,
        "token_usage": {"input": 0, "output": 0},
        "status": "initialized",
    }
    
    print(f"\n{'='*60}")
    print(f"🔬 STARTING RESEARCH SESSION: {session_id}")
    print(f"{'='*60}")
    print(f"Query: {initial_state['user_query']}\n")
    
    try:
        # Execute workflow
        start_time = time.time()
        result = await aether_workflow.ainvoke(initial_state)
        execution_time = time.time() - start_time
        
        # Print results
        print(f"\n{'='*60}")
        print(f"✅ RESEARCH COMPLETE")
        print(f"{'='*60}\n")
        
        # Decomposition
        if result.get("decomposition"):
            print("📋 Query Decomposition:")
            decomp = result["decomposition"]
            print(f"  Type: {decomp.research_type}")
            print(f"  Complexity: {decomp.estimated_complexity}")
            print(f"  Sub-queries:")
            for idx, sq in enumerate(decomp.sub_queries, 1):
                print(f"    {idx}. {sq}")
        
        # Research findings
        if result.get("research_outputs"):
            print(f"\n🔍 Research Findings ({len(result['research_outputs'])} outputs)")
            for idx, output in enumerate(result["research_outputs"], 1):
                print(f"  {idx}. {output.sub_query}")
                print(f"     - Sources: {output.sources_consulted}")
                print(f"     - Findings: {len(output.findings)}")
        
        # Critic assessment
        if result.get("critic_output"):
            print(f"\n👁️ Critic Assessment: {result['critic_output'].overall_assessment}")
            if result["critic_output"].red_flags:
                print(f"   Red Flags: {len(result['critic_output'].red_flags)}")
        
        # Verification
        if result.get("verifier_output"):
            print(f"\n✔️ Verification Score: {result['verifier_output'].cross_reference_score}/100")
            print(f"   Consensus: {result['verifier_output'].consensus_level}")
        
        # Fact-checking
        if result.get("fact_checker_output"):
            print(f"\n📚 Fact-Check Accuracy: {result['fact_checker_output'].factual_accuracy_score:.1f}%")
        
        # Final report
        if result.get("writer_output"):
            writer = result["writer_output"]
            print(f"\n✍️ Final Report")
            print(f"  Title: {writer.title}")
            print(f"  Confidence: {writer.confidence_score:.1f}%")
            print(f"  Key Findings: {len(writer.key_findings)}")
            print(f"  Citations: {len(writer.citations)}")
        
        # Cost metrics
        print(f"\n💰 Cost Metrics")
        print(f"  Total Cost: ${result.get('total_cost', 0):.4f}")
        total_tokens = cost_tracker.get_total_tokens()
        print(f"  Total Tokens: {total_tokens['total']}")
        print(f"  Execution Time: {execution_time:.2f}s")
        
        # Execution log
        print(f"\n📊 Execution Log")
        print(f"  Events: {len(logger.get_execution_log()['events'])}")
        print(f"  Status: {result.get('status', 'unknown')}")
        
        print(f"\n{'='*60}\n")
        
        return result
    
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        logger.log_error("workflow", str(e))
        raise


if __name__ == "__main__":
    asyncio.run(test_full_workflow())