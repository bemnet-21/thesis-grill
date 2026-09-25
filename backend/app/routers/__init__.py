from app.routers.sessions import router as sessions_router
from app.routers.theses import router as theses_router
from app.routers.users import router as users_router

__all__ = ["sessions_router", "theses_router", "users_router"]
