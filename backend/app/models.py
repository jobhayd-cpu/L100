from __future__ import annotations

import enum
from datetime import date, datetime
from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.database import Base

settings = get_settings()


# ─── Enums ────────────────────────────────────────────────────────────────────


class StageEnum(str, enum.Enum):
    carpeta_investigacion = "carpeta_investigacion"
    judicial = "judicial"
    amparo_indirecto = "amparo_indirecto"


class IssueSeverityEnum(str, enum.Enum):
    alta = "alta"
    media = "media"
    baja = "baja"


class IssueStatusEnum(str, enum.Enum):
    pendiente = "pendiente"
    confirmada = "confirmada"
    descartada = "descartada"


# ─── Models ───────────────────────────────────────────────────────────────────


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre_corto: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    jurisdiccion: Mapped[Optional[str]] = mapped_column(String(100))
    estado_procesal: Mapped[Optional[str]] = mapped_column(String(200))
    cliente_alias: Mapped[Optional[str]] = mapped_column(String(200))
    notas: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[List["Document"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    events: Mapped[List["Event"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    issues: Mapped[List["Issue"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    drafts: Mapped[List["Draft"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)

    titulo: Mapped[str] = mapped_column(String(500), nullable=False)
    tipo: Mapped[Optional[str]] = mapped_column(String(100))
    stage: Mapped[Optional[StageEnum]] = mapped_column(
        Enum(StageEnum, name="stage_enum"), nullable=True
    )
    autoridad: Mapped[Optional[str]] = mapped_column(String(300))
    fecha_documento: Mapped[Optional[date]] = mapped_column(Date)
    fecha_notificacion: Mapped[Optional[date]] = mapped_column(Date)
    anexo_num: Mapped[Optional[str]] = mapped_column(String(50))

    file_path: Mapped[Optional[str]] = mapped_column(String(1000))
    sha256: Mapped[Optional[str]] = mapped_column(String(64))

    es_escaneado: Mapped[bool] = mapped_column(Boolean, default=False)
    requiere_ocr: Mapped[bool] = mapped_column(Boolean, default=False)
    total_pages: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    case: Mapped[Optional["Case"]] = relationship(back_populates="documents")
    pages: Mapped[List["DocumentPage"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number"
    )
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("sha256", name="uq_documents_sha256"),)

    @property
    def citation_date(self) -> str:
        if self.fecha_documento:
            return self.fecha_documento.strftime("%Y-%m-%d")
        return "s/f"

    def format_citation(self, page: int) -> str:
        """Return citation string: Titulo (Autoridad), fecha, p. N"""
        auth = self.autoridad or "s/a"
        return f"{self.titulo} ({auth}), {self.citation_date}, p. {page}"


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based
    texto_extraido: Mapped[Optional[str]] = mapped_column(Text)
    ocr_confidence: Mapped[Optional[float]] = mapped_column(Float)
    is_ocr: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped["Document"] = relationship(back_populates="pages")

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_docpage_docid_pagenum"),
        Index("ix_document_pages_document_id", "document_id"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    texto_chunk: Mapped[str] = mapped_column(Text, nullable=False)
    page_from: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based
    page_to: Mapped[int] = mapped_column(Integer, nullable=False)    # 1-based inclusive

    # Citation metadata (denormalized for fast retrieval)
    doc_titulo: Mapped[Optional[str]] = mapped_column(String(500))
    doc_autoridad: Mapped[Optional[str]] = mapped_column(String(300))
    doc_fecha: Mapped[Optional[str]] = mapped_column(String(20))  # ISO date or "s/f"
    doc_anexo_num: Mapped[Optional[str]] = mapped_column(String(50))

    embedding: Mapped[Optional[List[float]]] = mapped_column(
        Vector(settings.embedding_dim), nullable=True
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_docid_idx"),
        Index("ix_document_chunks_document_id", "document_id"),
    )

    def format_citation(self) -> str:
        """Return formatted citation for this chunk."""
        auth = self.doc_autoridad or "s/a"
        fecha = self.doc_fecha or "s/f"
        page_str = str(self.page_from) if self.page_from == self.page_to else f"{self.page_from}-{self.page_to}"
        return f"{self.doc_titulo} ({auth}), {fecha}, p. {page_str}"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    fecha_hora: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    tipo_evento: Mapped[Optional[str]] = mapped_column(String(200))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    fuente_chunk_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["Case"] = relationship(back_populates="events")
    __table_args__ = (Index("ix_events_case_id", "case_id"),)


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    tipo: Mapped[Optional[str]] = mapped_column(String(200))
    descripcion: Mapped[Optional[str]] = mapped_column(Text)
    severidad: Mapped[Optional[IssueSeverityEnum]] = mapped_column(
        Enum(IssueSeverityEnum, name="issue_severity_enum"), nullable=True
    )
    estado: Mapped[Optional[IssueStatusEnum]] = mapped_column(
        Enum(IssueStatusEnum, name="issue_status_enum"), default=IssueStatusEnum.pendiente
    )
    fundamento: Mapped[Optional[str]] = mapped_column(Text)
    consecuencia: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["Case"] = relationship(back_populates="issues")
    __table_args__ = (Index("ix_issues_case_id", "case_id"),)


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    tipo: Mapped[Optional[str]] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    fecha: Mapped[Optional[date]] = mapped_column(Date)
    estado: Mapped[Optional[str]] = mapped_column(String(100))
    cuerpo_markdown: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    case: Mapped["Case"] = relationship(back_populates="drafts")
    __table_args__ = (Index("ix_drafts_case_id", "case_id"),)
