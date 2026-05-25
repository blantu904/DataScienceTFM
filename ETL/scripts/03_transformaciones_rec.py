# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# =============================================================================
#  03_transformaciones_rec.py  --  FASE 3: Recodificación de campos REC
# =============================================================================

import os
import sys
import logging
import re
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OUTPUT_DIR, LOG_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [REC] %(levelname)s -- %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "03_transformaciones_rec.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# =============================================================================
#  1. anticoag_prev_rec  (1-5)
# =============================================================================

def _rec_anticoag(val) -> int | None:
    if pd.isna(val):
        return 1
    v = str(val).strip().lower()
    if not v or v in ("nan", "no", "ninguno", "ninguna"):
        return 1
    if "no anticoag" in v or v == "sí":
        return 2
    if any(x in v for x in ["sintrom", "acenocum", "warfar", "aldocumar"]):
        return 3
    if any(x in v for x in ["heparin", "enoxaparin", "clexane", "bemiparin"]):
        return 4
    if any(x in v for x in ["apixab", "rivarox", "xarelto", "dabigatr",
                              "edoxab", "pradaxa", "eliquis", "lixiana", "savaysa"]):
        return 5
    return None


def calcular_anticoag_prev_rec(df: pd.DataFrame) -> pd.DataFrame:
    col_texto = "AnticoagPrev"
    col_rec   = "anticoag_prev_rec"
    col_num   = "anticoag"

    if col_num in df.columns:
        base = pd.to_numeric(df[col_num], errors="coerce")
        valida = base.between(1, 5)
        df[col_rec] = base.where(valida).astype("Int64")
    else:
        df[col_rec] = pd.NA

    if col_texto in df.columns:
        mask_falta = df[col_rec].isna()
        calculado = df.loc[mask_falta, col_texto].apply(_rec_anticoag)
        df.loc[mask_falta, col_rec] = calculado.astype("Int64")

    no_mapeados = df[df[col_rec].isna() & df.get(col_texto, pd.Series()).notna()]
    if len(no_mapeados):
        log.warning(f"  anticoag_prev_rec: {len(no_mapeados)} sin mapear:")
        for _, row in no_mapeados.iterrows():
            log.warning(f"    NHC={row.get('NHC','?')}  texto='{row.get(col_texto,'?')}'")

    n = df[col_rec].notna().sum()
    log.info(f"  anticoag_prev_rec: {n} valores calculados")
    log.info(f"    Distribución:\n{df[col_rec].value_counts().sort_index().to_string()}")
    return df


# =============================================================================
#  2. Oclusion_rec  (1-10)
# =============================================================================

def _rec_oclusion(val) -> int | None:
    if pd.isna(val):
        return None
    v = str(val).strip().upper()
    if not v or v == "NAN":
        return None
    if any(x in v for x in ["TAND", "ACI + M", "ACI+M", "CAROT", "CAROTIDA", "ACI+ACM"]):
        return 5
    if any(x in v for x in ["BASILAR", "BASIL", "TOP BAS", "VB", "VERTEBRO", "VERTEBROBASILAR"]):
        return 6
    if v in ("ACI", "ACII", "ACII ", "ACI ") or (
            "ACI" in v and "M1" not in v and "M2" not in v and "M3" not in v):
        if "+" not in v:
            return 4
    if re.search(r'\bM1\b', v) and "M2" not in v and "M3" not in v:
        return 1
    if re.search(r'\bM2\b', v) and "M3" not in v and "ACI" not in v:
        return 2
    if any(x in v for x in ["M3", "M4", "M5"]):
        return 3
    if re.search(r'\bACP\b', v) or "CEREBRAL POST" in v:
        return 7
    if re.search(r'\bACA\b', v) or re.search(r'\bA3\b', v):
        return 8
    if any(x in v for x in ["PICA", "CEREBELO", "CEREBELOSA", "CEREBELOSO"]):
        return 9
    return 10


def calcular_oclusion_rec(df: pd.DataFrame) -> pd.DataFrame:

    col_texto = "NiveldeObstrucción"   
    col_rec   = "Oclusion_rec"
    col_viejo = "Oclusion"

    if col_viejo in df.columns:
        base = pd.to_numeric(df[col_viejo], errors="coerce")
        valida = base.between(1, 10)
        df[col_rec] = base.where(valida).astype("Int64")
    else:
        df[col_rec] = pd.NA

    if col_texto in df.columns:
        mask_falta = df[col_rec].isna()
        calculado = df.loc[mask_falta, col_texto].apply(_rec_oclusion)
        df.loc[mask_falta, col_rec] = calculado.astype("Int64")

    no_map = df[df[col_rec].isna() & df.get(col_texto, pd.Series()).notna()]
    if len(no_map):
        log.warning(f"  Oclusion_rec: {len(no_map)} sin mapear")

    n = df[col_rec].notna().sum()
    log.info(f"  Oclusion_rec: {n} valores calculados")
    log.info(f"    Distribución:\n{df[col_rec].value_counts().sort_index().to_string()}")
    return df


# =============================================================================
#  3. iniciodesconocido_rec  (0-2)
# =============================================================================

def calcular_iniciodesconocido_rec(df: pd.DataFrame) -> pd.DataFrame:
    col_rec       = "iniciodesconocido_rec"
    col_existing  = "iniciodesconocido"
    col_missmatch = "Missmatch"
    col_inicio    = "Iniciosíntomas"    
    col_despertar = "Despertar"

    if col_existing in df.columns:
        base = pd.to_numeric(df[col_existing], errors="coerce")
        valida = base.between(0, 2)
        df[col_rec] = base.where(valida).astype("Int64")
    else:
        df[col_rec] = pd.NA

    mask_falta = df[col_rec].isna()
    if mask_falta.any():
        def _inferir(row):
            inicio = row.get(col_inicio, pd.NA)
            if pd.notna(inicio) and str(inicio).strip() not in ("", "nan"):
                return 0
            despertar = row.get(col_despertar, pd.NA)
            missmatch = str(row.get(col_missmatch, "")).strip().lower()
            if pd.notna(despertar) and str(despertar).strip() not in ("", "nan"):
                if missmatch in ("sí", "si", "yes", "1", "true"):
                    return 2
                return 1
            return pd.NA

        inferido = df[mask_falta].apply(_inferir, axis=1).astype("Int64")
        df.loc[mask_falta, col_rec] = inferido

    n = df[col_rec].notna().sum()
    log.info(f"  iniciodesconocido_rec: {n} valores calculados")
    log.info(f"    Distribución:\n{df[col_rec].value_counts().sort_index().to_string()}")
    return df


# =============================================================================
#  4. anticoagHosp_rec  (1-5)
# =============================================================================

def calcular_anticoaghsp_rec(df: pd.DataFrame) -> pd.DataFrame:
    col_texto = "AnticoaIntrahosp"
    col_rec   = "anticoagHosp_rec"
    col_num   = "anticoagHosp"

    if col_num in df.columns:
        base = pd.to_numeric(df[col_num], errors="coerce")
        valida = base.between(1, 5)
        df[col_rec] = base.where(valida).astype("Int64")
    else:
        df[col_rec] = pd.NA

    if col_texto in df.columns:
        mask_falta = df[col_rec].isna()
        calculado = df.loc[mask_falta, col_texto].apply(_rec_anticoag)
        df.loc[mask_falta, col_rec] = calculado.astype("Int64")

    no_map = df[df[col_rec].isna() & df.get(col_texto, pd.Series()).notna()]
    if len(no_map):
        log.warning(f"  anticoagHosp_rec: {len(no_map)} sin mapear:")
        for _, row in no_map.iterrows():
            log.warning(f"    NHC={row.get('NHC','?')}  texto='{row.get(col_texto,'?')}'")

    n = df[col_rec].notna().sum()
    log.info(f"  anticoagHosp_rec: {n} valores calculados")
    log.info(f"    Distribución:\n{df[col_rec].value_counts().sort_index().to_string()}")
    return df


# =============================================================================
#  5. TH_rec  (0-6)  -- Transformación Hemorrágica (ECASS)
# =============================================================================

def _rec_th(val) -> int | None:
    if pd.isna(val):
        return 0

    v = str(val).strip().lower()

    if not v or v in ("nan", "-", "--", "nd", "na", "n/a"):
        return 0

    if v == "no":
        return 0
    if any(x in v for x in ["sin th", "no th", "no transf", "sin transform",
                              "no hemo", "sin hemo", "ausencia"]):
        return 0

    # Clasificación ECASS explícita
    if "ph2" in v or "ph 2" in v:
        return 4
    if "phi" in v or "ph1" in v or "ph 1" in v:
        return 3
    if "phr" in v or "ph r" in v or "ph remot" in v:
        return 5
    if "hi2" in v or "hi 2" in v:
        return 2
    if "hi1" in v or "hi 1" in v or "ih 1" in v or "ih1" in v or "petequi" in v:
        return 1

    # ── FIX: casos nuevos detectados en revisión manual ──────────────────────
    # "Transformación hemorrágica IH 1" -> HI1
    if re.search(r'ih\s*1', v) or re.search(r'i\.?h\.?\s*1', v):
        return 1
    # "Transformación hemorrágica" sin especificar grado -> no evaluable
    if re.match(r'^transformaci[oó]n\s+hemor', v) and not any(
            x in v for x in ["ih", "hi", "ph", "1", "2", "3", "4"]):
        return 6
    # "Hemorragia intraventricular" -> fuera de clasificación ECASS parenquimatosa
    if "intraventricular" in v:
        return 6
    # ─────────────────────────────────────────────────────────────────────────

    if any(x in v for x in ["hematoma", "transform hemor", "t. hemor",
                              "th post", "th tras"]):
        return 3

    if "hsa" in v:
        return 2

    if any(x in v for x in ["sufusion", "sufusión", "minima suf"]):
        return 1

    if any(x in v for x in ["extravasac", "contraste"]):
        return 1

    if any(x in v for x in ["no evalua", "no valora", "sin imagen",
                              "sin control", "no disponib"]):
        return 6

    return None


def calcular_th_rec(df: pd.DataFrame) -> pd.DataFrame:
    col_texto = "Hemorragia"
    col_rec   = "TH_rec"
    col_th    = "TH"

    if col_th in df.columns:
        base = pd.to_numeric(df[col_th], errors="coerce")
        valida = base.between(0, 6)
        df[col_rec] = base.where(valida).astype("Int64")
    else:
        df[col_rec] = pd.NA

    if col_texto in df.columns:
        mask_falta = df[col_rec].isna()
        calculado = df.loc[mask_falta, col_texto].apply(_rec_th)
        df.loc[mask_falta, col_rec] = pd.array(calculado, dtype="Int64")

    no_map = df[df[col_rec].isna() & df.get(col_texto, pd.Series()).notna()]
    if len(no_map):
        log.warning(f"  TH_rec: {len(no_map)} sin mapear -> REQUIEREN REVISIÓN MANUAL ECASS:")
        for _, row in no_map.iterrows():
            log.warning(f"    NHC={row.get('NHC','?')}  texto='{row.get(col_texto,'?')}'")
        ruta_rev = os.path.join(OUTPUT_DIR, "revision_manual_TH_rec.csv")
        try:
            no_map[["NHC", col_texto]].to_csv(ruta_rev, index=False, mode='w')
            log.warning(f"  -> Exportado a {ruta_rev}")
        except PermissionError:
            log.error(f"  -> No se pudo escribir {ruta_rev}: fichero abierto en otro programa."
                      f" Ciérralo y repite la fase 3.")

    n = df[col_rec].notna().sum()
    log.info(f"  TH_rec: {n} valores calculados")
    log.info(f"    Distribución:\n{df[col_rec].value_counts().sort_index().to_string()}")
    return df


# =============================================================================
#  Pipeline principal
# =============================================================================

def run():
    log.info("=" * 60)
    log.info("FASE 3 -- TRANSFORMACIONES REC")
    log.info("=" * 60)

    df = pd.read_csv(os.path.join(OUTPUT_DIR, "clean_principal.csv"))
    log.info(f"Filas cargadas: {len(df)}")

    log.info("\n--- 3.1  anticoag_prev_rec ---")
    df = calcular_anticoag_prev_rec(df)

    log.info("\n--- 3.2  Oclusion_rec ---")
    df = calcular_oclusion_rec(df)

    log.info("\n--- 3.3  iniciodesconocido_rec ---")
    df = calcular_iniciodesconocido_rec(df)

    log.info("\n--- 3.4  anticoagHosp_rec ---")
    df = calcular_anticoaghsp_rec(df)

    log.info("\n--- 3.5  TH_rec ---")
    df = calcular_th_rec(df)

    log.info("\n  Resumen campos REC:")
    for col in ["anticoag_prev_rec", "Oclusion_rec", "iniciodesconocido_rec",
                "anticoagHosp_rec", "TH_rec"]:
        if col in df.columns:
            n_ok   = df[col].notna().sum()
            n_null = df[col].isna().sum()
            log.info(f"    {col:30s}: {n_ok:>3} valores  |  {n_null:>3} NULL")

    df.to_csv(os.path.join(OUTPUT_DIR, "transformed_principal.csv"), index=False)
    log.info("\n[OK]  Fase 3 completada.")
    return df


if __name__ == "__main__":
    run()