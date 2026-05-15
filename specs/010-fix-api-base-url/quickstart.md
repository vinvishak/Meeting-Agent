# Quickstart: Fix Dashboard API Base URL

## Scenario 1 — Production dashboard loads (happy path)

1. Deploy to Railway (or any remote host)
2. Open `https://<host>/app` in a browser
3. **Expected**: Overview section loads with org health data — no red error banner
4. **Expected**: All navigation tabs (Goals, Teams, Projects, Meetings, Insights) load data

## Scenario 2 — Local development not broken

1. Start the local server: `uv run uvicorn src.api.app:create_app --factory --port 8000`
2. Open `http://localhost:8000/app`
3. **Expected**: Dashboard loads identically to before the fix

## Scenario 3 — Browser console is clean

1. Open the dashboard on Railway
2. Open browser DevTools → Console tab
3. **Expected**: No `net::ERR_CONNECTION_REFUSED` or `Failed to fetch` errors targeting `localhost`
