import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.database import init_db
from app.routers import videos

load_dotenv()

app = FastAPI(
    title="YouTube Clone API",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

ALLOWED_ORIGIN = os.getenv("FRONTEND_URL", "http://localhost:5173")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir archivos estáticos (videos y thumbnails)
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.middleware("http")
async def add_upload_security_headers(request, call_next):
    response = await call_next(request)
    if request.url.path == "/api/uploads" or request.url.path.startswith("/api/uploads/"):
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# Registrar routers
app.include_router(videos.router, prefix="/api")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api")
def read_root():
    return {"message": "YouTube Clone Backend API"}


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}
