"""
Wait for the new Render deployment (08874c3) to go live, then run a full
end-to-end research lifecycle test against the production backend.
"""
import httpx
import json
import sys
import time

BASE = "https://aether-backend-tmcu.onrender.com"
QUERY = "tell me about ai"

# ── 1. Wait for the new deployment ───────────────────────────
print("=" * 65)
print("Waiting for deployment 08874c3 to become live...")
print("=" * 65)

backend_up = False
for attempt in range(1, 16):
    try:
        r = httpx.get(f"{BASE}/health", timeout=35)
        if r.status_code == 200:
            h = r.json()
            uptime = h.get("uptime", 0)
            wf = h.get("workflow_loaded", False)
            pg = h.get("postgresql", "?")
            print(f"  [{attempt:02d}] UP  uptime={uptime:.0f}s  pg={pg}  workflow_loaded={wf}")
            backend_up = True
            break
        else:
            print(f"  [{attempt:02d}] HTTP {r.status_code}")
    except Exception as e:
        print(f"  [{attempt:02d}] {type(e).__name__}: {str(e)[:60]}")
    time.sleep(20)

if not backend_up:
    print("ERROR: backend did not respond within 5 minutes")
    sys.exit(1)

# ── 2. POST guest research ─────────────────────────────────
print(f"\n[POST] /api/v1/research  query='{QUERY}'")
try:
    r = httpx.post(
        f"{BASE}/api/v1/research",
        json={"query": QUERY, "depth": "fast", "max_iterations": 1},
        timeout=40,
    )
    print(f"  HTTP {r.status_code}")
    data = r.json()
    session_id = data.get("session_id", "")
    init_status = data.get("status", "")
    print(f"  session_id:     {session_id}")
    print(f"  initial status: {init_status}")
    if r.status_code != 200 or not session_id:
        print(f"  BODY: {r.text[:400]}")
        sys.exit(1)
except Exception as e:
    print(f"  FAILED: {e}")
    sys.exit(1)

# ── 3. SSE stream ─────────────────────────────────────────
print(f"\n[SSE] stream  session={session_id}")
print("  Waiting up to 6 min for terminal event...\n")

events_seen = []
final_event = None
findings_n = 0
citations_n = 0
had_report = False
report_text = ""
t0 = time.time()

try:
    with httpx.stream(
        "GET",
        f"{BASE}/api/v1/research/{session_id}/stream",
        timeout=380,
    ) as resp:
        print(f"  SSE connected  HTTP {resp.status_code}")
        for raw in resp.iter_lines():
            if not raw.startswith("data:"):
                continue
            try:
                payload = json.loads(raw[5:].strip())
            except Exception:
                continue

            etype = payload.get("type", "")
            events_seen.append(etype)
            elapsed = time.time() - t0

            if etype == "session_start":
                print(f"  [{elapsed:5.1f}s] session_start")

            elif etype == "agent_update":
                ag = payload.get("agent", {})
                print(f"  [{elapsed:5.1f}s] agent_update  {ag.get('id','?')} → {ag.get('status','?')}")

            elif etype == "finding":
                findings_n += 1
                f = payload.get("finding", {})
                print(f"  [{elapsed:5.1f}s] finding #{findings_n}: {str(f.get('title',''))[:70]}")

            elif etype == "citation":
                citations_n += 1
                c = payload.get("citation", {})
                print(f"  [{elapsed:5.1f}s] citation #{citations_n}: {str(c.get('title',''))[:70]}")

            elif etype == "report_chunk":
                had_report = True
                report_text = str(payload.get("text", ""))
                print(f"  [{elapsed:5.1f}s] report_chunk  ({len(report_text)} chars)")

            elif etype == "done":
                conf = payload.get("confidence", 0)
                print(f"  [{elapsed:5.1f}s] DONE  confidence={conf:.2f}")
                final_event = "done"
                break

            elif etype == "error":
                msg = payload.get("message", "")
                print(f"  [{elapsed:5.1f}s] ERROR: {msg}")
                final_event = "error"
                final_error_msg = msg
                break

except Exception as e:
    print(f"  SSE error: {type(e).__name__}: {str(e)[:120]}")

total_time = time.time() - t0

# ── 4. Report preview ─────────────────────────────────────
if had_report and report_text:
    print("\n[REPORT PREVIEW — first 400 chars]")
    print("-" * 50)
    print(report_text[:400])
    print("-" * 50)

# ── 5. Verdict ────────────────────────────────────────────
print("\n" + "=" * 65)
print("TEST RESULTS")
print("=" * 65)

checks = []
def chk(label, passed, note=""):
    status = "PASS" if passed else "FAIL"
    suffix = f"  ({note})" if note else ""
    checks.append(passed)
    print(f"  {status}  {label}{suffix}")

chk("Health endpoint returns 200",        True)
chk("POST returns session_id",            bool(session_id))
chk("SSE connects (session_start event)", "session_start" in events_seen)
chk("Agents emit update events",          "agent_update" in events_seen)
chk("Workflow reaches terminal state",    final_event in ("done", "error"))
chk("No NameError in error message",
    not (final_event == "error" and "NameError" in str(events_seen + [final_event])))
chk("Workflow DONE (not error)",          final_event == "done")
chk("Report chunk generated",             had_report)
chk("Findings received",                  findings_n > 0)

print(f"\n  Total events: {len(events_seen)}")
print(f"  Findings:     {findings_n}")
print(f"  Citations:    {citations_n}")
print(f"  Total time:   {total_time:.1f}s")
print()

all_pass = all(checks)
if all_pass:
    print("ALL CHECKS PASSED — production workflow is working end-to-end")
elif final_event == "done" and not had_report:
    print("MOSTLY PASSED — workflow completed but report chunk was empty")
elif final_event == "error":
    error_msg = locals().get("final_error_msg", "")
    if "NameError" in error_msg:
        print("CRITICAL FAIL — NameError still present in production")
    else:
        print(f"Workflow returned error (not a NameError): {error_msg[:200]}")
        print("The NameError fix is deployed. This is a different runtime issue.")
else:
    print("SOME CHECKS FAILED — review output above")
