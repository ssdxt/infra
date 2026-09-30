from .dev import router as dev_router
from .ent import router as ent_router
from .user import router as user_router
from .auth import router as auth_router
from .space import router as space_router
from .kbase import router as kbase_router
from .task import router as task_router
from .chat import router as chat_router


__all__ = [
    'dev_router',
    'user_router',
    'auth_router',
    'ent_router',
    'space_router',
    'kbase_router',
    'task_router',
    'chat_router',
]
