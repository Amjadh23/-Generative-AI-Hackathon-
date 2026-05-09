# Hilti RouteIQ Architecture

## 1. System Purpose

Hilti RouteIQ is an AI sales visit copilot for field salespeople and managers. The core product question is:

> Which customers should a salesperson visit today, and in what order, if the goal is not only shorter travel but higher sales return?

The application combines four major capabilities:

1. Customer prioritization: score assigned customers by predicted visit likelihood and business value.
2. Value-aware route planning: choose and order daily stops by value, urgency, proximity, and expected visit duration.
3. Field experience: provide a mobile PWA with today's route, live map, navigation aids, customer detail, visit logging, and AI visit recap.
4. Manager visibility: aggregate rep activity, AI recap outcomes, and future-potential rankings.

The implementation is intentionally demo-friendly: it uses synthetic Kuala Lumpur sales data, a local SQLite database, local model artifacts, and optional local Ollama for LLM features.

## 2. High-Level Architecture

```text
React PWA (frontend/)
  |
  | HTTP JSON
  v
FastAPI backend (backend/app/)
  |
  | sqlite3
  v
SQLite seed DB (backend/data/seed/hilti.sqlite)
  |
  +-- XGBoost prioritization artifacts
  |
  +-- Route optimization service
  |
  +-- Ollama LLM client for RIQ assistant and visit recaps
```

The backend owns business logic and data mutation. The frontend owns user interaction, display state, device integrations, map rendering, and external browser APIs such as geolocation and speech synthesis.

## 3. Repository Layout

```text
.
|-- backend/
|   |-- app/
|   |   |-- main.py                         # FastAPI app setup and CORS
|   |   |-- api/routes.py                   # HTTP endpoint definitions
|   |   |-- core/schemas.py                 # Pydantic response/request contracts
|   |   |-- data/generate.py                # Synthetic data and SQLite seed generation
|   |   |-- ml/score.py                     # Public customer scoring facade
|   |   |-- ml/prioritization/              # XGBoost features, engine, explanations
|   |   |-- routing/solve.py                # Distance, ETA, route selection/order
|   |   |-- recommend/service.py            # Day-plan orchestration
|   |   |-- assistant/router.py             # Grounded RIQ assistant prompt flow
|   |   |-- llm/                            # Ollama client, recap, focus text
|   |   `-- admin/service.py                # Manager dashboard aggregates
|   |-- data/seed/                         # SQLite, CSV exports, model artifacts
|   |-- tests/                             # Backend contract/unit tests
|   |-- requirements.txt
|   `-- Dockerfile
|
|-- frontend/
|   |-- src/
|   |   |-- App.tsx                         # Top-level app state and view routing
|   |   |-- lib/api.ts                      # API client and TypeScript contracts
|   |   |-- lib/routing.ts                  # OSRM route geometry and turn parsing
|   |   |-- hooks/                          # Geolocation, speech, turn-by-turn state
|   |   |-- pages/                          # Today, map, customer, manager, settings
|   |   `-- components/                     # Reusable UI pieces
|   |-- public/                            # PWA icons and static assets
|   |-- vite.config.ts                     # Vite, React, PWA config
|   `-- package.json
|
|-- specs/                                # Product/specification artifacts
|-- pitch/                                # Pitch deck assets
|-- docker-compose.yml
|-- README.md
`-- PROJECT_CONTEXT.md
```

## 4. Backend Architecture

### 4.1 Application Entry Point

`backend/app/main.py` creates the FastAPI application:

- Loads `.env` values with `python-dotenv`.
- Configures CORS for local Vite dev servers and LAN demos.
- Includes the API router from `app.api.routes`.
- Exposes `/` as a friendly service index and `/health` through the router.

The backend is designed to run from the `backend` directory so imports resolve as `app.*`.

### 4.2 API Layer

`backend/app/api/routes.py` is the HTTP boundary. It keeps endpoint handlers thin and delegates domain work to services.

Main endpoints:

| Method | Path | Responsibility |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/salespeople` | List reps and territories |
| `GET` | `/salespeople/{id}/day-plan` | Build optimized day plan |
| `GET` | `/salespeople/{id}/territory` | Return territory and home-base coordinates |
| `GET` | `/customers/{id}` | Customer detail, score, explanations, visits, orders |
| `POST` | `/visits` | Persist a manual visit log |
| `POST` | `/assistant/ask` | Ask the RIQ grounded assistant |
| `POST` | `/visits/recap` | Convert transcript into structured visit recap |
| `GET` | `/admin/dashboard` | Manager dashboard aggregates |
| `PATCH` | `/admin/customers/{id}/assignment` | Reassign customer to a salesperson |

Most endpoints call `_ensure_database()`, which creates `backend/data/seed/hilti.sqlite` with synthetic data if it does not already exist.

### 4.3 Data Layer

The project uses SQLite directly through Python's standard `sqlite3` module. There is no ORM.

`backend/app/data/generate.py` owns schema creation and synthetic seed generation. It creates these tables:

| Table | Purpose |
|---|---|
| `territories` | Territory id, name, center coordinates, radius |
| `salespeople` | Rep id, territory, home coordinates, max daily stops |
| `customers` | Account profile, assigned rep, coordinates, CRM priority, order/pipeline signals |
| `visit_history` | Historical and newly logged visits |
| `orders` | Historical orders by customer and product family |

The default dataset contains:

- 5 Kuala Lumpur-style territories.
- 5 salespeople, one per territory.
- 80 customers per territory by default, for 400 total customers.
- Visit history and orders per customer.
- Generated XGBoost prioritization artifacts beside the SQLite database.

The `priority` column in `customers` is retained as a raw synthetic CRM field for display and data generation, but it is intentionally excluded from the model feature set.

### 4.4 Domain Contracts

`backend/app/core/schemas.py` defines Pydantic models used by API responses and requests. Important contracts include:

- `DayPlan`: a daily route for one salesperson.
- `DayPlanStop`: one recommended customer visit with score, ETA, reasons, expected return, and meeting focus.
- `OptimizationSummary`: comparison against a naive value-blind baseline.
- `VisitCreate` and `VisitCreated`: manual visit logging.
- `AssistantRequest` and `AssistantResponse`: RIQ chat interaction.
- `VisitRecapRequest` and `VisitRecapResponse`: LLM structured recap.
- `CustomerAssignmentPayload` and `CustomerAssignmentResult`: admin reassignment.

The frontend mirrors these contracts in `frontend/src/lib/api.ts`.

## 5. Scoring and Prioritization

Customer scoring is split into a public scoring facade and a model-specific prioritization engine.

### 5.1 Public Scoring Facade

`backend/app/ml/score.py` exposes:

- `score_customer(customer_id, database_path)`
- `score_customer_row(row, database_path, connection)`
- `top_customers_for_salesperson(salesperson_id, limit, database_path)`

It returns a `CustomerScore` dataclass:

```text
customer_id
score                         # 0-100 presentation score
visit_likelihood_score         # 0-1 model score
priority_class                 # Low, Medium, High
recommended_action             # Schedule follow-up or Visit today
expected_return_rm
reason
contributions
top_reasons
xgboost_explanation_payload
```

If XGBoost artifacts are missing, the facade falls back to a transparent heuristic using recency, pipeline, average order value, and reorder probability.

### 5.2 Feature Engineering

`backend/app/ml/prioritization/features.py` builds model inputs. The model feature list is:

```text
segment_encoded
territory_id_encoded
avg_order_value_band_encoded
open_pipeline_band_encoded
last_visit_days
reorder_probability
past_order_count
total_order_value_band_encoded
days_since_last_order
visit_count
last_visit_outcome_encoded
distance_from_salesperson_home_km
nearby_customer_count
```

Important design choice: `customers.priority` is not in `FEATURE_COLUMNS`. This prevents the model from simply replaying the raw CRM priority field.

Feature engineering derives:

- Encoded segment, territory, and last visit outcome.
- Banded order/pipeline values.
- Historical order count and total order value.
- Days since last order.
- Visit count and latest visit outcome.
- Distance from assigned salesperson home.
- Nearby customer density within the same territory.

### 5.3 XGBoost Engine

`backend/app/ml/prioritization/engine.py` handles:

- Training and saving model artifacts with `train_and_save_artifacts()`.
- Loading and caching runtime model bundles.
- Binning raw visit likelihood into `Low`, `Medium`, or `High`.
- Mapping priority classes to recommended actions.
- Producing Tree SHAP-style contribution payloads with XGBoost `pred_contribs=True`.

Model artifacts live next to the seed database:

```text
backend/data/seed/prioritization_xgb.json
backend/data/seed/prioritization_meta.json
backend/data/seed/prioritization_feature_columns.json
```

The engine caches model bundles and customer positions in process to avoid reloading the booster or rescanning all coordinates for every customer during dashboard scoring.

### 5.4 Human-Readable Explanations

The raw model contribution values are converted into human-facing reasons through:

- `backend/app/ml/prioritization/meanings.py`
- `backend/app/ml/prioritization/feature_meanings.json`

The resulting API payload includes:

- `score_contributions`: feature-to-contribution map.
- `top_reasons`: short sales-facing explanation sentences.
- `xgboost_explanation`: structured base value and top priority reasons.

## 6. Day Plan and Route Optimization

The day plan is built in `backend/app/recommend/service.py`.

### 6.1 Day Plan Flow

For `GET /salespeople/{id}/day-plan`, the backend:

1. Ensures the SQLite database exists.
2. Loads the salesperson and all assigned customer rows.
3. Scores assigned customers through `top_customers_for_salesperson()`.
4. Keeps the top scoring candidates, currently limited to 18.
5. Converts scores into `RouteCandidate` objects with coordinates, value score, priority class, and visit duration.
6. Optimizes the selected route with `optimize_route()`.
7. Enriches route stops with customer names, scores, expected returns, top reasons, and meeting focus.
8. Builds an `OptimizationSummary` against a deterministic baseline.
9. Returns a `DayPlan`.

### 6.2 Route Selection

`backend/app/routing/solve.py` first chooses stops with `_greedy_value_aware()`.

The selection heuristic repeatedly picks the remaining candidate with the best marginal value:

```text
candidate.value_score / (travel_eta_minutes + visit_duration_minutes)
```

This means a high-scoring but far-away account can win if the value justifies the travel, while nearby low-value accounts are not selected only because they are close.

### 6.3 Route Ordering

After selecting stops, `optimize_route()` searches for the best visit order:

- If selected stops are empty, it returns an empty plan.
- If there are 9 or fewer selected stops, it brute-forces permutations.
- It minimizes total time, not just distance.
- Total time includes travel ETA plus on-site visit duration.

The default seed data sets each salesperson's `max_daily_stops` to 8, which keeps brute-force ordering practical for the demo.

### 6.4 Visit Duration and ETA

Visit duration is estimated from segment and priority class:

| Segment | Base duration |
|---|---:|
| `project_site` | 45 min |
| `distributor` | 25 min |
| `maintenance` | 35 min |
| other/default | 35 min |

Priority adjusts the base:

- `High`: add 5 minutes, capped at 60.
- `Low`: subtract 5 minutes, floored at 20.
- `Medium`: no adjustment.

Driving distance uses haversine distance. ETA uses a simple average-speed assumption of 24 km/h and has a minimum of 4 minutes.

### 6.5 Baseline Comparison

The optimization summary compares the optimized plan against a naive baseline:

- Randomly sample the same number of customers using a fixed seed.
- Visit nearest customer next.
- Ignore customer value.

The summary reports routes evaluated, baseline expected return, baseline distance, value gain, distance saved, and value uplift percentage.

## 7. LLM Architecture

LLM features are optional and depend on local Ollama.

### 7.1 Ollama Client

`backend/app/llm/client.py` is a thin standard-library HTTP client for Ollama's `/api/chat` endpoint.

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2:3b` | Chat model |
| `OLLAMA_TIMEOUT_SECONDS` | `60` | Request timeout |
| `OLLAMA_TEMPERATURE` | `0.2` | Default generation temperature |

The client supports plain chat and JSON-mode chat. Failures raise `LLMError`, which the API layer turns into HTTP 503.

### 7.2 RIQ Assistant

`backend/app/assistant/router.py` powers `POST /assistant/ask`.

Flow:

1. Build today's `DayPlan` for the salesperson.
2. Identify the current or next stop.
3. Build a JSON fact sheet containing only trusted plan, score, customer, route, and optimization facts.
4. Send the fact sheet and user question to Ollama with a strict JSON response schema.
5. Coerce and validate the response before returning it.

The assistant prompt explicitly instructs the model not to invent customer names, distances, ringgit amounts, or scores. The response is also sanitized so hallucinated `related_customer_id` values are dropped unless they exist in the current plan.

### 7.3 Visit Recap

`backend/app/llm/recap.py` powers `POST /visits/recap`.

Flow:

1. Validate that the customer exists.
2. Send the free-form transcript to Ollama with a strict structured extraction schema.
3. Normalize outcome, sentiment, products, due date, and confidence.
4. Optionally persist the recap as a visit record.
5. If persisted, update `customers.last_visit_days` to `0`.

Supported outcomes:

```text
order
follow_up
no_interest
closed
```

Supported product families:

```text
anchors
power_tools
firestop
measuring
fasteners
```

### 7.4 Meeting Focus Text

`backend/app/llm/explain.py` builds non-LLM focus guidance for stops by inspecting customer order history and segment. Despite living in `llm/`, it does not call the model. It produces deterministic one-line meeting focus text, such as cross-sell suggestions or segment-specific discovery guidance.

## 8. Admin and Manager Architecture

`backend/app/admin/service.py` builds the manager dashboard returned by `GET /admin/dashboard`.

It combines:

- Rep summaries: customer count, top expected return, AI recap counts, interested recaps, active follow-ups.
- Customer rankings: RouteIQ score, expected return, visit signal, future-potential index.
- Customer assignment options.
- Recent AI recaps.
- Recap impact story for before/after comparison.

### 8.1 Future Potential

The manager dashboard creates two values:

- `future_potential_baseline`: score based mainly on the static RouteIQ score.
- `future_potential_index`: blend of RouteIQ score and recent visit trajectory.

Recent visit trajectory is derived from weighted outcomes:

| Outcome | Weight |
|---|---:|
| `order` | 14 |
| `closed` | 12 |
| `follow_up` | 7 |
| `no_interest` | -10 |

AI recap notes receive extra positive weight when they include structured next actions.

### 8.2 Customer Assignment

`PATCH /admin/customers/{id}/assignment` changes both:

- `assigned_salesperson_id`
- `territory_id`

The territory is taken from the target salesperson, so reassignment keeps customer territory and rep territory aligned.

## 9. Frontend Architecture

The frontend is a Vite + React + TypeScript PWA.

### 9.1 App State and View Routing

`frontend/src/App.tsx` is the top-level state container. It manages:

- Current salesperson.
- Salespeople list.
- Day plan.
- Territory.
- Selected customer id.
- Loading and error states.
- Current view.

Views are local React state, not URL routes:

```text
today
map
customer
settings
manager
```

The default salesperson id is `sp-kl-central`.

### 9.2 API Client

`frontend/src/lib/api.ts` defines:

- TypeScript versions of backend response shapes.
- `get`, `post`, and `patch` helpers.
- Endpoint wrappers such as `fetchDayPlan`, `fetchCustomer`, `askAssistant`, and `recapVisit`.

The API base URL comes from:

```text
VITE_API_BASE_URL
```

If unset, it defaults to:

```text
http://localhost:8000
```

The base URL is normalized by trimming trailing slashes to avoid accidental double-slash paths.

### 9.3 Today Page

`frontend/src/pages/TodayPage.tsx` presents:

- Hero summary for the selected salesperson and territory.
- Optimization impact card.
- Total expected return and travel distance.
- Next best visit.
- Meeting focus.
- Ordered visit list.

Selecting a stop moves the app into the customer detail view.

### 9.4 Map Page

`frontend/src/pages/MapPage.tsx` renders the live route experience.

Key dependencies:

- `maplibre-gl` for map rendering.
- CARTO Positron map style.
- Browser geolocation through `useGeolocation`.
- Public OSRM route service through `frontend/src/lib/routing.ts`.
- Browser speech synthesis through `useTurnByTurn`.

Map behavior:

1. Render stop markers from the backend day plan.
2. Read current GPS position or use a demo fallback.
3. Request route geometry from OSRM using current position plus planned stops.
4. Draw route line and live accuracy circle.
5. Provide navigation start/stop, voice toggle, follow-me, and demo-location controls.
6. Show current/next maneuver instructions while navigating.
7. Render the RIQ chat widget over the map.

If OSRM fails or returns no route, the frontend falls back to straight-line waypoint geometry.

### 9.5 Customer Detail Page

`frontend/src/pages/CustomerDetailPage.tsx` loads `GET /customers/{id}` and displays:

- Segment, name, score, priority class, and visit likelihood.
- Google Maps navigation link.
- Expected return, average order value, reorder probability.
- Human-readable score reasons.
- Feature contribution bars.
- Recent orders.
- Recent visits.
- AI visit recap panel.
- Manual visit logging form.

Manual visit logging calls `POST /visits`. AI recap calls `POST /visits/recap`. After either persists data, the app refreshes the plan and customer details.

### 9.6 Manager Page

`frontend/src/pages/ManagerPage.tsx` loads `GET /admin/dashboard` and displays:

- Rep recap activity.
- Recent AI recap outcomes.
- Interested-only filtering.
- Before/after future-potential impact.
- Spotlight account lift.

### 9.7 PWA Setup

`frontend/vite.config.ts` uses `vite-plugin-pwa`.

PWA behavior:

- Standalone app manifest.
- Hilti RouteIQ name, colors, and icon.
- Auto-updating service worker.
- Network-first runtime cache for `/salespeople/*/day-plan` responses.

## 10. Primary Request Flows

### 10.1 Loading Today's Plan

```text
App.tsx
  -> fetchSalespeople()
  -> fetchDayPlan(selectedSalespersonId)
  -> GET /salespeople/{id}/day-plan
  -> build_day_plan()
  -> top_customers_for_salesperson()
  -> score_customer_row()
  -> predict_with_explanations()
  -> optimize_route()
  -> build_focus()
  -> DayPlan JSON
  -> TodayPage / MapPage render
```

### 10.2 Opening a Customer

```text
StopCard or map marker click
  -> selectedCustomerId set in App.tsx
  -> CustomerDetailPage
  -> fetchCustomer(customerId)
  -> GET /customers/{id}
  -> load customer, visits, orders
  -> score_customer()
  -> return detail + explanations
```

### 10.3 Logging a Manual Visit

```text
CustomerDetailPage form submit
  -> POST /visits
  -> validate customer exists
  -> insert visit_history row
  -> set customer.last_visit_days = 0
  -> refresh day plan and customer detail
```

### 10.4 Saving an AI Recap

```text
VisitRecapPanel
  -> POST /visits/recap
  -> validate customer exists
  -> Ollama JSON extraction
  -> normalize structured fields
  -> optional insert visit_history row
  -> set customer.last_visit_days = 0
  -> manager dashboard can now show recap and future-potential lift
```

### 10.5 Asking RIQ

```text
MascotChat
  -> POST /assistant/ask
  -> build current day plan
  -> build fact sheet from plan/customer score
  -> Ollama JSON answer
  -> validate intent, suggestions, related_customer_id
  -> chat response in UI
```

### 10.6 Manager Dashboard

```text
ManagerPage
  -> GET /admin/dashboard
  -> build_manager_dashboard()
  -> load reps and customers
  -> score customers
  -> compute visit signals and future-potential rankings
  -> return reps, rankings, recent AI recaps, recap impact
```

## 11. External Integrations

| Integration | Location | Purpose | Failure behavior |
|---|---|---|---|
| Ollama | Backend | Assistant and visit recap | API returns 503 through `LLMError` |
| OSRM public route API | Frontend | Real road geometry and maneuvers | Falls back to straight-line geometry |
| Browser geolocation | Frontend | Live position | User can enable demo location |
| Browser speech synthesis | Frontend | Turn-by-turn voice | Silently ignored if unavailable |
| Google Maps URL | Frontend | External navigation link from customer page | Opens in new tab/app |

## 12. Configuration

### Backend

Common environment variables:

```text
CORS_ORIGINS
OLLAMA_HOST
OLLAMA_MODEL
OLLAMA_TIMEOUT_SECONDS
OLLAMA_TEMPERATURE
```

The backend defaults are optimized for local development and demos.

### Frontend

Common environment variable:

```text
VITE_API_BASE_URL
```

Use this when testing from a phone on the same network, for example:

```text
VITE_API_BASE_URL=http://192.168.x.x:8000
```

### Docker Compose

`docker-compose.yml` builds both services:

- Backend on host port `8000`.
- Frontend on host port `5173`.
- Frontend depends on backend.
- Source folders are mounted for development-like iteration.

## 13. Testing Strategy

Backend tests cover the main domain contracts and behavioral guarantees:

| Test file | Coverage |
|---|---|
| `test_health.py` | API health |
| `test_day_plan.py` | Day-plan API contract and optimization summary |
| `test_scoring.py` | Feature exclusions, scoring, top-customer ordering |
| `test_routing.py` | Haversine distance, value-aware selection, brute-force ordering |
| `test_assistant.py` | Grounded prompt construction and response coercion |
| `test_recap.py` | Recap extraction, persistence, customer validation |
| `test_admin.py` | Manager dashboard and reassignment |
| `test_data_generation.py` | Seed generation behavior |

LLM tests monkeypatch model calls so the suite does not require Ollama to be running.

Frontend validation is currently script-based through:

```text
npm run lint
npm run build
```

## 14. Architectural Tradeoffs

### 14.1 SQLite Instead of a Server Database

SQLite keeps the demo portable and easy to reset. It is appropriate for a hackathon/prototype but would need a multi-user database in production.

### 14.2 Direct SQL Instead of ORM

The code uses direct SQL for clarity and low dependency overhead. This keeps data access explicit, but schema changes require careful manual updates across queries and tests.

### 14.3 Local XGBoost Artifacts

Model artifacts are stored beside the seed database. This makes the scoring path deterministic and offline-friendly, but production would likely use a trained model registry, scheduled retraining, and artifact versioning.

### 14.4 Local Ollama

Ollama avoids external LLM API dependencies and supports offline demos. The tradeoff is that LLM features depend on local installation, model availability, and machine performance.

### 14.5 Frontend OSRM Calls

The browser calls the public OSRM demo server directly for route geometry. This avoids backend routing infrastructure, but production should proxy or replace this with an approved routing provider, add rate-limit handling, and consider traffic/time-window constraints.

### 14.6 Local View State Instead of URL Routing

The PWA uses local React state for view routing. This is simple for a mobile demo but means deep links and browser history are limited.

## 15. Production Evolution Path

Natural next steps if this prototype becomes a production system:

1. Replace synthetic SQLite data with CRM, ERP, order, activity, and territory feeds.
2. Move persistence to Postgres or another managed relational database.
3. Add authentication and role-based access for reps and managers.
4. Version model artifacts and store prediction logs for auditability.
5. Add proper model monitoring for drift, feature freshness, and score distribution changes.
6. Replace public OSRM calls with a supported routing provider that includes traffic, time windows, and service constraints.
7. Move LLM prompting behind stricter retrieval, policy checks, observability, and redaction.
8. Add background jobs for daily plan precomputation and recap analysis.
9. Add URL routing and deeper offline support in the PWA.
10. Expand tests around frontend behavior, API error states, and data migration.

## 16. Mental Model

The simplest way to understand RouteIQ is:

```text
Data tells us who the customers are.
Prioritization tells us who matters most today.
Routing tells us which valuable stops fit into the day.
The PWA helps the salesperson execute the plan.
Recaps turn field conversations back into structured CRM signals.
The manager dashboard turns those signals into team visibility.
```

The scoring pass is the center of gravity. It feeds both explanations for the salesperson and value inputs for routing. Visit logs and AI recaps then flow back into the same SQLite data store, influencing later detail views, manager reporting, and future plan generation.
