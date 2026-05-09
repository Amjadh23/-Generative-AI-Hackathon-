# RouteIQ — project context (for a new machine or teammate)

Copy this file (and the repo) to another laptop so Cursor, teammates, or future-you understand **what this app is**, **how it is built**, and **how to run it**. This complements `README.md` with architecture, hackathon framing, and **Ollama** setup.

---

## One-line pitch

**RouteIQ** is an AI copilot for Hilti field sales: it ranks **which customers** to visit today (with **explainable reasons**), builds a **value-aware visit order** (not just shortest drive), and supports **voice visit recaps** plus **RIQ** (grounded chat). *Google Maps optimizes the drive; RouteIQ optimizes the visit.*

---

## Hackathon problem statement (alignment)

Official ask (paraphrased): build an **AI** solution that helps salespeople decide **which customers to visit** and **in what order** in their **assigned area**, optimizing **travel efficiency**, **proximity**, and **sales return**.

| Theme | How RouteIQ addresses it |
|--------|---------------------------|
| Which customers | ML **visit likelihood** + **priority class** (Low / Medium / High) per assigned customer |
| What order | **Route optimizer** trades **expected return** vs **distance** (haversine), respects **max daily stops** |
| Assigned area | Customers tied to **salesperson**; **territories** in seed data |
| Travel / proximity | Distances and ETAs on the day plan; **Navigate** opens Google Maps for the next stop |
| Sales return | **Expected return (RM)** and value-aware ordering |

---

## Architecture (high level)

1. **Data** — SQLite DB (`backend/data/seed/hilti.sqlite`) + CSV exports under `backend/data/seed/csv/`. Synthetic **Kuala Lumpur**-style dataset: customers, visits, orders, salespeople, territories.
2. **Submodule 1 — prioritization** — Feature engineering **without** using CRM `priority` as a model input. **XGBoost** regression → `visit_likelihood_score` (0–1) → **priority class** bins. **Tree SHAP-style** contributions → human sentences via `feature_meanings.json`. **Canonical spec:** [`specs/submodule-1-prioritization-architecture.md`](specs/submodule-1-prioritization-architecture.md).
3. **Route layer (Submodule 2)** — Each stop has **`priority_class`**, **coordinates**, **`max_daily_stops`**, and **estimated `visit_duration_minutes`** (segment + priority heuristic). Selection and ordering optimize **value per unit time** (travel ETA + on-site duration); permutation search minimizes **total time** (drive + visits), not distance alone.
4. **Rep experience** — React **PWA** (`frontend/`): today’s plan, map, customer detail, navigate, recap UI, mascot chat.
5. **Generative AI** — **Ollama** (local LLM) for **RIQ** (`/assistant/ask`) and **visit recap** (`/visits/recap`). Prompts are **grounded** on JSON “facts” from the API so the model should not invent numbers.
6. **Managers** — Admin **dashboard** endpoint aggregates rep/customer/recap signals.

**Important nuance:** Explanations and routing both **consume the same** customer scores (one scoring pass; two outputs: *why* and *order*).

---

## Repository layout (short)

| Path | Role |
|------|------|
| `backend/app/main.py` | FastAPI app, CORS |
| `backend/app/api/routes.py` | HTTP API |
| `backend/app/ml/prioritization/` | Features, XGBoost engine, `feature_meanings.json` |
| `backend/app/ml/score.py` | `CustomerScore`, ties DB rows to predictor + fallback heuristic |
| `backend/app/recommend/service.py` | Day plan: score → route → stops |
| `backend/app/routing/solve.py` | Distance + optimization |
| `backend/app/assistant/router.py` | RIQ: builds fact sheet → Ollama |
| `backend/app/llm/` | Ollama client, recap pipeline |
| `backend/data/seed/` | `hilti.sqlite`, `prioritization_xgb.json`, CSVs |
| `frontend/` | Vite + React + TypeScript PWA |
| `specs/` | SDD / design notes; **Submodule 1 architecture** in `submodule-1-prioritization-architecture.md` |
| `docker-compose.yml` | Optional full stack in containers |

---

## Prerequisites on a new laptop

### Required (core app + scoring)

- **Python 3.11+** (3.12/3.14 often work; project uses a venv)
- **Node.js** (LTS) + **npm** — for the frontend
- **Git** — to clone/copy the repo

### Required only for RIQ + voice recap (LLM features)

- **[Ollama](https://ollama.com/)** installed **locally** on the same machine that runs the backend (default URL `http://localhost:11434`).

Without Ollama:

- Day plan, customer detail, scoring, map, and **non-LLM** flows still work.
- **`POST /assistant/ask`** and **`POST /visits/recap`** return **503** if Ollama is unreachable.

### Ollama quick setup (Windows)

1. Install Ollama from the official site: https://ollama.com/download  
2. Start Ollama (it usually runs as a service / tray app).  
3. Pull the model the project expects (see `backend/.env.example`):

   ```powershell
   ollama pull llama3.2:3b
   ```

4. Optional: `ollama list` to confirm the model is present.

Environment variables (copy `backend/.env.example` → `backend/.env`):

- `OLLAMA_HOST` — default `http://localhost:11434`
- `OLLAMA_MODEL` — default `llama3.2:3b`
- `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_TEMPERATURE`

---

## How to run locally (PowerShell)

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API base: **http://127.0.0.1:8000**  
- Health check: **GET /health**

**Note:** Use `python -m uvicorn ...` from the `backend` folder so imports resolve. If `fastapi dev` is not found, the venv may not be activated or the `[standard]` extra did not install the CLI.

**Tests** (from `backend`, with `PYTHONPATH` set):

```powershell
cd backend
$env:PYTHONPATH = "$PWD"
.\.venv\Scripts\python.exe -m pytest -q
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

- App: **http://localhost:5173**

Copy `frontend/.env.example` → `frontend/.env` or `.env.local` if you need a non-default API URL (e.g. phone on Wi‑Fi):

```env
VITE_API_BASE_URL=http://localhost:8000
```

### Docker (optional)

From repo root:

```powershell
docker compose up --build
```

---

## API surface (cheat sheet)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| GET | `/salespeople` | List reps |
| GET | `/salespeople/{id}/day-plan` | Today’s optimized plan |
| GET | `/salespeople/{id}/territory` | Territory + home base |
| GET | `/customers/{id}` | Customer + **visit_likelihood_score**, **priority_class**, **crm_priority** (raw seed field, not a model feature), **top_reasons**, explanations |
| POST | `/visits` | Log a visit |
| POST | `/assistant/ask` | RIQ (**needs Ollama**) |
| POST | `/visits/recap` | AI recap (**needs Ollama**) |
| GET | `/admin/dashboard` | Manager view |

Default demo salesperson id used in the frontend: `sp-kl-central` (see `frontend/src/lib/api.ts`).

---

## Data & ML artifacts

- First run can **seed** SQLite via API (`_ensure_database` in routes) or you can generate explicitly:

  ```powershell
  cd backend
  python -m app.data.generate --csv
  ```

- Prioritization model files (next to the DB under `backend/data/seed/`):

  - `prioritization_xgb.json`
  - `prioritization_meta.json`
  - `prioritization_feature_columns.json`

If artifacts are missing, scoring falls back to a **heuristic** (still no CRM `priority` in that path’s contribution keys for the XGB path; heuristic uses raw fields like pipeline for display logic).

---

## Pitch / positioning (for judges)

- **Problem:** Maps optimize **driving**; reps need **visit value**, **capture**, and **manager visibility**.  
- **Differentiator:** Explainable **ranking** + **grounded** LLM (facts from your stack).  
- **Honesty:** Dataset is **synthetic** but **realistic** for demo; production would swap in CRM feeds.

---

## Module roadmap (conversation context)

- **Submodule 1** (current): visit likelihood, priority class, SHAP-style reasons, LLM payload — **not** “use CRM priority as model input.” See `specs/submodule-1-prioritization-architecture.md`.  
- **Submodule 2 / Module 2** (future): richer **route** optimization (e.g. time windows, traffic, stricter territory constraints). The app already has a **value-aware** router as a foundation.

---

## Troubleshooting

| Issue | What to check |
|--------|----------------|
| `ModuleNotFoundError: app` when running pytest | Set `PYTHONPATH` to the `backend` directory (see above). |
| CORS errors in browser | `CORS_ORIGINS` in `backend/.env`; include `http://localhost:5173`. |
| Assistant / recap 503 | Ollama running? Model pulled? `OLLAMA_HOST` / `OLLAMA_MODEL` correct? |
| Phone cannot reach API | Use PC LAN IP in `VITE_API_BASE_URL` and allow firewall on port 8000. |

---

## What to copy to the other laptop

Minimum:

1. This file: **`PROJECT_CONTEXT.md`**
2. The full **repository** (or ZIP of the project)

On the new machine: install Python, Node, dependencies, **Ollama + model** if you need RIQ/recap, then run backend + frontend as above.

---

*Last aligned with repo layout and Ollama env as of project state; adjust version pins in `requirements.txt` / `package.json` if they change.*
