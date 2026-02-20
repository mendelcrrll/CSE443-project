from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agents import available_agents, format_redditor_context, run_agent
from .search_tool import search_posts
from .store import LocalStore

app = FastAPI(title="CSE443 Multi-Agent Backend", version="0.1.0")
store = LocalStore()

SAVE_BUCKETS = {"journal", "definitions", "threads", "drafts", "audit_logs"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    active_agent: Literal["yapper", "definer", "redditor", "engager", "auditor"]
    enabled_agents: list[str] = Field(default_factory=list)
    model_name: str = "gpt-4o-mini"
    search_query: str | None = None
    save_to: Literal["journal", "definitions", "threads", "drafts", "audit_logs"] | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class SaveRequest(BaseModel):
    bucket: str
    content: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/agents")
def agents() -> dict[str, list[str]]:
    return {"agents": available_agents()}


@app.post("/search")
def search(req: SearchRequest) -> dict[str, object]:
    return {"query": req.query, "results": search_posts(req.query, req.limit)}


@app.post("/chat")
def chat(req: ChatRequest) -> dict[str, object]:
    if req.enabled_agents and req.active_agent not in req.enabled_agents:
        raise HTTPException(status_code=400, detail="active_agent must be in enabled_agents.")

    context = ""
    tool_results = []
    if req.active_agent == "redditor":
        query = req.search_query or req.message
        tool_results = search_posts(query, limit=5)
        context = format_redditor_context(tool_results)

    try:
        output = run_agent(
            agent=req.active_agent,
            message=req.message,
            model_name=req.model_name,
            context=context,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if req.save_to:
        store.save(
            req.save_to,
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "agent": req.active_agent,
                "message": req.message,
                "response": output,
            },
        )

    return {
        "active_agent": req.active_agent,
        "response": output,
        "tool_results": tool_results,
    }


@app.post("/memory")
def save(req: SaveRequest) -> dict[str, str]:
    if req.bucket not in SAVE_BUCKETS:
        raise HTTPException(status_code=400, detail=f"bucket must be one of {sorted(SAVE_BUCKETS)}")
    store.save(
        req.bucket,
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "content": req.content,
        },
    )
    return {"status": "saved"}


@app.get("/memory/{bucket}")
def list_saved(bucket: str) -> dict[str, object]:
    if bucket not in SAVE_BUCKETS:
        raise HTTPException(status_code=400, detail=f"bucket must be one of {sorted(SAVE_BUCKETS)}")
    return {"bucket": bucket, "items": store.list(bucket)}
