# Retro HTML UI

This is a standalone HTML/CSS/JS frontend that keeps the retro chatroom style and connects to the existing FastAPI backend.

## Files

- `index.html`
- `styles.css`
- `app.js`

## Run

1. Start backend:

```powershell
python -m uvicorn backend.app.main:app --reload
```

2. Serve this folder on a local static server (required for browser fetch/CORS behavior):

```powershell
cd retro-html-ui
python -m http.server 5500
```

3. Open:

- `http://127.0.0.1:5500`

## Features

- Chatrooms are stored per username in browser `localStorage`.
- Users can create rooms, re-enter old rooms, and view prior conversation history.
- Messages still use backend `/agents` and `/chat`.

## Notes

- Backend URL is set in `app.js` as `http://127.0.0.1:8000`.
- Browser storage means history is local to the current browser/device.
