from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import ask, cases, documents, health, search

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="Legal Case Knowledge Base",
    description=(
        "Base de conocimiento local para asuntos penales federales y de Coahuila "
        "(defensa, amparos indirectos). Soporta ingestión de PDFs (nativo + OCR), "
        "búsqueda semántica con pgvector y generación de respuestas con citas."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(cases.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(ask.router)


@app.get("/")
async def root():
    return {
        "message": "Legal Case Knowledge Base API",
        "docs": "/docs",
        "health": "/health",
    }
