# -*- coding: utf-8 -*-
# =============================================================================
#  02_limpieza.py  --  FASE 2: Limpieza y normalización
#
#
#  Entrada:  raw_principal.csv, raw_as.csv, raw_inflamacion.csv
#  Salida:   clean_principal.csv, clean_as.csv, clean_inflamacion.csv
#
#  Operaciones:
#   - Parseo de fechas (serial Excel, DD/MM/YYYY, datetime)
#   - Conversión de tiempos (fracción de día → minutos enteros)
#   - Normalización de categóricas (Genero, Lateralidad, Procedimiento...)
#   - Conversión numérica (protegiendo campos de texto)
#   - Normalización de valores <X, X,Y (comas decimales)
# =============================================================================

import os, sys, logging, re
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    OUTPUT_DIR, LOG_DIR,
    BOOL_TRUE, BOOL_FALSE,
    GENERO_MAP, LATERALIDAD_MAP, DESTINO_ALTA_MAP,
    PROCEDIMIENTO_MAP, ETIOLOGIA_MAP,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LIMPIEZA] %(levelname)s -- %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "02_limpieza.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Columnas que son texto puro → NUNCA convertir a numérico ─────────────────
TEXT_COLS = {
    # Metadatos analítica
    "Doctor", "Centro", "Servicio", "Centro_procesamiento",
    "Diagnostico_solicitud", "Ubicacion", "Observaciones_peticion",
    "Info_adicional", "Patologia_descripcion", "Numero_solicitud",
    "Genero", "Lateralidad", "Procedimiento",
    "Etiologia", "Etiología",                     
    "Complicaciones", "ComplicacionesPost",
    "Complicaciones Post",                         
    "DestinoAlta",
    "AnticoagPrev", "AnticoaIntrahosp", "NuevoAnticoaAlta",
    "Stent", "Stentriever", "TipodeCierre", "TICI",
    "LugarCodigo", "LugarCódigo",                 
    "NiveldeObstrucción", "NiveldeObstruccion",
    "Horario",
    "Hemoragia", "Hemorragia",                      
    "DesviaciónLM", "InfartoEstablecido", "Edema",
    "FA_Novo", "FANovo",                            
    "Causadelamuerte",
    "FA conocida",
    "Inmunofijacion", "AlbuminaTira", "CreatininaTira",
    "ProteinaCReactiva", "PCR_Ultrasensible",
    "FechadeAlta", "FECHA", "Fecha_solicitud",
    "Recanalizacion", "Recanalización",
    "RecanalizacionCarotida", "RecanalizaciónCarótida",
     "Horapuerta",
    "HoraTC",
    "LlamadaNeuro",
    "ultimaimagenTC",
    "HoraentradaSala",
    "HoraAguja",
    "Primerpase",
    "Perfusiónfibri",
    "HoraPunción",
    "HoraTriaje",
    "ValoradoNeuro",
}

# ── Columnas de tiempo en fracción de día → convertir a minutos ───────────────
TIEMPO_FRACDIA_COLS = [
    "TiempoSintomasPuerta",
    "TiempoPuertaValoración",
    "TiempollamadaValoración",
    "TiempoValoraciónTC",
    "TiempoPuertaTC",
    "TiempoTC",
    "TiempoPuertaSala",
    "TiempoTCSala",
    "TiempoPuertaPunción",
    "TiempoSalaPunción",
    "Tiempopuertarecanalización",
    "Tiempopunción1ºpase",
    "Tiemposíntomasrecanalización",
]


HORA_COLS = [
    "CódigoIctus",      
    "ValoradoNeuro",    
    "HoraTC",           
    "ultimaimagenTC",    
    "HoraentradaSala",  
    "HoraPunción",       
    "HoraAguja",
    "Primerpase",       
    "Recanalización",
    "Horapuerta",        
    "LlamadaNeuro",
    "HoraTriaje",
    "Iniciosíntomas",   
]


# =============================================================================
#  Utilidades
# =============================================================================

# =============================================================================
#  Validación de fechas
#  Rango clínico aceptable para esta serie: 2015-01-01 … hoy.
#  - Cualquier fecha fuera de rango se trata como NaT y se registra en el log
#    de errores, que se exporta a output/errores_fechas.csv al final de la fase.
#  - El límite superior se calcula en tiempo de ejecución para que no quede
#    obsoleto al reutilizar el script.
# =============================================================================
_FECHA_MIN = pd.Timestamp("2015-01-01")
_FECHA_MAX = pd.Timestamp.now().normalize()   

# Acumulador de errores: lista de dicts {columna, valor_raw, fecha_parseada, motivo}
_errores_fechas: list[dict] = []


def _registrar_error_fecha(columna: str, valor_raw, fecha_parseada, motivo: str) -> None:
    """Añade una entrada al registro de fechas inválidas."""
    _errores_fechas.append({
        "columna":       columna,
        "valor_raw":     repr(valor_raw),
        "fecha_parseada": str(fecha_parseada.date()) if pd.notna(fecha_parseada) else "",
        "motivo":        motivo,
    })


def parsear_fecha(v) -> pd.Timestamp:
    """Convierte serial Excel (int, float o string numérico), DD/MM/YYYY,
    M/D/YYYY, datetime o string a Timestamp.
    Devuelve NaT si el valor es nulo, no parseable o está fuera del rango
    clínico aceptable (_FECHA_MIN … _FECHA_MAX).
    Los errores se acumulan en _errores_fechas para exportar al final."""
    if pd.isna(v):
        return pd.NaT
    if isinstance(v, pd.Timestamp):
        ts = v
    elif isinstance(v, (int, float)):
        try:
            ts = pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(v))
        except Exception:
            return pd.NaT
    else:
        s = str(v).strip()
        if not s or s in ("-", "--", "nd", "n/a", "na"):
            return pd.NaT
        ts = pd.NaT
        # Serial Excel como string (e.g. "45663")
        try:
            n = int(float(s))
            if 40000 < n < 60000:
                ts = pd.Timestamp("1899-12-30") + pd.Timedelta(days=n)
        except Exception:
            pass
        # Formatos fecha string: M/D/YYYY (Excel US) primero, luego resto
        if pd.isna(ts):
            for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    ts = pd.Timestamp(pd.to_datetime(s, format=fmt))
                    break
                except Exception:
                    pass
        if pd.isna(ts):
            try:
                ts = pd.Timestamp(pd.to_datetime(s, dayfirst=True))
            except Exception:
                pass
        if pd.isna(ts):
            # Valor que no pudo parsearse con ningún formato
            _registrar_error_fecha("?", v, pd.NaT, f"formato no reconocido: {repr(s)}")
            return pd.NaT

    # ── Validación de rango ───────────────────────────────────────────────────
    if ts < _FECHA_MIN:
        _registrar_error_fecha("?", v, ts,
            f"fecha anterior al mínimo permitido ({_FECHA_MIN.date()})")
        return pd.NaT
    if ts > _FECHA_MAX:
        _registrar_error_fecha("?", v, ts,
            f"fecha posterior a hoy ({_FECHA_MAX.date()})")
        return pd.NaT

    return ts


def _parsear_fecha_col(serie: pd.Series, nombre_col: str) -> pd.Series:
    """Aplica parsear_fecha a una columna completa, inyectando el nombre de
    columna en los registros de error para facilitar la depuración."""
    def _f(v):
        antes = len(_errores_fechas)
        ts = parsear_fecha(v)
        # Si se añadió un error, actualizar su columna (parsear_fecha no la conoce)
        if len(_errores_fechas) > antes:
            _errores_fechas[-1]["columna"] = nombre_col
        return ts
    return serie.apply(_f)


def exportar_errores_fechas(output_dir: str) -> None:
    """Exporta el registro de errores a output/errores_fechas.csv.
    Si no hay errores, no crea el fichero."""
    if not _errores_fechas:
        log.info("  Validación fechas: sin errores detectados.")
        return
    ruta = os.path.join(output_dir, "errores_fechas.csv")
    df_err = pd.DataFrame(_errores_fechas)
    df_err.to_csv(ruta, index=False, encoding="utf-8")
    log.warning(f"  Validación fechas: {len(_errores_fechas)} valor(es) inválido(s) → {ruta}")
    for _, row in df_err.iterrows():
        log.warning(f"    [{row['columna']}] raw={row['valor_raw']:30s} "
                    f"parsed={row['fecha_parseada']:12s} motivo={row['motivo']}")


def fracdia_a_minutos(v) -> float | None:
    """Convierte fracción de día a minutos enteros. Valores negativos → NaN."""
    if pd.isna(v):
        return pd.NA
    try:
        mins = float(v) * 24 * 60
        if mins < 0:
            return pd.NA
        return round(mins)
    except Exception:
        return pd.NA


def hora_a_str(v) -> str | None:
    """Normaliza hora (datetime.time, HH:MM, fracción) a string HH:MM."""
    if pd.isna(v) or str(v).strip() in ("", "nan", "NaT"):
        return pd.NA
    import datetime
    if isinstance(v, datetime.time):
        return v.strftime("%H:%M")
    if isinstance(v, pd.Timestamp):
        return v.strftime("%H:%M")
    s = str(v).strip()
    # formato HH:MM:SS o HH:MM
    m = re.match(r"^(\d{1,2}):(\d{2})", s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    # fracción de día
    try:
        f = float(s.replace(",", "."))
        if 0 <= f < 1:
            total_min = int(round(f * 24 * 60))
            h, mn = divmod(total_min, 60)
            return f"{h % 24:02d}:{mn:02d}"
    except Exception:
        pass
    return s


def limpiar_numerico(v):
    """Limpia strings con coma decimal, prefijos <, > y espacios."""
    if pd.isna(v):
        return pd.NA
    s = str(v).strip()
    s = re.sub(r"[<>≤≥]", "", s)  
    s = s.replace(",", ".")
    s = re.sub(r"\s+", "", s)
    try:
        return float(s)
    except ValueError:
        return pd.NA


def normalizar_map(serie: pd.Series, mapa: dict) -> pd.Series:
    """Aplica un diccionario de normalización (case-insensitive)."""
    def _f(v):
        if pd.isna(v):
            return pd.NA
        k = str(v).strip().lower()
        return mapa.get(k, str(v).strip())
    return serie.map(_f)


# =============================================================================
#  Limpieza principal
# =============================================================================

def limpiar_principal(df: pd.DataFrame) -> pd.DataFrame:
    log.info("  --- Limpiando principal ---")

    # 1. FECHA principal
    if "FECHA" in df.columns:
        df["FECHA"] = _parsear_fecha_col(df["FECHA"], "FECHA")
        df["FECHA"] = df["FECHA"].apply(
            lambda v: v.strftime("%Y-%m-%d") if pd.notna(v) and hasattr(v, "strftime") else pd.NA
        )
        log.info(f"  FECHA no nulos: {df['FECHA'].notna().sum()}")

    # 2. Tiempos fracción de día → minutos
    for c in TIEMPO_FRACDIA_COLS:
        if c in df.columns:
            df[c] = df[c].apply(fracdia_a_minutos)
    log.info(f"  Tiempos convertidos a minutos: {[c for c in TIEMPO_FRACDIA_COLS if c in df.columns]}")

    # 3. Horas → string HH:MM 
    for c in HORA_COLS:
        if c in df.columns:
            df[c] = df[c].apply(hora_a_str)

    # 4. FechadeAlta (puede ser serial, string DD/MM/YYYY o duplicado)
    if "FechadeAlta" in df.columns:
        df["FechadeAlta"] = _parsear_fecha_col(df["FechadeAlta"], "FechadeAlta")
        df["FechadeAlta"] = df["FechadeAlta"].apply(
            lambda v: v.strftime("%Y-%m-%d") if pd.notna(v) and hasattr(v, "strftime") else pd.NA
        )
        log.info(f"  FechadeAlta no nulos: {df['FechadeAlta'].notna().sum()}")

    # 5. FInicio / FechaFin (seriales Excel en 2024-25, datetime en 2024)
    for fc in ["FInicio", "FechaFin"]:
        if fc in df.columns:
            df[fc] = _parsear_fecha_col(df[fc], fc)
            df[fc] = df[fc].apply(
                lambda v: v.strftime("%Y-%m-%d") if pd.notna(v) and hasattr(v, "strftime") else pd.NA
            )

    # 6. Categóricas
    if "Genero"      in df.columns: df["Genero"]      = normalizar_map(df["Genero"], GENERO_MAP)
    if "Lateralidad" in df.columns: df["Lateralidad"] = normalizar_map(df["Lateralidad"], LATERALIDAD_MAP)
    if "DestinoAlta" in df.columns: df["DestinoAlta"] = normalizar_map(df["DestinoAlta"], DESTINO_ALTA_MAP)
    if "Procedimiento" in df.columns:
        df["Procedimiento"] = normalizar_map(df["Procedimiento"],
            {k.lower(): v for k, v in PROCEDIMIENTO_MAP.items()})
    if "Etiologia" in df.columns:
        df["Etiologia"] = normalizar_map(df["Etiologia"],
            {k.lower(): v for k, v in ETIOLOGIA_MAP.items()})

    # 7. NHC_real como entero
    if "NHC_real" in df.columns:
        df["NHC_real"] = pd.to_numeric(df["NHC_real"], errors="coerce").astype("Int64")

    # 8. Conversión numérica de columnas analíticas (quitar comas decimales / prefijos <)
    analitica_texto_especial = {
        "ProteinaCReactiva", "PCR_Ultrasensible", "FiltradoGlomerularCKDEPI",
        "Prealbumina", "BilirrubinaDirect", "TSH_suero", "BilirrubinaTotal",
    }
    for col in df.columns:
        if col in TEXT_COLS:
            continue
        if col in analitica_texto_especial:
            df[col] = df[col].apply(limpiar_numerico)
            continue
        # Intentar conversión numérica estándar
        if df[col].dtype == object:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ".").str.strip(),
                errors="coerce"
            )

    log.info(f"  Shape final principal: {df.shape}")
    return df


# =============================================================================
#  Limpieza AS
# =============================================================================

def limpiar_as(df: pd.DataFrame) -> pd.DataFrame:


    log.info("  --- Limpiando AS ---")

    # ── NUEVO: renombrar columnas AS a nombres canónicos ──────────────────
    ALIAS_AS = {
        "TSH suero":                                    "TSH_suero",
        "T4 libre suero":                               "T4libre_suero",
        "Filtrado Glomerular estimado CKD-EPI suero":   "FiltradoGlomerularCKDEPI",
        "Proteina C Reactiva (mg/dl)":                  "ProteinaCReactiva",
        "PCR Ultrasensible suero":                      "PCR_Ultrasensible",
        "Bilirrubina Directa suero ":                    "BilirrubinaDirect",
        "Bilirrubina Total suero ":                      "BilirrubinaTotal",
        "Prealbumina suero":                            "Prealbumina",
        "Inmunofijacion suero":                         "Inmunofijacion",
        "Albumina en tira":                             "AlbuminaTira",
        "Creatinina en tira":                           "CreatininaTira",
    }
    df = df.rename(columns={k: v for k, v in ALIAS_AS.items() if k in df.columns})
    # ─────────────────────────────────────────────────────────────────────

    # Fecha solicitud (serial Excel)
    if "Fecha_solicitud" in df.columns:
        df["Fecha_solicitud"] = _parsear_fecha_col(df["Fecha_solicitud"], "Fecha_solicitud")
        df["Fecha_solicitud"] = df["Fecha_solicitud"].apply(
            lambda v: v.strftime("%Y-%m-%d") if pd.notna(v) and hasattr(v, "strftime") else pd.NA
        )
        # Usar como Fecha (PK de ANALITICA)
        if "Fecha" not in df.columns:
            df["Fecha"] = df["Fecha_solicitud"]
        log.info(f"  Fecha_solicitud no nulos: {df['Fecha_solicitud'].notna().sum()}")

    # Campos texto → no convertir
    AS_TEXT = TEXT_COLS | {"Fecha_solicitud", "Fecha"}

    # Analítica con comas/prefijos
    analitica_especial = {
        "ProteinaCReactiva", "PCR_Ultrasensible", "FiltradoGlomerularCKDEPI",
        "Prealbumina", "BilirrubinaDirect", "TSH_suero",
        "BilirrubinaTotal", "Inmunofijacion", "AlbuminaTira", "CreatininaTira",
    }
    for col in df.columns:
        if col in AS_TEXT:
            continue
        if col in analitica_especial:
            df[col] = df[col].apply(limpiar_numerico)
            continue
        if df[col].dtype == object:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ".").str.strip(),
                errors="coerce"
            )

    # Log metadatos
    meta = ["Doctor", "Centro", "Servicio", "Centro_procesamiento",
            "Diagnostico_solicitud", "Info_adicional", "Patologia_descripcion"]
    presente = {c: df[c].notna().sum() for c in meta if c in df.columns}
    log.info(f"  Metadatos AS con datos: {presente}")
    return df


# =============================================================================
#  Limpieza Inflamación
# =============================================================================

def limpiar_inflamacion(df: pd.DataFrame) -> pd.DataFrame:
    log.info("  --- Limpiando Inflamación ---")
    for col in df.columns:
        if col == "NHC":
            continue
        if df[col].dtype == object:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ".").str.strip(),
                errors="coerce"
            )
    log.info(f"  Shape Inflamación: {df.shape}")
    return df


# =============================================================================
#  run
# =============================================================================

def run():
    log.info("=" * 60)
    log.info("FASE 2 -- LIMPIEZA")
    log.info("=" * 60)

    in_principal   = os.path.join(OUTPUT_DIR, "raw_principal.csv")
    in_as          = os.path.join(OUTPUT_DIR, "raw_as.csv")
    in_inflamacion = os.path.join(OUTPUT_DIR, "raw_inflamacion.csv")

    df_p = pd.read_csv(in_principal,   encoding="utf-8", low_memory=False)
    df_a = pd.read_csv(in_as,          encoding="utf-8", low_memory=False)
    df_i = pd.read_csv(in_inflamacion, encoding="utf-8", low_memory=False)

    log.info(f"  Principal leído: {df_p.shape}")
    log.info(f"  AS leído:        {df_a.shape}")
    log.info(f"  Inflamación leído: {df_i.shape}")

    df_p = limpiar_principal(df_p)
    df_a = limpiar_as(df_a)
    df_i = limpiar_inflamacion(df_i)

    out_p = os.path.join(OUTPUT_DIR, "clean_principal.csv")
    out_a = os.path.join(OUTPUT_DIR, "clean_as.csv")
    out_i = os.path.join(OUTPUT_DIR, "clean_inflamacion.csv")

    df_p.to_csv(out_p, index=False, encoding="utf-8")
    df_a.to_csv(out_a, index=False, encoding="utf-8")
    df_i.to_csv(out_i, index=False, encoding="utf-8")

    log.info(f"  Exportado: {out_p}  ({len(df_p)} filas)")
    log.info(f"  Exportado: {out_a}  ({len(df_a)} filas)")
    log.info(f"  Exportado: {out_i}  ({len(df_i)} filas)")

    # ── Exportar registro de fechas inválidas ─────────────────────────────────
    exportar_errores_fechas(OUTPUT_DIR)

    return {"principal": out_p, "as": out_a, "inflamacion": out_i}


if __name__ == "__main__":
    run()