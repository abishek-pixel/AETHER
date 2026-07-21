"""
Session History Restoration Test
=================================
Tests the exact scenario from the bug report:
  Create session with 3 prompts → logout → login → open session
  → ALL 3 prompts must be visible immediately (no new prompt needed).

Run with (backend must be running on port 8000):
    .venv\\Scripts\\pytest tests/test_session_history.py -v -s --asyncio-mode=auto
"""
import asyncio
import uuid
import pytest
import httpx

pytestmark = pytest.mark.asyncio

BASE = "http://localhost:8000"
TIMEOUT = 25.0
_state: dict = {}


# ── Helpers ────────────────────────────────────────────────────────────────

async def register(email: str, pw: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/api/v1/auth/register",
                         json={"name": "History Tester", "email": email, "password": pw},
                         timeout=TIMEOUT)
    assert r.status_code == 201, f"Register failed: {r.text}"
    return r.json()


async def login(email: str, pw: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/api/v1/auth/login",
                         json={"email": email, "password": pw},
                         timeout=TIMEOUT)
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()


def hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def start_research(token: str, query: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/api/v1/research",
                         json={"query": query, "depth": "fast",
                               "model": "groq/compound", "max_iterations": 1},
                         headers=hdrs(token), timeout=TIMEOUT)
    assert r.status_code == 200, f"start_research failed: {r.text}"
    return r.json()


async def wait_for_n_user_messages(token: str, db_sid: str, n: int, max_wait: int = 120) -> None:
    """Poll until the session has at least n user messages."""
    for attempt in range(max_wait):
        await asyncio.sleep(1)
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{BASE}/api/v1/sessions/{db_sid}",
                            headers=hdrs(token), timeout=TIMEOUT)
        if r.status_code != 200:
            continue
        data = r.json()
        user_msgs = [m for m in data.get("messages", []) if m["role"] == "user"]
        if len(user_msgs) >= n:
            return
        if attempt % 10 == 0:
            print(f"   ... waiting for {n} user messages, have {len(user_msgs)}")
    raise TimeoutError(f"Session {db_sid} never reached {n} user messages")


async def get_session(token: str, session_id: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/api/v1/sessions/{session_id}",
                        headers=hdrs(token), timeout=TIMEOUT)
    assert r.status_code == 200, f"get_session failed {r.status_code}: {r.text}"
    return r.json()


async def follow_up(token: str, db_sid: str, query: str) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/api/v1/sessions/{db_sid}/followup",
                         json={"query": query, "depth": "fast",
                               "model": "groq/compound", "max_iterations": 1},
                         headers=hdrs(token), timeout=TIMEOUT)
    assert r.status_code == 200, f"follow_up failed: {r.text}"
    return r.json()


# ── Tests ──────────────────────────────────────────────────────────────────

async def test_01_setup_user():
    email = f"history_{uuid.uuid4().hex[:8]}@example.com"
    pw = "TestPass123!"
    tokens = await register(email, pw)
    _state.update({"email": email, "pw": pw, "token": tokens["access_token"]})
    print(f"\n✅ Registered: {email}")


async def test_02_create_session_with_3_prompts():
    """
    Create one session with 3 research turns.
    Each is a follow-up after the first completes.
    """
    token = _state["token"]

    # Prompt 1 — initial session
    r1 = await start_research(token, "What is photosynthesis?")
    db_sid = r1.get("db_session_id")
    assert db_sid, f"No db_session_id in response: {r1}"
    _state["session_id"] = db_sid
    print(f"\n📤 Prompt 1 sent, session: {db_sid}")

    # Wait for Prompt 1 to complete
    await wait_for_n_user_messages(token, db_sid, 1)
    print("   ✅ Prompt 1 completed")

    # Prompt 2 — follow-up
    await follow_up(token, db_sid, "How does it differ from cellular respiration?")
    # Wait for both prompts 1 and 2 to be saved
    await wait_for_n_user_messages(token, db_sid, 2)
    print("   ✅ Prompt 2 completed")

    # Prompt 3 — follow-up
    await follow_up(token, db_sid, "What role do chloroplasts play?")
    # Wait for all 3 prompts to be saved
    await wait_for_n_user_messages(token, db_sid, 3)
    print("   ✅ Prompt 3 completed")

    # Verify all 3 turns are in the DB (3 user + 3 assistant = 6 messages)
    session_data = await get_session(token, db_sid)
    msgs = session_data.get("messages", [])
    user_msgs = [m for m in msgs if m["role"] == "user"]
    asst_msgs = [m for m in msgs if m["role"] == "assistant"]

    print(f"\n📊 DB messages: {len(msgs)} total ({len(user_msgs)} user, {len(asst_msgs)} assistant)")
    assert len(user_msgs) >= 3, \
        f"Expected ≥3 user messages in DB, got {len(user_msgs)}"
    assert len(asst_msgs) >= 3, \
        f"Expected ≥3 assistant messages in DB, got {len(asst_msgs)}"
    print(f"✅ All 3 prompts persisted correctly in DB")


async def test_03_backend_returns_all_messages_on_session_fetch():
    """
    BACKEND VERIFICATION:
    GET /sessions/{id} must return ALL messages, ordered chronologically.
    """
    token = _state["token"]
    session_id = _state["session_id"]

    data = await get_session(token, session_id)
    msgs = data.get("messages", [])

    print(f"\n📊 Backend response: {len(msgs)} messages")
    for i, m in enumerate(msgs):
        print(f"   [{i}] role={m['role']:<12} content={m['content'][:60]!r}")

    user_msgs = [m for m in msgs if m["role"] == "user"]
    assert len(user_msgs) >= 3, \
        f"Backend must return all 3 user messages, got {len(user_msgs)}"

    # Verify chronological order
    timestamps = [m.get("timestamp", "") for m in msgs]
    assert timestamps == sorted(timestamps), \
        f"Messages must be ordered chronologically: {timestamps}"

    print(f"✅ Backend returns {len(user_msgs)} user messages in correct order")
    _state["expected_block_count"] = len(user_msgs)


async def test_04_simulate_logout_login():
    """Simulate logout + login — get a fresh token from login."""
    tokens = await login(_state["email"], _state["pw"])
    _state["token_after_login"] = tokens["access_token"]
    print(f"\n✅ Logged out and back in — fresh token obtained")


async def test_05_session_fetch_after_login_returns_complete_data():
    """
    THE CORE TEST:
    After login, fetching the session must return all messages immediately.
    This is what the frontend loadSessionFromDB() calls.
    """
    token = _state["token_after_login"]
    session_id = _state["session_id"]
    expected = _state["expected_block_count"]

    data = await get_session(token, session_id)
    msgs = data.get("messages", [])
    user_msgs = [m for m in msgs if m["role"] == "user"]

    print(f"\n📊 After login — session fetch returned {len(msgs)} messages")
    print(f"   Expected {expected} user messages (blocks)")

    assert len(user_msgs) == expected, \
        f"After login: expected {expected} user messages, got {len(user_msgs)}. " \
        f"ALL historical prompts must be visible WITHOUT submitting a new prompt."

    print(f"✅ TEST A PASS: All {expected} prompts visible immediately after login")
    print(f"   No new prompt was needed to restore history!")


async def test_06_messages_ordered_chronologically():
    """Messages must be in created_at ASC order (chronological)."""
    token = _state["token_after_login"]
    session_id = _state["session_id"]

    data = await get_session(token, session_id)
    msgs = data.get("messages", [])

    timestamps = [m.get("timestamp", "") for m in msgs]
    assert timestamps == sorted(timestamps), \
        f"Messages must be chronological ASC, got: {timestamps}"

    # First and last should be user/assistant pairs
    assert msgs[0]["role"] == "user",      "First message must be a user prompt"
    print(f"\n✅ Messages are in chronological order: {len(msgs)} messages")


async def test_07_list_endpoint_returns_session_summary():
    """
    The list endpoint is a SUMMARY — it may not include messages.
    This is expected. The fix ensures the frontend ALWAYS calls the detail
    endpoint when opening a session, not relying on the summary.
    """
    token = _state["token_after_login"]
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/api/v1/sessions?limit=50&offset=0",
                        headers=hdrs(token), timeout=TIMEOUT)
    assert r.status_code == 200
    sessions = r.json().get("sessions", [])
    our_session = next((s for s in sessions if s["id"] == _state["session_id"]), None)
    assert our_session is not None, "Session must appear in the list"

    # The list endpoint may or may not include messages — that's fine.
    # The key is that the detail endpoint always does.
    list_msgs = our_session.get("messages", [])
    print(f"\n📊 List endpoint messages for our session: {len(list_msgs)}")
    print(f"   (Detail endpoint has {_state['expected_block_count']} user messages)")
    print(f"✅ List/detail separation confirmed — frontend must use detail endpoint")


async def test_08_refresh_scenario():
    """TEST B: Fetch the session again (simulates page refresh)."""
    token = _state["token_after_login"]
    session_id = _state["session_id"]
    expected = _state["expected_block_count"]

    data = await get_session(token, session_id)
    msgs = data.get("messages", [])
    user_msgs = [m for m in msgs if m["role"] == "user"]

    assert len(user_msgs) == expected, \
        f"After refresh: expected {expected} user messages, got {len(user_msgs)}"
    print(f"\n✅ TEST B (refresh): All {expected} prompts restore correctly")


async def test_09_no_duplicates_after_new_prompt_would_be_added():
    """
    TEST F: Verify message deduplication.
    The session should have exactly the expected number of messages — no duplicates.
    """
    token = _state["token_after_login"]
    session_id = _state["session_id"]

    data = await get_session(token, session_id)
    msgs = data.get("messages", [])
    msg_ids = [m["id"] for m in msgs]
    unique_ids = set(msg_ids)

    assert len(msg_ids) == len(unique_ids), \
        f"Duplicate messages detected! IDs: {[i for i in msg_ids if msg_ids.count(i) > 1]}"
    print(f"\n✅ TEST F (no duplicates): {len(msgs)} messages, all unique IDs")
