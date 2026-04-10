from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─── Case ─────────────────────────────────────────────────────────────────────


class CaseCreate(BaseModel):
    nombre_corto: str
    jurisdiccion: Optional[str] = None
    estado_procesal: Optional[str] = None
    cliente_alias: Optional[str] = None
    notas: Optional[str] = None


class CaseRead(CaseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


# ─── Document ─────────────────────────────────────────────────────────────────


class DocumentIngestRequest(BaseModel):
    case_id: Optional[int] = None
    folder_path: Optional[str] = Field(None, description="Local folder path to scan for PDFs/images")
    titulo: Optional[str] = None
    tipo: Optional[str] = None
    stage: Optional[str] = None
    autoridad: Optional[str] = None
    fecha_documento: Optional[date] = None
    fecha_notificacion: Optional[date] = None
    anexo_num: Optional[str] = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: Optional[int]
    titulo: str
    tipo: Optional[str]
    stage: Optional[str]
    autoridad: Optional[str]
    fecha_documento: Optional[date]
    fecha_notificacion: Optional[date]
    anexo_num: Optional[str]
    file_path: Optional[str]
    sha256: Optional[str]
    es_escaneado: bool
    total_pages: Optional[int]
    created_at: datetime


class DocumentIndexResponse(BaseModel):
    document_id: int
    chunks_created: int
    message: str


# ─── Search ───────────────────────────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str
    case_id: Optional[int] = None
    top_k: int = Field(10, ge=1, le=50)
    keyword_weight: float = Field(0.3, ge=0.0, le=1.0)


class ChunkResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    chunk_id: int
    document_id: int
    texto_chunk: str
    page_from: int
    page_to: int
    citation: str
    score: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    results: List[ChunkResult]
    total: int


# ─── Ask ──────────────────────────────────────────────────────────────────────


class AskRequest(BaseModel):
    question: str
    case_id: Optional[int] = None
    top_k: int = Field(8, ge=1, le=20)


class AskResponse(BaseModel):
    question: str
    answer: str
    mode: str  # "rag" | "retrieval_only"
    citations: List[str]
    chunks_used: List[ChunkResult]


# ─── Event ────────────────────────────────────────────────────────────────────


class EventCreate(BaseModel):
    case_id: int
    fecha_hora: Optional[datetime] = None
    tipo_evento: Optional[str] = None
    descripcion: Optional[str] = None


class EventRead(EventCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ─── Issue ────────────────────────────────────────────────────────────────────


class IssueCreate(BaseModel):
    case_id: int
    tipo: Optional[str] = None
    descripcion: Optional[str] = None
    severidad: Optional[str] = None
    estado: Optional[str] = "pendiente"
    fundamento: Optional[str] = None
    consecuencia: Optional[str] = None


class IssueRead(IssueCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ─── Draft ────────────────────────────────────────────────────────────────────


class DraftCreate(BaseModel):
    case_id: int
    tipo: Optional[str] = None
    version: int = 1
    fecha: Optional[date] = None
    estado: Optional[str] = None
    cuerpo_markdown: Optional[str] = None


class DraftRead(DraftCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
