from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import SessionLocal, init_db
from .routers import auth, me, posts, responses

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.seed_on_start:
        from .seed import seed

        with SessionLocal() as db:
            seed(db)
    yield


app = FastAPI(title="Business Club — Startups & Vacancies", version="0.1.0", lifespan=lifespan)

for r in (auth.router, me.router, posts.router, responses.router):
    app.include_router(r)

# The mini-app is embedded by Telegram clients (web.telegram.org uses an iframe), so framing is
# allowed only for Telegram origins instead of being denied outright.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"  # personal data must not be cached
    return response


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")
