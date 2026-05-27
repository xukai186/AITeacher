from fastapi import Depends, FastAPI

from app.auth.permissions import require_admin
from app.models.user import User
from app.routers import auth as auth_router
from app.routers import me as me_router

app = FastAPI(title="AITeacher API", version="0.1.0")
app.include_router(auth_router.router)
app.include_router(me_router.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/admin/ping")
def admin_ping(_: User = Depends(require_admin())) -> dict[str, str]:
    return {"pong": "admin"}
