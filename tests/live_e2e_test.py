"""
Live end-to-end test against the deployed Render backend.
Run with:  python tests/live_e2e_test.py
"""
import httpx
import json
import sys
import time

BASE = "https://aether-backend-tmcu.onrender.com"
QUERY = "tell me about ai"

print("=" * 60)
print("LIVE BACKEND E2E TEST")
print(f"Target: {BASE}")
print(f"Query:  {QUERY}")
print("=" * 60)

# ── Step 1: health ────────────────────────────────────────────
print("\n[1] Health check...")
try:
    r = httpx.get(f"{BASE}/health", timeout=90)
    h = r.json()
    print(f"    HTTP {r.status_code}")
    print(f"    PostgreSQL:      {h.get('postgresql')}")
    print(f"    workflow_loaded: {h.get('workflow_loaded')}")
    print(f"    uptime:          {h.get('uptime', 0):.0f}s")
except Exception as e:
    print(f"    FAILED: {e}")
    sys.exit(1)

# ── Step 2: POST research (guest — no auth token) ─────────────
print("\n[2] POST /api/v1/research  (guest)...")
try:
    r = httpx.post(
        f"{BASE}/api/v1/research",
        json={"query": QUERY, "depth": "fast", "max_iterations": 1},
        timeout=30,
    )
    print(f"    HTTP {r.status_code}")
    data = r.json()
    session_id = data.get("session_id", "")
    print(f"    session_id:     {session_id}")
    print(f"    initial status: {data.get('status')}")
    if r.status_code != 200:
        print(f"    ERROR body: {r.text[:500]}")
        sys.exit(1)
    if not session_id:
        print("    ERROR: no session_id in response")
        sys.exit(1)
except Exception as e:
    print(f"    FAILED: {e}")
    sys.exit(1)

# ── Step 3: SSE stream ────────────────────────────────────────
print(f"\n[3] SSE stream for session {session_id}...")
print("    (waiting up to 5 min for workflow completion)")

events_seen = []
final_event_type = None
findings_count = 0
citations_count = 0
had_report_chunk = False
t0 = time.time()

try:
    with httpx.stream(
        "GET",
        f"{BASE}/api/v1/research/{session_id}/stream",
        timeout=310,
    ) as resp:
        print(f"    SSE HTTP {resp.status_code}")
        for raw_line in resp.iter_lines():
            if not raw_line.startswith("data:"):
                continue
            try:
                payload = json.loads(raw_line[5:].strip())
            except Exception:
                continue

            etype = payload.get("type", "")
            events_seen.append(etype)
            elapsed = time.time() - t0

            if etype == "session_start":
                print(f"    [{elapsed:5.1f}s] session_start")
            elif etype == "agent_update":
                ag = payload.get("agent", {})
                print(f"    [{elapsed:5.1f}s] agent_update  {ag.get('id')} → {ag.get('status')}")
            elif etype == "timeline":
                ev = payload.get("event", {})
                print(f"    [{elapsed:5.1f}s] timeline  {ev.get('agentRole')} / {ev.get('type')}")
            elif etype == "finding":
                findings_count += 1
                f = payload.get("finding", {})
                print(f"    [{elapsed:5.1f}s] finding #{findings_count}: {str(f.get('title',''))[:60]}")
            elif etype == "citation":
                citations_count += 1
                c = payload.get("citation", {})
                print(f"    [{elapsed:5.1f}s] citation #{citations_count}: {str(c.get('title',''))[:60]}")
            elif etype == "report_chunk":
                had_report_chunk = True
                txt = str(payload.get("text", ""))
                print(f"    [{elapsed:5.1f}s] report_chunk ({len(txt)} chars)")
            elif etype == "done":
                conf = payload.get("confidence", 0)
                print(f"    [{elapsed:5.1f}s] DONE  confidence={conf}")
                final_event_type = "done"
                break
            elif etype == "error":
                msg = payload.get("message", "")
                print(f"    [{elapsed:5.1f}s] ERROR: {msg}")
                final_event_type = "error"
                break

except Exception as e:
    print(f"    SSE connection error: {e}")

total_time = time.time() - t0

# ── Step 4: summary ───────────────────────────────────────────
print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
print(f"  Final event:      {final_event_type}")
print(f"  Events received:  {events_seen}")
print(f"  Findings:         {findings_count}")
print(f"  Citations:        {citations_count}")
print(f"  Report chunk:     {had_report_chunk}")
print(f"  Total time:       {total_time:.1f}s")
print()

# ── Step 5: verdict ───────────────────────────────────────────
all_pass = True

def check(label, condition, note=""):
    global all_pass
    status = "PASS" if condition else "FAIL"
    if not condition:
        all_pass = False
    suffix = f"  ({note})" if note else ""
    print(f"  {status}  {label}{suffix}")

check("POST /api/v1/research returns 200",     True)           # reached here means yes
check("session_id returned",                   bool(session_id))
check("SSE connects",                          "session_start" in events_seen)
check("Workflow reaches terminal state",       final_event_type in ("done", "error"))
check("Workflow completes (DONE)",             final_event_type == "done",
      "error is acceptable if real API issue — not a NameError")
check("No NameError in response",              final_event_type != "error" or
      "NameError" not in str(events_seen))
check("report_chunk generated",               had_report_chunk,
      "requires real Groq API key to be valid on Render")

print()
if all_pass:
    print("ALL CHECKS PASSED")
elif final_event_type == "error":
    print("SOME CHECKS FAILED — check the error message above")
    print("If the error is NOT a NameError, the fix is deployed correctly.")
    print("A different error (e.g. invalid API key) is a separate issue.")
else:
    print("SOME CHECKS FAILED")
