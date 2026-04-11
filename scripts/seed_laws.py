#!/usr/bin/env python3
"""
Descarga e ingesta de leyes mexicanas de referencia al sistema L100.

Las leyes federales se obtienen de la Cámara de Diputados (diputados.gob.mx).
Se crea un caso especial "LEYES-REFERENCIA" en el que se almacenan todos los
documentos para que las búsquedas semánticas sin case_id las incluyan.

Uso:
    python scripts/seed_laws.py [--api-url http://localhost:8000]
                                [--laws-dir ./laws]
                                [--force-download]
                                [--download-only]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx no instalado. Ejecuta: pip install httpx")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Catálogo de leyes
# ---------------------------------------------------------------------------

FEDERAL_LAWS = [
    {
        "filename": "CPEUM.pdf",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CPEUM.pdf",
        "titulo": "Constitución Política de los Estados Unidos Mexicanos",
        "autoridad": "Congreso Constituyente / H. Congreso de la Unión",
    },
    {
        "filename": "CNPP.pdf",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CNPP.pdf",
        "titulo": "Código Nacional de Procedimientos Penales",
        "autoridad": "H. Congreso de la Unión",
    },
    {
        "filename": "CPF.pdf",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CPF.pdf",
        "titulo": "Código Penal Federal",
        "autoridad": "H. Congreso de la Unión",
    },
    {
        "filename": "LAmp.pdf",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LAmp.pdf",
        "titulo": "Ley de Amparo",
        "autoridad": "H. Congreso de la Unión",
    },
    {
        "filename": "LFDO.pdf",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LFDO.pdf",
        "titulo": "Ley Federal contra la Delincuencia Organizada",
        "autoridad": "H. Congreso de la Unión",
    },
    {
        "filename": "LOPJF.pdf",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LOPJF.pdf",
        "titulo": "Ley Orgánica del Poder Judicial de la Federación",
        "autoridad": "H. Congreso de la Unión",
    },
    {
        "filename": "LNE.pdf",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LNE.pdf",
        "titulo": "Ley Nacional de Ejecución Penal",
        "autoridad": "H. Congreso de la Unión",
    },
    {
        "filename": "LNMASCMP.pdf",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LNMASCMP.pdf",
        "titulo": "Ley Nacional de Mecanismos Alternativos de Solución de Controversias en Materia Penal",
        "autoridad": "H. Congreso de la Unión",
    },
    {
        "filename": "LNSIJPA.pdf",
        "url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/LNSIJPA.pdf",
        "titulo": "Ley Nacional del Sistema Integral de Justicia Penal para Adolescentes",
        "autoridad": "H. Congreso de la Unión",
    },
]

CASE_NAME = "LEYES-REFERENCIA"
DEFAULT_API = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def download_file(url: str, dest: Path, force: bool = False) -> bool:
    """Download url to dest. Returns True if file was (re)downloaded."""
    if dest.exists() and not force:
        print(f"    [SKIP] Ya existe: {dest.name}")
        return False

    print(f"    [↓] Descargando {dest.name} ...")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as r:
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        size_kb = dest.stat().st_size // 1024
        print(f"    [OK] {dest.name} ({size_kb} KB)")
        return True
    except Exception as exc:
        print(f"    [ERROR] No se pudo descargar {url}: {exc}")
        if dest.exists():
            dest.unlink()
        return False


def get_or_create_case(client: httpx.Client, nombre_corto: str) -> Optional[int]:
    resp = client.post("/cases", json={"nombre_corto": nombre_corto, "notas": "Leyes de referencia federal y local"})
    if resp.status_code == 409:
        all_cases = client.get("/cases").json()
        for c in all_cases:
            if c["nombre_corto"] == nombre_corto:
                return c["id"]
        return None
    if resp.is_success:
        return resp.json()["id"]
    print(f"  [ERROR] No se pudo crear caso: {resp.status_code} {resp.text}")
    return None


def ingest_file(client: httpx.Client, file_path: str, case_id: int, titulo: str, autoridad: str) -> Optional[int]:
    payload = {
        "case_id": case_id,
        "folder_path": str(Path(file_path).parent),
        "titulo": titulo,
        "autoridad": autoridad,
    }
    resp = client.post("/documents/ingest", json=payload, timeout=300)
    if not resp.is_success:
        print(f"    [ERROR] Ingesta fallida ({resp.status_code}): {resp.text[:200]}")
        return None
    docs = resp.json()
    if not docs:
        print("    [WARN] La API no retornó documentos (posible duplicado ya ingresado).")
        return None
    doc_id = docs[0]["id"]
    print(f"    [OK] Ingesta OK → doc_id={doc_id}")
    return doc_id


def index_document(client: httpx.Client, doc_id: int) -> int:
    resp = client.post(f"/documents/{doc_id}/index", timeout=600)
    if not resp.is_success:
        print(f"    [ERROR] Index fallido ({resp.status_code}): {resp.text[:200]}")
        return 0
    chunks = resp.json().get("chunks_created", 0)
    print(f"    [OK] Indexado: {chunks} chunks")
    return chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga e ingesta leyes de referencia en L100")
    parser.add_argument("--api-url", default=DEFAULT_API, help=f"URL del API (default: {DEFAULT_API})")
    parser.add_argument(
        "--laws-dir",
        default=str(Path(__file__).resolve().parent.parent / "laws"),
        help="Carpeta local donde se guardan los PDFs (default: ./laws)",
    )
    parser.add_argument("--force-download", action="store_true", help="Re-descarga aunque el archivo ya exista")
    parser.add_argument("--download-only", action="store_true", help="Solo descarga, no ingesta al API")
    args = parser.parse_args()

    laws_dir = Path(args.laws_dir)
    laws_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Descargar PDFs ──────────────────────────────────────────────────
    print("\n=== FASE 1: Descarga de leyes ===\n")
    downloaded: list[dict] = []
    for law in FEDERAL_LAWS:
        dest = laws_dir / law["filename"]
        print(f"  {law['titulo']}")
        ok = download_file(law["url"], dest, force=args.force_download)
        if dest.exists():
            downloaded.append({**law, "path": str(dest)})
        time.sleep(0.5)  # ser amables con el servidor

    if args.download_only:
        print(f"\n=== Descarga completa: {len(downloaded)} archivos en {laws_dir} ===")
        return

    if not downloaded:
        print("\nNo hay archivos para ingestar. Verifica la conexión a internet.")
        sys.exit(1)

    # ── 2. Ingestar al API ─────────────────────────────────────────────────
    print(f"\n=== FASE 2: Ingesta al API ({args.api_url}) ===\n")
    with httpx.Client(base_url=args.api_url, timeout=30) as client:
        # Health check
        try:
            health = client.get("/health").json()
            print(f"  API: {health.get('status')} | pgvector: {health.get('pgvector')}\n")
        except Exception as exc:
            print(f"  [ERROR] No se pudo conectar al API: {exc}")
            print("  Asegúrate de que el backend esté corriendo: docker compose up -d")
            sys.exit(1)

        # Crear / obtener caso de referencia
        print(f"  Creando caso '{CASE_NAME}'...")
        case_id = get_or_create_case(client, CASE_NAME)
        if not case_id:
            print("  [ERROR] No se pudo obtener el case_id. Abortando.")
            sys.exit(1)
        print(f"  case_id = {case_id}\n")

        total_docs = 0
        total_chunks = 0

        for law in downloaded:
            print(f"  Procesando: {law['titulo']}")

            # Ingestar cada archivo individualmente usando upload endpoint
            law_path = Path(law["path"])
            try:
                with open(law_path, "rb") as f:
                    upload_resp = client.post(
                        "/documents/upload",
                        files={"file": (law_path.name, f, "application/pdf")},
                        data={
                            "case_id": str(case_id),
                            "titulo": law["titulo"],
                            "autoridad": law["autoridad"],
                        },
                        timeout=300,
                    )
                if not upload_resp.is_success:
                    print(f"    [ERROR] Upload fallido ({upload_resp.status_code}): {upload_resp.text[:200]}")
                    continue
                doc_id = upload_resp.json()["id"]
                print(f"    [OK] Subida OK → doc_id={doc_id}")
            except Exception as exc:
                print(f"    [ERROR] {exc}")
                continue

            # Indexar
            print(f"    Indexando doc_id={doc_id} (puede tardar varios minutos)...")
            chunks = index_document(client, doc_id)
            total_docs += 1
            total_chunks += chunks
            time.sleep(1)

        print(
            f"\n=== Carga completa: {total_docs} leyes, {total_chunks} chunks totales ===\n"
            f"Busca con: GET {args.api_url}/search?query=TU_CONSULTA\n"
            f"           POST {args.api_url}/ask  {{\"question\": \"¿Cuáles son los requisitos de la detención en flagrancia?\"}}"
        )


if __name__ == "__main__":
    main()
