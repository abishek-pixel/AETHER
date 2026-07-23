"""
Integration test — Diagnostic Task 8
Reproduces the production research lifecycle to verify:
  1. POST /api/v1/research succeeds and returns a session_id
  2. The background workflow actually starts
  3. At least one agent event is logged (supervisor → researcher → ...)
  4. The session transitions out of "running" within a timeout
  5. The stream endpoint emits at least one SSE event
  6. The workflow completes (or fails with an explicit error) — never stays "idle"

Run with:
    pytest tests/test_research_lifecycle.py -v

Environment variables required:
  GROQ_API_KEY, TAVILY_API_KEY, SERPER_API_KEY, DATABASE_URL (or defaults)

To run offline / without real API keys the test mocks the external calls.
"""
import asyncio
import json
import os
import time
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure minimum env vars before importing the app
os.environ.setdefault("GROQ_API_KEY",   os.environ.get("GROQ_API_KEY",   "gsk_test_placeholder"))
os.environ.setdefault("TAVILY_API_KEY", os.environ.get("TAVILY_API_KEY", "tvly-test"))
os.environ.setdefault("SERPER_API_KEY", os.environ.get("SERPER_API_KEY", "serper_test"))
os.environ.setdefault("DATABASE_URL",   os.environ.get("DATABASE_URL",   "postgresql+asyncpg://postgres:password@localhost:5432/aether_test"))
os.environ.setdefault("ENVIRONMENT",    "development")
os.environ.setdefault("SECRET_KEY",     "test_secret_key_32_chars_minimum_xx")

# ── FastAPI test client ────────────────────────────────────────────────────
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIMPLE_QUERY = "Tell me about teleportation"
POST_TIMEOUT = 10   # seconds for the POST itself to return
WORKFLOW_POLL_TIMEOUT = 90  # seconds to wait for workflow to leave "running"
SSE_WAIT_TIMEOUT = 15  # seconds to wait for first SSE event


# ---------------------------------------------------------------------------
# Shared DB + startup mock (applied module-wide)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="module")
def mock_db_startup():
    """
    Patch out all database I/O during tests so we don't need a real PostgreSQL.
    """
    with (
        patch("src.database.session.init_db", new_callable=AsyncMock),
        patch("src.database.session.AsyncSessionLocal", MagicMock()),
        patch("src.repositories.session.SessionRepository.create", new_callable=AsyncMock,
              return_value={"id": "00000000-0000-0000-0000-000000000001"}),
        patch("src.repositories.session.SessionRepository.update_status", new_callable=AsyncMock),
        patch("src.repositories.message.MessageRepository.create", new_callable=AsyncMock),
        patch("src.repositories.report.ReportRepository.upsert", new_callable=AsyncMock),
        patch("src.repositories.usage.UsageRepository.log", new_callable=AsyncMock),
        patch("src.memory.knowledge_graph.KnowledgeGraph.connect",
              new_callable=AsyncMock,
              side_effect=Exception("Neo4j unavailable in tests")),
        patch("src.memory.vector_store.VectorStore.initialize",
              new_callable=AsyncMock,
              side_effect=Exception("Qdrant unavailable in tests")),
    ):
        yield


# ---------------------------------------------------------------------------
# Test 1 — POST returns 200 and a session_id immediately
# ---------------------------------------------------------------------------

class TestPostReturns200:
    """Verify the POST endpoint returns quickly with a session placeholder."""

    def test_post_returns_immediately(self):
        """POST /api/v1/research must return HTTP 200 with status='running' immediately.
        
        Note: TestClient executes background tasks synchronously before returning,
        so we only verify the response shape here, not timing.
        The session status will be 'running' at the time of response.
        """
        from src.api.main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/v1/research",
                json={
                    "query": SIMPLE_QUERY,
                    "depth": "fast",
                    "model": "groq/compound",
                    "max_iterations": 1,
                },
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        data = resp.json()
        assert "session_id" in data, "Response must contain session_id"
        assert data["session_id"], "session_id must not be empty"
        # The placeholder is created before background task runs
        assert "status" in data, "Response must contain status"
        # Status is either 'running' (placeholder returned before bg task) or
        # terminal state (TestClient ran bg task synchronously before returning)
        assert data["status"] in ("running", "completed", "complete", "done", "error"), (
            f"Unexpected status: {data['status']!r}"
        )


# ---------------------------------------------------------------------------
# Test 2 — Workflow actually starts (mocked LLM + search)
# ---------------------------------------------------------------------------

class TestWorkflowStartsWithMocks:
    """
    Verify the full research lifecycle executes with mocked external calls.
    This test does NOT require real API keys.
    """

    @pytest.mark.asyncio
    async def test_workflow_completes_with_mocks(self):
        """Workflow must complete (not stay 'running') within WORKFLOW_POLL_TIMEOUT."""
        from src.api.main import app, research_sessions

        # ── Supervisor mock — returns a valid QueryDecomposition JSON ──
        supervisor_json = json.dumps({
            "original_query": SIMPLE_QUERY,
            "sub_queries": ["What is teleportation?", "Is quantum teleportation real?"],
            "research_type": "factual",
            "estimated_complexity": "low",
            "priority_order": [0, 1],
        })

        researcher_json = json.dumps({
            "sub_query": "What is teleportation?",
            "findings": [
                {
                    "claim": "Teleportation refers to the theoretical transfer of matter.",
                    "source_url": "https://example.com/tp",
                    "source_title": "Teleportation Explained",
                    "confidence": 0.85,
                }
            ],
            "search_queries_used": ["teleportation"],
            "sources_consulted": 2,
        })

        critic_json = json.dumps({
            "overall_assessment": "acceptable",
            "feedback_items": [],
            "red_flags": [],
            "strengths": ["Good sourcing"],
        })

        verifier_json = json.dumps({
            "verified_claims": [],
            "cross_reference_score": 80,
            "consensus_level": "moderate",
        })

        fact_checker_json = json.dumps({
            "citation_checks": [],
            "factual_accuracy_score": 85,
            "flagged_claims": [],
            "recommended_corrections": [],
        })

        writer_json = json.dumps({
            "title": "Teleportation: A Research Overview",
            "summary": "Teleportation is a concept from physics and science fiction.",
            "main_content": "## Overview\n\nTeleportation involves transferring matter.",
            "key_findings": ["Teleportation is theoretical", "Quantum teleportation transfers states"],
            "citations": ["https://example.com/tp"],
            "confidence_score": 82,
            "caveats": ["This is a simplified overview"],
        })

        _responses = [
            supervisor_json,
            researcher_json,
            researcher_json,
            critic_json,
            verifier_json,
            fact_checker_json,
            writer_json,
        ]
        _call_count = {"n": 0}

        async def _mock_ainvoke(self_llm, *args, **kwargs):
            idx = _call_count["n"] % len(_responses)
            _call_count["n"] += 1
            msg = MagicMock()
            msg.content = _responses[idx]
            return msg

        mock_httpx_resp = MagicMock(status_code=200, text="page content here")

        with (
            patch("langchain_groq.ChatGroq.ainvoke", new=_mock_ainvoke),
            patch("src.tools.search.TavilySearch.search", new_callable=AsyncMock,
                  return_value=[{"title": "t", "url": "https://example.com/tp",
                                 "content": "content", "relevance_score": 0.9}]),
            patch("src.tools.search.SerperSearch.search", new_callable=AsyncMock,
                  return_value=[]),
            patch("httpx.AsyncClient.get", new_callable=AsyncMock,
                  return_value=mock_httpx_resp),
        ):
            from httpx import AsyncClient, ASGITransport
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                timeout=POST_TIMEOUT,
            ) as client:
                resp = await client.post(
                    "/api/v1/research",
                    json={
                        "query": SIMPLE_QUERY,
                        "depth": "fast",
                        "model": "groq/compound",
                        "max_iterations": 1,
                    },
                )

            assert resp.status_code == 200
            data = resp.json()
            session_id = data["session_id"]
            assert session_id, "Must return a session_id"
            assert data["status"] == "running"

            # Poll until workflow exits "running" or timeout
            deadline = time.time() + WORKFLOW_POLL_TIMEOUT
            final_status = "running"
            while time.time() < deadline:
                await asyncio.sleep(1)
                if session_id in research_sessions:
                    final_status = research_sessions[session_id]["response"].get("status", "running")
                    if final_status not in ("running",):
                        break

            assert final_status not in ("running",), (
                f"Workflow is still 'running' after {WORKFLOW_POLL_TIMEOUT}s — "
                "it is HANGING. The background task never completed."
            )
            assert final_status in ("completed", "complete", "done", "error"), (
                f"Expected terminal status, got {final_status!r}"
            )


# ---------------------------------------------------------------------------
# Test 3 — Workflow runs even when Neo4j and Qdrant are unavailable
# ---------------------------------------------------------------------------

class TestWorkflowWithoutOptionalServices:
    """Verify startup succeeds when Neo4j and Qdrant are both unavailable."""

    @pytest.mark.asyncio
    async def test_startup_survives_without_neo4j_and_qdrant(self):
        """
        Startup must complete without raising even when Neo4j DNS fails and
        Qdrant connection fails.  Both services are optional.
        """
        # The mock_db_startup fixture already patches both to raise.
        # Just call startup_event and verify no exception propagates.
        from src.api.main import startup_event
        # Should not raise
        await startup_event()

        from src.api.main import knowledge_graph, vector_store
        assert knowledge_graph is None, "knowledge_graph must be None when Neo4j is unavailable"
        assert vector_store is None, "vector_store must be None when Qdrant is unavailable"


# ---------------------------------------------------------------------------
# Test 4 — SSE endpoint emits at least one event
# ---------------------------------------------------------------------------

class TestSSEEmitsEvents:
    """Verify the SSE stream sends at least a session_start event."""

    def test_sse_sends_session_start(self):
        """GET /api/v1/research/{session_id}/stream must emit 'session_start'."""
        from src.api.main import app, research_sessions

        fake_session_id = "session_test_sse_1234"
        research_sessions[fake_session_id] = {
            "request": {"query": SIMPLE_QUERY, "depth": "fast", "model": "groq/compound"},
            "response": {
                "status": "completed",
                "confidence_score": 0.8,
                "key_findings": ["finding 1"],
                "citations": [],
                "main_content": "Test content",
                "title": "Test",
                "errors": [],
                "db_session_id": None,
            },
            "full_result": {},
            "timestamp": None,
            "db_session_id": None,
            "user_id": None,
        }

        events_received = []
        with TestClient(app) as client:
            with client.stream(
                "GET",
                f"/api/v1/research/{fake_session_id}/stream",
                timeout=SSE_WAIT_TIMEOUT,
            ) as response:
                assert response.status_code == 200
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        payload = json.loads(line[5:].strip())
                        events_received.append(payload)
                        if len(events_received) >= 3:
                            break

        event_types = [e.get("type") for e in events_received]
        assert "session_start" in event_types, (
            f"Expected 'session_start' event, got: {event_types}"
        )


# ---------------------------------------------------------------------------
# Test 5 — Environment variable check raises on missing critical keys
# ---------------------------------------------------------------------------

class TestEnvVarCheck:
    """Verify _check_required_env_vars raises on missing critical keys."""

    def test_raises_on_missing_groq_key(self):
        """_check_required_env_vars must raise RuntimeError when GROQ_API_KEY is empty."""
        from src.core.config import get_settings, Settings
        from src.api.main import _check_required_env_vars
        import importlib
        import src.api.main as main_mod

        # Temporarily replace the module-level settings with one that has no GROQ key
        original_settings = main_mod.settings
        empty_settings = Settings(
            groq_api_key="",
            tavily_api_key="tvly-test",
            serper_api_key="serper_test",
            database_url="postgresql+asyncpg://localhost/test",
            environment="development",
        )
        main_mod.settings = empty_settings

        try:
            with pytest.raises(RuntimeError, match="Missing required environment variables"):
                _check_required_env_vars()
        finally:
            main_mod.settings = original_settings

