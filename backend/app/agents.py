import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from textwrap import dedent
from typing import Any

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

from .search_tool import search_posts

NODE_NAMES = ["yapper", "definer", "redditor", "engager", "auditor"]
SUPPORTING_NODES = {"definer", "redditor", "engager"}

# Below are prompts for each node define their specific roles and expected JSON outputs, 
# guiding them to process the user's input in a structured way while adhering 
# to constraints like avoiding diagnoses or treatment recommendations. 

# The leader prompt is dynamically adjusted based on the active agent's style, 
# providing tailored guidance for parsing the user's narrative and 
# extracting relevant information.

# The definer prompt instructs the Definer node to translate symptom language into 
# standardized terminology and plain-language definitions, 
# emphasizing that it should not make diagnoses. The expected output is 
# a JSON object containing a list of standardized symptoms, definitions 
# for relevant terms, and an evidence mapping.
DEFINER_PROMPT = dedent(
    """
    You are the Definer node.
    Translate symptom language to standardized terminology and plain-language definitions.
    Do not diagnose.
    Return JSON ONLY:
    {
      "standardized_symptom_list": ["string"],
      "definitions": [{"term": "string", "definition": "string"}],
      "evidence_mapping": ["string"]
    }
    """
).strip()

# The prompt for the Redditor node instructs it to search for relevant threads 
# in a local subreddit index, summarize their relevance, 
# and return structured information about the threads and subreddit metadata. 
# It emphasizes ethical sourcing of keywords and context, 
# and explicitly prohibits making diagnoses. 
# The expected output is a JSON object containing a list of relevant threads with 
# their titles, URLs, summaries, and scores, as well as any relevant subreddit metadata.
REDDITOR_PROMPT = dedent(
    """
    You are the Redditor node.
    Use subreddit_search to find ethically useful community threads.
    Do not claim diagnoses.
    Return JSON ONLY:
    {
      "relevant_threads": [{"title": "string", "url": "string", "summary": "string", "score": 0.0}],
      "subreddit_metadata": ["string"]
    }
    """
).strip()

ENGAGER_PROMPT = dedent(
    """
    You are the Engager node.
    Draft a respectful community post and questions for a medical professional.
    Keep language non-diagnostic.
    Return JSON ONLY:
    {
      "draft_message": "string",
      "posting_guidelines": ["string"],
      "questions_for_medical_professional": ["string"]
    }
    """
).strip()

AUDITOR_PROMPT = dedent(
    """
    You are the Auditor node and are always active.
    Check for diagnosing language, treatment recommendations, probabilistic claims, and alarmist framing.
    Rewrite risky language safely.
    Return JSON ONLY:
    {
      "flagged_segments": ["string"],
      "revision_suggestions": ["string"],
      "safe_output": "string"
    }
    """
).strip()

LEADER_RESPONSE_PROMPT = dedent(
    """
    You are the leader assistant speaking directly to the user.
    Give a concise, supportive, non-diagnostic response in plain language.
    Do not draft a community post unless the user explicitly asks for one.
    Avoid repetitive canned closing lines (for example: "I'm here to listen and support you.").
    End naturally based on the conversation instead of using the same sign-off each turn.
    Include at most:
    - a short acknowledgement of what they shared
    - 1-3 clarifying follow-up questions when useful
    - a brief safety note ONLY when there are clear red flags, severe symptoms, crisis language,
      self-harm risk, or the user asks for diagnosis/treatment advice
    Do NOT add a clinician reminder by default for routine symptom discussion.
    """
).strip()


def available_agents() -> list[str]:
    return list(NODE_NAMES)


def _leader_prompt_for(active_agent: str) -> str:
    role_guidance = {
        "yapper": "Prioritize narrative parsing and symptom extraction.",
        "definer": "Prioritize precise symptom terminology and uncertainty boundaries.",
        "redditor": "Prioritize ethically sourcing community-search keywords and context.",
        "engager": "Prioritize respectful drafting and actionable follow-up questions.",
        "auditor": "Prioritize risk-sensitive interpretation and conservative wording.",
    }
    guidance = role_guidance.get(active_agent, role_guidance["yapper"])
    return dedent(
        f"""
        You are the Leader Node and your active style is "{active_agent}".
        {guidance}
        You must NOT diagnose, prescribe treatments, or claim certainty.
        Parse user free-form text into JSON ONLY with this schema:
        {{
          "narrative_summary": "string",
          "candidate_symptoms": ["string"],
          "questions_to_clarify": ["string"],
          "research_keywords": ["string"],
          "engagement_ready": false,
          "raw_symptom_phrases": ["string"],
          "timeline_information": "string",
          "reported_impacts": ["string"],
          "uncertainties": ["string"]
        }}
        """
    ).strip()


def _load_key_from_dotenv(dotenv_path: Path) -> str | None:
    if not dotenv_path.exists():
        return None

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != "OPENAI_API_KEY":
            continue
        key = value.strip().strip('"').strip("'")
        return key or None
    return None


def _resolve_openai_api_key() -> str:
    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key

    project_root = Path(__file__).resolve().parents[2]
    dotenv_key = _load_key_from_dotenv(project_root / ".env")
    if dotenv_key:
        return dotenv_key

    secret_file = project_root / "secret-key.txt"
    if secret_file.exists():
        file_key = secret_file.read_text(encoding="utf-8").strip()
        if file_key:
            return file_key

    raise RuntimeError(
        "OpenAI API key is missing. Set OPENAI_API_KEY, or add OPENAI_API_KEY to .env, or place the key in secret-key.txt."
    )


def _make_model(model_name: str) -> ChatOpenAI:
    return ChatOpenAI(model=model_name, temperature=0.2, api_key=_resolve_openai_api_key())


def _extract_text(result: dict[str, Any]) -> str:
    message = result["messages"][-1]
    text = getattr(message, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item and isinstance(item["text"], str):
                chunks.append(item["text"])
            elif isinstance(item, str):
                chunks.append(item)
        return "\n".join(chunks)
    return str(content)


def _parse_json(text: str, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return fallback
    return fallback


def _build_message(history: list[dict[str, str]], payload: dict[str, Any]) -> str:
    history_text = "\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in history[-8:])
    return dedent(
        f"""
        Conversation history:
        {history_text if history_text else "(none)"}

        Payload JSON:
        {json.dumps(payload, ensure_ascii=True)}
        """
    ).strip()


@tool
def subreddit_search(query: str, limit: int = 5) -> str:
    """Search local subreddit index for relevant threads."""
    return json.dumps(search_posts(query, limit=limit), ensure_ascii=True)


def _invoke_node(system_prompt: str, model_name: str, user_content: str, tools: list[Any] | None = None) -> str:
    agent = create_agent(_make_model(model_name), tools=tools or [], system_prompt=system_prompt)
    result = agent.invoke({"messages": [{"role": "user", "content": user_content}]})
    return _extract_text(result)


def _dedupe_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for line in lines:
        normalized = re.sub(r"\s+", " ", line.strip().lower())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(line.strip())
    return deduped


def _normalize_enabled_agents(active_agent: str, enabled_agents: list[str]) -> list[str]:
    if enabled_agents:
        enabled = {name for name in enabled_agents if name in SUPPORTING_NODES}
    else:
        enabled = set(SUPPORTING_NODES)
    if active_agent in enabled:
        enabled.remove(active_agent)
    return sorted(enabled)


def _should_run_engager(message: str, leader_output: dict[str, Any]) -> bool:
    if bool(leader_output.get("engagement_ready", False)):
        return True
    text = message.lower()
    triggers = ["draft", "write", "post", "reddit", "community", "message", "send this"]
    return any(trigger in text for trigger in triggers)


def _build_leader_response(
    model_name: str,
    message: str,
    conversation_history: list[dict[str, str]],
    leader_output: dict[str, Any],
) -> str:
    request = _build_message(
        conversation_history,
        {
            "user_prompt": message,
            "leader_output": leader_output,
            "task": "Respond to the user directly as the leader assistant",
        },
    )
    return _invoke_node(LEADER_RESPONSE_PROMPT, model_name, request)


def _aggregate_outputs(
    leader_response: str,
    leader_output: dict[str, Any],
    node_outputs: dict[str, dict[str, Any]],
) -> str:
    lines: list[str] = []
    if leader_response.strip():
        lines.append(leader_response.strip())

    definer = node_outputs.get("definer", {})
    definitions = definer.get("definitions", []) if isinstance(definer, dict) else []
    if isinstance(definitions, list) and definitions:
        term_lines: list[str] = []
        for item in definitions[:3]:
            if not isinstance(item, dict):
                continue
            term = str(item.get("term", "")).strip()
            definition = str(item.get("definition", "")).strip()
            if term and definition:
                term_lines.append(f"- {term}: {definition}")
        if term_lines:
            lines.append("Possible terms to research:")
            lines.extend(term_lines)

    redditor = node_outputs.get("redditor", {})
    threads = redditor.get("relevant_threads", []) if isinstance(redditor, dict) else []
    if isinstance(threads, list) and threads:
        thread_lines: list[str] = []
        for thread in threads[:2]:
            if not isinstance(thread, dict):
                continue
            title = str(thread.get("title", "")).strip()
            url = str(thread.get("url", "")).strip()
            if title and url:
                thread_lines.append(f"- {title} ({url})")
        if thread_lines:
            lines.append("Community threads you could review:")
            lines.extend(thread_lines)

    engager = node_outputs.get("engager", {})
    draft_message = str(engager.get("draft_message", "")).strip() if isinstance(engager, dict) else ""
    if draft_message:
        lines.append("Draft message (optional):")
        lines.append(draft_message)

    candidate_symptoms = leader_output.get("candidate_symptoms", [])
    if isinstance(candidate_symptoms, list) and candidate_symptoms:
        joined = ", ".join(str(item) for item in candidate_symptoms[:5])
        lines.append(f"Captured symptom keywords: {joined}")

    return "\n".join(_dedupe_lines(lines))


def _rule_based_audit(text: str) -> list[str]:
    checks = [
        r"\byou (have|likely have|definitely have)\b",
        r"\bdiagnos(is|e|ed)\b",
        r"\bcure\b",
        r"\bguarantee(d)?\b",
        r"\b\d{1,3}%\b",
        r"\bmust take\b",
    ]
    flags: list[str] = []
    lowered = text.lower()
    for pattern in checks:
        if re.search(pattern, lowered):
            flags.append(f"Matched risky pattern: {pattern}")
    return flags


def run_orchestration(
    message: str,
    model_name: str,
    conversation_history: list[dict[str, str]],
    active_agent: str,
    enabled_agents: list[str],
    search_query: str | None = None,
) -> dict[str, Any]:
    if active_agent not in NODE_NAMES:
        raise ValueError(f"Unknown leader node: {active_agent}")

    leader_payload = {"user_prompt": message}
    leader_request = _build_message(conversation_history, leader_payload)
    leader_text = _invoke_node(_leader_prompt_for(active_agent), model_name, leader_request)
    leader_output = _parse_json(
        leader_text,
        {
            "narrative_summary": leader_text.strip(),
            "candidate_symptoms": [],
            "questions_to_clarify": [],
            "research_keywords": [],
            "engagement_ready": False,
            "raw_symptom_phrases": [],
            "timeline_information": "",
            "reported_impacts": [],
            "uncertainties": [],
        },
    )
    leader_response = _build_leader_response(model_name, message, conversation_history, leader_output)

    selected_supporting_nodes = _normalize_enabled_agents(active_agent, enabled_agents)
    if "engager" in selected_supporting_nodes and not _should_run_engager(message, leader_output):
        selected_supporting_nodes = [name for name in selected_supporting_nodes if name != "engager"]

    node_outputs: dict[str, dict[str, Any]] = {}
    thread_summaries: list[dict[str, Any]] = []

    def run_definer() -> tuple[str, dict[str, Any]]:
        request = _build_message(
            conversation_history,
            {
                "leader_output": leader_output,
                "task": "standardize symptom terms and define them plainly",
            },
        )
        text = _invoke_node(DEFINER_PROMPT, model_name, request)
        return "definer", _parse_json(text, {"standardized_symptom_list": [], "definitions": [], "evidence_mapping": []})

    def run_redditor() -> tuple[str, dict[str, Any]]:
        keywords = leader_output.get("research_keywords", [])
        query = search_query or (" ".join(str(item) for item in keywords if str(item).strip()) or message)
        request = _build_message(
            conversation_history,
            {
                "leader_output": leader_output,
                "search_query": query,
                "task": "find relevant discussion threads and summarize relevance",
            },
        )
        text = _invoke_node(REDDITOR_PROMPT, model_name, request, tools=[subreddit_search])
        parsed = _parse_json(text, {"relevant_threads": [], "subreddit_metadata": []})
        return "redditor", parsed

    def run_engager() -> tuple[str, dict[str, Any]]:
        request = _build_message(
            conversation_history,
            {
                "leader_output": leader_output,
                "task": "draft a respectful post and medical appointment questions",
            },
        )
        text = _invoke_node(ENGAGER_PROMPT, model_name, request)
        parsed = _parse_json(
            text,
            {
                "draft_message": text.strip(),
                "posting_guidelines": [],
                "questions_for_medical_professional": [],
            },
        )
        return "engager", parsed

    workers: dict[str, Any] = {
        "definer": run_definer,
        "redditor": run_redditor,
        "engager": run_engager,
    }

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(workers[name]) for name in selected_supporting_nodes if name in workers]
        for future in futures:
            try:
                name, parsed = future.result()
            except Exception:
                continue
            else:
                node_outputs[name] = parsed
                if name == "redditor":
                    threads = parsed.get("relevant_threads", [])
                    if isinstance(threads, list):
                        thread_summaries = [item for item in threads if isinstance(item, dict)]

    aggregated_output = _aggregate_outputs(leader_response, leader_output, node_outputs)
    rule_flags = _rule_based_audit(aggregated_output)

    audit_request = _build_message(
        conversation_history,
        {
            "aggregated_output": aggregated_output,
            "required_constraints": [
                "No diagnosis",
                "No treatment prescription",
                "No probabilistic certainty",
                "No alarmist framing",
            ],
        },
    )
    audit_text = _invoke_node(AUDITOR_PROMPT, model_name, audit_request)
    audit_output = _parse_json(
        audit_text,
        {
            "flagged_segments": [],
            "revision_suggestions": [],
            "safe_output": aggregated_output,
        },
    )

    combined_flags = []
    combined_flags.extend(str(item) for item in audit_output.get("flagged_segments", []) if str(item).strip())
    combined_flags.extend(rule_flags)
    audit_output["flagged_segments"] = _dedupe_lines(combined_flags)

    safe_output = str(audit_output.get("safe_output", "")).strip() or aggregated_output
    return {
        "response": safe_output,
        "leader_response": leader_response,
        "leader_output": leader_output,
        "supporting_outputs": node_outputs,
        "aggregated_output": aggregated_output,
        "audit_output": audit_output,
        "selected_supporting_nodes": selected_supporting_nodes,
        "thread_summaries": thread_summaries,
    }
