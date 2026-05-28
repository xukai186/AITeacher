from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_admin
from app.database import get_db
from app.models import ModelPolicy, User
from app.schemas.model_policy import ModelPolicyOut, ModelPolicyUpsert
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/model-policies", tags=["admin-model-policies"])


@router.get("", response_model=list[ModelPolicyOut])
def list_model_policies(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> list[ModelPolicyOut]:
    rows = db.execute(
        select(ModelPolicy)
        .where(ModelPolicy.org_id == admin.org_id)
        .order_by(ModelPolicy.scene.asc())
    ).scalars().all()
    return [
        ModelPolicyOut(
            id=str(p.id),
            org_id=str(p.org_id),
            scene=p.scene,
            provider=p.provider,
            model=p.model,
            params=p.params,
        )
        for p in rows
    ]


@router.put("/{scene}", response_model=ModelPolicyOut)
def upsert_model_policy(
    scene: str,
    payload: ModelPolicyUpsert,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin()),
) -> ModelPolicyOut:
    existing = db.execute(
        select(ModelPolicy).where(ModelPolicy.org_id == admin.org_id, ModelPolicy.scene == scene)
    ).scalar_one_or_none()

    if existing is None:
        policy = ModelPolicy(
            org_id=admin.org_id, scene=scene, provider=payload.provider, model=payload.model, params=payload.params
        )
        db.add(policy)
        db.flush()
        record_audit(
            db,
            actor=admin,
            action="model_policy.upsert",
            target_type="model_policy",
            target_id=str(policy.id),
            before=None,
            after={"scene": policy.scene, "provider": policy.provider, "model": policy.model, "params": policy.params},
        )
        db.commit()
        db.refresh(policy)
        return ModelPolicyOut(
            id=str(policy.id),
            org_id=str(policy.org_id),
            scene=policy.scene,
            provider=policy.provider,
            model=policy.model,
            params=policy.params,
        )

    before = {"scene": existing.scene, "provider": existing.provider, "model": existing.model, "params": existing.params}
    existing.provider = payload.provider
    existing.model = payload.model
    existing.params = payload.params
    db.flush()
    record_audit(
        db,
        actor=admin,
        action="model_policy.upsert",
        target_type="model_policy",
        target_id=str(existing.id),
        before=before,
        after={"scene": existing.scene, "provider": existing.provider, "model": existing.model, "params": existing.params},
    )
    db.commit()
    db.refresh(existing)
    return ModelPolicyOut(
        id=str(existing.id),
        org_id=str(existing.org_id),
        scene=existing.scene,
        provider=existing.provider,
        model=existing.model,
        params=existing.params,
    )

