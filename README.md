# Hilti RouteIQ

AI sales visit copilot for Hilti field salespeople and account managers.

Google Maps tells the salesperson the shortest route. RouteIQ tells the salesperson the most valuable route.

## What is built

- SDD artifacts under `specs/`, including **Submodule 1 (prioritization + explainability):** [`specs/submodule-1-prioritization-architecture.md`](specs/submodule-1-prioritization-architecture.md).
- FastAPI backend with contract-first demo endpoints.
- React + TypeScript PWA shell with install metadata.
- Docker Compose setup for local demo.
- Synthetic Kuala Lumpur sales dataset with 5 territories, 5 salespeople, 400 customers, visits, and orders.
- Heuristic AI scoring and a value-aware route optimizer fallback.

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
fastapi dev app/main.py
```

Backend: `http://localhost:8000`

Install `backend/requirements-ai.txt` when starting M1-M3 data generation, scoring, and routing work.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

### Docker Compose

```powershell
docker compose up --build
```

## Demo Script

1. Open the PWA on a phone-sized browser viewport.
2. Show expected return, travel distance, and recommended stops.
3. Tap **Navigate** to open Google Maps for the next customer.
4. Explain that RouteIQ selects the most valuable route, while Google Maps only navigates to the next stop.
5. Install the app via browser **Add to Home Screen** once served over HTTPS or localhost.

## Next Module

M1 synthetic data is available:

```powershell
cd backend
python -m app.data.generate --csv
```

This creates `backend/data/seed/hilti.sqlite` and CSV exports with 5 KL territories, 5 salespeople, 400 customers, visits, and orders.

Next up: M2 customer scoring, then M3 route optimization.
