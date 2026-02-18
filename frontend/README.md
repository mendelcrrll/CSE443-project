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

## Notes

- This includes your shared MUI package via:
  - `@digitalaidseattle/mui: file:C:/Users/mende/DAS/component-library/packages/mui`
- If install fails because of private/internal deps in that package, remove that dependency line and keep standard `@mui/material` deps only.
