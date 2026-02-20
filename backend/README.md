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

## API endpoints

- `GET /health`
- `GET /agents`
- `POST /search`
- `POST /chat`
- `POST /memory`
- `GET /memory/{bucket}`

## Frontend CORS

The backend currently allows these local origins:
- `http://localhost:5173`
- `http://127.0.0.1:5173`
- `http://localhost:5500`
- `http://127.0.0.1:5500`

## Example request

```powershell
curl -X POST "http://127.0.0.1:8000/chat" `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"I have headaches around my cycle and fatigue\",\"active_agent\":\"redditor\",\"enabled_agents\":[\"redditor\"],\"save_to\":\"journal\"}"
```

## Notes

- This is intentionally lightweight for testing architecture and flow.
- The `redditor` agent enriches answers with local thread matches from `pmdd.json`.
- No diagnosis logic is implemented; prompts keep the tool non-diagnostic.
