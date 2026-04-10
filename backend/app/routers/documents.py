from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models import Document, DocumentChunk, DocumentPage
from app.schemas import DocumentIndexResponse, DocumentIngestRequest, DocumentRead
from app.services.chunking import chunk_pages
from app.services.embeddings import embed_texts
from app.services.ingestion import compute_sha256, extract_pages, scan_folder

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)
settings = get_settings()

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/cases/uploads")


async def _ingest_file(
    db: AsyncSession,
    file_path: str,
    *,
    case_id: Optional[int],
    titulo: Optional[str],
    tipo: Optional[str],
    stage: Optional[str],
    autoridad: Optional[str],
    fecha_documento,
    fecha_notificacion,
    anexo_num: Optional[str],
) -> Document:
    sha = compute_sha256(file_path)

    # Deduplicate by hash
    existing = await db.execute(select(Document).where(Document.sha256 == sha))
    if doc := existing.scalar_one_or_none():
        logger.info("Document already ingested (sha256=%s), returning existing", sha)
        return doc

    filename = Path(file_path).name
    resolved_titulo = titulo or filename

    pages_data = extract_pages(file_path, ocr_lang=settings.ocr_lang)
    total_pages = len(pages_data)
    any_ocr = any(is_ocr for _, _, is_ocr, _ in pages_data)

    doc = Document(
        case_id=case_id,
        titulo=resolved_titulo,
        tipo=tipo,
        stage=stage,
        autoridad=autoridad,
        fecha_documento=fecha_documento,
        fecha_notificacion=fecha_notificacion,
        anexo_num=anexo_num,
        file_path=file_path,
        sha256=sha,
        es_escaneado=any_ocr,
        requiere_ocr=any_ocr,
        total_pages=total_pages,
    )
    db.add(doc)
    await db.flush()  # get doc.id

    for page_num, text, is_ocr, conf in pages_data:
        page = DocumentPage(
            document_id=doc.id,
            page_number=page_num,
            texto_extraido=text,
            ocr_confidence=conf,
            is_ocr=is_ocr,
        )
        db.add(page)

    await db.commit()
    await db.refresh(doc)
    return doc


@router.post("/ingest", response_model=List[DocumentRead], status_code=status.HTTP_201_CREATED)
async def ingest_documents(
    payload: DocumentIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest documents from a local folder path.
    Stores metadata and extracts text (native or OCR).
    """
    if not payload.folder_path:
        raise HTTPException(
            status_code=422,
            detail="Debes proporcionar folder_path en el body.",
        )

    # Resolve and sanitize the folder path
    folder = os.path.realpath(os.path.abspath(payload.folder_path))
    if not os.path.isdir(folder):
        raise HTTPException(status_code=422, detail="La carpeta proporcionada no existe o no es accesible.")

    files = scan_folder(folder)
    if not files:
        raise HTTPException(status_code=422, detail="No se encontraron archivos PDF o imagen en la carpeta.")

    ingested = []
    for fp in files:
        try:
            doc = await _ingest_file(
                db,
                fp,
                case_id=payload.case_id,
                titulo=payload.titulo,
                tipo=payload.tipo,
                stage=payload.stage,
                autoridad=payload.autoridad,
                fecha_documento=payload.fecha_documento,
                fecha_notificacion=payload.fecha_notificacion,
                anexo_num=payload.anexo_num,
            )
            ingested.append(doc)
        except Exception as exc:
            logger.error("Error ingesting %s: %s", fp, exc)

    return ingested


@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    case_id: Optional[int] = Form(None),
    titulo: Optional[str] = Form(None),
    tipo: Optional[str] = Form(None),
    stage: Optional[str] = Form(None),
    autoridad: Optional[str] = Form(None),
    fecha_documento: Optional[str] = Form(None),
    fecha_notificacion: Optional[str] = Form(None),
    anexo_num: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a single document file (multipart form)."""
    from datetime import date as date_type

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_filename = Path(file.filename or "upload").name  # Strip any path components
    dest = os.path.join(UPLOAD_DIR, safe_filename)
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    def parse_date(s):
        if not s:
            return None
        try:
            return date_type.fromisoformat(s)
        except ValueError:
            return None

    doc = await _ingest_file(
        db,
        dest,
        case_id=case_id,
        titulo=titulo,
        tipo=tipo,
        stage=stage,
        autoridad=autoridad,
        fecha_documento=parse_date(fecha_documento),
        fecha_notificacion=parse_date(fecha_notificacion),
        anexo_num=anexo_num,
    )
    return doc


@router.post("/{document_id}/index", response_model=DocumentIndexResponse)
async def index_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """
    Create chunks + embeddings from a previously ingested document and store into pgvector.
    """
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    # Load pages
    pages_result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    pages = pages_result.scalars().all()

    if not pages:
        raise HTTPException(status_code=422, detail="El documento no tiene páginas extraídas. Primero ingestarlo.")

    # Delete existing chunks
    existing_chunks = await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    for ch in existing_chunks.scalars().all():
        await db.delete(ch)
    await db.flush()

    # Build (page_num, text) list
    page_tuples = [(p.page_number, p.texto_extraido or "") for p in pages]
    raw_chunks = chunk_pages(page_tuples)

    if not raw_chunks:
        raise HTTPException(status_code=422, detail="No se pudo extraer texto del documento para indexar.")

    # Embed all chunks
    texts = [t for _, _, t in raw_chunks]
    embeddings = embed_texts(texts)

    fecha_str = doc.citation_date

    for idx, ((page_from, page_to, text), embedding) in enumerate(zip(raw_chunks, embeddings)):
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=idx,
            texto_chunk=text,
            page_from=page_from,
            page_to=page_to,
            doc_titulo=doc.titulo,
            doc_autoridad=doc.autoridad,
            doc_fecha=fecha_str,
            doc_anexo_num=doc.anexo_num,
            embedding=embedding,
        )
        db.add(chunk)

    await db.commit()
    return DocumentIndexResponse(
        document_id=document_id,
        chunks_created=len(raw_chunks),
        message=f"Se crearon {len(raw_chunks)} chunks con embeddings.",
    )


@router.get("", response_model=List[DocumentRead])
async def list_documents(
    case_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Document).order_by(Document.created_at.desc())
    if case_id is not None:
        q = q.where(Document.case_id == case_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return doc
