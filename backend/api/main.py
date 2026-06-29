"""
Main FastAPI application entrypoint.

Responsibilities:
  - Create the FastAPI app and register all routers
  - Run startup tasks: initialize the database schema, build/verify the
    RAG vector index, so the app is fully ready before it accepts traffic
  - Configure CORS so the Streamlit frontend (running on a different port)
    can call this API from the browser
  - Expose a health check endpoint for monitoring / load balancers

Run with:
    uvicorn backend.api.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.analytics_routes import router as analytics_router
from backend.api.api_schemas import HealthResponse
from backend.api.chat_routes import router as chat_router
from backend.api.ticket_routes import router as ticket_router
from backend.database.db import init_db
from backend.rag.retriever import initialize_knowledge_base
from backend.utils.config import settings
from backend.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI's recommended startup/shutdown hook. Code before `yield` runs
    once when the app starts (before accepting any requests); code after
    `yield` would run on shutdown (we don't need any cleanup here, but the
    pattern is there for e.g. closing connections gracefully later).
    """
    logger.info("Starting Enterprise AI Support Agent API (env={})", settings.app_env)

    init_db()

    # build_from_knowledge_base() internally no-ops if already populated,
    # so this is safe to call on every startup without re-embedding
    # everything each time the server restarts.
    initialize_knowledge_base(force_rebuild=False)

    logger.info("Startup complete — API ready to accept requests")
    yield
    logger.info("Shutting down Enterprise AI Support Agent API")


app = FastAPI(
    title="TechNova Cloud — Enterprise AI Support Agent",
    description=(
        "Production-style AI customer support platform demonstrating RAG, "
        "agentic tool calling, LangGraph workflow orchestration, and "
        "conversational memory."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Streamlit's default dev server runs on a different port (8501) than this
# API (8000), so the browser treats them as different origins. CORS must
# explicitly allow the frontend's origin or the browser will block the
# request before it even reaches FastAPI.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened to specific origins in a real deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(ticket_router)
app.include_router(analytics_router)


@app.get("/", response_model=HealthResponse)
@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Simple liveness/readiness check — confirms the app is up and shows
    which LLM model and environment it's configured for.
    """
    return HealthResponse(status="ok", app_env=settings.app_env, llm_model=settings.llm_model)
