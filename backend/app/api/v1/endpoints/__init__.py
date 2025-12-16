from .auth import router as auth_router
from .upload import router as upload_router
from .export_html import router as export_router  # ← AGREGAR ESTA LÍNEA

__all__ = ['auth_router', 'upload_router', 'export_router']  # ← AGREGAR export_router