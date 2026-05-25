# -*- coding: utf-8 -*-
# =============================================================================
#  04_carga.py  —  FASE 4: Carga en SQL Server
# =============================================================================

import os
import sys
import logging
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OUTPUT_DIR, LOG_DIR, SQLSERVER_CONFIG, TABLA_ORDER

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CARGA] %(levelname)s -- %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "04_carga.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


# =============================================================================
#  Conexión SQL Server
# =============================================================================

def get_engine():
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
    log.info(f"  Engine creado: {cfg['server']} / {cfg['database']}")
    return engine


# =============================================================================
#  Utilidad de selección
# =============================================================================

def _select(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Selecciona y renombra columnas disponibles. Loguea las que no existan."""
    available = {k: v for k, v in col_map.items() if k in df.columns}
    missing = [k for k in col_map if k not in df.columns]
    if missing:
        log.warning(f"    Columnas no encontradas en DataFrame: {missing}")
    return df[list(available.keys())].rename(columns=available)


# =============================================================================
#  Extractores — fuente: transformed_principal.csv
# =============================================================================

def extraer_paciente(df: pd.DataFrame) -> pd.DataFrame:
    out = _select(df, {
        "NHC":         "NHC",
        "Edad":        "Edad",
        "Genero":      "Genero",
        "Hemisferico": "Hemisferio",
        "FOP":         "FOP",
    })
    out = out.drop_duplicates(subset=["NHC"], keep="first")
    out["NHC"] = pd.to_numeric(out["NHC"], errors="coerce").astype("Int64")
    return out.dropna(subset=["NHC"])


def extraer_antecedentes(df: pd.DataFrame) -> pd.DataFrame:
    out = _select(df, {
        "NHC":         "NHC",
        "FA conocida": "FAconocida",
        "FA":          "FA_num",
        "Etiología":   "Etiologia",
    })
    return out.drop_duplicates(subset=["NHC"], keep="first").dropna(subset=["NHC"])


def extraer_medicacion_previa(df: pd.DataFrame) -> pd.DataFrame:
    out = _select(df, {
        "NHC":               "NHC",
        "anticoag_prev_rec": "anticoag_prev_rec",
        "AnticoagPrev":      "AnticoagPrev",
        "anticoag":          "anticoag_num",
        "Antiagreg.Prev":    "AntiagrePrev",
    })
    return out.drop_duplicates(subset=["NHC"], keep="first").dropna(subset=["NHC"])


def extraer_tiempos_llegada(df: pd.DataFrame) -> pd.DataFrame:
    out = _select(df, {
        "NHC":            "NHC",
        "FECHA":          "FECHA",
        "Iniciosíntomas": "InicioSintomas",
        "Despertar":      "Despertar",
        "HoraTriaje":     "HoraTriaje",
        "Horapuerta":     "Horapuerta",
        "LlamadaNeuro":   "LlamadaNeuro",
        "ValoradoNeuro":  "ValoradoNeuro",
        "HoraTC":         "HoraTC",
        "ultimaimagenTC": "ultimaimagenTC",
        "Turno":          "Turno",
        "Horario":        "Horario",
        "Dia":            "Dia",
    })
    out["FECHA"] = out["FECHA"].astype(str)
    return out.dropna(subset=["NHC", "FECHA"])


def extraer_tiempos_intervencion(df: pd.DataFrame) -> pd.DataFrame:
    out = _select(df, {
        "NHC":             "NHC",
        "FECHA":           "FECHA",
        "HoraPunción":     "HoraPuncion",   
        "Perfusiónfibri":  "Perfusionfibri",
        "HoraentradaSala": "HoraentradaSala",
        "HoraAguja":       "HoraAguja",
        "Primerpase":      "Primerpase",
    })
    out["FECHA"] = out["FECHA"].astype(str)
    return out.dropna(subset=["NHC", "FECHA"])


def extraer_intervalos(df: pd.DataFrame) -> pd.DataFrame:
    out = _select(df, {
        "NHC":                          "NHC",
        "FECHA":                        "FECHA",
        "TiempoSintomasPuerta":         "T_SintomasPuerta",
        "TiempoPuertaValoración":       "T_PuertaValoracion",
        "TiempollamadaValoración":      "T_LlamadaValoracion",
        "TiempoValoraciónTC":           "T_ValoraciónTC",
        "TiempoPuertaTC":               "T_PuertaTC",
        "TiempoTC":                     "T_TC",
        "TiempoPuertaSala":             "T_PuertaSala",
        "TiempoTCSala":                 "T_TCSala",
        "TiempoPuertaPunción":          "T_PuertaPuncion",
        "TiempoSalaPunción":            "T_SalaPuncion",
        "Tiempopuertarecanalización":   "T_PuertaRecanalizacion",
        "Tiempopunción1ºpase":          "T_Puncion1Pase",
        "Tiempopunciónrecanalización":  "T_PuncionRecanalizacion",
        "Tiemposíntomasrecanalización": "T_SintomasRecanalizacion",
    })
    out["FECHA"] = out["FECHA"].astype(str)

    cols_intervalo = [c for c in out.columns if c not in ("NHC", "FECHA")]
    for col in cols_intervalo:
        # Forzar a object para permitir asignación mixta string/numérico
        out[col] = out[col].astype(object)

        mask_hhmmss = out[col].astype(str).str.match(r'^\d{1,2}:\d{2}(:\d{2})?$', na=False)
        if mask_hhmmss.any():
            minutos = (
                pd.to_timedelta(out.loc[mask_hhmmss, col])
                .dt.total_seconds()
                .div(60)
                .round()
            )
            out.loc[mask_hhmmss, col] = minutos.values  # .values evita problemas de índice

        out[col] = pd.to_numeric(out[col], errors="coerce")

    return out.dropna(subset=["NHC", "FECHA"])


def extraer_scores_inicio(df: pd.DataFrame) -> pd.DataFrame:
    out = _select(df, {
        "NHC":          "NHC",
        "FECHA":        "FECHA",
        "mRs inicio":   "mRs_inicio",
        "NIHSS inicio": "NIHSS_inicio",
        "ASPECTS":      "ASPECTS",
    })
    out["FECHA"] = out["FECHA"].astype(str)
    return out.dropna(subset=["NHC", "FECHA"])


def extraer_procedimiento(df: pd.DataFrame) -> pd.DataFrame:
    out = _select(df, {
        "NHC":                    "NHC",
        "FECHA":                  "FECHA",
        "Oclusion_rec":           "Oclusion_rec",
        "NiveldeObstrucción":     "NivelObstruccion",
        "iniciodesconocido_rec":  "iniciodesconocido_rec",
        "Missmatch":              "Missmatch",
        "Lateralidad":            "Lateralidad",
        "Procedimiento":          "Procedimiento",
        "NottoIctus":             "NottoIctus",
        "TICI":                   "TICI",
        "Recanalización":         "Recanalizacion",
        "RecanalizaciónCarótida": "RecanalizacionCarotida",
        "TH_rec":                 "TH_rec",
        "Hemoragia":              "Hemoragia_texto",
        "InfartoEstablecido":     "InfartoEstablecido",
        "Edema":                  "Edema",
        "DesviaciónLM":           "DesviaciónLM",   
        "LugarCódigo":            "LugarCodigo",
        "Complicaciones":         "Complicaciones",
        "ATP":                    "ATP",
    })
    out["FECHA"] = out["FECHA"].astype(str)
    if "Procedimiento" in out.columns:
        out["Procedimiento"] = out["Procedimiento"].fillna("Desconocido")
    return out.dropna(subset=["NHC", "FECHA"])


def extraer_tratamiento_farm(df: pd.DataFrame) -> pd.DataFrame:
    out = _select(df, {
        "NHC":              "NHC",
        "FECHA":            "FECHA",
        "Fibrinolítico":    "Fibrinolitico",
        "FIV":              "FIV",
        "FIVia":            "FIVia",
        "anticoagHosp_rec": "anticoagHosp_rec",
        "AnticoaIntrahosp": "AnticoaIntrahosp",
        "NuevoAnticoaAlta": "NuevoAnticoaAlta",
    })
    out["FECHA"] = out["FECHA"].astype(str)
    return out.dropna(subset=["NHC", "FECHA"])


def extraer_materiales(df: pd.DataFrame) -> pd.DataFrame:
    out = _select(df, {
        "NHC":         "NHC",
        "FECHA":       "FECHA",
        "Pases":       "Pases",
        "Stent":       "Stent",
        "Stentriever": "Stentriever",
        "TipodeCierre": "TipodeCierre",
    })
    out["FECHA"] = out["FECHA"].astype(str)
    return out.dropna(subset=["NHC", "FECHA"])


def extraer_inflamacion(df_infl: pd.DataFrame) -> pd.DataFrame:
    df_infl = df_infl.copy()
    df_infl["NHC"] = pd.to_numeric(df_infl["NHC"], errors="coerce").astype("Int64")
    df_infl = df_infl.dropna(subset=["NHC"])
    for col in [c for c in df_infl.columns if c != "NHC"]:
        df_infl[col] = (
            df_infl[col].astype(str).str.strip()
            .replace({"-": None, " -": None, "--": None, "nan": None, "": None})
        )
        df_infl[col] = pd.to_numeric(df_infl[col], errors="coerce")
    return df_infl


# =============================================================================
#  Extractores analítica — fuente: clean_as.csv
# =============================================================================

def _extraer_analitica_base(df_as: pd.DataFrame) -> pd.DataFrame:
    df_as = df_as.copy()
    df_as.columns = (
        df_as.columns
        .str.strip()
        .str.replace("\xa0", " ", regex=False)
    )
    df_as["NHC"] = pd.to_numeric(df_as["NHC"], errors="coerce").astype("Int64")
    return df_as.dropna(subset=["NHC"])


_COLS_TEXTO_AS = {
    "Inmunofijacion", "AlbuminaTira", "CreatininaTira",
    "Fecha_solicitud", "Fecha", "NHC",
    "Doctor", "Centro", "Servicio", "Centro_procesamiento",
    "Diagnostico_solicitud", "Ubicacion", "Observaciones_peticion",
    "Info_adicional", "Patologia_descripcion", "Numero_solicitud",
}


def _limpiar_floats_as(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if col in _COLS_TEXTO_AS:
            continue
        if df[col].dtype == object:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.strip().str.replace(",", ".", regex=False)
                    .replace({"nan": None, "": None, "-": None, " -": None, "--": None}),
                errors="coerce"
            )
    return df


def extraer_analitica_lipidos(df_as: pd.DataFrame) -> pd.DataFrame:
    df = _extraer_analitica_base(df_as)
    df = _limpiar_floats_as(df)
    return _select(df, {
        "NHC":                  "NHC",
        "Fecha":                "Fecha",
        "ApolipoproteínaAI":    "ApolipoproteínaAI",
        "ApolipoproteínaB100":  "ApolipoproteínaB100",
        "Lipoproteina_a":       "Lipoproteina_a",
        "ColesterolNoHDL":      "ColesterolNoHDL",
        "Colesterol suero":     "Colesterol_suero",
        "HDL Colesterol suero": "HDLColesterol",
        "LDLColesterol":        "LDLColesterol",
        "Trigliceridos":        "Trigliceridos",
    }).dropna(subset=["NHC"])


def extraer_analitica_metabolica(df_as: pd.DataFrame) -> pd.DataFrame:
    df = _extraer_analitica_base(df_as)
    df = _limpiar_floats_as(df)
    result = _select(df, {
        "NHC":                      "NHC",
        "Fecha":                    "Fecha",
        "Glucosa suero":            "Glucosa_suero",
        "HbA1c":                    "HbA1c",
        "Homocisteina":             "Homocisteina",
        "Creatinina suero":         "Creatinina_suero",
        "FiltradoGlomerularCKDEPI": "FiltradoGlomerularCKDEPI",
        "Urea suero":               "Urea_suero",
        "Sodio suero":              "Sodio_suero",
        "Potasio suero":            "Potasio_suero",
        "Cloro suero":              "Cloro_suero",
        "Calcio Total suero":       "CalcioTotal",
        "Magnesio suero":           "Magnesio_suero",
        "Zinc suero":               "Zinc_suero",
        "Vitamina B12 suero":       "VitaminaB12",
        "AcidoFolico":              "AcidoFolico",
        "TSH_suero":                "TSH_suero",
        "T4libre_suero":            "T4libre_suero",
        "PCR_Ultrasensible":        "PCR_Ultrasensible",
        "ProteinaCReactiva":        "ProteinaCReactiva",
    }).dropna(subset=["NHC"])

    for col in result.columns:
        if col in ("NHC", "Fecha"):
            continue
        if result[col].dtype == object:
            result[col] = pd.to_numeric(
                result[col].astype(str).str.strip().str.replace(",", ".", regex=False)
                    .replace({"nan": None, "": None, "-": None, "None": None}),
                errors="coerce"
            )
    return result


def extraer_analitica_hepatica(df_as: pd.DataFrame) -> pd.DataFrame:
    df = _extraer_analitica_base(df_as)
    df = _limpiar_floats_as(df)
    return _select(df, {
        "NHC":                          "NHC",
        "Fecha":                        "Fecha",
        "ALT suero":                    "ALT_suero",
        "AST suero":                    "AST_suero",
        "GGT suero":                    "GGT_suero",
        "Fosfatasa Alcalina suero":     "FosfatasaAlcalina",
        "Bilirrubina Total suero":      "BilirrubinaTotal",
        "Bilirrubina Directa suero":    "BilirrubinaDirect",
        "CK suero":                     "CK_suero",
        "Lactato Deshidrogenasa suero": "LactatoDeshidrogenasa",
    }).dropna(subset=["NHC"])


def extraer_analitica_proteinas(df_as: pd.DataFrame) -> pd.DataFrame:
    df = _extraer_analitica_base(df_as)
    df = _limpiar_floats_as(df)
    return _select(df, {
        "NHC":                "NHC",
        "Fecha":              "Fecha",
        "ProteinasTotales":   "ProteinasTotales",
        "Prealbumina":        "Prealbumina",
        "Albumina_suero":     "Albumina_suero",
        "Transferrina suero": "Transferrina",
        "BetaGlobulina":      "BetaGlobulina",
        "Inmunofijacion":     "Inmunofijacion",
    }).dropna(subset=["NHC"])


def extraer_analitica_orina(df_as: pd.DataFrame) -> pd.DataFrame:
    df = _extraer_analitica_base(df_as)
    df = _limpiar_floats_as(df)
    return _select(df, {
        "NHC":                         "NHC",
        "Fecha":                       "Fecha",
        "AlbuminaOrina":               "AlbuminaOrina",
        "CreatininaOrina":             "CreatininaOrina",
        "AlbuminaTira":                "AlbuminaTira",
        "Albumina/creatinina en tira": "AlbuminaCreatinina",
        "CreatininaTira":              "CreatininaTira",
        "DensidadOrina":               "DensidadOrina",
    }).dropna(subset=["NHC"])


def extraer_analitica_peticion(df_as: pd.DataFrame) -> pd.DataFrame:
    df = _extraer_analitica_base(df_as)
    return _select(df, {
        "NHC":                    "NHC",
        "Fecha":                  "Fecha",
        "Fecha_solicitud":        "Fecha_solicitud",
        "Numero_solicitud":       "Numero_solicitud",
        "Doctor":                 "Doctor",
        "Centro":                 "Centro",
        "Servicio":               "Servicio",
        "Centro_procesamiento":   "Centro_procesamiento",
        "Diagnostico_solicitud":  "Diagnostico_solicitud",
        "Ubicacion":              "Ubicacion",
        "Observaciones_peticion": "Observaciones_peticion",
        "Info_adicional":         "Info_adicional",
        "Patologia_descripcion":  "Patologia_descripcion",
    }).dropna(subset=["NHC"])


def extraer_alta_hospitalaria(df: pd.DataFrame, df_proc: pd.DataFrame) -> pd.DataFrame:
    fecha_por_nhc = (df_proc.dropna(subset=["NHC", "FECHA"])
                            .drop_duplicates("NHC")
                            .set_index("NHC")["FECHA"])
    if "FECHA" not in df.columns:
        df = df.copy()
        df["FECHA"] = df["NHC"].map(fecha_por_nhc)

    out = _select(df, {
        "NHC":               "NHC",
        "FECHA":             "FECHA",
        "FechadeAlta":       "FechadeAlta",
        "DestinoAlta":       "DestinoAlta",
        "FA_Novo":           "FA_Novo",
        "Causadelamuerte":   "Causadelamuerte",
        "FAnovo_num":        "FAnovo_num",
        "ComplicacionesPost": "ComplicacionesPost",
    })
    out["FECHA"] = out["FECHA"].astype(str)
    return out.dropna(subset=["NHC", "FECHA"])


def extraer_resultado_recam(df: pd.DataFrame, df_proc: pd.DataFrame) -> pd.DataFrame:
    fecha_por_nhc = (df_proc.dropna(subset=["NHC", "FECHA"])
                            .drop_duplicates("NHC")
                            .set_index("NHC")["FECHA"])
    if "FECHA" not in df.columns:
        df = df.copy()
        df["FECHA"] = df["NHC"].map(fecha_por_nhc)


    out = _select(df, {
        "NHC":          "NHC",
        "FECHA":        "FECHA",
        "Pases":        "Pases",
        "Recanalización": "Recanalizacion",
        "TICI":         "TICI",
        "NIHSS_24h":    "NIHSS_24h",   
        "NIHSS_alta":   "NIHSS_alta",   
        "mRs_alta":     "mRs_alta",   
    })
    out["FECHA"] = out["FECHA"].astype(str)
    for col in ["NIHSS_24h", "NIHSS_alta", "mRs_alta"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["NHC", "FECHA"])


def extraer_seguimiento(df: pd.DataFrame, df_proc: pd.DataFrame) -> pd.DataFrame:
    fecha_por_nhc = (df_proc.dropna(subset=["NHC", "FECHA"])
                            .drop_duplicates("NHC")
                            .set_index("NHC")["FECHA"])
    if "FECHA" not in df.columns:
        df = df.copy()
        df["FECHA"] = df["NHC"].map(fecha_por_nhc)
    out = _select(df, {
        "NHC":        "NHC",
        "FECHA":      "FECHA",
        "mRs_90dias": "mRs_90dias",
    })
    out["FECHA"] = out["FECHA"].astype(str)
    return out[out["mRs_90dias"].notna()].dropna(subset=["NHC", "FECHA"])


# =============================================================================
#  Filtrado de NHCs huérfanos
# =============================================================================

def filtrar_nhcs_huerfanos(df: pd.DataFrame, nhcs_validos: set, nombre: str) -> pd.DataFrame:
    nhc_norm = pd.to_numeric(df["NHC"], errors="coerce")
    mask = nhc_norm.isin(nhcs_validos)
    descartados = df[~mask]
    if not descartados.empty:
        nhcs_desc = sorted(nhc_norm[~mask].dropna().astype(int).unique().tolist())
        log.warning(
            f"  {nombre}: {len(descartados)} fila(s) descartada(s) "
            f"por NHC sin PACIENTE → {nhcs_desc}"
        )
    return df[mask].copy()


# =============================================================================
#  Filtrado de claves compuestas huérfanas (FK NHC+FECHA)
# =============================================================================

def filtrar_claves_huerfanas(df_hijo: pd.DataFrame,
                              df_padre: pd.DataFrame,
                              nombre_hijo: str,
                              nombre_padre: str) -> pd.DataFrame:
    """
    Descarta filas de df_hijo cuya clave compuesta (NHC, FECHA) no existe
    en df_padre. Evita errores de FK al cargar tablas del dominio episodio.
    Causa del bug: pacientes con FECHA='nan' pasan la extracción pero no
    llegan a TIEMPOS_LLEGADA (filtradas por parseo de fechas en fase 02),
    dejando huérfanos en las tablas hijas.
    """
    claves_padre = set(
        zip(df_padre["NHC"].astype(str), df_padre["FECHA"].astype(str))
    )
    mask = df_hijo.apply(
        lambda r: (str(r["NHC"]), str(r["FECHA"])) in claves_padre, axis=1
    )
    n_huerfanos = (~mask).sum()
    if n_huerfanos > 0:
        nhcs_desc = df_hijo.loc[~mask, "NHC"].astype(str).unique().tolist()
        log.warning(
            f"  {nombre_hijo}: {n_huerfanos} fila(s) huérfana(s) descartadas "
            f"(NHC+FECHA sin registro en {nombre_padre}) → NHCs: {nhcs_desc}"
        )
    return df_hijo[mask].copy()


# =============================================================================
#  Carga genérica en SQL Server
# =============================================================================

def cargar_tabla(engine, df: pd.DataFrame, tabla: str) -> int:
    if df.empty:
        log.warning(f"  {tabla}: dataframe vacío, nada que cargar")
        return 0

    COLS_TEXTO = {
        "Doctor", "Centro", "Servicio", "Centro_procesamiento",
        "Diagnostico_solicitud", "Ubicacion", "Observaciones_peticion",
        "Info_adicional", "Patologia_descripcion", "Numero_solicitud",
        "Genero", "Lateralidad", "Procedimiento", "Etiologia",
        "Complicaciones", "ComplicacionesPost",
        "DestinoAlta", "AnticoagPrev", "AnticoaIntrahosp", "NuevoAnticoaAlta",
        "Stent", "Stentriever", "TipodeCierre", "TICI",
        "NivelObstruccion", "LugarCodigo", "Horario",
        "Hemoragia", "Hemoragia_texto", "InfartoEstablecido", "Edema",  # ← añadir "Hemoragia"
    "NIHSS_alta", "mRs_alta", 
        "FA_Novo", "FANovo", "Causadelamuerte",
        "AlbuminaTira", "CreatininaTira", "Inmunofijacion",
        "FechadeAlta", "FECHA", "Fecha", "Fecha_solicitud",
        "Recanalizacion", "RecanalizacionCarotida", "Fibrinolitico",
        "InicioSintomas", "Despertar",
        "Horapuerta", "HoraTriaje", "LlamadaNeuro", "ValoradoNeuro",
        "HoraTC", "ultimaimagenTC", "HoraentradaSala",
        "HoraPuncion", "HoraAguja", "Primerpase",
        "Turno", "Dia", "FAconocida", "AntiagrePrev",
        "Missmatch", "Perfusionfibri", "DesviaciónLM",
        "Causadelamuerte",
    }

    df = df.copy()
    for col in df.columns:
        if str(df[col].dtype) in ("Int64", "boolean"):
            df[col] = df[col].where(df[col].notna(), None).astype(object)
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d").where(df[col].notna(), None)
        elif col.strip() not in {c.strip() for c in COLS_TEXTO}:
            converted = pd.to_numeric(
                df[col].astype(str).str.strip().str.replace(",", ".", regex=False)
                    .replace({"nan": None, "": None, "-": None,
                               " -": None, "--": None, "None": None}),
                errors="coerce"
            )
            if converted.notna().any():
                df[col] = converted

    max_params = 2000
    chunksize  = max(1, max_params // len(df.columns))

    df.to_sql(
        tabla, con=engine,
        if_exists="append",
        index=False,
        method=None,
        chunksize=chunksize,
    )
    log.info(f"  {tabla:25s}: {len(df):>4} filas insertadas")
    return len(df)


# =============================================================================
#  Pipeline principal
# =============================================================================

def run():
    log.info("=" * 60)
    log.info("FASE 4 -- CARGA EN SQL SERVER  (v4.0)")
    log.info("=" * 60)

    df_principal = pd.read_csv(
        os.path.join(OUTPUT_DIR, "transformed_principal.csv"), low_memory=False)
    df_infl = pd.read_csv(
        os.path.join(OUTPUT_DIR, "clean_inflamacion.csv"), low_memory=False)
    df_as = pd.read_csv(
        os.path.join(OUTPUT_DIR, "clean_as.csv"), low_memory=False)

    log.info(f"  Principal: {df_principal.shape} | AS: {df_as.shape} | Inflamación: {df_infl.shape}")

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    log.info("  Conexión SQL Server OK")

    df_pac     = extraer_paciente(df_principal)
    df_antec   = extraer_antecedentes(df_principal)
    df_medprev = extraer_medicacion_previa(df_principal)
    df_tllg    = extraer_tiempos_llegada(df_principal)
    df_tint    = extraer_tiempos_intervencion(df_principal)
    df_intv    = extraer_intervalos(df_principal)
    df_scores  = extraer_scores_inicio(df_principal)
    df_proc    = extraer_procedimiento(df_principal)
    df_trat    = extraer_tratamiento_farm(df_principal)
    df_mat     = extraer_materiales(df_principal)
    df_infl2   = extraer_inflamacion(df_infl)
    df_lipid   = extraer_analitica_lipidos(df_as)
    df_metab   = extraer_analitica_metabolica(df_as)
    df_hep     = extraer_analitica_hepatica(df_as)
    df_prot    = extraer_analitica_proteinas(df_as)
    df_orina   = extraer_analitica_orina(df_as)
    df_pet     = extraer_analitica_peticion(df_as)
    df_alta    = extraer_alta_hospitalaria(df_principal, df_proc)
    df_recam   = extraer_resultado_recam(df_principal, df_proc)
    df_seg     = extraer_seguimiento(df_principal, df_proc)

    nhcs_validos = set(pd.to_numeric(df_pac["NHC"], errors="coerce").dropna())
    log.info(f"  NHCs válidos en PACIENTE: {len(nhcs_validos)}")

    # ── Filtrar huérfanos NHC (tablas analítica → PACIENTE) ───────────────────
    df_infl2 = filtrar_nhcs_huerfanos(df_infl2, nhcs_validos, "INFLAMACION")
    df_lipid = filtrar_nhcs_huerfanos(df_lipid, nhcs_validos, "ANALITICA_LIPIDOS")
    df_metab = filtrar_nhcs_huerfanos(df_metab, nhcs_validos, "ANALITICA_METABOLICA")
    df_hep   = filtrar_nhcs_huerfanos(df_hep,   nhcs_validos, "ANALITICA_HEPATICA")
    df_prot  = filtrar_nhcs_huerfanos(df_prot,  nhcs_validos, "ANALITICA_PROTEINAS")
    df_orina = filtrar_nhcs_huerfanos(df_orina, nhcs_validos, "ANALITICA_ORINA")
    df_pet   = filtrar_nhcs_huerfanos(df_pet,   nhcs_validos, "ANALITICA_PETICION")


    log.info("  Filtrando claves NHC+FECHA huérfanas respecto a TIEMPOS_LLEGADA...")
    df_tint   = filtrar_claves_huerfanas(df_tint,   df_tllg, "TIEMPOS_INTERVENCION",  "TIEMPOS_LLEGADA")
    df_intv   = filtrar_claves_huerfanas(df_intv,   df_tllg, "INTERVALOS_CALCULADOS", "TIEMPOS_LLEGADA")
    df_scores = filtrar_claves_huerfanas(df_scores, df_tllg, "SCORES_INICIO",          "TIEMPOS_LLEGADA")
    df_proc   = filtrar_claves_huerfanas(df_proc,   df_tllg, "PROCEDIMIENTO",          "TIEMPOS_LLEGADA")
    df_trat   = filtrar_claves_huerfanas(df_trat,   df_tllg, "TRATAMIENTO_FARM",       "TIEMPOS_LLEGADA")
    df_mat    = filtrar_claves_huerfanas(df_mat,    df_tllg, "MATERIALES_DISP",        "TIEMPOS_LLEGADA")
    df_alta   = filtrar_claves_huerfanas(df_alta,   df_tllg, "ALTA_HOSPITALARIA",      "TIEMPOS_LLEGADA")
    df_recam  = filtrar_claves_huerfanas(df_recam,  df_tllg, "RESULTADO_RECAM",        "TIEMPOS_LLEGADA")
    df_seg    = filtrar_claves_huerfanas(df_seg,    df_tllg, "SEGUIMIENTO",            "TIEMPOS_LLEGADA")

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

    log.info("\n  Limpiando tablas previas (orden inverso FK)...")
    tablas_orden_inverso = [
        "SEGUIMIENTO", "RESULTADO_RECAM", "ALTA_HOSPITALARIA",
        "ANALITICA_PETICION", "ANALITICA_ORINA", "ANALITICA_PROTEINAS",
        "ANALITICA_HEPATICA", "ANALITICA_METABOLICA", "ANALITICA_LIPIDOS",
        "INFLAMACION", "MATERIALES_DISP", "TRATAMIENTO_FARM",
        "PROCEDIMIENTO", "SCORES_INICIO", "INTERVALOS_CALCULADOS",
        "TIEMPOS_INTERVENCION", "TIEMPOS_LLEGADA",
        "MEDICACION_PREVIA", "ANTECEDENTES", "PACIENTE",
    ]
    with engine.begin() as conn:
        for tabla in tablas_orden_inverso:
            conn.execute(text(f"DELETE FROM {tabla}"))
            log.info(f"    Truncada: {tabla}")

    log.info("\n  Cargando tablas:")
    total = 0
    for tabla, df in cargas:
        total += cargar_tabla(engine, df, tabla)

    log.info(f"\n  Total filas cargadas: {total}")
    log.info("\n[OK]  Fase 4 completada.")


if __name__ == "__main__":
    run()