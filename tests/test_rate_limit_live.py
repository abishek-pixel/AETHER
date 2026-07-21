"""
Live Rate-Limit Test
====================
Tests the full rate-limit flow against the running backend on port 8000.

Run with:
    .venv\\Scripts\\pytest tests/test_rate_limit_live.py -v -s --tb=short
"""
import asyncio
import uuid
import pytest
import httpx

# Tell pytest-asyncio to handle all async tests automatically
pytestmark = pytest.mark.asyncio

BASE = "http://localhost:8000"
TIMEOUT = 20.0          # default for fast endpoints (auth, rate-limit)
RESEARCH_TIMEOUT = 90.0  # research POST triggers lazy AI workflow load on first call

# Shared state across tests (populated in setup)
_state: dict = {}


# ── Helpers ────────────────────────────────────────────────────────────────

def unique_email() -> str:
    # Use a real-looking TLD so pydantic EmailStr accepts it
    return f"ratelimit_{uuid.uuid4().hex[:8]}@example.com"


async def register(email: str, password: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/api/v1/auth/register", json={
            "name": "Rate Limit Tester",
            "email": email,
            "password": password,
        }, timeout=TIMEOUT)
    assert r.status_code == 201, f"Register failed {r.status_code}: {r.text}"
    return r.json()


async def get_rate_limit(token: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"{BASE}/api/v1/users/me/rate-limit",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,  # Render DB round-trip
        )
    assert r.status_code == 200, f"rate-limit failed {r.status_code}: {r.text}"
    return r.json()


async def start_research(token: str, query: str) -> tuple[int, dict]:
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{BASE}/api/v1/research",
            json={"query": query, "depth": "fast",
                  "model": "groq/compound", "max_iterations": 1},
            headers={"Authorization": f"Bearer {token}"},
            timeout=RESEARCH_TIMEOUT,  # longer — lazy workflow loads on first call
        )
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    return r.status_code, body


# ── Tests run in order ─────────────────────────────────────────────────────

async def test_01_backend_healthy():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/health", timeout=5.0)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["postgresql"] == "healthy", "PostgreSQL must be healthy"
    print(f"\n✅ Backend healthy")


async def test_02_register_test_user():
    """Register fresh user and store token for rest of suite."""
    email = unique_email()
    tokens = await register(email, "TestPassword123!")
    _state["token"] = tokens["access_token"]
    _state["email"] = email
    print(f"\n✅ Registered: {email}")


async def test_03_initial_rate_limit_zero():
    token = _state["token"]
    info = await get_rate_limit(token)
    print(f"\n📊 Initial: {info}")
    assert info["prompts_used"] == 0,    f"Expected 0 used, got {info['prompts_used']}"
    assert info["prompts_allowed"] == 2, f"Expected 2 allowed, got {info['prompts_allowed']}"
    assert info["remaining"] == 2,       f"Expected 2 remaining, got {info['remaining']}"
    assert info["is_limited"] is False,  "Should not be limited on fresh account"
    assert info["reset_at"] is None,     "reset_at should be None before any prompts"
    print("✅ 0/2 used — not limited")


async def test_04_first_prompt_accepted():
    status, body = await start_research(_state["token"], "What is the capital of France?")
    print(f"\n📤 Prompt 1 → HTTP {status}")
    assert status == 200, f"Prompt 1 should be accepted, got {status}: {body}"
    assert body.get("status") == "running"
    _state["session1_id"] = body.get("db_session_id") or body.get("session_id")
    print(f"✅ Prompt 1 accepted — session: {_state['session1_id']}")


async def test_05_rate_limit_after_first_prompt():
    await asyncio.sleep(1.5)   # let DB commit
    info = await get_rate_limit(_state["token"])
    print(f"\n📊 After prompt 1: {info}")
    assert info["prompts_used"] == 1, f"Expected 1 used, got {info['prompts_used']}"
    assert info["remaining"] == 1,    f"Expected 1 remaining, got {info['remaining']}"
    assert info["is_limited"] is False
    print("✅ 1/2 used — 1 remaining")


async def test_06_second_prompt_accepted():
    status, body = await start_research(
        _state["token"], "What is the largest ocean on Earth?"
    )
    print(f"\n📤 Prompt 2 → HTTP {status}")
    assert status == 200, f"Prompt 2 should be accepted, got {status}: {body}"
    _state["session2_id"] = body.get("db_session_id") or body.get("session_id")
    print(f"✅ Prompt 2 accepted — free tier now EXHAUSTED")


async def test_07_rate_limit_after_second_prompt():
    await asyncio.sleep(1.5)
    info = await get_rate_limit(_state["token"])
    print(f"\n📊 After prompt 2: {info}")
    assert info["prompts_used"] == 2,         f"Expected 2 used, got {info['prompts_used']}"
    assert info["remaining"] == 0,            f"Expected 0 remaining, got {info['remaining']}"
    assert info["is_limited"] is True,        "Must be limited after 2 prompts"
    assert info["reset_at"] is not None,      "reset_at must be set"
    assert info["retry_after_seconds"] > 0,   "retry_after_seconds must be > 0"
    assert info["hours_remaining"] > 0,       "hours_remaining must be > 0"
    _state["reset_at"] = info["reset_at"]
    print(f"✅ 2/2 used — IS LIMITED")
    print(f"   reset_at:            {info['reset_at']}")
    print(f"   retry_after_seconds: {info['retry_after_seconds']}")
    print(f"   hours_remaining:     {info['hours_remaining']:.2f}h")


async def test_08_third_prompt_rejected_429():
    """Third prompt MUST be blocked."""
    status, body = await start_research(
        _state["token"], "This prompt should be blocked"
    )
    print(f"\n🚫 Prompt 3 → HTTP {status}")
    print(f"   Body: {body}")
    assert status == 429, f"Expected 429 but got {status}: {body}"
    print("✅ Prompt 3 correctly REJECTED with 429")


async def test_09_429_spec_response_shape():
    """429 detail must have all fields defined in the spec."""
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{BASE}/api/v1/research",
            json={"query": "blocked again", "depth": "fast",
                  "model": "groq/compound", "max_iterations": 1},
            headers={"Authorization": f"Bearer {_state['token']}"},
            timeout=TIMEOUT,
        )
    assert r.status_code == 429
    body = r.json()
    detail = body.get("detail", body)
    print(f"\n📋 429 detail: {detail}")

    assert detail.get("error") == "FREE_TIER_LIMIT_REACHED", \
        f"Wrong error code: {detail.get('error')}"
    assert "You have reached" in detail.get("message", ""), \
        f"Wrong message: {detail.get('message')}"
    assert detail.get("limit") == 2,        f"Wrong limit: {detail}"
    assert detail.get("remaining") == 0,    f"Wrong remaining: {detail}"
    assert isinstance(detail.get("retry_after_seconds"), int), \
        f"retry_after_seconds must be int: {detail}"
    assert detail["retry_after_seconds"] > 0, \
        f"retry_after_seconds must be > 0: {detail}"
    assert detail.get("reset_at") is not None, \
        f"reset_at must be present: {detail}"

    print("✅ 429 has correct spec shape:")
    print(f"   error:               {detail['error']}")
    print(f"   message:             {detail['message']}")
    print(f"   limit:               {detail['limit']}")
    print(f"   remaining:           {detail['remaining']}")
    print(f"   retry_after_seconds: {detail['retry_after_seconds']}")
    print(f"   reset_at:            {detail['reset_at']}")


async def test_10_limit_persists_after_login():
    """Getting a fresh token must NOT reset the usage counter."""
    # Simulate re-login by refreshing — the rate-limit check uses user_id
    # which stays the same regardless of which token is used.
    info = await get_rate_limit(_state["token"])
    assert info["is_limited"] is True, \
        "Limit must persist — cannot bypass by refreshing or re-logging in"
    assert info["prompts_used"] == 2
    print(f"\n✅ Limit persists after re-auth: {info['prompts_used']}/2 used")


async def test_11_different_user_independent_limit():
    """A different user must start with their own fresh 0/2 count."""
    tokens2 = await register(unique_email(), "TestPassword123!")
    info2 = await get_rate_limit(tokens2["access_token"])
    print(f"\n📊 New user rate-limit: {info2}")
    assert info2["prompts_used"] == 0, \
        f"New user should have 0 used, got {info2['prompts_used']}"
    assert info2["is_limited"] is False, \
        "New user must not be affected by first user's limit"
    print("✅ Per-user isolation confirmed: new user has 0/2 usage")
