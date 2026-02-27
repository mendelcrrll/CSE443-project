## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

```powershell
pip install -r backend/requirements.txt
```

3. Set your API key:

```powershell
$env:OPENAI_API_KEY="your-key"
```

4. Run the API:

```powershell
python -m uvicorn backend.app.main:app --reload
```

## Architecture implemented

- Leader-first orchestration (`yapper`) using LangChain `create_agent`
- Toggleable supporting nodes: `definer`, `redditor`, `engager`
- Aggregator pass to remove duplicate statements
- Always-on `auditor` pass to enforce non-diagnostic output constraints
- Session-level memory persisted to local SQLite (`backend/data/local.db`)
- Local subreddit search integration (`pmdd_search/pmdd.json`)

## API endpoints

- `GET /health`
- `GET /agents`
- `POST /search`
- `POST /chat`
- `POST /memory`
- `GET /memory/{bucket}?session_id=default`

## `/chat` payload (backward compatible)

```json
{
  "message": "I have headaches around my cycle and fatigue",
  "active_agent": "yapper",
  "enabled_agents": ["yapper", "definer", "redditor", "engager"],
  "model_name": "gpt-4o-mini",
  "save_to": "journal",
  "session_id": "default"
}
```

`session_id` is optional and defaults to `default`.

## Notes

- The frontend can stay unchanged and continue calling `/chat` the same way.
- `auditor` is always executed before returning the final response.
- Outputs are support-oriented and intentionally non-diagnostic.
- SQLite is built into Python, so no additional database dependency is required.
