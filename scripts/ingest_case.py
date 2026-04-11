#!/usr/bin/env python3
"""
CLI script to ingest and index a case folder in one command.

Usage:
    python ingest_case.py --case-name "CASE-0001" --folder ./cases/CASE-0001 \
        --stage carpeta_investigacion --autoridad "Ministerio Público" \
        [--api-url http://localhost:8000]

The script will:
  1. Create the case (if it doesn't exist)
  2. Ingest all PDFs/images in the folder
  3. Index (chunk + embed) each document
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)


DEFAULT_API = "http://localhost:8000"


def create_case(client: httpx.Client, nombre_corto: str, notas: Optional[str] = None) -> int:
    resp = client.post(
        "/cases",
        json={"nombre_corto": nombre_corto, "notas": notas},
    )
    if resp.status_code == 409:
        # Already exists; fetch it
        all_cases = client.get("/cases").json()
        for c in all_cases:
            if c["nombre_corto"] == nombre_corto:
                print(f"  [OK] Caso ya existe (id={c['id']})")
                return c["id"]
        raise RuntimeError("Caso existe pero no se pudo recuperar el id")
    resp.raise_for_status()
    data = resp.json()
    print(f"  [OK] Caso creado (id={data['id']})")
    return data["id"]


def ingest_folder(
    client: httpx.Client,
    case_id: int,
    folder: str,
    stage: Optional[str],
    autoridad: Optional[str],
    fecha_documento: Optional[str],
    anexo_num: Optional[str],
) -> list[int]:
    payload = {
        "case_id": case_id,
        "folder_path": folder,
        "stage": stage,
        "autoridad": autoridad,
        "fecha_documento": fecha_documento,
        "anexo_num": anexo_num,
    }
    # Remove None values
    payload = {k: v for k, v in payload.items() if v is not None}
    resp = client.post("/documents/ingest", json=payload, timeout=300)
    resp.raise_for_status()
    docs = resp.json()
    ids = [d["id"] for d in docs]
    print(f"  [OK] {len(ids)} documento(s) ingestado(s): {ids}")
    return ids


def index_document(client: httpx.Client, doc_id: int) -> int:
    resp = client.post(f"/documents/{doc_id}/index", timeout=300)
    resp.raise_for_status()
    data = resp.json()
    chunks = data["chunks_created"]
    print(f"  [OK] Documento {doc_id} indexado: {chunks} chunks")
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingestar e indexar una carpeta de un caso legal"
    )
    parser.add_argument("--case-name", required=True, help="Nombre corto del caso (único)")
    parser.add_argument("--folder", required=True, help="Ruta local a la carpeta con PDFs/imágenes")
    parser.add_argument(
        "--stage",
        choices=["carpeta_investigacion", "judicial", "amparo_indirecto"],
        default=None,
        help="Etapa procesal de los documentos",
    )
    parser.add_argument("--autoridad", default=None, help="Autoridad emisora de los documentos")
    parser.add_argument("--fecha-documento", default=None, help="Fecha del documento (YYYY-MM-DD)")
    parser.add_argument("--anexo-num", default=None, help="Número de anexo")
    parser.add_argument("--notas", default=None, help="Notas del caso")
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API,
        help=f"URL base del API (default: {DEFAULT_API})",
    )
    args = parser.parse_args()

    print(f"\n=== Ingesta y Indexación: {args.case_name} ===\n")

    with httpx.Client(base_url=args.api_url) as client:
        # Health check
        try:
            health = client.get("/health").json()
            print(f"Estado del API: {health.get('status')} | pgvector: {health.get('pgvector')}")
        except Exception as exc:
            print(f"ADVERTENCIA: No se pudo conectar al API en {args.api_url}: {exc}")
            sys.exit(1)

        print("\n1. Creando/verificando caso...")
        case_id = create_case(client, args.case_name, args.notas)

        print("\n2. Ingestando documentos...")
        doc_ids = ingest_folder(
            client,
            case_id=case_id,
            folder=args.folder,
            stage=args.stage,
            autoridad=args.autoridad,
            fecha_documento=args.fecha_documento,
            anexo_num=args.anexo_num,
        )

        if not doc_ids:
            print("  No se ingestaron documentos.")
            return

        print("\n3. Indexando documentos (creando chunks + embeddings)...")
        total_chunks = 0
        for doc_id in doc_ids:
            try:
                total_chunks += index_document(client, doc_id)
            except Exception as exc:
                print(f"  [ERROR] Documento {doc_id}: {exc}")

        print(f"\n=== Listo: {len(doc_ids)} documentos, {total_chunks} chunks totales ===")
        print(f"\nPuedes buscar con:\n  GET {args.api_url}/search?query=TU_BUSQUEDA&case_id={case_id}")
        print(f"  POST {args.api_url}/ask  {{\"question\": \"tu pregunta\", \"case_id\": {case_id}}}")


if __name__ == "__main__":
    main()
