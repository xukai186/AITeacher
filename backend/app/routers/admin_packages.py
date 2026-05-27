from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_admin
from app.database import get_db
from app.models import Package, User
from app.schemas.package import PackageCreate, PackageOut
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/packages", tags=["admin-packages"])


@router.post("", response_model=PackageOut, status_code=status.HTTP_201_CREATED)
def create_package(
    payload: PackageCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> PackageOut:
    pkg = Package(org_id=admin.org_id, name=payload.name, subject_codes=payload.subject_codes)
    db.add(pkg)
    db.flush()
    record_audit(
        db,
        actor=admin,
        action="package.create",
        target_type="package",
        target_id=str(pkg.id),
        after={"name": pkg.name, "subjects": pkg.subject_codes},
    )
    db.commit()
    db.refresh(pkg)
    return PackageOut(id=pkg.id, name=pkg.name, subject_codes=pkg.subject_codes)


@router.get("", response_model=list[PackageOut])
def list_packages(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> list[PackageOut]:
    rows = db.execute(
        select(Package).where(Package.org_id == admin.org_id).order_by(Package.name)
    ).scalars().all()
    return [PackageOut(id=p.id, name=p.name, subject_codes=p.subject_codes) for p in rows]
