from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import DocumentChunk
from app.schemas import ChunkResult, SearchRequest, SearchResponse
from app.services.embeddings import embed_query

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger(__name__)


@router.get("", response_model=SearchResponse)
async def search(
    query: str = Query(..., description="Búsqueda por texto o semántica"),
    case_id: Optional[int] = Query(None),
    top_k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    return await _do_search(SearchRequest(query=query, case_id=case_id, top_k=top_k), db)


@router.post("", response_model=SearchResponse)
async def search_post(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    return await _do_search(payload, db)


async def _do_search(payload: SearchRequest, db: AsyncSession) -> SearchResponse:
    """
    Hybrid search: semantic (cosine similarity via pgvector) + keyword (ILIKE).
    Returns ranked chunks with citations.
    """
    query_vec = embed_query(payload.query)
    query_vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

    # Build case filter
    case_filter = ""
    if payload.case_id is not None:
        case_filter = f"AND d.case_id = {payload.case_id}"

    # Combined query: semantic + keyword score
    sql = text(
        f"""
        SELECT
            dc.id,
            dc.document_id,
            dc.texto_chunk,
            dc.page_from,
            dc.page_to,
            dc.doc_titulo,
            dc.doc_autoridad,
            dc.doc_fecha,
            dc.doc_anexo_num,
            CASE
                WHEN dc.embedding IS NOT NULL
                THEN 1 - (dc.embedding <=> :query_vec::vector)
                ELSE 0
            END AS semantic_score,
            CASE
                WHEN dc.texto_chunk ILIKE :keyword THEN 1.0
                ELSE 0.0
            END AS keyword_score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE 1=1 {case_filter}
        ORDER BY
            (
                CASE WHEN dc.embedding IS NOT NULL
                     THEN 1 - (dc.embedding <=> :query_vec::vector)
                     ELSE 0 END
                * :vec_weight
            ) + (
                CASE WHEN dc.texto_chunk ILIKE :keyword THEN 1.0 ELSE 0.0 END
                * :kw_weight
            ) DESC
        LIMIT :top_k
        """
    )

    keyword_weight = payload.keyword_weight
    vec_weight = 1.0 - keyword_weight
    keyword_pattern = f"%{payload.query}%"

    result = await db.execute(
        sql,
        {
            "query_vec": query_vec_str,
            "keyword": keyword_pattern,
            "top_k": payload.top_k,
            "vec_weight": vec_weight,
            "kw_weight": keyword_weight,
        },
    )
    rows = result.fetchall()

    chunks: List[ChunkResult] = []
    for row in rows:
        auth = row.doc_autoridad or "s/a"
        fecha = row.doc_fecha or "s/f"
        page_str = str(row.page_from) if row.page_from == row.page_to else f"{row.page_from}-{row.page_to}"
        citation = f"{row.doc_titulo} ({auth}), {fecha}, p. {page_str}"
        score = float(row.semantic_score) * vec_weight + float(row.keyword_score) * keyword_weight
        chunks.append(
            ChunkResult(
                chunk_id=row.id,
                document_id=row.document_id,
                texto_chunk=row.texto_chunk,
                page_from=row.page_from,
                page_to=row.page_to,
                citation=citation,
                score=round(score, 4),
            )
        )

    return SearchResponse(query=payload.query, results=chunks, total=len(chunks))
