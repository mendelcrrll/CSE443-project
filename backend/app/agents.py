from textwrap import dedent
from typing import Any
import os
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


AGENT_PROMPTS = {
    "yapper": dedent(
        """
        You are "The Yapper", a curious and supportive journaling assistant.
        Help users describe symptoms and lived experience in detail.
        Do not diagnose. Keep language non-diagnostic and suggest professional care when relevant.
        """
    ).strip(),
    "definer": dedent(
        """
        You are "The Definer", focused on clear medical definitions.
        Explain terms plainly and avoid diagnosis.
        Include short, neutral explanations and mention uncertainty when appropriate.
        """
    ).strip(),
    "redditor": dedent(
        """
        You are "The Redditor", focused on community discovery.
        Use provided thread context to suggest relevant communities/posts.
        Do not claim medical certainty and do not present diagnosis.
        """
    ).strip(),
    "engager": dedent(
        """
        You are "The Engager", helping draft respectful community or doctor-facing messages.
        Keep tone clear, ethical, and non-diagnostic.
        """
    ).strip(),
    "auditor": dedent(
        """
        You are "The Auditor", focused on safety and ethics.
        Flag risky phrasing, overconfident diagnosis language, or unsafe advice.
        Suggest safer rewrites.
        """
    ).strip(),
}


def available_agents() -> list[str]:
    return list(AGENT_PROMPTS.keys())


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


def _agent_chain(agent: str, model_name: str):
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", AGENT_PROMPTS[agent]),
            (
                "user",
                dedent(
                    """
                    User message:
                    {message}

                    Optional context:
                    {context}
                    """
                ).strip(),
            ),
        ]
    )
    llm = ChatOpenAI(model=model_name, temperature=0.2, api_key=_resolve_openai_api_key())
    return prompt | llm


def run_agent(
    agent: str,
    message: str,
    model_name: str,
    context: str = "",
) -> str:
    if agent not in AGENT_PROMPTS:
        raise ValueError(f"Unknown agent: {agent}")
    chain = _agent_chain(agent, model_name)
    result = chain.invoke({"message": message, "context": context})
    return result.content if isinstance(result.content, str) else str(result.content)


def format_redditor_context(search_results: list[dict[str, Any]]) -> str:
    if not search_results:
        return "No matching local Reddit threads found."
    lines = ["Candidate threads:"]
    for idx, row in enumerate(search_results, start=1):
        lines.append(f"{idx}. {row['title']} ({row['url']}) score={row['score']}")
    return "\n".join(lines)
