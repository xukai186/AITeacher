"""Seed the dev database with a demo org, admin, staff, package and student."""
from __future__ import annotations

from sqlalchemy import select

from app.auth.security import hash_password
from app.database import SessionLocal
from app.models import (
    Organization,
    Package,
    StaffStudent,
    StudentProfile,
    StudentSubject,
    User,
    UserRole,
)


def main() -> None:
    db = SessionLocal()
    try:
        org = db.execute(
            select(Organization).where(Organization.name == "Demo Org")
        ).scalar_one_or_none()
        if org is None:
            org = Organization(name="Demo Org")
            db.add(org)
            db.flush()

        def ensure_user(email: str, role: UserRole, name: str, password: str) -> User:
            existing = db.execute(
                select(User).where(User.org_id == org.id, User.email == email)
            ).scalar_one_or_none()
            if existing:
                return existing
            user = User(
                org_id=org.id,
                email=email,
                password_hash=hash_password(password),
                role=role,
                name=name,
            )
            db.add(user)
            db.flush()
            return user

        admin = ensure_user("admin@demo.example", UserRole.org_admin, "Admin", "admin123")
        staff = ensure_user("teacher@demo.example", UserRole.org_staff, "Teacher", "teach123")
        student = ensure_user("student@demo.example", UserRole.student, "Student", "stud123")

        pkg = db.execute(
            select(Package).where(Package.org_id == org.id, Package.name == "Standard")
        ).scalar_one_or_none()
        if pkg is None:
            pkg = Package(
                org_id=org.id, name="Standard", subject_codes=["politics", "english", "math"]
            )
            db.add(pkg)
            db.flush()

        if db.get(StudentProfile, student.id) is None:
            db.add(StudentProfile(user_id=student.id, exam_year=2027, package_id=pkg.id))

        for code in pkg.subject_codes:
            exists = db.execute(
                select(StudentSubject).where(
                    StudentSubject.student_user_id == student.id,
                    StudentSubject.subject_code == code,
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(StudentSubject(student_user_id=student.id, subject_code=code))

        link = db.execute(
            select(StaffStudent).where(
                StaffStudent.staff_user_id == staff.id,
                StaffStudent.student_user_id == student.id,
            )
        ).scalar_one_or_none()
        if link is None:
            db.add(
                StaffStudent(
                    staff_user_id=staff.id,
                    student_user_id=student.id,
                    assigned_by_user_id=admin.id,
                )
            )

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
