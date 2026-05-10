import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

load_dotenv()


def _cors_origins() -> list[str]:
    """Always include local Vite dev servers; extend with CORS_ORIGINS (comma-separated).

    If CORS_ORIGINS replaces defaults entirely, a typo can otherwise cause the exact
    \"No 'Access-Control-Allow-Origin'\" browser error for localhost:5173.
    """
    defaults = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw:
        return defaults
    extra = [origin.strip() for origin in raw.split(",") if origin.strip()]
    merged: list[str] = []
    seen: set[str] = set()
    for origin in [*defaults, *extra]:
        if origin not in seen:
            seen.add(origin)
            merged.append(origin)
    return merged


app = FastAPI(
    title="Hilti RouteIQ",
    description="Hackathon backend for an AI sales visit copilot.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    # Vite on any port from localhost / LAN IP (phone demo on same Wi‑Fi)
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3})(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    """Avoid a bare 404 when opening http://localhost:8000/ in the browser."""
    return {
        "service": "Hilti RouteIQ API",
        "health": "/health",
        "docs": "/docs",
        "manager_dashboard": "/admin/dashboard",
    }
