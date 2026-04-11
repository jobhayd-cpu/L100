from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Case
from app.schemas import CaseCreate, CaseRead

router = APIRouter(prefix="/cases", tags=["cases"])


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED)
async def create_case(payload: CaseCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Case).where(Case.nombre_corto == payload.nombre_corto))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Ya existe un caso con ese nombre_corto")

    case = Case(**payload.model_dump())
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


@router.get("", response_model=list[CaseRead])
async def list_cases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Case).order_by(Case.created_at.desc()))
    return result.scalars().all()


@router.get("/{case_id}", response_model=CaseRead)
async def get_case(case_id: int, db: AsyncSession = Depends(get_db)):
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    return case
