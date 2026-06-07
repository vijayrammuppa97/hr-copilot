from .auth     import router as auth_router
from .chat     import router as chat_router
from .users    import router as users_router
from .cases    import router as cases_router
from .admin    import router as admin_router
from .documents import router as documents_router

__all__ = [
    "auth_router", "chat_router", "users_router",
    "cases_router", "admin_router", "documents_router",
]
