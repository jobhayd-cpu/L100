from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    db_ok = False
    pgvector_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
        result = await db.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        )
        pgvector_ok = result.scalar() == "vector"
    except Exception:
        return {"status": "error", "detail": "Database connection failed"}

    return {
        "status": "ok",
        "database": "connected" if db_ok else "error",
        "pgvector": "enabled" if pgvector_ok else "not_found",
        "openai_configured": settings.has_openai,
        "embedding_model": settings.embedding_model if settings.has_openai else "local_fallback",
    }
