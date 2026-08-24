import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import engine, Base
from app.models import *  # Ensure all SQLAlchemy models are registered
from app.routers import (
    auth_router,
    doctors_router,
    appointments_router,
    summaries_router,
    admin_router,
    calendar_router,
    notifications_router,
)
from app.services.background_worker import start_background_tasks, stop_background_tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if not exist
    Base.metadata.create_all(bind=engine)
    # Start background scheduler
    start_background_tasks()
    yield
    # Shutdown background scheduler
    stop_background_tasks()


app = FastAPI(
    title=settings.APP_NAME,
    description="Next-Generation Healthcare Appointment & AI Follow-up Management Platform with Role-Based Portals, LLM Pre/Post Summaries, Double-Booking Concurrency Control, and Google Calendar Integration.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static")
templates_dir = os.path.join(base_dir, "templates")

os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Include API routers
app.include_router(auth_router)
app.include_router(doctors_router)
app.include_router(appointments_router)
app.include_router(summaries_router)
app.include_router(admin_router)
app.include_router(calendar_router)
app.include_router(notifications_router)


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"app_name": settings.APP_NAME}
    )


@app.get("/health")
def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "env": settings.APP_ENV,
        "llm_provider": settings.LLM_PROVIDER,
        "email_backend": settings.EMAIL_BACKEND,
        "google_calendar_enabled": settings.GOOGLE_CALENDAR_ENABLED
    }
