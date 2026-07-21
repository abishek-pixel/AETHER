"""
Aether Research API — main FastAPI application.
Integrates PostgreSQL persistence, JWT authentication, and the multi-agent pipeline.

LAZY LOADING: The heavy AI workflow (AetherWorkflow, SentenceTransformer, LangGraph)
is NOT imported at module level.  It is loaded on first research request so that:
  - /health responds immediately after process start
  - Render's 512 MB starter instance doesn't OOM during cold start
"""
import time
import json
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

# ── Heavy AI imports are deferred — do NOT import at top level ────────────
# from src.core.graph import aether_workflow   ← loaded lazily below
# from src.core.state import AetherState       ← loaded lazily below
# from src.memory.*                            ← loaded lazily below

from src.core.config import get_settings
from src.database.session import get_db, init_db
from src.routers.auth import router as auth_router
from src.routers.sessions import router as sessions_router
from src.routers.messages import router as messages_router
from src.routers.feedback import router as feedback_router
from src.routers.users import router as users_router

# Repositories for persisting research results
from src.repositories.session import SessionRepository
from src.repositories.message import MessageRepository
from src.repositories.report import ReportRepository
from src.repositories.usage import UsageRepository
from src.database.session import AsyncSessionLocal

# Optional auth dependency (research endpoints work with or without auth)
from src.auth.dependencies import bearer_scheme
from src.auth.security import decode_token
from src.repositories.user import UserRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
START_TIME = time.time()
settings = get_settings()

# ── CORS origin list ───────────────────────────────────────────────────────

def _build_cors_origins() -> list[str]:
    """Build the allowed origins list from config + hardcoded localhost origins."""
    origins = [
        "http://localhost:8080",
        "http://localhost:8081",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:4173",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8081",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    # Add production frontend origin(s) from environment variable.
    # FRONTEND_URL may be comma-separated for multiple origins.
    if settings.frontend_url:
        for origin in settings.frontend_url.split(","):
            origin = origin.strip()
            if origin and origin not in origins:
                origins.append(origin)
    return origins


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Aether Research API",
    description="Multi-agent AI research system — production-ready SaaS backend",
    version="2.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
    max_age=600,
)

# ── Include routers ────────────────────────────────────────────────────────

app.include_router(auth_router,     prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(feedback_router, prefix="/api/v1")
app.include_router(users_router,    prefix="/api/v1")

# ── Middleware ─────────────────────────────────────────────────────────────

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t = time.time()
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} {response.status_code} {time.time()-t:.3f}s")
    response.headers["X-Process-Time"] = str(time.time() - t)
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

# ── Global state ───────────────────────────────────────────────────────────

memory_manager: Optional[Any] = None
knowledge_graph: Optional[Any] = None
vector_store: Optional[Any] = None

# In-process cache: maps backend session_id → response dict for SSE polling
# NOTE: this is a temporary runtime cache for SSE polling only.
# All persistent data (sessions, messages, reports) is stored in PostgreSQL.
research_sessions: Dict[str, Dict[str, Any]] = {}

# ── Lazy AI workflow loader ────────────────────────────────────────────────
# Heavy imports (LangGraph, SentenceTransformer, all agents) are deferred
# until the first research request so /health stays lightweight.

_aether_workflow: Optional[Any] = None
_AetherState: Optional[Any] = None
_workflow_lock = asyncio.Lock()


async def _get_workflow():
    """Return the compiled AetherWorkflow, loading it on first call."""
    global _aether_workflow, _AetherState
    if _aether_workflow is not None:
        return _aether_workflow, _AetherState

    async with _workflow_lock:
        # Double-checked locking
        if _aether_workflow is not None:
            return _aether_workflow, _AetherState

        logger.info("⏳ Loading AI workflow (first request)…")
        import importlib
        graph_mod = importlib.import_module("src.core.graph")
        state_mod = importlib.import_module("src.core.state")
        _aether_workflow = graph_mod.aether_workflow
        _AetherState = state_mod.AetherState
        logger.info("✅ AI workflow loaded")

    return _aether_workflow, _AetherState

# ── Lifecycle ──────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """
    Startup sequence designed to keep /health responsive immediately.

    1. PostgreSQL init  — fast (just verifies tables exist)
    2. Neo4j / Qdrant   — optional, failures are non-fatal
    3. AI workflow      — NOT loaded here; deferred to first research request
    """
    global memory_manager, knowledge_graph, vector_store

    # ── PostgreSQL ──
    try:
        await init_db()
        logger.info("✅ PostgreSQL tables created / verified")
    except Exception as e:
        # Log but don't crash — DB might be temporarily unavailable.
        # Requests that need the DB will fail with a proper error.
        logger.error(f"❌ PostgreSQL init failed: {e}")

    # ── Neo4j (optional) ──
    try:
        from src.memory.knowledge_graph import KnowledgeGraph as KG
        kg = KG(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        await kg.connect()
        knowledge_graph = kg
        logger.info("✅ Neo4j connected")
    except Exception as e:
        logger.warning(f"⚠️  Neo4j unavailable (optional): {e}")
        knowledge_graph = None

    # ── Qdrant (optional) ──
    try:
        from src.memory.vector_store import VectorStore as VS
        vs = VS(host=settings.qdrant_host, port=settings.qdrant_port)
        await vs.initialize()
        vector_store = vs
        logger.info("✅ Qdrant initialized")
    except Exception as e:
        logger.warning(f"⚠️  Qdrant unavailable (optional): {e}")
        vector_store = None

    if knowledge_graph or vector_store:
        from src.memory.memory_manager import MemoryManager as MM
        memory_manager = MM(knowledge_graph, vector_store)

    # NOTE: AI workflow (LangGraph, SentenceTransformer, agents) is NOT loaded
    # here — it will be loaded lazily on the first research request.


@app.on_event("shutdown")
async def shutdown_event():
    if knowledge_graph:
        try:
            await knowledge_graph.disconnect()
        except Exception:
            pass

# ── Helpers ────────────────────────────────────────────────────────────────

def normalize_confidence_score(score: Any) -> float:
    try:
        v = float(score)
    except (TypeError, ValueError):
        return 0.0
    if v > 1:
        v = v / 100
    return max(0.0, min(v, 1.0))


def build_workflow_status(result: Dict[str, Any], writer_output: Any) -> tuple[str, List[str]]:
    errors = [str(e) for e in result.get("errors", [])]
    if writer_output:
        return "completed", errors
    if str(result.get("status", "")).lower() in {"completed", "complete", "done"}:
        return "completed", errors
    if not errors:
        errors.append("Research workflow finished without a final report")
    return "error", errors


def format_report_as_markdown(writer_output: Any) -> str:
    if not writer_output:
        return "No report available"
    report = f"# {writer_output.title}\n\n"
    report += f"## Executive Summary\n{writer_output.summary}\n\n"
    report += "## Key Findings\n"
    for f in writer_output.key_findings:
        report += f"- {f}\n"
    report += f"\n## Main Content\n{writer_output.main_content}\n\n"
    if writer_output.caveats:
        report += "## Caveats\n"
        for c in writer_output.caveats:
            report += f"- {c}\n"
    if writer_output.citations:
        report += "\n## Citations\n"
        for c in writer_output.citations:
            report += f"- {c}\n"
    return report


async def _get_optional_user_id(
    credentials=Depends(bearer_scheme),
) -> Optional[uuid.UUID]:
    """Try to extract user_id from JWT; return None if no token present."""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") == "access":
            return uuid.UUID(payload["sub"])
    except Exception:
        pass
    return None


async def _persist_completed_research(
    backend_session_id: str,
    db_session_id: Optional[uuid.UUID],
    user_id: Optional[uuid.UUID],
    query: str,
    depth: str,
    model: str,
    writer_output: Any,
    execution_time: float,
    total_cost: float,
    token_usage: Dict[str, int],
    workflow_status: str,
    timeline_events: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Save completed research to PostgreSQL."""
    if db_session_id is None:
        return
    try:
        async with AsyncSessionLocal() as db:
            # Update session status
            session_repo = SessionRepository(db)
            await session_repo.update_status(db_session_id, workflow_status)

            # Save user query as a message
            msg_repo = MessageRepository(db)
            await msg_repo.create(db_session_id, "user", query)

            # Save report
            if writer_output:
                report_repo = ReportRepository(db)
                await report_repo.upsert(
                    session_id=db_session_id,
                    title=writer_output.title,
                    summary=writer_output.summary,
                    main_content=writer_output.main_content,
                    citations=writer_output.citations or [],
                    key_findings=writer_output.key_findings or [],
                    confidence_score=normalize_confidence_score(writer_output.confidence_score),
                    execution_time=execution_time,
                    cost=total_cost,
                    # Persist timeline events so they survive page refresh
                    timeline_events=timeline_events or [],
                )
                # Save report as assistant message
                await msg_repo.create(
                    db_session_id, "assistant",
                    format_report_as_markdown(writer_output)
                )

            # Log token usage
            if user_id and (token_usage.get("input", 0) + token_usage.get("output", 0)) > 0:
                usage_repo = UsageRepository(db)
                await usage_repo.log(
                    user_id=user_id,
                    session_id=db_session_id,
                    model_used=model,
                    input_tokens=token_usage.get("input", 0),
                    output_tokens=token_usage.get("output", 0),
                    estimated_cost=total_cost,
                )

            await db.commit()
            logger.info(f"✅ Research persisted to PostgreSQL: session {db_session_id}")
    except Exception as e:
        logger.error(f"❌ Failed to persist research to PostgreSQL: {e}")


# ── Pydantic models ────────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000, description="The research query")
    depth: str = Field("balanced", description="fast | balanced | deep")
    model: str = Field("groq/compound", description="Model to use")
    max_iterations: int = Field(2, ge=1, le=5)
    verify_results: bool = Field(True)
    include_citations: bool = Field(True)

    @field_validator("depth")
    @classmethod
    def validate_depth(cls, v: str) -> str:
        allowed = {"fast", "balanced", "deep"}
        if v not in allowed:
            raise ValueError(f"depth must be one of {allowed}")
        return v

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query must not be empty or whitespace")
        return stripped


class ResearchResponse(BaseModel):
    status: str
    session_id: str
    db_session_id: Optional[str] = None
    title: Optional[str] = None
    research_summary: Optional[str] = None
    main_content: Optional[str] = None
    key_findings: List[str] = []
    citations: List[str] = []
    caveats: List[str] = []
    confidence_score: float = 0.0
    cost_metrics: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    execution_time: float = 0.0
    total_tokens: Optional[Dict[str, int]] = None


class ExportRequest(BaseModel):
    format: str = Field("markdown")
    include_citations: bool = True
    include_reasoning: bool = True


# ── Health ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """
    Lightweight health check — must respond immediately.

    Does NOT:
      - Load the AI workflow
      - Connect to Neo4j / Qdrant
      - Run expensive queries

    Checks PostgreSQL with a simple SELECT 1 (fast, < 1ms on healthy DB).
    """
    db_status = "unavailable"
    try:
        from src.database.session import AsyncSessionLocal as _sl
        from sqlalchemy import text
        async with _sl() as db:
            await db.execute(text("SELECT 1"))
            db_status = "healthy"
    except Exception as e:
        logger.warning(f"Health check DB probe failed: {e}")

    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": time.time() - START_TIME,
        "postgresql": db_status,
        # Omit Neo4j/Qdrant from basic health — they are optional services
        "workflow_loaded": _aether_workflow is not None,
    }


@app.get("/")
async def root():
    return {
        "name": "Aether Research API",
        "version": "2.0.0",
        "docs": "/api/docs",
        "health": "/health",
    }


# ── Research pipeline ──────────────────────────────────────────────────────

@app.options("/api/v1/research", include_in_schema=False)
async def research_options():
    return Response(status_code=200)


@app.post("/api/v1/research", response_model=ResearchResponse)
async def start_research(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
    credentials=Depends(bearer_scheme),
):
    """
    Start a new research session.

    Returns a session_id immediately; the pipeline runs in the background.
    Connect to GET /api/v1/research/{session_id}/stream for live SSE updates.
    If the user is authenticated (Bearer token), the session is persisted to PostgreSQL.
    """
    backend_session_id = f"session_{int(time.time() * 1000)}"

    # Resolve authenticated user (optional)
    user_id: Optional[uuid.UUID] = None
    if credentials is not None:
        try:
            payload = decode_token(credentials.credentials)
            if payload.get("type") == "access":
                user_id = uuid.UUID(payload["sub"])
        except Exception:
            pass

    # ── Rate-limit: free-tier users get FREE_TIER_PROMPT_LIMIT prompts per 6 hours ──
    # Uses a DB advisory lock to prevent race conditions (two simultaneous requests).
    if user_id is not None:
        try:
            async with AsyncSessionLocal() as db:
                from src.repositories.usage import UsageRepository, FREE_TIER_PROMPT_LIMIT, FREE_TIER_WINDOW_HOURS
                from src.repositories.user import UserRepository
                user_repo = UserRepository(db)
                db_user = await user_repo.get_by_id(user_id)
                if db_user and db_user.plan == "free":
                    usage_repo = UsageRepository(db)
                    rate_info = await usage_repo.check_and_reserve_prompt(user_id)
                    if not rate_info["allowed"]:
                        raise HTTPException(
                            status_code=429,
                            detail={
                                "error": "FREE_TIER_LIMIT_REACHED",
                                "message": f"You have reached the free-tier research limit of {FREE_TIER_PROMPT_LIMIT} prompts per {FREE_TIER_WINDOW_HOURS} hours.",
                                "limit": FREE_TIER_PROMPT_LIMIT,
                                "remaining": 0,
                                "retry_after_seconds": rate_info["retry_after_seconds"],
                                "reset_at": rate_info["reset_at"],
                            },
                        )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Rate-limit check failed (continuing): {e}")

    # Create a PostgreSQL session record if authenticated
    db_session_id: Optional[uuid.UUID] = None
    if user_id is not None:
        try:
            async with AsyncSessionLocal() as db:
                session_repo = SessionRepository(db)
                db_session_dict = await session_repo.create(
                    user_id=user_id,
                    query=request.query,
                    depth=request.depth,
                    model=request.model,
                )
                await db.commit()
                db_session_id = uuid.UUID(db_session_dict["id"])
                logger.info(f"DB session created: {db_session_id}")
        except Exception as e:
            logger.error(f"Failed to create DB session: {e}")

    # Store placeholder in memory for SSE polling
    placeholder = ResearchResponse(
        status="running",
        session_id=backend_session_id,
        db_session_id=str(db_session_id) if db_session_id else None,
        errors=[],
        execution_time=0.0,
        total_tokens={"input": 0, "output": 0},
    )
    research_sessions[backend_session_id] = {
        "request": request.model_dump(),
        "response": placeholder.model_dump(),
        "full_result": {},
        "timestamp": datetime.utcnow(),
        "db_session_id": str(db_session_id) if db_session_id else None,
        "user_id": str(user_id) if user_id else None,
    }

    async def _run_workflow():
        t0 = time.time()
        try:
            # Load AI workflow lazily (only on first research request)
            workflow, AetherState = await _get_workflow()

            initial_state: dict = {
                "user_query": request.query,
                "decomposition": None,
                "research_outputs": [],
                "critic_output": None,
                "verifier_output": None,
                "fact_checker_output": None,
                "writer_output": None,
                "messages": [],
                "current_iteration": 0,
                "max_iterations": request.max_iterations,
                "confidence_scores": {},
                "errors": [],
                "total_cost": 0.0,
                "token_usage": {"input": 0, "output": 0},
                "status": "initialized",
                "depth": request.depth,
            }

            result = await workflow.ainvoke(initial_state)

            writer_output = result.get("writer_output")
            total_cost = result.get("total_cost", 0.0)
            execution_time = time.time() - t0
            workflow_status, workflow_errors = build_workflow_status(result, writer_output)

            completed = ResearchResponse(
                status=workflow_status,
                session_id=backend_session_id,
                db_session_id=str(db_session_id) if db_session_id else None,
                title=writer_output.title if writer_output else None,
                research_summary=writer_output.summary if writer_output else None,
                main_content=writer_output.main_content if writer_output else None,
                key_findings=writer_output.key_findings if writer_output else [],
                citations=writer_output.citations if writer_output else [],
                caveats=writer_output.caveats if writer_output else [],
                confidence_score=normalize_confidence_score(
                    writer_output.confidence_score if writer_output else 0.0
                ),
                cost_metrics={
                    "total_cost": total_cost,
                    "breakdown": result.get("cost_breakdown", {}),
                    "within_budget": total_cost < settings.cost_limit_per_session,
                },
                errors=workflow_errors,
                execution_time=execution_time,
                total_tokens=result.get("token_usage", {}),
            )

            research_sessions[backend_session_id].update({
                "response": completed.model_dump(),
                "full_result": result,
                "timestamp": datetime.utcnow(),
            })

            logger.info(f"Research {backend_session_id} completed in {execution_time:.2f}s")

            # ── Persist to PostgreSQL ──
            # Collect timeline events accumulated during SSE streaming
            persisted_timeline = research_sessions.get(backend_session_id, {}).get("timeline_events", [])
            await _persist_completed_research(
                backend_session_id=backend_session_id,
                db_session_id=db_session_id,
                user_id=user_id,
                query=request.query,
                depth=request.depth,
                model=request.model,
                writer_output=writer_output,
                execution_time=execution_time,
                total_cost=total_cost,
                token_usage=result.get("token_usage", {}),
                workflow_status=workflow_status,
                timeline_events=persisted_timeline,
            )

            # ── Persist findings to Neo4j (optional) ──
            if memory_manager and result.get("research_outputs"):
                try:
                    findings = []
                    for ro in result["research_outputs"]:
                        for f in ro.findings:
                            findings.append({
                                "claim": f.claim,
                                "source_url": f.source_url or "",
                                "source_title": f.source_title or "",
                                "confidence": f.confidence,
                                "tags": [backend_session_id],
                            })
                    if findings:
                        await memory_manager.track_research_session(
                            query=request.query,
                            findings=findings,
                            tags=[request.depth, backend_session_id],
                        )
                except Exception as e:
                    logger.warning(f"Neo4j persistence failed (non-fatal): {e}")

        except Exception as e:
            execution_time = time.time() - t0
            logger.exception(f"Research workflow failed: {backend_session_id}")
            research_sessions[backend_session_id]["response"]["status"] = "error"
            research_sessions[backend_session_id]["response"]["errors"] = [str(e)]
            research_sessions[backend_session_id]["response"]["execution_time"] = execution_time
            # Update DB session status on failure
            if db_session_id:
                try:
                    async with AsyncSessionLocal() as db:
                        repo = SessionRepository(db)
                        await repo.update_status(db_session_id, "error")
                        await db.commit()
                except Exception:
                    pass

    background_tasks.add_task(_run_workflow)
    return placeholder


# ── SSE stream ─────────────────────────────────────────────────────────────

@app.get("/api/v1/research/{session_id}/stream")
async def stream_research(
    session_id: str,
    token: str | None = None,   # JWT passed as ?token= for EventSource
):
    """Stream research progress via Server-Sent Events."""

    async def event_generator():
        try:
            # Wait up to 10s for session to be registered
            for _ in range(20):
                if session_id in research_sessions:
                    break
                await asyncio.sleep(0.5)

            if session_id not in research_sessions:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Session not found'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'session_start', 'session_id': session_id, 'timestamp': datetime.utcnow().isoformat()})}\n\n"

            agent_sequence = [
                ("supervisor",   "thinking",  15, "Decomposing query"),
                ("researcher",   "searching", 30, "Querying sources"),
                ("researcher",   "searching", 55, "Analysing results"),
                ("critic",       "debating",  40, "Challenging claims"),
                ("verifier",     "verifying", 50, "Cross-referencing"),
                ("fact-checker", "verifying", 60, "Checking facts"),
                ("writer",       "writing",   80, "Synthesising report"),
            ]
            tl_type_map = {
                "thinking": "decompose", "searching": "search",
                "debating": "debate",    "verifying": "verify", "writing": "write",
            }
            agent_idx = 0
            elapsed = 0

            while elapsed < 300:
                await asyncio.sleep(2)
                elapsed += 2
                current_status = (
                    research_sessions.get(session_id, {})
                    .get("response", {})
                    .get("status", "running")
                )

                if current_status == "running":
                    a_id, a_status, a_prog, a_msg = agent_sequence[agent_idx % len(agent_sequence)]
                    agent_idx += 1
                    tl_event = {'id': f'tl_{elapsed}', 'ts': int(datetime.utcnow().timestamp()*1000), 'agentRole': a_id, 'type': tl_type_map.get(a_status, "search"), 'text': a_msg}
                    yield f"data: {json.dumps({'type': 'agent_update', 'agent': {'id': a_id, 'role': a_id, 'name': a_id.replace('-', ' ').title(), 'status': a_status, 'progress': a_prog, 'message': a_msg}})}\n\n"
                    yield f"data: {json.dumps({'type': 'timeline', 'event': tl_event})}\n\n"
                    # Accumulate timeline events for persistence
                    research_sessions[session_id].setdefault("timeline_events", []).append(tl_event)
                    yield ": heartbeat\n\n"
                elif current_status in ("completed", "complete", "done", "error", "failed"):
                    break

            final = research_sessions.get(session_id, {})
            response = final.get("response", {})
            final_status = response.get("status", "")

            if final_status in ("completed", "complete", "done"):
                confidence = normalize_confidence_score(response.get("confidence_score", 0.0))

                for i, agent_id in enumerate(["supervisor", "researcher", "critic", "verifier", "fact-checker", "writer"]):
                    disp = agent_id.replace("-", " ").title()
                    tl_done = {'id': f'done_{agent_id}', 'ts': int(datetime.utcnow().timestamp()*1000)+i, 'agentRole': agent_id, 'type': 'done', 'text': f'{disp} completed'}
                    yield f"data: {json.dumps({'type': 'agent_update', 'agent': {'id': agent_id, 'role': agent_id, 'name': disp, 'status': 'done', 'progress': 100, 'message': 'Complete'}})}\n\n"
                    yield f"data: {json.dumps({'type': 'timeline', 'event': tl_done})}\n\n"
                    research_sessions[session_id].setdefault("timeline_events", []).append(tl_done)
                    await asyncio.sleep(0.02)

                for i, finding in enumerate(response.get("key_findings", [])):
                    yield f"data: {json.dumps({'type': 'finding', 'finding': {'id': f'f_{i}', 'agentRole': 'researcher', 'title': finding[:80], 'summary': finding, 'citationIds': [], 'confidence': confidence, 'relevance': 1.0, 'createdAt': int(datetime.utcnow().timestamp()*1000)}})}\n\n"
                    await asyncio.sleep(0.03)

                for i, citation in enumerate(response.get("citations", [])):
                    yield f"data: {json.dumps({'type': 'citation', 'citation': {'id': f'c_{i}', 'title': citation[:80], 'url': '', 'source': 'Backend', 'snippet': citation, 'verification': 'verified', 'confidence': confidence}})}\n\n"
                    await asyncio.sleep(0.03)

                for finding in response.get("key_findings", [])[:5]:
                    yield f"data: {json.dumps({'type': 'reasoning', 'text': finding})}\n\n"
                    await asyncio.sleep(0.02)

                report_text = response.get("main_content") or response.get("research_summary")
                if report_text:
                    title = response.get("title", "")
                    if title:
                        report_text = f"# {title}\n\n{report_text}"
                    yield f"data: {json.dumps({'type': 'report_chunk', 'text': report_text})}\n\n"

                # Include db_session_id so frontend can link to persisted session
                db_sid = response.get("db_session_id")
                yield f"data: {json.dumps({'type': 'done', 'confidence': confidence, 'session_id': session_id, 'db_session_id': db_sid})}\n\n"

            elif final_status in ("error", "failed"):
                errors = response.get("errors", ["Unknown error"])
                yield f"data: {json.dumps({'type': 'error', 'message': '; '.join(str(e) for e in errors)})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Research timed out. Please try again.'})}\n\n"

        except Exception as e:
            logger.error(f"SSE error for {session_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Status / legacy endpoints kept for backward compat ────────────────────

@app.get("/api/v1/research/{session_id}/status")
async def get_research_status(session_id: str):
    if session_id not in research_sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    data = research_sessions[session_id]
    resp = data["response"]
    req = data["request"]
    return {
        "session_id": session_id,
        "db_session_id": data.get("db_session_id"),
        "status": resp.get("status", "unknown"),
        "query": req.get("query", ""),
        "depth": req.get("depth", "balanced"),
        "model": req.get("model", ""),
        "created_at": data["timestamp"].isoformat(),
        "updated_at": data["timestamp"].isoformat(),
        "progress": 100.0 if resp.get("status") in ("completed", "complete", "done") else 20.0,
        "errors": resp.get("errors", []),
    }


# ── Follow-up research endpoint (Issue 2 — Continuous Research Chat) ──────

class FollowUpRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000, description="Follow-up question")
    depth: str = Field("balanced")
    model: str = Field("groq/compound")
    max_iterations: int = Field(2, ge=1, le=5)

    @field_validator("depth")
    @classmethod
    def validate_depth(cls, v: str) -> str:
        allowed = {"fast", "balanced", "deep"}
        if v not in allowed:
            raise ValueError(f"depth must be one of {allowed}")
        return v

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query must not be empty or whitespace")
        return stripped


@app.post("/api/v1/sessions/{db_session_id}/followup")
async def follow_up_research(
    db_session_id: str,
    request: FollowUpRequest,
    background_tasks: BackgroundTasks,
    credentials=Depends(bearer_scheme),
):
    """
    Continue a research session with a follow-up question.
    Creates a new backend_session_id for SSE streaming while keeping the
    conversation linked to the original PostgreSQL session.
    """
    # Verify authenticated user owns this session
    user_id: Optional[uuid.UUID] = None
    if credentials is not None:
        try:
            payload = decode_token(credentials.credentials)
            if payload.get("type") == "access":
                user_id = uuid.UUID(payload["sub"])
        except Exception:
            pass

    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required for follow-up")

    # ── Rate-limit: same free-tier check as initial research ──
    try:
        async with AsyncSessionLocal() as db:
            from src.repositories.usage import UsageRepository, FREE_TIER_PROMPT_LIMIT, FREE_TIER_WINDOW_HOURS
            from src.repositories.user import UserRepository
            user_repo = UserRepository(db)
            db_user = await user_repo.get_by_id(user_id)
            if db_user and db_user.plan == "free":
                usage_repo = UsageRepository(db)
                rate_info = await usage_repo.check_and_reserve_prompt(user_id)
                if not rate_info["allowed"]:
                    raise HTTPException(
                        status_code=429,
                        detail={
                            "error": "FREE_TIER_LIMIT_REACHED",
                            "message": f"You have reached the free-tier research limit of {FREE_TIER_PROMPT_LIMIT} prompts per {FREE_TIER_WINDOW_HOURS} hours.",
                            "limit": FREE_TIER_PROMPT_LIMIT,
                            "remaining": 0,
                            "retry_after_seconds": rate_info["retry_after_seconds"],
                            "reset_at": rate_info["reset_at"],
                        },
                    )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Follow-up rate-limit check failed (continuing): {e}")

    # Verify the DB session exists and belongs to the user
    try:
        async with AsyncSessionLocal() as db:
            from src.repositories.session import SessionRepository as SessRepo
            sess_repo = SessRepo(db)
            existing = await sess_repo.get_by_id_for_user(
                uuid.UUID(db_session_id), user_id
            )
            if existing is None:
                raise HTTPException(status_code=404, detail="Session not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    # Create a new in-memory backend session for this follow-up
    backend_session_id = f"session_{int(time.time() * 1000)}"

    placeholder = ResearchResponse(
        status="running",
        session_id=backend_session_id,
        db_session_id=db_session_id,
        errors=[],
        execution_time=0.0,
        total_tokens={"input": 0, "output": 0},
    )
    research_sessions[backend_session_id] = {
        "request": request.model_dump(),
        "response": placeholder.model_dump(),
        "full_result": {},
        "timestamp": datetime.utcnow(),
        "db_session_id": db_session_id,
        "user_id": str(user_id),
        "is_followup": True,
    }

    async def _run_followup():
        t0 = time.time()
        try:
            workflow, AetherState = await _get_workflow()

            initial_state: dict = {
                "user_query": request.query,
                "decomposition": None,
                "research_outputs": [],
                "critic_output": None,
                "verifier_output": None,
                "fact_checker_output": None,
                "writer_output": None,
                "messages": [],
                "current_iteration": 0,
                "max_iterations": request.max_iterations,
                "confidence_scores": {},
                "errors": [],
                "total_cost": 0.0,
                "token_usage": {"input": 0, "output": 0},
                "status": "initialized",
                "depth": request.depth,
            }

            result = await workflow.ainvoke(initial_state)
            writer_output = result.get("writer_output")
            total_cost = result.get("total_cost", 0.0)
            execution_time = time.time() - t0
            workflow_status, workflow_errors = build_workflow_status(result, writer_output)

            completed = ResearchResponse(
                status=workflow_status,
                session_id=backend_session_id,
                db_session_id=db_session_id,
                title=writer_output.title if writer_output else None,
                research_summary=writer_output.summary if writer_output else None,
                main_content=writer_output.main_content if writer_output else None,
                key_findings=writer_output.key_findings if writer_output else [],
                citations=writer_output.citations if writer_output else [],
                caveats=writer_output.caveats if writer_output else [],
                confidence_score=normalize_confidence_score(
                    writer_output.confidence_score if writer_output else 0.0
                ),
                cost_metrics={"total_cost": total_cost, "breakdown": {}, "within_budget": True},
                errors=workflow_errors,
                execution_time=execution_time,
                total_tokens=result.get("token_usage", {}),
            )

            research_sessions[backend_session_id].update({
                "response": completed.model_dump(),
                "full_result": result,
                "timestamp": datetime.utcnow(),
            })

            # Collect timeline events accumulated during SSE streaming for this follow-up
            followup_timeline = research_sessions.get(backend_session_id, {}).get("timeline_events", [])

            # Persist follow-up as a new message pair in the existing DB session
            await _persist_completed_research(
                backend_session_id=backend_session_id,
                db_session_id=uuid.UUID(db_session_id),
                user_id=user_id,
                query=request.query,
                depth=request.depth,
                model=request.model,
                writer_output=writer_output,
                execution_time=execution_time,
                total_cost=total_cost,
                token_usage=result.get("token_usage", {}),
                workflow_status=workflow_status,
                timeline_events=followup_timeline,
            )

        except Exception as e:
            execution_time = time.time() - t0
            logger.exception(f"Follow-up workflow failed: {backend_session_id}")
            research_sessions[backend_session_id]["response"]["status"] = "error"
            research_sessions[backend_session_id]["response"]["errors"] = [str(e)]
            research_sessions[backend_session_id]["response"]["execution_time"] = execution_time

    background_tasks.add_task(_run_followup)
    return placeholder


@app.post("/api/v1/research/{session_id}/export")
async def export_research(session_id: str, export_request: ExportRequest):
    if session_id not in research_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    full_result = research_sessions[session_id].get("full_result", {})
    writer_output = full_result.get("writer_output")
    content = format_report_as_markdown(writer_output)
    return Response(
        content=content.encode(),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="aether_{session_id}.md"'},
    )


@app.get("/api/v1/users/me/rate-limit")
async def get_rate_limit(credentials=Depends(bearer_scheme)):
    """
    Return the current rate-limit status for the authenticated user.
    Response:
      prompts_used        — prompts used in current rolling window
      prompts_allowed     — max allowed (free tier = 2, unlimited = -1)
      remaining           — prompts left (0 if limited)
      reset_at            — ISO UTC timestamp when oldest prompt expires
      retry_after_seconds — seconds until reset (0 if not limited)
      hours_remaining     — convenience float (hours until reset)
      is_limited          — true if user has hit the limit
    """
    user_id: Optional[uuid.UUID] = None
    if credentials is not None:
        try:
            payload = decode_token(credentials.credentials)
            if payload.get("type") == "access":
                user_id = uuid.UUID(payload["sub"])
        except Exception:
            pass

    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        async with AsyncSessionLocal() as db:
            from src.repositories.usage import UsageRepository, FREE_TIER_PROMPT_LIMIT, FREE_TIER_WINDOW_HOURS
            from src.repositories.user import UserRepository
            user_repo = UserRepository(db)
            db_user = await user_repo.get_by_id(user_id)

            # Pro/unlimited users — no limit
            if db_user and db_user.plan != "free":
                return {
                    "prompts_used": 0,
                    "prompts_allowed": -1,
                    "remaining": -1,
                    "reset_at": None,
                    "retry_after_seconds": 0,
                    "hours_remaining": 0.0,
                    "is_limited": False,
                }

            usage_repo = UsageRepository(db)
            rate_info = await usage_repo.count_prompts_in_window(user_id)

            retry_after = rate_info.get("retry_after_seconds", 0)
            hours_remaining = round(retry_after / 3600, 2) if retry_after > 0 else 0.0

            return {
                "prompts_used": rate_info["prompts_used"],
                "prompts_allowed": rate_info["prompts_allowed"],
                "remaining": rate_info["remaining"],
                "reset_at": rate_info["reset_at"],
                "retry_after_seconds": retry_after,
                "hours_remaining": hours_remaining,
                "is_limited": rate_info["prompts_used"] >= rate_info["prompts_allowed"],
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rate-limit check error: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch rate limit info")


@app.get("/api/v1/analytics")
async def get_analytics():
    completed = [
        s for s in research_sessions.values()
        if s["response"].get("status") in ("completed", "complete", "done")
    ]
    return {
        "total_sessions": len(research_sessions),
        "completed_sessions": len(completed),
        "average_confidence": (
            sum(s["response"].get("confidence_score", 0) for s in completed) / len(completed)
            if completed else 0.0
        ),
        "timestamp": datetime.utcnow().isoformat(),
    }
