from app.routers.auth import router as auth_router
from app.routers.doctors import router as doctors_router
from app.routers.appointments import router as appointments_router
from app.routers.summaries import router as summaries_router
from app.routers.admin import router as admin_router
from app.routers.calendar import router as calendar_router
from app.routers.notifications import router as notifications_router

__all__ = [
    "auth_router",
    "doctors_router",
    "appointments_router",
    "summaries_router",
    "admin_router",
    "calendar_router",
    "notifications_router",
]
