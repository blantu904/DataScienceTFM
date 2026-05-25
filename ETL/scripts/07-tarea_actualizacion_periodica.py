# -*- coding: utf-8 -*-
# =============================================================================
#  07_tarea_actualizacion_periodica.py  —  Actualización incremental del registro de ictus
#  VERSIÓN 1.0
#
#  PROPÓSITO:
#    Detectar pacientes nuevos (NHC no presentes en la BD) en el fichero Excel
#    y cargarlos de forma incremental sin reprocesar los registros existentes.
#    Diseñado para ejecución periódica (semanal/mensual).
#
#  FLUJO:
#    1. AUDITORÍA   → obtiene NHCs ya presentes en SQL Server (tabla PACIENTE)
#    2. EXTRACCIÓN  → lee las hojas del Excel (reutiliza lógica de 01_extraccion)
#    3. DETECCIÓN   → calcula el delta: filas nuevas no presentes en la BD
#    4. LIMPIEZA    → aplica el pipeline de 02_limpieza + 03_transformaciones
#    5. CARGA INCR. → inserta solo el delta respetando el orden de FKs
#    6. REPORTE     → genera resumen en logs y fichero JSON de auditoría
#
#  EJECUCIÓN MANUAL:
#    python 07_tarea_actualizacion_periodica.py
#
#  EJECUCIÓN PROGRAMADA (Windows Task Scheduler):
#    Acción: python C:\ruta\07_tarea_actualizacion_periodica.py
#    Desencadenador: semanal, cada lunes a las 07:00
#
#  EJECUCIÓN PROGRAMADA (Linux cron):
#    0 7 * * 1  /usr/bin/python3 /ruta/07_tarea_actualizacion_periodica.py >> /ruta/logs/cron.log 2>&1
#
#  SALIDA:
#    - logs/07_tarea_actualizacion_periodica.log         → log detallado de la ejecución
#    - logs/auditoria_actualizacion.json → historial de ejecuciones (append)
#    - output/delta_principal.csv        → snapshot del delta procesado
# =============================================================================

import os
import sys
import json
import logging
import hashlib
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

# ── Importar módulos del pipeline existente ───────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    XLSX_PATH, OUTPUT_DIR, LOG_DIR, SQLSERVER_CONFIG, TABLA_ORDER,
    SHEET_PRINCIPAL, SHEET_AS, SHEET_INFLAMACION,
    COL_ALIASES, ANEXAR_PREFIX,
    BOOL_TRUE, BOOL_FALSE,
    GENERO_MAP, LATERALIDAD_MAP, DESTINO_ALTA_MAP,
    PROCEDIMIENTO_MAP, ETIOLOGIA_MAP,
    VALID_RANGES,
)

# Importar funciones del pipeline existente
import importlib

_ext = importlib.import_module("01_extraccion")
_lim = importlib.import_module("02_limpieza")
_tra = importlib.import_module("03_transformaciones_rec")
_car = importlib.import_module("04_carga")


# =============================================================================
#  Configuración de logging
# =============================================================================

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ACTUALIZACION] %(levelname)s -- %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_DIR, "07_tarea_actualizacion_periodica.log"),
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

AUDITORIA_PATH = os.path.join(LOG_DIR, "auditoria_actualizacion.json")


# =============================================================================
#  1. CONEXIÓN Y AUDITORÍA DE LA BASE DE DATOS
# =============================================================================

def get_engine():
    """Crea el engine de SQLAlchemy para SQL Server."""
    cfg = SQLSERVER_CONFIG
    if cfg["trusted"]:
        conn_str = (
            f"DRIVER={{{cfg['driver']}}};"
            f"SERVER={cfg['server']};"
            f"DATABASE={cfg['database']};"
            "Trusted_Connection=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={{{cfg['driver']}}};"
            f"SERVER={cfg['server']};"
            f"DATABASE={cfg['database']};"
            f"UID={cfg['username']};"
            f"PWD={cfg['password']};"
        )
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}")
    return engine


def obtener_nhcs_en_bd(engine) -> set:
    """
    Consulta la tabla PACIENTE y devuelve el conjunto de NHCs ya cargados.
    Esta es la referencia para calcular el delta.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT NHC FROM PACIENTE"))
            nhcs = {int(row[0]) for row in result if row[0] is not None}
        log.info(f"  NHCs en BD (tabla PACIENTE): {len(nhcs)}")
        return nhcs
    except Exception as e:
        log.error(f"  Error al consultar PACIENTE: {e}")
        raise


def verificar_conexion(engine) -> bool:
    """Comprueba que la conexión a SQL Server está activa."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("  Conexión SQL Server: OK")
        return True
    except Exception as e:
        log.error(f"  Conexión SQL Server: FALLO — {e}")
        return False


# =============================================================================
#  2. EXTRACCIÓN DEL EXCEL (reutiliza 01_extraccion)
# =============================================================================

def extraer_excel() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Lee el fichero Excel usando las funciones de 01_extraccion.py.
    Devuelve: (df_principal, df_as, df_inflamacion)
    """
    if not os.path.exists(XLSX_PATH):
        raise FileNotFoundError(f"Fichero Excel no encontrado: {XLSX_PATH}")

    log.info(f"  Leyendo Excel: {XLSX_PATH}")
    xlsx = pd.ExcelFile(XLSX_PATH)

    df_principal   = _ext.extraer_principal(xlsx)
    df_as          = _ext.extraer_as(xlsx)
    df_inflamacion = _ext.extraer_inflamacion(xlsx)

    log.info(f"  Excel leído → principal: {len(df_principal)} filas | "
             f"AS: {len(df_as)} filas | Inflamación: {len(df_inflamacion)} filas")

    return df_principal, df_as, df_inflamacion


# =============================================================================
#  3. DETECCIÓN DEL DELTA (filas nuevas)
# =============================================================================

def calcular_delta(
    df_principal: pd.DataFrame,
    df_inflamacion: pd.DataFrame,
    df_as: pd.DataFrame,
    nhcs_en_bd: set,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Filtra cada DataFrame manteniendo solo los NHCs que NO están en la BD.

    Estrategia de detección:
      - Principal / Inflamación: filtra directamente por NHC.
      - AS: filtra por NHC para incluir la analítica de los nuevos pacientes.

    Devuelve: (delta_principal, delta_inflamacion, delta_as)
    """
    def _nhc_to_int(df: pd.DataFrame) -> pd.Series:
        return pd.to_numeric(df["NHC"], errors="coerce")

    # ── Delta principal ────────────────────────────────────────────────────────
    df_principal["_NHC_int"] = _nhc_to_int(df_principal)
    nuevos_mask = ~df_principal["_NHC_int"].isin(nhcs_en_bd)
    delta_principal = df_principal[nuevos_mask].drop(columns=["_NHC_int"]).copy()

    nhcs_nuevos = set(
        df_principal.loc[nuevos_mask, "_NHC_int"].dropna().astype(int)
    )
    df_principal.drop(columns=["_NHC_int"], inplace=True)

    log.info(f"  Pacientes en Excel: {len(df_principal)} | "
             f"Ya en BD: {len(df_principal) - len(delta_principal)} | "
             f"Nuevos (delta): {len(delta_principal)}")

    if len(delta_principal) == 0:
        log.info("  No se detectaron pacientes nuevos. BD ya actualizada.")
        return (
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
        )

    log.info(f"  NHCs nuevos detectados: {sorted(nhcs_nuevos)}")

    # ── Delta inflamación ──────────────────────────────────────────────────────
    df_inflamacion["_NHC_int"] = _nhc_to_int(df_inflamacion)
    delta_inflamacion = df_inflamacion[
        df_inflamacion["_NHC_int"].isin(nhcs_nuevos)
    ].drop(columns=["_NHC_int"]).copy()
    df_inflamacion.drop(columns=["_NHC_int"], inplace=True)
    log.info(f"  Delta Inflamación: {len(delta_inflamacion)} filas")

    # ── Delta AS ───────────────────────────────────────────────────────────────
    df_as["_NHC_int"] = _nhc_to_int(df_as)
    delta_as = df_as[
        df_as["_NHC_int"].isin(nhcs_nuevos)
    ].drop(columns=["_NHC_int"]).copy()
    df_as.drop(columns=["_NHC_int"], inplace=True)
    log.info(f"  Delta AS (analítica): {len(delta_as)} filas")

    return delta_principal, delta_inflamacion, delta_as


# =============================================================================
#  4. LIMPIEZA Y TRANSFORMACIÓN DEL DELTA
# =============================================================================

def limpiar_delta(
    delta_principal: pd.DataFrame,
    delta_inflamacion: pd.DataFrame,
    delta_as: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Aplica el pipeline de limpieza (02_limpieza) y transformación
    (03_transformaciones_rec) sobre el delta.
    """
    log.info("  Aplicando limpieza al delta...")

    # Guardar delta como CSV temporal para reutilizar los módulos existentes
    _tmp_princ = os.path.join(OUTPUT_DIR, "_tmp_delta_principal.csv")
    _tmp_infl  = os.path.join(OUTPUT_DIR, "_tmp_delta_inflamacion.csv")
    _tmp_as    = os.path.join(OUTPUT_DIR, "_tmp_delta_as.csv")

    delta_principal.to_csv(_tmp_princ, index=False, encoding="utf-8")
    delta_inflamacion.to_csv(_tmp_infl, index=False, encoding="utf-8")
    delta_as.to_csv(_tmp_as, index=False, encoding="utf-8")

    # ── Limpieza (02_limpieza) ─────────────────────────────────────────────────
    clean_principal   = _lim.limpiar_principal(pd.read_csv(_tmp_princ, low_memory=False))
    clean_inflamacion = _lim.limpiar_inflamacion(pd.read_csv(_tmp_infl, low_memory=False))
    clean_as          = _lim.limpiar_as(pd.read_csv(_tmp_as, low_memory=False))

    # ── Transformación (03_transformaciones_rec) ───────────────────────────────
    transformed = _tra.transformar(clean_principal)

    # Limpiar temporales
    for f in [_tmp_princ, _tmp_infl, _tmp_as]:
        try:
            os.remove(f)
        except OSError:
            pass

    log.info(f"  Delta limpio → principal: {len(transformed)} filas | "
             f"inflamación: {len(clean_inflamacion)} | AS: {len(clean_as)}")

    return transformed, clean_inflamacion, clean_as


# =============================================================================
#  5. CARGA INCREMENTAL
# =============================================================================

def cargar_tabla_incremental(
    engine,
    df: pd.DataFrame,
    tabla: str,
    nhcs_nuevos: set,
) -> int:
    """
    Inserta filas en la tabla destino.
    Usa INSERT con manejo de duplicados (ON CONFLICT / try-insert).
    Si un NHC ya existe en una tabla secundaria (analítica) se omite.
    """
    if df is None or len(df) == 0:
        log.info(f"  {tabla:25s}: 0 filas (vacío, omitido)")
        return 0

    # Conversión de tipos: Int64 nullable → int64 estándar
    for col in df.select_dtypes(include=["Int64"]).columns:
        df[col] = df[col].astype("float64")

    # Conversión de datetime para SQL Server
    for col in df.select_dtypes(include=["datetime64"]).columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    max_params = 2000
    chunksize  = max(1, max_params // max(len(df.columns), 1))

    try:
        df.to_sql(
            tabla,
            con=engine,
            if_exists="append",
            index=False,
            method=None,
            chunksize=chunksize,
        )
        log.info(f"  {tabla:25s}: {len(df):>4} filas insertadas ✓")
        return len(df)
    except Exception as e:
        # En caso de conflicto de clave primaria (paciente ya existente en esa
        # tabla), intentamos fila a fila para insertar solo las que no existen.
        log.warning(f"  {tabla}: inserción en bloque falló ({e}). "
                    "Intentando inserción fila a fila...")
        insertadas = 0
        for _, row in df.iterrows():
            try:
                row.to_frame().T.to_sql(
                    tabla, con=engine, if_exists="append", index=False
                )
                insertadas += 1
            except Exception:
                pass  # fila ya existente → omitir
        log.info(f"  {tabla:25s}: {insertadas:>4} filas insertadas (modo fila a fila)")
        return insertadas


def cargar_delta(
    engine,
    transformed: pd.DataFrame,
    clean_inflamacion: pd.DataFrame,
    clean_as: pd.DataFrame,
) -> dict:
    """
    Prepara y carga todas las tablas para el delta.
    Reutiliza los extractores de 04_carga.py para construir cada DataFrame
    tabla a tabla y los inserta en el orden correcto de FKs.
    """
    log.info("  Preparando extractores de tablas...")

    df_pac     = _car.extraer_paciente(transformed)
    df_antec   = _car.extraer_antecedentes(transformed)
    df_medprev = _car.extraer_medicacion_previa(transformed)
    df_tllg    = _car.extraer_tiempos_llegada(transformed)
    df_tint    = _car.extraer_tiempos_intervencion(transformed)
    df_intv    = _car.extraer_intervalos(transformed)
    df_scores  = _car.extraer_scores_inicio(transformed)
    df_proc    = _car.extraer_procedimiento(transformed)
    df_trat    = _car.extraer_tratamiento_farm(transformed)
    df_mat     = _car.extraer_materiales(transformed)
    df_infl2   = _car.extraer_inflamacion(clean_inflamacion)
    df_lipid   = _car.extraer_analitica_lipidos(clean_as)
    df_metab   = _car.extraer_analitica_metabolica(clean_as)
    df_hep     = _car.extraer_analitica_hepatica(clean_as)
    df_prot    = _car.extraer_analitica_proteinas(clean_as)
    df_orina   = _car.extraer_analitica_orina(clean_as)
    df_pet     = _car.extraer_analitica_peticion(clean_as)
    df_alta    = _car.extraer_alta_hospitalaria(transformed, df_proc)
    df_recam   = _car.extraer_resultado_recam(transformed, df_proc)
    df_seg     = _car.extraer_seguimiento(transformed, df_proc)

    # NHCs válidos del delta (solo los del delta, no los históricos)
    nhcs_validos = set(pd.to_numeric(df_pac["NHC"], errors="coerce").dropna())
    df_infl2 = _car.filtrar_nhcs_huerfanos(df_infl2, nhcs_validos, "INFLAMACION")
    df_lipid = _car.filtrar_nhcs_huerfanos(df_lipid, nhcs_validos, "ANALITICA_LIPIDOS")
    df_metab = _car.filtrar_nhcs_huerfanos(df_metab, nhcs_validos, "ANALITICA_METABOLICA")
    df_hep   = _car.filtrar_nhcs_huerfanos(df_hep,   nhcs_validos, "ANALITICA_HEPATICA")
    df_prot  = _car.filtrar_nhcs_huerfanos(df_prot,  nhcs_validos, "ANALITICA_PROTEINAS")
    df_orina = _car.filtrar_nhcs_huerfanos(df_orina, nhcs_validos, "ANALITICA_ORINA")
    df_pet   = _car.filtrar_nhcs_huerfanos(df_pet,   nhcs_validos, "ANALITICA_PETICION")

    cargas = [
        ("PACIENTE",              df_pac),
        ("ANTECEDENTES",          df_antec),
        ("MEDICACION_PREVIA",     df_medprev),
        ("TIEMPOS_LLEGADA",       df_tllg),
        ("TIEMPOS_INTERVENCION",  df_tint),
        ("INTERVALOS_CALCULADOS", df_intv),
        ("SCORES_INICIO",         df_scores),
        ("PROCEDIMIENTO",         df_proc),
        ("TRATAMIENTO_FARM",      df_trat),
        ("MATERIALES_DISP",       df_mat),
        ("INFLAMACION",           df_infl2),
        ("ANALITICA_LIPIDOS",     df_lipid),
        ("ANALITICA_METABOLICA",  df_metab),
        ("ANALITICA_HEPATICA",    df_hep),
        ("ANALITICA_PROTEINAS",   df_prot),
        ("ANALITICA_ORINA",       df_orina),
        ("ANALITICA_PETICION",    df_pet),
        ("ALTA_HOSPITALARIA",     df_alta),
        ("RESULTADO_RECAM",       df_recam),
        ("SEGUIMIENTO",           df_seg),
    ]

    resumen = {}
    total = 0
    log.info("  Cargando delta en SQL Server (orden FK):")
    for tabla, df in cargas:
        n = cargar_tabla_incremental(engine, df, tabla, nhcs_validos)
        resumen[tabla] = n
        total += n

    log.info(f"  Total filas insertadas en esta ejecución: {total}")
    return resumen


# =============================================================================
#  6. AUDITORÍA Y REPORTE
# =============================================================================

def calcular_hash_excel(path: str) -> str:
    """Calcula el hash MD5 del fichero Excel para detectar cambios."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def guardar_auditoria(
    inicio: datetime,
    fin: datetime,
    nhcs_nuevos: list,
    resumen_carga: dict,
    hash_excel: str,
    estado: str,
    error: str = None,
):
    """
    Añade una entrada al fichero JSON de auditoría con los detalles
    de la ejecución. El fichero crece en cada ejecución (append).
    """
    entrada = {
        "timestamp_inicio":   inicio.isoformat(),
        "timestamp_fin":      fin.isoformat(),
        "duracion_segundos":  round((fin - inicio).total_seconds(), 1),
        "estado":             estado,
        "hash_excel":         hash_excel,
        "nhcs_nuevos":        sorted(nhcs_nuevos),
        "total_nhcs_nuevos":  len(nhcs_nuevos),
        "filas_por_tabla":    resumen_carga,
        "total_filas":        sum(resumen_carga.values()) if resumen_carga else 0,
        "error":              error,
    }

    historial = []
    if os.path.exists(AUDITORIA_PATH):
        try:
            with open(AUDITORIA_PATH, "r", encoding="utf-8") as f:
                historial = json.load(f)
        except json.JSONDecodeError:
            historial = []

    historial.append(entrada)

    with open(AUDITORIA_PATH, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)

    log.info(f"  Auditoría guardada en: {AUDITORIA_PATH}")


def mostrar_resumen_consola(
    nhcs_nuevos: list,
    resumen_carga: dict,
    duracion: float,
):
    """Imprime un resumen legible al final de la ejecución."""
    linea = "=" * 60
    log.info(linea)
    log.info("  RESUMEN DE ACTUALIZACIÓN")
    log.info(linea)
    log.info(f"  Pacientes nuevos incorporados : {len(nhcs_nuevos)}")
    log.info(f"  NHCs                          : {sorted(nhcs_nuevos) if nhcs_nuevos else '—'}")
    log.info(f"  Duración total                : {duracion:.1f} s")
    log.info("  Filas insertadas por tabla:")
    for tabla, n in resumen_carga.items():
        if n > 0:
            log.info(f"    {tabla:30s}: {n:>4}")
    log.info(f"  Total filas                   : {sum(resumen_carga.values())}")
    log.info(linea)


# =============================================================================
#  PIPELINE PRINCIPAL
# =============================================================================

def run():
    inicio   = datetime.now()
    estado   = "OK"
    error_msg = None
    nhcs_nuevos: list = []
    resumen_carga: dict = {}
    hash_excel = ""

    log.info("=" * 60)
    log.info(f"FASE 5 -- ACTUALIZACIÓN INCREMENTAL  ({inicio.strftime('%Y-%m-%d %H:%M')})")
    log.info("=" * 60)

    try:
        # ── Hash del Excel para detectar si ha cambiado desde la última ejecución
        hash_excel = calcular_hash_excel(XLSX_PATH)
        log.info(f"  Hash Excel (MD5): {hash_excel}")

        # Comparar con la última ejecución registrada
        if os.path.exists(AUDITORIA_PATH):
            with open(AUDITORIA_PATH, "r", encoding="utf-8") as f:
                historial = json.load(f)
            if historial:
                ultimo_hash = historial[-1].get("hash_excel", "")
                if ultimo_hash == hash_excel and historial[-1].get("estado") == "OK":
                    log.info("  El Excel no ha cambiado desde la última ejecución exitosa.")
                    log.info("  No hay nada que actualizar. Saliendo.")
                    return

        # ── 1. Conexión ───────────────────────────────────────────────────────
        engine = get_engine()
        if not verificar_conexion(engine):
            raise ConnectionError("No se puede conectar a SQL Server.")

        # ── 2. NHCs en BD ─────────────────────────────────────────────────────
        nhcs_en_bd = obtener_nhcs_en_bd(engine)

        # ── 3. Extracción del Excel ───────────────────────────────────────────
        log.info("  Extrayendo datos del Excel...")
        df_principal, df_as, df_inflamacion = extraer_excel()

        # ── 4. Delta ──────────────────────────────────────────────────────────
        log.info("  Calculando delta (pacientes nuevos)...")
        delta_principal, delta_inflamacion, delta_as = calcular_delta(
            df_principal, df_inflamacion, df_as, nhcs_en_bd
        )

        if len(delta_principal) == 0:
            log.info("  BD ya actualizada. No se requiere ninguna carga.")
            fin = datetime.now()
            guardar_auditoria(
                inicio, fin, [], {},
                hash_excel, "SIN_CAMBIOS"
            )
            return

        nhcs_nuevos = sorted(
            pd.to_numeric(delta_principal["NHC"], errors="coerce")
            .dropna().astype(int).tolist()
        )

        # Guardar snapshot del delta para trazabilidad
        delta_snap = os.path.join(OUTPUT_DIR, "delta_principal.csv")
        delta_principal.to_csv(delta_snap, index=False, encoding="utf-8")
        log.info(f"  Snapshot del delta guardado: {delta_snap}")

        # ── 5. Limpieza + Transformación ──────────────────────────────────────
        log.info("  Limpiando y transformando el delta...")
        transformed, clean_inflamacion, clean_as = limpiar_delta(
            delta_principal, delta_inflamacion, delta_as
        )

        # ── 6. Carga incremental ──────────────────────────────────────────────
        log.info("  Cargando delta en SQL Server...")
        resumen_carga = cargar_delta(
            engine, transformed, clean_inflamacion, clean_as
        )

    except Exception as e:
        estado     = "ERROR"
        error_msg  = str(e)
        log.error(f"  ERROR CRÍTICO: {e}", exc_info=True)

    finally:
        fin = datetime.now()
        duracion = (fin - inicio).total_seconds()

        guardar_auditoria(
            inicio, fin, nhcs_nuevos, resumen_carga,
            hash_excel, estado, error_msg
        )

        if estado == "OK":
            mostrar_resumen_consola(nhcs_nuevos, resumen_carga, duracion)
            log.info("[OK]  Fase 7 completada.")
        else:
            log.error(f"[FALLO]  Fase 7 terminó con errores. Revisar logs.")


# =============================================================================
#  Entrada
# =============================================================================

if __name__ == "__main__":
    run()