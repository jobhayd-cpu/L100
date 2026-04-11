# Leyes de Referencia

Esta carpeta almacena los PDFs de leyes federales y locales usados como base de conocimiento del sistema.
Los archivos son descargados automáticamente por el script `scripts/seed_laws.py` desde fuentes oficiales.

## Leyes federales incluidas

| Archivo | Ley | Fuente |
|---|---|---|
| `CPEUM.pdf` | Constitución Política de los Estados Unidos Mexicanos | diputados.gob.mx |
| `CNPP.pdf` | Código Nacional de Procedimientos Penales | diputados.gob.mx |
| `CPF.pdf` | Código Penal Federal | diputados.gob.mx |
| `LAmp.pdf` | Ley de Amparo | diputados.gob.mx |
| `LFDO.pdf` | Ley Federal contra la Delincuencia Organizada | diputados.gob.mx |
| `LOPJF.pdf` | Ley Orgánica del Poder Judicial de la Federación | diputados.gob.mx |
| `LNE.pdf` | Ley Nacional de Ejecución Penal | diputados.gob.mx |
| `LNMASCMP.pdf` | Ley Nacional de Mecanismos Alternativos de Solución de Controversias en Materia Penal | diputados.gob.mx |
| `LNSIJPA.pdf` | Ley Nacional del Sistema Integral de Justicia Penal para Adolescentes | diputados.gob.mx |

## Leyes de Coahuila incluidas

| Archivo | Ley | Fuente |
|---|---|---|
| `CPEC.txt` | Código Penal del Estado de Coahuila de Zaragoza | congresocoahuila.gob.mx |
| `CPPEC.txt` | Código de Procedimientos Penales del Estado de Coahuila (anterior al CNPP) | congresocoahuila.gob.mx |

## Cómo cargar / actualizar

```bash
# Desde la raíz del proyecto, con el backend corriendo:
python scripts/seed_laws.py

# Forzar re-descarga aunque ya existan los archivos:
python scripts/seed_laws.py --force-download

# Sólo descargar, sin ingestar (útil para revisar antes):
python scripts/seed_laws.py --download-only
```

> Los documentos se cargan en un caso especial llamado **LEYES-REFERENCIA** sin `stage`,
> para que las búsquedas semánticas puedan incluirlas al buscar con `case_id=None`.
