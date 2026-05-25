# -*- coding: utf-8 -*-
# =============================================================================
#  01_extraccion.py  --  FASE 1: Extracción del fichero Excel
#
#  Fuente principal: hoja "Conjunto" (198 cols, 391 filas)
#    - Contiene datos clínicos + analítica Anexar1.* fusionados
#    - PseudoID = clave de fila; 
#
#  Fuentes secundarias:
#    - "AS"          → analítica completa 
#    - "Inflamación" → marcadores inflamatorios 
#
#  Salida: raw_principal.csv, raw_as.csv, raw_inflamacion.csv
# =============================================================================

import os, sys, logging
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    XLSX_PATH, OUTPUT_DIR, LOG_DIR,
    SHEET_PRINCIPAL, SHEET_AS, SHEET_INFLAMACION,
    COL_ALIASES, ANEXAR_PREFIX,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [EXTRACCIÓN] %(levelname)s -- %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "01_extraccion.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
def quitar_prefijo_anexar(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina el prefijo 'Anexar1.' de los nombres de columna."""
    return df.rename(columns={
        c: c[len(ANEXAR_PREFIX):]
        for c in df.columns if c.startswith(ANEXAR_PREFIX)
    })


def aplicar_aliases(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas según COL_ALIASES (solo las que existan)."""
    return df.rename(columns={k: v for k, v in COL_ALIASES.items() if k in df.columns})


def deduplicar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Combina columnas duplicadas usando backfill horizontal.

    IMPORTANTE: todas las fusiones se realizan ANTES de eliminar duplicados.
    Si se hace drop en cada iteración del bucle, la primera llamada a
    ~df.columns.duplicated() descarta la segunda ocurrencia de TODOS los
    campos duplicados pendientes, no solo del que se acaba de procesar,
    destruyendo datos antes de que se hayan fusionado.
    """
    dup_names = df.columns[df.columns.duplicated()].unique()

    for name in dup_names:
        cols = df.loc[:, df.columns == name]

        df[name] = cols.bfill(axis=1).iloc[:, 0]

        log.info(f"  Columnas duplicadas combinadas correctamente: {name}")

    # Drop único al final: en este punto todas las columnas duplicadas
    # ya contienen el mismo valor fusionado → conservar la primera es seguro
    df = df.loc[:, ~df.columns.duplicated()]

    return df

def construir_nhc_real(df: pd.DataFrame) -> pd.DataFrame:
    """
    Construye NHC como la clave real del paciente para que todas las tablas
    (PACIENTE, TIEMPOS, PROCEDIMIENTO, EVOLUCION, INFLAMACION, ANALITICA)
    usen el mismo identificador y las FK funcionen.

    Jerarquía:
      1. NHC_real (= Anexar1.NHC HUMV fusionado con NHC.1)
      2. NHC (PseudoID) como fallback para pacientes sin NHC real

    """
    if "NHC_real" not in df.columns:
        log.warning("  NHC_real no encontrado — usando NHC (PseudoID) como clave")
        return df

    # NHC = NHC_real si existe, PseudoID (NHC actual) si no
    df["NHC"] = df["NHC_real"].fillna(df["NHC"])
    n_real   = df["NHC_real"].notna().sum()
    n_pseudo = df["NHC_real"].isna().sum()
    log.info(f"  NHC construido: {n_real} con NHC real, {n_pseudo} con PseudoID (fallback)")
    log.info(f"  NHC muestra tras construir: {df['NHC'].dropna().head(5).tolist()}")
    df = df.drop(columns=["NHC_real"])
    return df


# ─────────────────────────────────────────────────────────────────────────────
def extraer_principal(xlsx: pd.ExcelFile) -> pd.DataFrame:
    """Lee la hoja Conjunto y la prepara como fuente principal."""
    log.info(f"  Leyendo hoja '{SHEET_PRINCIPAL}'...")
    df = pd.read_excel(xlsx, sheet_name=SHEET_PRINCIPAL)
    log.info(f"  Shape original: {df.shape}")

    # 1. Quitar prefijo Anexar1.
    df = quitar_prefijo_anexar(df)

    # 2. Aplicar aliases canónicos
    #    Tras este paso pueden existir DOS columnas llamadas 'NHC_real':
    #      - NHC.1      → NHC_real  (133 pacientes con inflamación)
    #      - NHC HUMV   → NHC_real  (320 pacientes con analítica AS)
    #    pandas permite columnas duplicadas; las gestionamos a continuación.
    df = aplicar_aliases(df)
    verificar_columnas_faltantes(df, COL_ALIASES)

    # 3. Fusionar las dos NHC_real con fillna ANTES de deduplicar_columnas,
    #    para que el NHC real quede disponible para construir_nhc_real.
    #    Identificamos todas las ocurrencias de NHC_real por posición.
    nhc_real_cols = [i for i, c in enumerate(df.columns) if c == "NHC_real"]
    if len(nhc_real_cols) >= 2:
        # Combinamos todas las columnas NHC_real en la primera
        primera = df.columns[nhc_real_cols[0]]
        for idx in nhc_real_cols[1:]:
            df.iloc[:, nhc_real_cols[0]] = df.iloc[:, nhc_real_cols[0]].fillna(df.iloc[:, idx])
        # Renombramos las duplicadas para que deduplicar_columnas las elimine limpiamente
        cols = list(df.columns)
        for idx in nhc_real_cols[1:]:
            cols[idx] = "__nhc_real_dup__"
        df.columns = cols
        df = df.drop(columns=["__nhc_real_dup__"], errors="ignore")
       

    # 4. Construir NHC canónico ANTES de deduplicar (NHC_real ya está lista)
    df = construir_nhc_real(df)

    # 5. Combinar campos duplicados restantes
    print("Duplicadas antes de deduplicar_columnas():", df.columns[df.columns.duplicated()])
    df = deduplicar_columnas(df)

    # 6. Eliminar columnas redundantes / operativas
    #    TICIfinal NO se descarta — tiene 333 valores y se carga en PROCEDIMIENTO
    cols_descartar = [
        "Edad_AS", "Sexo_AS",
        "IncisionCierre",
        "salaocupada", "BB", "SALA4o32",
        "Fecha.1", "HoraInicio",
        "Aclaraciones mRS 90d",
        # LugarCódigo con tilde ya fue fusionada en LugarCodigo por deduplicar_columnas()
        # Etiología ya fue renombrada a Etiologia por el alias en config.py
    ]
    df = df.drop(columns=[c for c in cols_descartar if c in df.columns])

    log.info(f"  Shape tras limpieza de columnas: {df.shape}")
    log.info(f"  NIHSS_24h no nulos:          {df['NIHSS_24h'].notna().sum() if 'NIHSS_24h' in df.columns else 'NO'}")
    log.info(f"  FechadeAlta no nulos:          {df['FechadeAlta'].notna().sum() if 'FechadeAlta' in df.columns else 'NO'}")
    log.info(f"  ComplicacionesPost no nulos: {df['ComplicacionesPost'].notna().sum() if 'ComplicacionesPost' in df.columns else 'NO'}")
    log.info(f"  Doctor no nulos:             {df['Doctor'].notna().sum() if 'Doctor' in df.columns else 'NO'}")
    # ── Verificación BUG-A/B (v4.0) ──────────────────────────────────────────
    log.info(f"  TICIfinal no nulos:          {df['TICIfinal'].notna().sum() if 'TICIfinal' in df.columns else 'FALTA — revisar aliases'}")
    log.info(f"  LugarCodigo no nulos:        {df['LugarCodigo'].notna().sum() if 'LugarCodigo' in df.columns else 'FALTA — revisar aliases'}")
    log.info(f"  Etiologia no nulos:          {df['Etiologia'].notna().sum() if 'Etiologia' in df.columns else 'FALTA — revisar aliases'}")
    # ─────────────────────────────────────────────────────────────────────────
    return df


def extraer_as(xlsx: pd.ExcelFile) -> pd.DataFrame:
    """
    Lee la hoja AS (analítica independiente, 1742 filas).
    Fuente de metadatos de solicitud (Doctor, Centro, Servicio...)
    y analítica para pacientes no presentes en Conjunto.
    """
    log.info(f"  Leyendo hoja '{SHEET_AS}'...")
    df = pd.read_excel(xlsx, sheet_name=SHEET_AS)
    log.info(f"  Shape original AS: {df.shape}")

    # Renombrar NHC HUMV → NHC antes de aliases
    df = df.rename(columns={"NHC HUMV": "NHC"})
    df = aplicar_aliases(df)

    
    meta = ["Doctor", "Centro", "Servicio", "Centro_procesamiento",
            "Diagnostico_solicitud", "Info_adicional", "Patologia_descripcion"]
    for c in meta:
        n = df[c].notna().sum() if c in df.columns else "NO"
        log.info(f"    {c}: {n}")
    return df


def extraer_inflamacion(xlsx: pd.ExcelFile) -> pd.DataFrame:
    """Lee la hoja Inflamación (133 filas)."""
    log.info(f"  Leyendo hoja '{SHEET_INFLAMACION}'...")
    df = pd.read_excel(xlsx, sheet_name=SHEET_INFLAMACION)
    log.info(f"  Shape Inflamación: {df.shape}")
    return df

def verificar_columnas_faltantes(df: pd.DataFrame, col_mapping: dict):
    """
    Muestra columnas del Excel que no se encontraron en el DataFrame
    tras aplicar los aliases.
    """
    real_cols = df.columns.tolist()
    faltantes = []
    for excel_col, db_col in col_mapping.items():
        if excel_col not in real_cols and db_col not in real_cols:
            # Buscar nombres aproximados en el DataFrame
            posibles = [c for c in real_cols
                        if excel_col.lower().replace(" ", "").replace("-", "") in c.lower().replace(" ", "").replace("-", "")]
            faltantes.append((excel_col, db_col, posibles))
    if faltantes:
        log.warning("Columnas con todos los valores nulos después del mapeo:")
        for excel_col, db_col, posibles in faltantes:
            log.warning(f"- Excel: '{excel_col}' → DB: '{db_col}' | Posibles columnas en DataFrame: {posibles}")
    else:
        log.info("Todas las columnas del mapeo se encontraron en el DataFrame.")


# ─────────────────────────────────────────────────────────────────────────────
def run() -> dict:
    log.info("=" * 60)
    log.info("FASE 1 -- EXTRACCIÓN")
    log.info("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    if not os.path.exists(XLSX_PATH):
        raise FileNotFoundError(f"Fichero Excel no encontrado: {XLSX_PATH}")

    xlsx = pd.ExcelFile(XLSX_PATH)
    log.info(f"Hojas disponibles: {xlsx.sheet_names}")

    df_principal   = extraer_principal(xlsx)
    df_as          = extraer_as(xlsx)
    df_inflamacion = extraer_inflamacion(xlsx)

    out_principal   = os.path.join(OUTPUT_DIR, "raw_principal.csv")
    out_as          = os.path.join(OUTPUT_DIR, "raw_as.csv")
    out_inflamacion = os.path.join(OUTPUT_DIR, "raw_inflamacion.csv")

    df_principal.to_csv(out_principal,   index=False, encoding="utf-8")
    df_as.to_csv(out_as,                 index=False, encoding="utf-8")
    df_inflamacion.to_csv(out_inflamacion, index=False, encoding="utf-8")

    log.info(f"  Exportado: {out_principal}  ({len(df_principal)} filas, {df_principal.shape[1]} cols)")
    log.info(f"  Exportado: {out_as}  ({len(df_as)} filas, {df_as.shape[1]} cols)")
    log.info(f"  Exportado: {out_inflamacion}  ({len(df_inflamacion)} filas)")

   
    for col in df_principal.columns:
        print(repr(col))
    return {
        "principal":   out_principal,
        "as":          out_as,
        "inflamacion": out_inflamacion,
    }

   

if __name__ == "__main__":
    run()