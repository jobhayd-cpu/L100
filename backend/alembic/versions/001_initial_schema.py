"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-10

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.config import get_settings

settings = get_settings()

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── cases ──────────────────────────────────────────────────────────────
    op.create_table(
        "cases",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("nombre_corto", sa.String(200), nullable=False, unique=True),
        sa.Column("jurisdiccion", sa.String(100)),
        sa.Column("estado_procesal", sa.String(200)),
        sa.Column("cliente_alias", sa.String(200)),
        sa.Column("notas", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── documents ──────────────────────────────────────────────────────────
    stage_enum = sa.Enum(
        "carpeta_investigacion",
        "judicial",
        "amparo_indirecto",
        name="stage_enum",
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer, sa.ForeignKey("cases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("titulo", sa.String(500), nullable=False),
        sa.Column("tipo", sa.String(100)),
        sa.Column("stage", stage_enum, nullable=True),
        sa.Column("autoridad", sa.String(300)),
        sa.Column("fecha_documento", sa.Date),
        sa.Column("fecha_notificacion", sa.Date),
        sa.Column("anexo_num", sa.String(50)),
        sa.Column("file_path", sa.String(1000)),
        sa.Column("sha256", sa.String(64), unique=True),
        sa.Column("es_escaneado", sa.Boolean, default=False),
        sa.Column("requiere_ocr", sa.Boolean, default=False),
        sa.Column("total_pages", sa.Integer),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_documents_case_id", "documents", ["case_id"])

    # ── document_pages ─────────────────────────────────────────────────────
    op.create_table(
        "document_pages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("texto_extraido", sa.Text),
        sa.Column("ocr_confidence", sa.Float),
        sa.Column("is_ocr", sa.Boolean, default=False),
        sa.UniqueConstraint("document_id", "page_number", name="uq_docpage_docid_pagenum"),
    )
    op.create_index("ix_document_pages_document_id", "document_pages", ["document_id"])

    # ── document_chunks ────────────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("texto_chunk", sa.Text, nullable=False),
        sa.Column("page_from", sa.Integer, nullable=False),
        sa.Column("page_to", sa.Integer, nullable=False),
        sa.Column("doc_titulo", sa.String(500)),
        sa.Column("doc_autoridad", sa.String(300)),
        sa.Column("doc_fecha", sa.String(20)),
        sa.Column("doc_anexo_num", sa.String(50)),
        sa.Column("embedding", Vector(settings.embedding_dim), nullable=True),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_docid_idx"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    # pgvector HNSW index for cosine similarity
    op.execute(
        "CREATE INDEX ix_chunks_embedding ON document_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # ── events ─────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "case_id",
            sa.Integer,
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fecha_hora", sa.DateTime(timezone=True)),
        sa.Column("tipo_evento", sa.String(200)),
        sa.Column("descripcion", sa.Text),
        sa.Column(
            "fuente_chunk_id",
            sa.Integer,
            sa.ForeignKey("document_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_events_case_id", "events", ["case_id"])

    # ── issues ─────────────────────────────────────────────────────────────
    severity_enum = sa.Enum("alta", "media", "baja", name="issue_severity_enum")
    status_enum = sa.Enum("pendiente", "confirmada", "descartada", name="issue_status_enum")
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "case_id",
            sa.Integer,
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(200)),
        sa.Column("descripcion", sa.Text),
        sa.Column("severidad", severity_enum, nullable=True),
        sa.Column("estado", status_enum, default="pendiente"),
        sa.Column("fundamento", sa.Text),
        sa.Column("consecuencia", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_issues_case_id", "issues", ["case_id"])

    # ── drafts ─────────────────────────────────────────────────────────────
    op.create_table(
        "drafts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "case_id",
            sa.Integer,
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(200)),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("fecha", sa.Date),
        sa.Column("estado", sa.String(100)),
        sa.Column("cuerpo_markdown", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_drafts_case_id", "drafts", ["case_id"])


def downgrade() -> None:
    op.drop_table("drafts")
    op.drop_table("issues")
    op.drop_table("events")
    op.drop_table("document_chunks")
    op.drop_table("document_pages")
    op.drop_table("documents")
    op.drop_table("cases")

    op.execute("DROP TYPE IF EXISTS issue_status_enum")
    op.execute("DROP TYPE IF EXISTS issue_severity_enum")
    op.execute("DROP TYPE IF EXISTS stage_enum")
