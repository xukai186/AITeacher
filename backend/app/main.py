from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    admin_model_policy,
    admin_packages,
    admin_staff,
    admin_students,
    auth as auth_router,
    chat as chat_router,
    me as me_router,
    org_students,
    staff_students,
    student_placement,
    student_profile,
    student_self_test,
    student_tasks,
    student_report,
    student_wrong_book,
    student_agent,
    student_master_plan,
    student_paper_gen_jobs,
    student_papers,
)

app = FastAPI(title="AITeacher API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(me_router.router)
app.include_router(admin_students.router)
app.include_router(admin_staff.router)
app.include_router(admin_packages.router)
app.include_router(admin_model_policy.router)
app.include_router(staff_students.router)
app.include_router(org_students.router)
app.include_router(student_profile.router)
app.include_router(student_placement.router)
app.include_router(student_tasks.router)
app.include_router(student_self_test.router)
app.include_router(student_report.router)
app.include_router(student_wrong_book.router)
app.include_router(student_agent.router)
app.include_router(student_master_plan.router)
app.include_router(student_paper_gen_jobs.router)
app.include_router(student_papers.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
