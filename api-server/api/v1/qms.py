from __future__ import annotations
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, QMSDocument

router = APIRouter(prefix="/qms", tags=["qms-quality"])

class QMSCreate(BaseModel):
    titre: str = Field(..., min_length=2, max_length=255)
    categorie: str = Field(..., min_length=2, max_length=100)
    version: Optional[str] = "1.0"
    contenu_markdown: Optional[str] = None
    fichier_url: Optional[str] = None

class QMSOut(BaseModel):
    id: int
    clinic_id: int
    titre: str
    categorie: str
    version: str
    contenu_markdown: Optional[str]
    fichier_url: Optional[str]
    statut: str
    created_at: str

    class Config:
        from_attributes = True

@router.get("/", response_model=List[QMSOut])
async def list_qms_documents(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(
        RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
        RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
    )),
):
    """Liste tous les documents et protocoles QMS de la clinique."""
    stmt = select(QMSDocument).where(QMSDocument.clinic_id == current_user["clinic_id"]).order_by(QMSDocument.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [
        QMSOut(
            id=d.id,
            clinic_id=d.clinic_id,
            titre=d.titre,
            categorie=d.categorie,
            version=d.version,
            contenu_markdown=d.contenu_markdown,
            fichier_url=d.fichier_url,
            statut=d.statut,
            created_at=d.created_at.isoformat() if d.created_at else "",
        ) for d in rows
    ]

@router.post("/", response_model=QMSOut, status_code=status.HTTP_201_CREATED)
async def create_qms_document(
    payload: QMSCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ADMIN, RoleEnum.MEDECIN)),
):
    """Crée un nouveau protocole ou document qualité QMS."""
    doc = QMSDocument(
        clinic_id=current_user["clinic_id"],
        titre=payload.titre,
        categorie=payload.categorie,
        version=payload.version or "1.0",
        contenu_markdown=payload.contenu_markdown,
        fichier_url=payload.fichier_url,
        created_by=current_user["id"],
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return QMSOut(
        id=doc.id,
        clinic_id=doc.clinic_id,
        titre=doc.titre,
        categorie=doc.categorie,
        version=doc.version,
        contenu_markdown=doc.contenu_markdown,
        fichier_url=doc.fichier_url,
        statut=doc.statut,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
    )
