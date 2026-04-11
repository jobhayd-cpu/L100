# L100 — Base de Conocimiento Legal Local

Sistema local de gestión y análisis de asuntos penales (defensa de imputados, amparo indirecto, Coahuila + Federal).  
Stack: **PostgreSQL 16 + pgvector** · **FastAPI** · **Python** · **Tesseract OCR** · **Docker Desktop (Windows)**

---

## Tabla de contenido

1. [Arquitectura](#arquitectura)
2. [Requisitos previos (Windows)](#requisitos-previos-windows)
3. [Instalación paso a paso](#instalación-paso-a-paso)
4. [Configuración (.env)](#configuración-env)
5. [Estructura de carpetas](#estructura-de-carpetas)
6. [Endpoints del API](#endpoints-del-api)
7. [Ingestión e indexación](#ingestión-e-indexación)
8. [Búsqueda y consultas con citas](#búsqueda-y-consultas-con-citas)
9. [Ejemplos de consultas (irregularidades y amparo)](#ejemplos-de-consultas)
10. [Migraciones de base de datos](#migraciones-de-base-de-datos)
11. [Referencia del esquema](#referencia-del-esquema)

---

## Arquitectura

```
Windows (host)
├── Docker Desktop
│   ├── Postgres 16 + pgvector  ←→  volumen persistente pgdata
│   └── FastAPI backend (Python 3.11)
│       ├── Ingestión PDF (nativo: pypdf + OCR: Tesseract/pypdfium2)
│       ├── Chunking por página
│       ├── Embeddings (OpenAI o fallback local)
│       └── pgvector para búsqueda semántica
└── scripts/ingest_case.py  (CLI local)
```

**Formato de cita estándar:**
```
{Documento} ({Autoridad}), {fecha_documento}, p. {página}
Ejemplo: Auto de vinculación (Juez de Control), 2025-03-18, p. 7
Si no hay fecha: ... s/f, p. 3
```

---

## Requisitos previos (Windows)

### 1. Docker Desktop

1. Descarga Docker Desktop desde <https://www.docker.com/products/docker-desktop/>
2. Instala y reinicia Windows.
3. Verifica en PowerShell:
   ```powershell
   docker --version
   docker compose version
   ```

### 2. Python 3.11+

1. Descarga desde <https://www.python.org/downloads/>
2. Marca **"Add Python to PATH"** durante la instalación.
3. Verifica:
   ```powershell
   python --version
   ```

### 3. Tesseract OCR (para PDFs escaneados y fotos)

1. Descarga el instalador de Tesseract para Windows desde:  
   <https://github.com/UB-Mannheim/tesseract/wiki>  
   (elige la versión más reciente que incluya español: `tesseract-ocr-w64-setup-*.exe`)

2. Durante la instalación:
   - Selecciona el idioma **Spanish (spa)** en los componentes adicionales.
   - Anota la ruta de instalación (por defecto: `C:\Program Files\Tesseract-OCR`)

3. Configura la variable de entorno en el archivo `.env` (ver siguiente sección):
   ```
   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

4. Verifica:
   ```powershell
   & "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
   ```

---

## Instalación paso a paso

### 1. Clonar / descargar el repositorio

```powershell
git clone https://github.com/jobhayd-cpu/L100.git
cd L100
```

### 2. Configurar variables de entorno

```powershell
copy .env.example .env
```

Edita `.env` con tu editor (Notepad, VS Code, etc.):
- Cambia `TESSERACT_CMD` si Tesseract está en una ruta diferente.
- Agrega tu `OPENAI_API_KEY` si quieres respuestas generadas por IA (opcional).

### 3. Iniciar los servicios con Docker

```powershell
docker compose up -d
```

Esto levanta:
- **PostgreSQL 16 + pgvector** en el puerto `5432`
- **FastAPI backend** en el puerto `8000`

Verifica que todo esté funcionando:
```powershell
docker compose ps
```

Espera ~30 segundos y prueba:
```powershell
curl http://localhost:8000/health
```

Deberías ver:
```json
{"status": "ok", "database": "connected", "pgvector": "enabled", ...}
```

### 4. Crear el entorno virtual de Python (para scripts locales)

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 5. Ejecutar migraciones (crear tablas)

Con Docker ejecutando, desde `backend/`:
```powershell
# Activa el venv si no está activo
venv\Scripts\activate

# Copia el .env al directorio backend para que Alembic lo encuentre
copy ..\.env .env

alembic upgrade head
```

---

## Configuración (.env)

| Variable | Default | Descripción |
|---|---|---|
| `POSTGRES_DB` | `legaldb` | Nombre de la base de datos |
| `POSTGRES_USER` | `legaluser` | Usuario de Postgres |
| `POSTGRES_PASSWORD` | `legalpass` | Contraseña (**cámbiala en producción**) |
| `DATABASE_URL` | (ver ejemplo) | URL para el backend (asyncpg) |
| `DATABASE_URL_SYNC` | (ver ejemplo) | URL para Alembic (psycopg2) |
| `OPENAI_API_KEY` | *(vacío)* | Clave OpenAI (opcional; sin clave el /ask funciona en modo recuperación) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Modelo de embeddings de OpenAI |
| `EMBEDDING_DIM` | `1536` | Dimensión del vector de embeddings |
| `CHAT_MODEL` | `gpt-4o` | Modelo de chat para /ask |
| `TESSERACT_CMD` | `tesseract` | Ruta al ejecutable de Tesseract |
| `OCR_LANG` | `spa` | Idioma para OCR |

---

## Estructura de carpetas

```
L100/
├── docker-compose.yml
├── .env.example
├── README.md
├── cases/                   ← Coloca aquí tus documentos
│   └── CASE-0001_NombreCorto/
│       ├── 01_carpeta_investigacion/
│       ├── 02_judicial/
│       └── 03_amparo_indirecto/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── routers/
│       │   ├── cases.py
│       │   ├── documents.py
│       │   ├── search.py
│       │   ├── ask.py
│       │   └── health.py
│       └── services/
│           ├── ingestion.py   (PDF nativo + OCR)
│           ├── chunking.py    (chunking por página)
│           ├── embeddings.py  (OpenAI o fallback local)
│           └── rag.py         (generación de respuestas)
└── scripts/
    ├── setup_db.sql           (extensiones SQL)
    └── ingest_case.py         (CLI de ingestión)
```

**Convención de nombres de archivos:**
```
YYYY-MM-DD__TIPO__AUTORIDAD__DESCRIPCION.pdf
Ejemplo: 2025-03-18__AUDIENCIA__JuezControl__Inicial.pdf
```

---

## Endpoints del API

Documentación interactiva en: **<http://localhost:8000/docs>**

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio |
| `POST` | `/cases` | Crear un caso |
| `GET` | `/cases` | Listar todos los casos |
| `GET` | `/cases/{id}` | Obtener un caso |
| `POST` | `/documents/ingest` | Ingestar documentos desde una carpeta local |
| `POST` | `/documents/upload` | Subir un documento por formulario |
| `POST` | `/documents/{id}/index` | Crear chunks + embeddings de un documento |
| `GET` | `/documents` | Listar documentos (filtrable por case_id) |
| `GET` | `/search?query=...` | Búsqueda híbrida (semántica + keyword) |
| `POST` | `/search` | Búsqueda con más opciones (body JSON) |
| `POST` | `/ask` | RAG: pregunta → recuperación → respuesta con citas |

---

## Ingestión e indexación

### Opción A: Script CLI (recomendado)

```powershell
# Desde la carpeta raíz del proyecto (con venv activado)
cd backend
venv\Scripts\activate

python ..\scripts\ingest_case.py `
  --case-name "CASE-0001_Lopez" `
  --folder "C:\Users\TuNombre\casos\Lopez\01_carpeta_investigacion" `
  --stage carpeta_investigacion `
  --autoridad "Ministerio Público Coahuila" `
  --fecha-documento 2025-01-15 `
  --api-url http://localhost:8000
```

### Opción B: API directa (PowerShell)

```powershell
# 1. Crear caso
$case = Invoke-RestMethod -Uri "http://localhost:8000/cases" `
  -Method POST -ContentType "application/json" `
  -Body '{"nombre_corto": "CASE-0001_Lopez", "jurisdiccion": "Coahuila"}'

$caseId = $case.id

# 2. Ingestar carpeta
$ingest = Invoke-RestMethod -Uri "http://localhost:8000/documents/ingest" `
  -Method POST -ContentType "application/json" `
  -Body "{
    `"case_id`": $caseId,
    `"folder_path`": `"C:/Users/TuNombre/casos/Lopez/01_carpeta_investigacion`",
    `"stage`": `"carpeta_investigacion`",
    `"autoridad`": `"Ministerio Público Coahuila`"
  }"

# 3. Indexar cada documento
foreach ($doc in $ingest) {
  Invoke-RestMethod -Uri "http://localhost:8000/documents/$($doc.id)/index" -Method POST
}
```

---

## Búsqueda y consultas con citas

### Búsqueda por keyword + semántica

```powershell
# GET simple
Invoke-RestMethod "http://localhost:8000/search?query=detención+ilegal&case_id=1"

# POST con más opciones
Invoke-RestMethod -Uri "http://localhost:8000/search" `
  -Method POST -ContentType "application/json" `
  -Body '{"query": "cadena de custodia", "case_id": 1, "top_k": 10}'
```

**Respuesta ejemplo:**
```json
{
  "query": "detención ilegal",
  "results": [
    {
      "chunk_id": 42,
      "document_id": 3,
      "texto_chunk": "...el imputado fue detenido a las 23:45 horas sin...",
      "page_from": 7,
      "page_to": 7,
      "citation": "IPH (Ministerio Público Coahuila), 2025-01-15, p. 7",
      "score": 0.89
    }
  ],
  "total": 5
}
```

### Preguntar con respuesta generada (/ask)

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ask" `
  -Method POST -ContentType "application/json" `
  -Body '{"question": "¿Hay irregularidades en la detención?", "case_id": 1}'
```

---

## Ejemplos de consultas

### Irregularidades en la detención

```powershell
# Buscar datos de detención
Invoke-RestMethod "http://localhost:8000/search?query=hora+detención+puesta+a+disposición&case_id=1"

# Preguntar por irregularidades
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method POST `
  -ContentType "application/json" `
  -Body '{"question": "¿Cuánto tiempo transcurrió entre la detención y la puesta a disposición? ¿Existe constancia de lectura de derechos?", "case_id": 1}'
```

### Amparo indirecto

```powershell
# Identificar actos reclamados
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method POST `
  -ContentType "application/json" `
  -Body '{"question": "¿Cuáles son los posibles actos reclamados para amparo indirecto? Identifica la autoridad responsable y la fecha de notificación.", "case_id": 1}'

# Plazos de amparo
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method POST `
  -ContentType "application/json" `
  -Body '{"question": "¿Cuál es la fecha de notificación de la vinculación a proceso y cuál sería el plazo para presentar amparo indirecto?", "case_id": 1}'
```

### Cadena de custodia

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method POST `
  -ContentType "application/json" `
  -Body '{"question": "¿Existen irregularidades en la cadena de custodia de las evidencias? Cita los documentos relevantes.", "case_id": 1}'
```

### Análisis de cautelares

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/ask" -Method POST `
  -ContentType "application/json" `
  -Body '{"question": "¿Existe fundamentación y motivación suficiente para la prisión preventiva impuesta? ¿Se analizaron medidas cautelares alternativas?", "case_id": 1}'
```

---

## Migraciones de base de datos

```powershell
cd backend
venv\Scripts\activate

# Ver estado de migraciones
alembic current

# Aplicar todas las migraciones pendientes
alembic upgrade head

# Revertir la última migración
alembic downgrade -1

# Generar nueva migración automática (después de cambiar models.py)
alembic revision --autogenerate -m "descripcion del cambio"
```

---

## Referencia del esquema

### `cases` — Asuntos
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | integer PK | |
| `nombre_corto` | varchar(200) | Identificador único del caso |
| `jurisdiccion` | varchar(100) | federal / coahuila |
| `estado_procesal` | varchar(200) | Estado actual del proceso |
| `cliente_alias` | varchar(200) | Alias del cliente |
| `notas` | text | Notas generales |

### `documents` — Documentos
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | integer PK | |
| `case_id` | FK → cases | Nullable (biblioteca general) |
| `titulo` | varchar(500) | Nombre del documento |
| `tipo` | varchar(100) | IPH, audiencia, auto, sentencia, amparo, etc. |
| `stage` | enum | `carpeta_investigacion` / `judicial` / `amparo_indirecto` |
| `autoridad` | varchar(300) | Autoridad emisora |
| `fecha_documento` | date | Fecha del documento (usada en citas) |
| `fecha_notificacion` | date | Fecha de notificación (clave para plazos de amparo) |
| `anexo_num` | varchar(50) | Número de anexo (opcional) |
| `file_path` | varchar(1000) | Ruta local al archivo |
| `sha256` | varchar(64) | Hash SHA-256 (evita duplicados) |
| `es_escaneado` | boolean | Si se usó OCR |
| `total_pages` | integer | Total de páginas |

### `document_pages` — Páginas
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | integer PK | |
| `document_id` | FK → documents | |
| `page_number` | integer | Número de página (empieza en **1**) |
| `texto_extraido` | text | Texto extraído (nativo u OCR) |
| `ocr_confidence` | float | Confianza promedio del OCR (0-100) |
| `is_ocr` | boolean | Si esta página fue procesada con OCR |

### `document_chunks` — Fragmentos para RAG
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | integer PK | |
| `document_id` | FK → documents | |
| `chunk_index` | integer | Índice del chunk en el documento |
| `texto_chunk` | text | Texto del fragmento |
| `page_from` | integer | Página inicio (1-based) |
| `page_to` | integer | Página fin (1-based, inclusive) |
| `doc_titulo` | varchar(500) | Título del documento (desnormalizado para citas) |
| `doc_autoridad` | varchar(300) | Autoridad (desnormalizado) |
| `doc_fecha` | varchar(20) | Fecha ISO o "s/f" |
| `embedding` | vector(1536) | Vector de embeddings (pgvector) |

### `events` — Cronología
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | integer PK | |
| `case_id` | FK → cases | |
| `fecha_hora` | timestamptz | Fecha y hora del evento |
| `tipo_evento` | varchar(200) | Tipo (detención, audiencia, vinculación, etc.) |
| `descripcion` | text | Descripción del evento |
| `fuente_chunk_id` | FK → document_chunks | Chunk fuente del evento |

### `issues` — Irregularidades / Oportunidades
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | integer PK | |
| `case_id` | FK → cases | |
| `tipo` | varchar(200) | Tipo de irregularidad |
| `descripcion` | text | Descripción detallada |
| `severidad` | enum | `alta` / `media` / `baja` |
| `estado` | enum | `pendiente` / `confirmada` / `descartada` |
| `fundamento` | text | Fundamento legal |
| `consecuencia` | text | Consecuencia procesal buscada |

### `drafts` — Escritos / Borradores
| Campo | Tipo | Descripción |
|---|---|---|
| `id` | integer PK | |
| `case_id` | FK → cases | |
| `tipo` | varchar(200) | Tipo de escrito (amparo, incidente, promoción, etc.) |
| `version` | integer | Versión del borrador |
| `fecha` | date | Fecha del escrito |
| `estado` | varchar(100) | Estado (borrador, revisión, final, etc.) |
| `cuerpo_markdown` | text | Contenido en Markdown |

---

## Notas adicionales

- **Sin clave OpenAI:** El endpoint `/ask` funciona en modo "recuperación" (devuelve los chunks más relevantes con citas, sin generar texto con IA).
- **Con clave OpenAI:** Se usa `text-embedding-3-small` para embeddings y `gpt-4o` para generación de respuestas.
- **Embeddings fallback:** Sin clave, se usa un embedding local basado en hashing de n-gramas (dim=1536 con padding). Funcional para keyword matching pero no para búsqueda semántica real.
- **Deduplicación:** Los documentos se identifican por SHA-256. Si intentas ingestar el mismo archivo dos veces, se devuelve el documento existente.
- **Páginas empezando en 1:** Todas las citas usan páginas del PDF empezando en 1, sin offset.

---

## Solución de problemas

### Error de conexión a la base de datos

```powershell
docker compose logs db
docker compose restart db
```

### Tesseract no encontrado

Verifica la ruta en `.env`:
```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### El vector pgvector no está habilitado

```powershell
docker compose exec db psql -U legaluser -d legaldb -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Ver logs del backend

```powershell
docker compose logs backend -f
```
