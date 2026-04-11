from __future__ import annotations

import logging
from typing import List, Optional

from app.config import get_settings
from app.schemas import AskResponse, ChunkResult

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """Eres un asistente jurídico especializado en derecho penal mexicano y amparo indirecto.
Tu función es analizar información de expedientes legales y proporcionar análisis precisos y fundamentados.
SIEMPRE cita tus fuentes en el formato: {Documento} ({Autoridad}), {fecha}, p. {página}.
Responde en español. No inventes información que no esté en los fragmentos proporcionados."""


def build_context(chunks: List[ChunkResult]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        parts.append(f"[{i}] {c.citation}\n{c.texto_chunk}")
    return "\n\n".join(parts)


def ask_with_rag(question: str, chunks: List[ChunkResult]) -> AskResponse:
    """
    Generate an answer using the retrieved chunks.
    If OpenAI API key is available, uses GPT for generation.
    Otherwise, returns retrieval-only mode.
    """
    if not chunks:
        return AskResponse(
            question=question,
            answer="No se encontraron fragmentos relevantes para responder esta pregunta.",
            mode="retrieval_only",
            citations=[],
            chunks_used=[],
        )

    citations = [c.citation for c in chunks]

    if not settings.has_openai:
        answer = (
            "Modo solo-recuperación (sin clave OpenAI). "
            "A continuación se muestran los fragmentos más relevantes encontrados:\n\n"
        )
        for i, c in enumerate(chunks, 1):
            answer += f"[{i}] {c.citation}\n{c.texto_chunk[:500]}...\n\n"
        return AskResponse(
            question=question,
            answer=answer,
            mode="retrieval_only",
            citations=citations,
            chunks_used=chunks,
        )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        context = build_context(chunks)
        user_content = (
            f"Contexto del expediente:\n\n{context}\n\n"
            f"Pregunta: {question}\n\n"
            "Responde usando SOLO la información del contexto. "
            "Cita las fuentes usando el formato indicado."
        )
        response = client.chat.completions.create(
            model=settings.chat_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        answer = response.choices[0].message.content or ""
        return AskResponse(
            question=question,
            answer=answer,
            mode="rag",
            citations=citations,
            chunks_used=chunks,
        )
    except Exception as exc:
        logger.error("OpenAI chat failed: %s", exc)
        answer = f"Error al generar respuesta con LLM: {exc}\n\nFragmentos recuperados:\n"
        for i, c in enumerate(chunks, 1):
            answer += f"[{i}] {c.citation}\n{c.texto_chunk[:300]}\n\n"
        return AskResponse(
            question=question,
            answer=answer,
            mode="retrieval_only",
            citations=citations,
            chunks_used=chunks,
        )
