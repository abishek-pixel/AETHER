from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages
from src.schemas.outputs import (
    QueryDecomposition,
    ResearcherOutput,
    CriticOutput,
    VerifierOutput,
    FactCheckerOutput,
    WriterOutput,
    AgentMessage,
)


def merge_lists(left: list, right: list) -> list:
    """Reducer that merges two lists."""
    return left + right


def update_dict(left: dict, right: dict) -> dict:
    """Reducer that updates a dict."""
    return {**left, **right}


class AetherState(TypedDict):
    """Global state for the Aether multi-agent system."""
    
    # Original query
    user_query: str
    
    # Supervisor decomposition
    decomposition: QueryDecomposition | None
    
    # Research phase
    research_outputs: Annotated[list[ResearcherOutput], merge_lists]
    
    # Critique phase
    critic_output: CriticOutput | None
    
    # Verification phase
    verifier_output: VerifierOutput | None
    
    # Fact-checking phase
    fact_checker_output: FactCheckerOutput | None
    
    # Final output
    writer_output: WriterOutput | None
    
    # Inter-agent communication
    messages: Annotated[list[AgentMessage], merge_lists]
    
    # Iteration tracking
    current_iteration: int
    max_iterations: int
    
    # Confidence tracking
    confidence_scores: Annotated[dict[str, float], update_dict]
    
    # Error handling
    errors: Annotated[list[str], merge_lists]
    
    # Cost tracking
    total_cost: float
    token_usage: dict[str, int]
    
    # Status
    status: str

    # Depth setting (fast | balanced | deep)
    depth: str
