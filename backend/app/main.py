from fastapi import FastAPI

from app.routers import admin_students, auth as auth_router, me as me_router

app = FastAPI(title="AITeacher API", version="0.1.0")
app.include_router(auth_router.router)
app.include_router(me_router.router)
app.include_router(admin_students.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
