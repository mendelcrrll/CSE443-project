# Vite Frontend (MUI)

## Setup

From repo root:

```powershell
cd frontend
copy .env.example .env
npm install
npm run dev
```

App runs at `http://127.0.0.1:5173`.

## Backend

Make sure backend is running at `http://127.0.0.1:8000`:

```powershell
python -m uvicorn backend.app.main:app --reload
```
