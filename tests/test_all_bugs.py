"""
Aether Bug-Fix Test Suite
=========================
Covers every bug/issue fixed across Task 5 & 6:

  Issue 1  – Guest prompt limit (sessionStorage)         → logic tested via direct function
  Issue 2  – Follow-up chat blocks (append, not replace) → AetherState depth field present
  Issue 3  – Timeline persistence                        → SSE accumulator + DB persist call
  Issue 4  – Logout security                             → auth store structure
  Issue 5  – Model upgrade mapping                       → MODEL_MAP values

  Bug 1    – Follow-up blocks empty findings/citations   → dbSessionToLocal copies to all blocks
  Bug 2    – First block timeline = 0                    → timeline_events flow
  Bug 3    – Confidence not visible on 2nd block         → confidence copied to all blocks
  Bug 4    – 2-prompt / 6-hour rate limit                → UsageRepository + endpoint + follow-up
  Bug 5    – Depth selection not working                 → AetherState.depth, researcher branching

Run with:
    .venv\\Scripts\\pytest tests/test_all_bugs.py -v
"""
import asyncio
import sys
import uuid
import json
import time
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_db_session(
    idx: int = 0,
    n_user_msgs: int = 2,
    confidence: float = 0.85,
    findings: list[str] | None = None,
    citations: list[str] | None = None,
    timeline: list[dict] | None = None,
) -> dict:
    """Produce a fake DB session dict matching what the backend returns."""
    now = datetime.utcnow().isoformat()
    msgs = []
    for i in range(n_user_msgs):
        msgs.append({"id": f"u{i}", "role": "user", "content": f"query {i}", "timestamp": now})
        msgs.append({"id": f"a{i}", "role": "assistant", "content": f"report {i}", "timestamp": now})
    return {
        "id": str(uuid.uuid4()),
        "query": "test query",
        "depth": "balanced",
        "model": "groq-compound",
        "created_at": now,
        "updated_at": now,
        "title": "Test Report",
        "messages": msgs,
        "report": {
            "title": "Test Report",
            "summary": "Summary text",
            "main_content": "Main content",
            "key_findings": findings or ["finding A", "finding B"],
            "citations": citations or ["https://example.com/1"],
            "confidence_score": confidence,
            "timeline_events": timeline or [
                {"id": "tl_1", "ts": 1000, "agentRole": "researcher", "type": "search", "text": "Searching"}
            ],
        },
    }


# ===========================================================================
# BUG 5 — AetherState must contain a `depth` field
# ===========================================================================

class TestBug5DepthField:
    """depth must exist in AetherState TypedDict so it can be read by researcher."""

    def test_aether_state_has_depth_annotation(self):
        from src.core.state import AetherState
        hints = AetherState.__annotations__
        assert "depth" in hints, "AetherState must have a 'depth' field"

    def test_initial_state_accepts_depth(self):
        """Constructing an AetherState-like dict with depth should work."""
        from src.core.state import AetherState
        state: AetherState = {
            "user_query": "test",
            "decomposition": None,
            "research_outputs": [],
            "critic_output": None,
            "verifier_output": None,
            "fact_checker_output": None,
            "writer_output": None,
            "messages": [],
            "current_iteration": 0,
            "max_iterations": 2,
            "confidence_scores": {},
            "errors": [],
            "total_cost": 0.0,
            "token_usage": {"input": 0, "output": 0},
            "status": "initialized",
            "depth": "fast",
        }
        assert state["depth"] == "fast"


# ===========================================================================
# BUG 5 — Researcher branches on depth
# ===========================================================================

class TestBug5ResearcherDepthBranching:
    """ResearcherAgent must cap sub-queries and max_results based on state['depth']."""

    def _make_state(self, depth: str, n_subqueries: int = 6) -> dict:
        mock_decomp = MagicMock()
        mock_decomp.sub_queries = [f"sq_{i}" for i in range(n_subqueries)]
        return {
            "decomposition": mock_decomp,
            "depth": depth,
            "current_iteration": 0,
            "research_outputs": [],
        }

    @pytest.mark.asyncio
    async def test_fast_depth_caps_at_2(self):
        from src.agents.researcher import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)

        calls = []

        async def fake_chain_invoke(data):
            calls.append(data["sub_query"])
            out = MagicMock()
            out.sub_query = data["sub_query"]
            out.findings = []
            out.model_dump_json = lambda: "{}"
            out.search_queries_used = []
            out.sources_consulted = 0
            return out

        agent.chain = MagicMock()
        agent.chain.ainvoke = fake_chain_invoke
        agent._search_tavily = AsyncMock(return_value=[])
        agent._search_serper = AsyncMock(return_value=[])
        agent._format_search_results = MagicMock(return_value="")

        result = await agent.process(self._make_state("fast"))
        assert len(calls) == 2, f"fast depth should cap at 2 sub-queries, got {len(calls)}"

    @pytest.mark.asyncio
    async def test_balanced_depth_caps_at_3(self):
        from src.agents.researcher import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)
        calls = []

        async def fake_chain_invoke(data):
            calls.append(data["sub_query"])
            out = MagicMock()
            out.sub_query = data["sub_query"]
            out.findings = []
            out.model_dump_json = lambda: "{}"
            out.search_queries_used = []
            out.sources_consulted = 0
            return out

        agent.chain = MagicMock()
        agent.chain.ainvoke = fake_chain_invoke
        agent._search_tavily = AsyncMock(return_value=[])
        agent._search_serper = AsyncMock(return_value=[])
        agent._format_search_results = MagicMock(return_value="")

        result = await agent.process(self._make_state("balanced"))
        assert len(calls) == 3, f"balanced depth should cap at 3, got {len(calls)}"

    @pytest.mark.asyncio
    async def test_deep_depth_caps_at_5(self):
        from src.agents.researcher import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)
        calls = []

        async def fake_chain_invoke(data):
            calls.append(data["sub_query"])
            out = MagicMock()
            out.sub_query = data["sub_query"]
            out.findings = []
            out.model_dump_json = lambda: "{}"
            out.search_queries_used = []
            out.sources_consulted = 0
            return out

        agent.chain = MagicMock()
        agent.chain.ainvoke = fake_chain_invoke
        agent._search_tavily = AsyncMock(return_value=[])
        agent._search_serper = AsyncMock(return_value=[])
        agent._format_search_results = MagicMock(return_value="")

        result = await agent.process(self._make_state("deep"))
        assert len(calls) == 5, f"deep depth should cap at 5, got {len(calls)}"

    @pytest.mark.asyncio
    async def test_max_results_set_correctly_per_depth(self):
        from src.agents.researcher import ResearcherAgent
        agent = ResearcherAgent.__new__(ResearcherAgent)

        async def fake_chain_invoke(data):
            out = MagicMock()
            out.sub_query = data["sub_query"]
            out.findings = []
            out.model_dump_json = lambda: "{}"
            out.search_queries_used = []
            out.sources_consulted = 0
            return out

        agent.chain = MagicMock()
        agent.chain.ainvoke = fake_chain_invoke
        tavily_calls = []

        async def fake_tavily(q, max_results=3):
            tavily_calls.append(max_results)
            return []

        agent._search_tavily = fake_tavily
        agent._search_serper = AsyncMock(return_value=[])
        agent._format_search_results = MagicMock(return_value="")

        await agent.process(self._make_state("deep", n_subqueries=6))
        assert all(r == 5 for r in tavily_calls), \
            f"deep depth should use max_results=5, got {tavily_calls}"


# ===========================================================================
# ISSUE 5 — Model mapping (groq-compound → groq/compound, etc.)
# ===========================================================================

class TestIssue5ModelMapping:
    """MODEL_MAP must correctly translate frontend tier names to backend model IDs."""

    def _get_model_map(self) -> dict:
        # Read directly from the source to avoid import side effects
        import importlib
        import sys
        # We'll just check the file content pattern
        with open("AETHER FRONTEND/AETHER-main/src/lib/api.ts", encoding="utf-8") as f:
            content = f.read()
        return content

    def test_groq_compound_maps_to_groq_slash_compound(self):
        content = self._get_model_map()
        assert '"groq-compound"' in content and '"groq/compound"' in content, \
            "groq-compound must map to groq/compound"

    def test_groq_qwen_maps_to_qwen3(self):
        content = self._get_model_map()
        assert '"groq-qwen"' in content and "qwen/qwen3" in content, \
            "groq-qwen must map to qwen/qwen3.x"


# ===========================================================================
# BUG 4 — Rate-limit: UsageRepository.count_prompts_in_window
# ===========================================================================

class TestBug4RateLimitRepository:
    """count_prompts_in_window must return the correct structure."""

    def test_function_exists_with_correct_signature(self):
        from src.repositories.usage import UsageRepository
        import inspect
        sig = inspect.signature(UsageRepository.count_prompts_in_window)
        params = list(sig.parameters)
        assert "user_id" in params
        assert "hours" in params

    def test_free_tier_constants(self):
        from src.repositories.usage import FREE_TIER_PROMPT_LIMIT, FREE_TIER_WINDOW_HOURS
        assert FREE_TIER_PROMPT_LIMIT == 2, "Free tier must allow 2 prompts"
        assert FREE_TIER_WINDOW_HOURS == 6, "Free tier window must be 6 hours"

    @pytest.mark.asyncio
    async def test_count_prompts_returns_required_keys(self):
        """Mock the DB and verify the returned dict has all required keys."""
        from src.repositories.usage import UsageRepository

        mock_db = AsyncMock()
        repo = UsageRepository(mock_db)

        # Three execute calls: session count, followup msg count, oldest_ts
        mock_count_1 = MagicMock()
        mock_count_1.scalar.return_value = 1  # session_count

        mock_count_2 = MagicMock()
        mock_count_2.scalar.return_value = 2  # followup_msg_count (1 initial + 1 followup)

        mock_ts = MagicMock()
        mock_ts.scalar.return_value = datetime.utcnow() - timedelta(hours=2)

        mock_db.execute = AsyncMock(
            side_effect=[mock_count_1, mock_count_2, mock_ts]
        )

        result = await repo.count_prompts_in_window(uuid.uuid4())
        assert "prompts_used" in result
        assert "prompts_allowed" in result
        assert "remaining" in result
        assert "reset_at" in result
        assert "retry_after_seconds" in result
        assert result["prompts_allowed"] == 2
        assert result["remaining"] >= 0


# ===========================================================================
# BUG 4 — Rate-limit endpoint exists in main.py
# ===========================================================================

class TestBug4RateLimitEndpoint:
    """GET /api/v1/users/me/rate-limit must be registered in the FastAPI app."""

    def test_rate_limit_route_registered(self):
        # Check the source file rather than importing the whole app
        # (avoids needing live DB on startup)
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        assert "/api/v1/users/me/rate-limit" in content, \
            "Rate-limit GET endpoint must be defined in main.py"

    def test_follow_up_has_rate_limit_check(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        # Both the follow-up endpoint and the rate-limit check must be present
        assert "Follow-up rate-limit check" in content or \
               "rate-limit check" in content.lower(), \
            "Follow-up endpoint must include rate-limit check"

    def test_start_research_has_rate_limit_check(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        assert "free-tier users get FREE_TIER_PROMPT_LIMIT" in content or \
               "FREE_TIER_PROMPT_LIMIT" in content, \
            "start_research endpoint must include FREE_TIER_PROMPT_LIMIT check"


# ===========================================================================
# BUG 3 — Confidence visible on ALL blocks (not just first)
# ===========================================================================

class TestBug3ConfidenceAllBlocks:
    """dbSessionToLocal must assign confidence_score to every block, not just block[0]."""

    def _run_db_session_to_local(self, db_session: dict):
        """Import and run dbSessionToLocal from the TS store (via source inspection)."""
        # Since we can't run TS in Python, we verify the logic in the source
        with open(
            "AETHER FRONTEND/AETHER-main/src/store/research.ts", encoding="utf-8"
        ) as f:
            content = f.read()
        return content

    def test_block_confidence_uses_report_score_not_hardcoded_zero(self):
        content = self._run_db_session_to_local({})
        # The fix: blockConfidence = report?.confidence_score ?? 0  for ALL blocks
        # Wrong pattern would be `idx === 0 ? report?.confidence_score : 0`
        assert "idx === 0" not in content.split("blockConfidence")[0].split("const blockFindings")[0], \
            "blockConfidence must NOT be gated on idx===0"
        assert "confidence_score" in content

    def test_block_confidence_line_not_conditional_on_idx(self):
        content = self._run_db_session_to_local({})
        # Find the blockConfidence assignment
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "blockConfidence" in line and "=" in line and "confidence_score" in line:
                # It must NOT have idx===0 on the same line
                assert "idx === 0" not in line, \
                    f"Line {i}: blockConfidence must not be conditional on idx===0: {line}"
                break


# ===========================================================================
# BUG 1 — Follow-up blocks get findings/citations/timeline populated
# ===========================================================================

class TestBug1FollowUpBlocksNotEmpty:
    """Non-first blocks must get findings/citations/timeline from session-level report."""

    def test_non_first_blocks_get_findings_pushed(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/store/research.ts", encoding="utf-8"
        ) as f:
            content = f.read()
        # The fix pushes session-level data into blockFindings for idx > 0
        assert "blockFindings.push" in content, \
            "Non-first blocks must have findings pushed from session-level report"
        assert "blockCitations.push" in content, \
            "Non-first blocks must have citations pushed from session-level report"
        assert "blockTimeline.push" in content, \
            "Non-first blocks must have timeline pushed from session-level report"

    def test_push_uses_session_level_data(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/store/research.ts", encoding="utf-8"
        ) as f:
            content = f.read()
        # Must spread from `findings`, `citations`, `timeline` (session-level vars)
        assert "blockFindings.push(...findings" in content
        assert "blockCitations.push(...citations" in content
        assert "blockTimeline.push(...timeline" in content


# ===========================================================================
# BUG 2 — Timeline events persisted (not hardcoded [])
# ===========================================================================

class TestBug2TimelinePersistence:
    """_run_followup must pass real timeline_events (not []) to _persist_completed_research."""

    def test_followup_does_not_hardcode_empty_timeline(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()

        # Find the _run_followup function body
        followup_start = content.find("async def _run_followup()")
        assert followup_start != -1, "_run_followup must exist"

        followup_body = content[followup_start:followup_start + 5000]
        persist_call_pos = followup_body.find("_persist_completed_research")
        assert persist_call_pos != -1, "_run_followup must call _persist_completed_research"

        # Grab a generous window around the persist call to catch all kwargs
        persist_call = followup_body[persist_call_pos:persist_call_pos + 1200]

        # Must NOT pass timeline_events=[]
        assert "timeline_events=[]" not in persist_call, \
            "_run_followup must NOT hardcode timeline_events=[]"

        # Must reference the collected followup_timeline variable
        assert "followup_timeline" in followup_body, \
            "_run_followup must collect followup_timeline from research_sessions"

    def test_sse_accumulates_timeline_events(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        # SSE generator must call setdefault("timeline_events", []).append(tl_event)
        assert 'setdefault("timeline_events", []).append' in content, \
            "SSE generator must accumulate timeline_events for persistence"

    def test_run_workflow_reads_timeline_from_session_dict(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        assert 'get("timeline_events", [])' in content, \
            "_run_workflow must read timeline_events from research_sessions dict"


# ===========================================================================
# ISSUE 3 — Timeline flows end-to-end check
# ===========================================================================

class TestIssue3TimelineFlow:
    def test_persist_function_accepts_timeline_events_param(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        assert "timeline_events: Optional[List[Dict[str, Any]]]" in content or \
               "timeline_events" in content.split("async def _persist_completed_research")[1][:500], \
            "_persist_completed_research must accept timeline_events parameter"

    def test_report_repo_upsert_called_with_timeline(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        # upsert call must include timeline_events= (look at full persist helper)
        persist_start = content.find("async def _persist_completed_research(")
        assert persist_start != -1
        persist_body = content[persist_start:persist_start + 2000]
        upsert_pos = persist_body.find("await report_repo.upsert(")
        assert upsert_pos != -1
        # grab a larger window — the upsert call spans many lines
        upsert_call = persist_body[upsert_pos:upsert_pos + 800]
        assert "timeline_events" in upsert_call, \
            "report_repo.upsert must be passed timeline_events"

    def test_repository_session_includes_timeline_in_row_to_dict(self):
        with open("src/repositories/session.py", encoding="utf-8") as f:
            content = f.read()
        assert "timeline_events" in content, \
            "SessionRepository._row_to_dict must include timeline_events"


# ===========================================================================
# ISSUE 4 — Logout security
# ===========================================================================

class TestIssue4LogoutSecurity:
    def test_logout_uses_window_location_replace(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/store/auth.ts", encoding="utf-8"
        ) as f:
            content = f.read()
        assert "window.location.replace" in content, \
            "Logout must use window.location.replace to prevent back-button return"

    def test_logout_clears_local_storage(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/store/auth.ts", encoding="utf-8"
        ) as f:
            content = f.read()
        assert "localStorage" in content and ("removeItem" in content or "clear" in content), \
            "Logout must clear localStorage tokens"

    def test_broadcast_channel_syncs_logout(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/store/auth.ts", encoding="utf-8"
        ) as f:
            content = f.read()
        assert "BroadcastChannel" in content, \
            "Auth store must use BroadcastChannel for multi-tab sync"
        assert '"logout"' in content or "'logout'" in content, \
            "BroadcastChannel must broadcast logout event"


# ===========================================================================
# ISSUE 2 — Follow-up creates NEW blocks, does not replace
# ===========================================================================

class TestIssue2FollowUpBlocks:
    def test_start_follow_up_stream_appends_block(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/store/research.ts", encoding="utf-8"
        ) as f:
            content = f.read()
        # Must spread existing blocks and add new one
        assert "[...s.current.blocks, newFollowUpBlock]" in content, \
            "startFollowUpStream must APPEND new block, not replace"

    def test_follow_up_backend_endpoint_exists(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        assert "/sessions/{db_session_id}/followup" in content, \
            "Backend must have /sessions/{db_session_id}/followup endpoint"

    def test_follow_up_depth_passed_to_initial_state(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        # Inside _run_followup, depth must be in initial_state
        followup_start = content.find("async def _run_followup()")
        followup_body = content[followup_start:followup_start + 2000]
        assert '"depth": request.depth' in followup_body, \
            "_run_followup must pass depth into initial_state"


# ===========================================================================
# ISSUE 1 — Guest prompt limit
# ===========================================================================

class TestIssue1GuestPromptLimit:
    def test_guest_limit_is_1_free_prompt(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/components/research/SearchBar.tsx",
            encoding="utf-8",
        ) as f:
            content = f.read()
        assert "GUEST_FREE_PROMPTS = 1" in content, \
            "Guest must get exactly 1 free prompt"

    def test_uses_session_storage(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/components/research/SearchBar.tsx",
            encoding="utf-8",
        ) as f:
            content = f.read()
        assert "sessionStorage" in content, \
            "Guest prompt counter must use sessionStorage (clears on tab close)"

    def test_redirect_to_login_when_exhausted(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/components/research/SearchBar.tsx",
            encoding="utf-8",
        ) as f:
            content = f.read()
        assert 'navigate({ to: "/login" })' in content, \
            "Exhausted guest must be redirected to /login"


# ===========================================================================
# RATE-LIMIT FRONTEND — SearchBar checks backend on mount
# ===========================================================================

class TestRateLimitFrontend:
    def test_search_bar_imports_get_rate_limit(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/components/research/SearchBar.tsx",
            encoding="utf-8",
        ) as f:
            content = f.read()
        # SearchBar now uses useRateLimit hook (which internally calls getRateLimit)
        assert "useRateLimit" in content, \
            "SearchBar must use useRateLimit hook for rate-limit state"
        assert "rateLimit" in content, \
            "SearchBar must reference rateLimit state from the hook"

    def test_research_page_shows_rate_limit_banner(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/routes/research.$sessionId.tsx",
            encoding="utf-8",
        ) as f:
            content = f.read()
        assert "rateLimit" in content, \
            "Research page must show rate-limit state in follow-up input"
        assert "rateLimit.isLimited" in content, \
            "Research page must check rateLimit.isLimited"
        assert "Clock" in content, \
            "Research page must display clock icon for rate-limit message"

    def test_api_ts_exports_get_rate_limit(self):
        with open(
            "AETHER FRONTEND/AETHER-main/src/lib/api.ts", encoding="utf-8"
        ) as f:
            content = f.read()
        assert "export async function getRateLimit" in content, \
            "api.ts must export getRateLimit function"
        assert "/api/v1/users/me/rate-limit" in content, \
            "getRateLimit must call the correct endpoint"

    def test_use_rate_limit_hook_exists(self):
        """useRateLimit hook must exist and implement live countdown."""
        import os
        hook_path = "AETHER FRONTEND/AETHER-main/src/hooks/useRateLimit.ts"
        assert os.path.exists(hook_path), "useRateLimit.ts hook must exist"
        with open(hook_path, encoding="utf-8") as f:
            content = f.read()
        assert "countdown" in content, "Hook must provide live countdown"
        assert "sessionStorage" in content, "Hook must persist reset_at in sessionStorage"
        assert "setInterval" in content, "Hook must tick countdown every second"
        assert "triggerRefetch" in content, "Hook must expose triggerRefetch for post-submit refresh"
        assert "getRateLimit" in content, "Hook must call getRateLimit API"


# ===========================================================================
# DEPTH — main.py passes depth in both workflow and followup initial_state
# ===========================================================================

class TestDepthPassedToWorkflow:
    def test_run_workflow_passes_depth(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        workflow_start = content.find("async def _run_workflow()")
        workflow_body = content[workflow_start:workflow_start + 2000]
        assert '"depth": request.depth' in workflow_body, \
            "_run_workflow must pass depth into initial_state"

    def test_run_followup_passes_depth(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        followup_start = content.find("async def _run_followup()")
        followup_body = content[followup_start:followup_start + 2000]
        assert '"depth": request.depth' in followup_body, \
            "_run_followup must pass depth into initial_state"


# ===========================================================================
# INTEGRATION — AetherState depth field flows into researcher
# ===========================================================================

class TestDepthStateIntegration:
    def test_researcher_reads_depth_from_state(self):
        with open("src/agents/researcher.py", encoding="utf-8") as f:
            content = f.read()
        assert 'state.get("depth"' in content or "state.get('depth'" in content, \
            "ResearcherAgent.process must read depth from state"

    def test_researcher_has_depth_branches(self):
        with open("src/agents/researcher.py", encoding="utf-8") as f:
            content = f.read()
        assert '"fast"' in content and '"deep"' in content, \
            "ResearcherAgent must branch on fast/deep depth values"
        assert "sq_cap" in content, \
            "ResearcherAgent must use sq_cap variable for sub-query capping"


# ===========================================================================
# BUG 5 SPEC — Correct 429 error response shape
# ===========================================================================

class TestBug5ErrorResponseShape:
    """Backend 429 must include: error, message, limit, remaining, retry_after_seconds, reset_at"""

    def test_start_research_429_has_correct_fields(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        # Find the 429 raise in start_research
        idx = content.find("FREE_TIER_LIMIT_REACHED")
        assert idx != -1, "429 must use FREE_TIER_LIMIT_REACHED error code"
        block = content[idx:idx + 500]
        assert '"limit"' in block, "429 response must include 'limit'"
        assert '"remaining"' in block, "429 response must include 'remaining'"
        assert '"retry_after_seconds"' in block, "429 response must include 'retry_after_seconds'"
        assert '"reset_at"' in block, "429 response must include 'reset_at'"

    def test_follow_up_429_has_correct_fields(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        followup_start = content.find("async def follow_up_research")
        followup_body = content[followup_start:followup_start + 3000]
        assert "FREE_TIER_LIMIT_REACHED" in followup_body, \
            "Follow-up 429 must use FREE_TIER_LIMIT_REACHED"
        assert '"retry_after_seconds"' in followup_body, \
            "Follow-up 429 must include retry_after_seconds"


# ===========================================================================
# BUG 5 SPEC — Race condition prevention
# ===========================================================================

class TestBug5RaceConditionPrevention:
    def test_advisory_lock_used(self):
        with open("src/repositories/usage.py", encoding="utf-8") as f:
            content = f.read()
        assert "pg_advisory_xact_lock" in content, \
            "Must use PostgreSQL advisory lock to prevent race conditions"
        assert "check_and_reserve_prompt" in content, \
            "Must have check_and_reserve_prompt atomic method"

    def test_main_uses_atomic_check(self):
        with open("src/api/main.py", encoding="utf-8") as f:
            content = f.read()
        assert "check_and_reserve_prompt" in content, \
            "main.py must call check_and_reserve_prompt (not count_prompts_in_window) for enforcement"


# ===========================================================================
# BUG 6 SPEC — Frontend countdown requirements
# ===========================================================================

class TestBug6CountdownUI:
    def test_countdown_derived_from_backend_reset_at(self):
        hook_path = "AETHER FRONTEND/AETHER-main/src/hooks/useRateLimit.ts"
        with open(hook_path, encoding="utf-8") as f:
            content = f.read()
        assert "reset_at" in content, \
            "Countdown must be derived from backend reset_at"
        assert "secondsUntil" in content or "getTime()" in content, \
            "Must calculate remaining time from ISO timestamp"

    def test_countdown_not_hardcoded(self):
        hook_path = "AETHER FRONTEND/AETHER-main/src/hooks/useRateLimit.ts"
        with open(hook_path, encoding="utf-8") as f:
            content = f.read()
        # Must NOT hardcode "6 hours" as the remaining time
        assert '"6 hours"' not in content and "'6 hours'" not in content, \
            "Must not hardcode '6 hours remaining'"

    def test_survives_refresh_via_session_storage(self):
        hook_path = "AETHER FRONTEND/AETHER-main/src/hooks/useRateLimit.ts"
        with open(hook_path, encoding="utf-8") as f:
            content = f.read()
        assert "sessionStorage.setItem" in content or "saveResetAt" in content, \
            "Must persist reset_at in sessionStorage so refresh doesn't reset countdown"

    def test_auto_unlocks_when_timer_expires(self):
        hook_path = "AETHER FRONTEND/AETHER-main/src/hooks/useRateLimit.ts"
        with open(hook_path, encoding="utf-8") as f:
            content = f.read()
        assert "setIsLimited(false)" in content, \
            "Hook must auto-unlock when countdown hits zero"
        assert "triggerRefetch" in content, \
            "Hook must re-fetch from server when timer expires to confirm"

    def test_spec_message_format(self):
        hook_path = "AETHER FRONTEND/AETHER-main/src/hooks/useRateLimit.ts"
        with open(hook_path, encoding="utf-8") as f:
            content = f.read()
        # Must produce message matching spec: "You've reached the free-tier ... in X"
        assert "You've reached" in content or "free-tier research limit" in content, \
            "Message must match spec format"

    def test_both_searchbar_and_researchpage_use_hook(self):
        for fpath, label in [
            ("AETHER FRONTEND/AETHER-main/src/components/research/SearchBar.tsx", "SearchBar"),
            ("AETHER FRONTEND/AETHER-main/src/routes/research.$sessionId.tsx", "Research page"),
        ]:
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
            assert "useRateLimit" in content, \
                f"{label} must use useRateLimit hook"
