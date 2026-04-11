from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.search import _do_search
from app.schemas import AskRequest, AskResponse, SearchRequest
from app.services.rag import ask_with_rag

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
async def ask(payload: AskRequest, db: AsyncSession = Depends(get_db)):
    """
    RAG-style endpoint: retrieve relevant chunks, then generate (or return) an answer with citations.
    If no OpenAI key is configured, returns retrieval-only mode.
    """
    search_payload = SearchRequest(
        query=payload.question,
        case_id=payload.case_id,
        top_k=payload.top_k,
    )
    search_result = await _do_search(search_payload, db)
    return ask_with_rag(payload.question, search_result.results)
