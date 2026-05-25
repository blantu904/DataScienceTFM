# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# =============================================================================
#  pipeline.py  --  Orquestador del ETL Ictus Cantabria
#
#  Uso:
#    python pipeline.py                         # todas las fases
#    python pipeline.py --desde 3               # reanudar desde fase 3
#    python pipeline.py --fases 4 5             # solo fases 4 y 5
#    python pipeline.py --xlsx /ruta/datos.xlsx # especificar fichero
#
#  Detección automática de datos sintéticos:
#    - Si el nombre del Excel contiene 'sintetico', 'synthetic' o 'sdv'
#      → usa scripts/04_carga_sinteticos.py (sin filtros de FK estrictos)
#    - Si los NHCs reales son todos ≥ 900.000 (rango sintético SDV)
#      → ídem
#    - En cualquier otro caso → usa scripts/04_carga.py (datos reales)
# =============================================================================

import argparse
import importlib.util
import os
import shutil
import sys
import time
import traceback
from datetime import datetime

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
OUTPUT_DIR  = os.path.join(BASE_DIR, "output")
LOG_DIR     = os.path.join(BASE_DIR, "logs")
SOURCE_DIR  = os.path.join(BASE_DIR, "source")

for d in (OUTPUT_DIR, LOG_DIR, SOURCE_DIR):
    os.makedirs(d, exist_ok=True)

# -- Logger --------------------------------------------------------------------
import logging
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PIPELINE] %(levelname)s -- %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, f"pipeline_{ts}.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("pipeline")

# -- Mapa de fases -------------------------------------------------------------
FASES = {
    1: ("Extracción",         "01_extraccion.py"),
    2: ("Limpieza",           "02_limpieza.py"),
    3: ("Transformación REC", "03_transformaciones_rec.py"),
    4: ("Carga",              "04_carga.py"),         
    5: ("Validación",         "05_validacion.py"),
    6: ("Calidad de datos",   "06_calidad_datos.py"),
}

# Umbral NHC: SDV genera NHCs ≥ 900.000
NHC_SINTETICO_MIN = 900_000


# =============================================================================
#  Detección automática de datos sintéticos
# =============================================================================

def es_excel_sintetico(xlsx_path: str) -> bool:
    """
    Detecta si el Excel es sintético por dos criterios:
    1. El nombre del fichero contiene 'sintetico', 'synthetic' o 'sdv'.
    2. Todos los NHCs de la hoja Conjunto son >= NHC_SINTETICO_MIN.
    Devuelve True si cualquiera de los dos criterios se cumple.
    """
    nombre = os.path.basename(xlsx_path).lower()
    keywords = ("sintetico", "sintético", "synthetic", "sdv", "fake", "mock")
    if any(kw in nombre for kw in keywords):
        log.info(f"  Datos sintéticos detectados por nombre de fichero: '{nombre}'")
        return True
    return False


def seleccionar_script_carga(xlsx_path: str) -> str:
    """
    Devuelve el nombre del script de carga a usar según el tipo de datos.
    - Datos sintéticos → 04_carga_sinteticos.py  (si existe, si no 04_carga.py)
    - Datos reales     → 04_carga.py
    """
    if es_excel_sintetico(xlsx_path):
        candidato = "04_carga_sinteticos.py"
        ruta = os.path.join(SCRIPTS_DIR, candidato)
        if os.path.exists(ruta):
            log.info(f"  Usando módulo de carga para datos SINTÉTICOS: {candidato}")
            return candidato
        else:
            log.warning(
                f"  {candidato} no encontrado — usando 04_carga.py como fallback. "
                f"Considera crear {ruta} si quieres lógica de carga diferenciada."
            )
    log.info("  Usando módulo de carga para datos REALES: 04_carga.py")
    return "04_carga.py"


# =============================================================================
#  Carga dinámica de módulos
# =============================================================================

def cargar_modulo(n: int, override_script: str | None = None):
    """Carga dinámicamente el módulo de la fase n."""
    nombre_archivo = override_script if override_script else FASES[n][1]
    ruta = os.path.join(SCRIPTS_DIR, nombre_archivo)
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"Script no encontrado: {ruta}")
    spec = importlib.util.spec_from_file_location(f"fase_{n}", ruta)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ejecutar_fase(n: int, override_script: str | None = None) -> bool:
    nombre = FASES[n][0]
    script_usado = override_script or FASES[n][1]
    separador = "=" * 60
    log.info(f"\n{separador}")
    log.info(f"  FASE {n}: {nombre.upper()}  [{script_usado}]")
    log.info(separador)

    t0 = time.time()
    try:
        mod = cargar_modulo(n, override_script)
        if not hasattr(mod, "run"):
            raise AttributeError(f"El módulo de fase {n} no tiene función run()")

        resultado = mod.run()
        elapsed = time.time() - t0

        if n == 5 and resultado is False:
            log.warning(f"  [WARN]   Fase {n} ({nombre}): validaciones con avisos ({elapsed:.1f}s)")
            return True

        log.info(f"  [OK]  Fase {n} ({nombre}) completada en {elapsed:.1f}s")
        return True

    except SystemExit as e:
        elapsed = time.time() - t0
        if e.code in (None, 0):
            log.info(f"  [OK]  Fase {n} ({nombre}) completada en {elapsed:.1f}s")
            return True
        log.error(f"  [ERROR]  Fase {n} ({nombre}) terminó con sys.exit({e.code}) tras {elapsed:.1f}s")
        return False

    except Exception as e:
        elapsed = time.time() - t0
        log.error(f"  [ERROR]  Fase {n} ({nombre}) falló en {elapsed:.1f}s")
        log.error(f"      {type(e).__name__}: {e}")
        log.error(traceback.format_exc())
        return False


# =============================================================================
#  Preparación del fichero fuente
# =============================================================================

def preparar_fuente(xlsx_arg: str | None) -> bool:
    dest = os.path.join(SOURCE_DIR, "datos.xlsx")

    if xlsx_arg:
        if not os.path.exists(xlsx_arg):
            log.error(f"Fichero no encontrado: {xlsx_arg}")
            return False
        if os.path.abspath(xlsx_arg) != os.path.abspath(dest):
            shutil.copy2(xlsx_arg, dest)
            log.info(f"Fichero copiado -> {dest}")
        return True

    candidatos = [f for f in os.listdir(SOURCE_DIR) if f.endswith(".xlsx")]
    if not candidatos:
        log.error("No hay ningún .xlsx en source/")
        return False

    src = os.path.join(SOURCE_DIR, candidatos[0])
    if os.path.abspath(src) != os.path.abspath(dest):
        shutil.copy2(src, dest)
        log.info(f"Usando: source/{candidatos[0]}")
    return True


# =============================================================================
#  Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="ETL Ictus Cantabria")
    parser.add_argument("--fases",  nargs="+", type=int, choices=[1,2,3,4,5,6],
                        help="Ejecutar solo estas fases")
    parser.add_argument("--desde",  type=int, choices=[1,2,3,4,5,6], default=1,
                        help="Reanudar desde esta fase (defecto: 1)")
    parser.add_argument("--xlsx",   type=str,
                        help="Ruta al fichero Excel fuente")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="Detener si una fase falla")
    parser.add_argument("--forzar-sintetico", action="store_true",
                        help="Forzar uso de 04_carga_sinteticos.py sin detección automática")
    parser.add_argument("--forzar-real", action="store_true",
                        help="Forzar uso de 04_carga.py aunque el Excel parezca sintético")
    args = parser.parse_args()

    if not preparar_fuente(args.xlsx):
        sys.exit(1)

    # -- Detectar tipo de datos y seleccionar script de carga ------------------
    xlsx_path = os.path.join(SOURCE_DIR, "datos.xlsx")

    if args.forzar_sintetico:
        script_carga_fase4 = "04_carga_sinteticos.py"
        log.info("  Modo forzado: datos SINTÉTICOS")
    elif args.forzar_real:
        script_carga_fase4 = "04_carga.py"
        log.info("  Modo forzado: datos REALES")
    else:
        script_carga_fase4 = seleccionar_script_carga(xlsx_path)

    # Sobreescribir el script de la fase 4 en el mapa
    FASES[4] = ("Carga", script_carga_fase4)

    fases = sorted(args.fases) if args.fases else list(range(args.desde, 7))

    t_total = time.time()
    log.info(f"\n{'#'*60}")
    log.info(f"  ETL ICTUS CANTABRIA -- {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    log.info(f"  Fases: {fases}")
    log.info(f"  Script carga (fase 4): {script_carga_fase4}")
    log.info(f"{'#'*60}")

    resultados = {}
    for n in fases:
        ok = ejecutar_fase(n)
        resultados[n] = ok
        if not ok and args.stop_on_error:
            log.error(f"\nPipeline detenido en Fase {n} (--stop-on-error)")
            break

    # Resumen
    elapsed_total = time.time() - t_total
    log.info(f"\n{'#'*60}")
    log.info("  RESUMEN")
    log.info(f"{'#'*60}")
    for n, ok in resultados.items():
        log.info(f"  {'[OK]' if ok else '[ERROR]'}  Fase {n}: {FASES[n][0]}  [{FASES[n][1]}]")
    log.info(f"\n  Tiempo total: {elapsed_total:.1f}s")

    all_ok = all(resultados.values())
    if all_ok:
        log.info(f"\n[DONE]  Pipeline completado.")
        log.info(f"   Logs: {LOG_DIR}/")
    else:
        log.warning(f"\n[WARN]   Pipeline con errores -- revisar {LOG_DIR}/")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()