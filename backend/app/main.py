from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .agents import available_agents, run_orchestration
from .search_tool import search_posts
from .store import SAVE_BUCKETS, SessionStore

app = FastAPI(title="CSE443 Multi-Agent Backend", version="0.2.0")
store = SessionStore()

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
    session_id: str = "default"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class SaveRequest(BaseModel):
    bucket: str
    content: str
    session_id: str = "default"


class DeleteSessionRequest(BaseModel):
    session_id: str = Field(min_length=1)


def _format_supporting_message(agent: str, payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None

    if agent == "definer":
        definitions = payload.get("definitions", [])
        if not isinstance(definitions, list) or not definitions:
            return None
        lines: list[str] = ["Possible definitions:"]
        for item in definitions[:3]:
            if not isinstance(item, dict):
                continue
            term = str(item.get("term", "")).strip()
            definition = str(item.get("definition", "")).strip()
            if term and definition:
                lines.append(f"- {term}: {definition}")
        return "\n".join(lines) if len(lines) > 1 else None

    if agent == "redditor":
        threads = payload.get("relevant_threads", [])
        if not isinstance(threads, list) or not threads:
            return None
        lines: list[str] = ["Related community threads:"]
        for thread in threads[:2]:
            if not isinstance(thread, dict):
                continue
            title = str(thread.get("title", "")).strip()
            url = str(thread.get("url", "")).strip()
            if title and url:
                lines.append(f"- {title} ({url})")
        return "\n".join(lines) if len(lines) > 1 else None

    if agent == "engager":
        draft = str(payload.get("draft_message", "")).strip()
        return f"Draft message option:\n{draft}" if draft else None

    return None


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

    session = store.get_session(req.session_id)
    history = session.get("conversation_history", [])
    history.append({"role": "user", "content": req.message})

    try:
        orchestration = run_orchestration(
            message=req.message,
            model_name=req.model_name,
            conversation_history=history,
            active_agent=req.active_agent,
            enabled_agents=req.enabled_agents,
            search_query=req.search_query,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response_text = str(orchestration["response"])
    leader_response = str(orchestration.get("leader_response", response_text))
    store.append_history(req.session_id, "user", req.message)
    store.append_history(req.session_id, "assistant", leader_response)

    leader_output = orchestration.get("leader_output", {})
    symptoms = leader_output.get("candidate_symptoms", [])
    if isinstance(symptoms, list):
        store.set_structured_symptom_list(req.session_id, [str(item) for item in symptoms])

    selected_nodes = orchestration.get("selected_supporting_nodes", [])
    active_nodes = [req.active_agent, *[str(item) for item in selected_nodes], "auditor"]
    store.set_active_agents(req.session_id, active_nodes)

    audit_output = orchestration.get("audit_output", {})
    store.append_audit_log(
        req.session_id,
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "active_agent": req.active_agent,
            "flagged_segments": audit_output.get("flagged_segments", []),
            "revision_suggestions": audit_output.get("revision_suggestions", []),
        },
    )

    if req.save_to:
        store.save(
            req.session_id,
            req.save_to,
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "agent": req.active_agent,
                "message": req.message,
                "response": response_text,
            },
        )

    supporting_outputs = orchestration.get("supporting_outputs", {})
    agent_messages: list[dict[str, str]] = [{"agent": req.active_agent, "text": leader_response}]
    for node_name in orchestration.get("selected_supporting_nodes", []):
        text = _format_supporting_message(str(node_name), supporting_outputs.get(str(node_name)))
        if text:
            agent_messages.append({"agent": str(node_name), "text": text})

    return {
        "active_agent": req.active_agent,
        "response": response_text,
        "agent_messages": agent_messages,
        "tool_results": orchestration.get("thread_summaries", []),
        "intermediate": leader_output,
        "supporting_outputs": supporting_outputs,
        "audit": audit_output,
    }


@app.post("/memory")
def save(req: SaveRequest) -> dict[str, str]:
    if req.bucket not in SAVE_BUCKETS:
        raise HTTPException(status_code=400, detail=f"bucket must be one of {sorted(SAVE_BUCKETS)}")
    store.save(
        req.session_id,
        req.bucket,
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "content": req.content,
        },
    )
    return {"status": "saved"}


@app.get("/memory/{bucket}")
def list_saved(bucket: str, session_id: str = "default") -> dict[str, object]:
    if bucket not in SAVE_BUCKETS:
        raise HTTPException(status_code=400, detail=f"bucket must be one of {sorted(SAVE_BUCKETS)}")
    return {"bucket": bucket, "session_id": session_id, "items": store.list_saved(session_id, bucket)}


@app.post("/session/delete")
def delete_session(req: DeleteSessionRequest) -> dict[str, object]:
    deleted = store.delete_session(req.session_id)
    return {"status": "deleted", "session_id": req.session_id, "deleted": deleted}
