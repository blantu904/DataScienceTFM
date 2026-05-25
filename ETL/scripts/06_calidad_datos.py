# -*- coding: utf-8 -*-
# =============================================================================
#  06_calidad_datos.py  -  FASE 6: Control de calidad y completitud de datos
#  VERSION 2.0 - Nombres de columna corregidos segun INFORMATION_SCHEMA
# =============================================================================

import os, sys, logging, pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOG_DIR, SQLSERVER_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CALIDAD] %(levelname)s -- %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "06_calidad_datos.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# =============================================================================
#  Variables a monitorizar - nombres verificados contra INFORMATION_SCHEMA
#  Formato: (Tabla, Columna, Descripcion, Categoria)
# =============================================================================
VARIABLES_MONITORIZAR = [

    # ── PACIENTE ──────────────────────────────────────────────────────────────
    ("PACIENTE",        "NHC",              "Identificador paciente",       "Demografico"),
    ("PACIENTE",        "Edad",             "Edad del paciente",            "Demografico"),
    ("PACIENTE",        "Genero",           "Sexo del paciente",            "Demografico"),
    ("PACIENTE",        "Hemisferio",       "Hemisferio afectado",          "Demografico"),
    ("PACIENTE",        "FOP",              "Foramen oval permeable",       "Demografico"),

    # ── ANTECEDENTES ──────────────────────────────────────────────────────────
    ("ANTECEDENTES",    "HTA",              "Hipertension arterial",        "Antecedentes"),
    ("ANTECEDENTES",    "DM",               "Diabetes mellitus",            "Antecedentes"),
    ("ANTECEDENTES",    "FAconocida",       "Fibrilacion auricular conocida","Antecedentes"),
    ("ANTECEDENTES",    "Dislipemia",       "Dislipemia",                   "Antecedentes"),
    ("ANTECEDENTES",    "Tabaquismo",       "Tabaquismo",                   "Antecedentes"),
    ("ANTECEDENTES",    "ACV_previo",       "ACV previo",                   "Antecedentes"),
    ("ANTECEDENTES",    "AIT_previo",       "AIT previo",                   "Antecedentes"),
    ("ANTECEDENTES",    "CardiopatiaIsq",   "Cardiopatia isquemica",        "Antecedentes"),
    ("ANTECEDENTES",    "Obesidad",         "Obesidad",                     "Antecedentes"),
    ("ANTECEDENTES",    "IRC",              "Insuf. renal cronica",         "Antecedentes"),
    ("ANTECEDENTES",    "Etiologia",        "Etiologia del ictus",          "Antecedentes"),

    # ── TIEMPOS_LLEGADA ───────────────────────────────────────────────────────
    ("TIEMPOS_LLEGADA", "Horapuerta",       "Hora de puerta",               "Tiempos"),
    ("TIEMPOS_LLEGADA", "HoraTC",           "Hora de TC",                   "Tiempos"),
    ("TIEMPOS_LLEGADA", "InicioSintomas",   "Hora inicio sintomas",         "Tiempos"),
    ("TIEMPOS_LLEGADA", "LlamadaNeuro",     "Hora llamada neurologo",       "Tiempos"),
    ("TIEMPOS_LLEGADA", "ValoradoNeuro",    "Hora valorado neurologo",      "Tiempos"),
    ("TIEMPOS_LLEGADA", "Turno",            "Turno de llegada",             "Tiempos"),
    ("TIEMPOS_LLEGADA", "Horario",          "Franja horaria",               "Tiempos"),
    ("TIEMPOS_LLEGADA", "ultimaimagenTC",   "Ultima imagen TC",             "Tiempos"),

    # ── SCORES_INICIO ─────────────────────────────────────────────────────────
    ("SCORES_INICIO",   "NIHSS_inicio",     "NIHSS al inicio",              "Clinico"),
    ("SCORES_INICIO",   "ASPECTS",          "ASPECTS",                      "Clinico"),
    ("SCORES_INICIO",   "mRs_inicio",       "Rankin previo al ictus",       "Clinico"),

    # ── PROCEDIMIENTO ─────────────────────────────────────────────────────────
    ("PROCEDIMIENTO",   "Procedimiento",    "Tipo de procedimiento",        "Procedimiento"),
    ("PROCEDIMIENTO",   "NivelObstruccion", "Nivel de obstruccion",         "Procedimiento"),
    ("PROCEDIMIENTO",   "TICIfinal",        "TICI final",                   "Procedimiento"),
    ("PROCEDIMIENTO",   "Complicaciones",   "Complicaciones",               "Procedimiento"),
    ("PROCEDIMIENTO",   "TH_rec",           "Transformacion hemorragica",   "Procedimiento"),
    ("PROCEDIMIENTO",   "Recanalizacion",   "Recanaligacion",               "Procedimiento"),
    ("PROCEDIMIENTO",   "Oclusion_rec",     "Oclusion recodificada",        "Procedimiento"),
    ("PROCEDIMIENTO",   "ATP",              "Uso de ATP/stent",             "Procedimiento"),

    # ── RESULTADO_RECAM ───────────────────────────────────────────────────────
    ("RESULTADO_RECAM", "NIHSS_24h",        "NIHSS a las 24h",              "Resultado"),
    ("RESULTADO_RECAM", "NIHSS_alta",       "NIHSS al alta",                "Resultado"),
    ("RESULTADO_RECAM", "mRs_alta",         "mRS al alta",                  "Resultado"),
    ("RESULTADO_RECAM", "Pases",            "Numero de pases",              "Resultado"),
    ("RESULTADO_RECAM", "TICI",             "TICI",                         "Resultado"),
    ("RESULTADO_RECAM", "Recanalizacion",   "Recanalizacion",               "Resultado"),

    # ── SEGUIMIENTO ───────────────────────────────────────────────────────────
    ("SEGUIMIENTO",     "mRs_90dias",       "mRS a 90 dias",                "Seguimiento"),
    ("SEGUIMIENTO",     "AcudenVisita90d",  "Acuden a visita 90 dias",      "Seguimiento"),

    # ── ALTA_HOSPITALARIA ─────────────────────────────────────────────────────
    ("ALTA_HOSPITALARIA","DestinoAlta",     "Destino al alta",              "Alta"),
    ("ALTA_HOSPITALARIA","FechadeAlta",     "Fecha de alta",                "Alta"),
    ("ALTA_HOSPITALARIA","ComplicacionesPost","Complicaciones post",        "Alta"),
    ("ALTA_HOSPITALARIA","FA_Novo",         "FA de novo",                   "Alta"),
    ("ALTA_HOSPITALARIA","Causadelamuerte", "Causa de la muerte",           "Alta"),
]


# =============================================================================
#  Funciones auxiliares
# =============================================================================

def get_engine():
    cfg = SQLSERVER_CONFIG
    conn_str = (
        f"DRIVER={{{cfg['driver']}}};SERVER={cfg['server']};DATABASE={cfg['database']};Trusted_Connection=yes;"
        if cfg["trusted"] else
        f"DRIVER={{{cfg['driver']}}};SERVER={cfg['server']};DATABASE={cfg['database']};UID={cfg['username']};PWD={cfg['password']};"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}")


def calcular_missing(engine, tabla, columna):
    try:
        q = f"""
            SELECT COUNT(*) AS total,
            SUM(CASE
                WHEN [{columna}] IS NULL THEN 1
                WHEN CAST([{columna}] AS NVARCHAR(MAX)) IN ('','-','Sin dato','sin dato','No consta') THEN 1
                ELSE 0
            END) AS missing
            FROM [{tabla}]
        """
        with engine.connect() as conn:
            r = conn.execute(text(q)).fetchone()
            return (r[0] or 0), (r[1] or 0)
    except Exception as e:
        log.warning(f"  SKIP {tabla}.{columna}: {e}")
        return None, None


def estado_calidad(pct):
    if pct is None: return "Sin datos"
    if pct == 0:    return "Completo"
    if pct <= 5:    return "Aceptable"
    if pct <= 20:   return "Mejorable"
    return "Critico"


def crear_tabla_calidad(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='CALIDAD_DATOS' AND xtype='U')
            CREATE TABLE CALIDAD_DATOS (
                ID           INT IDENTITY(1,1) PRIMARY KEY,
                Tabla        NVARCHAR(100),
                Columna      NVARCHAR(100),
                Descripcion  NVARCHAR(200),
                Categoria    NVARCHAR(100),
                N_Total      INT,
                N_Rellenos   INT,
                N_Missing    INT,
                Pct_Missing  FLOAT,
                Estado       NVARCHAR(50),
                FechaCalculo NVARCHAR(30)
            )
        """))
        conn.execute(text("DELETE FROM CALIDAD_DATOS"))
    log.info("  Tabla CALIDAD_DATOS preparada.")


# =============================================================================
#  Funcion principal
# =============================================================================

def run():
    log.info("=" * 70)
    log.info("  FASE 6 - Control de calidad y completitud de datos")
    log.info("=" * 70)

    engine = get_engine()
    fecha  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    crear_tabla_calidad(engine)

    filas = []
    log.info(f"\n  Calculando missing para {len(VARIABLES_MONITORIZAR)} variables...\n")

    for tabla, columna, descripcion, categoria in VARIABLES_MONITORIZAR:
        total, missing = calcular_missing(engine, tabla, columna)
        if total is None:
            continue

        pct    = round(missing / total * 100, 2) if total > 0 else 0.0
        estado = estado_calidad(pct)

        filas.append({
            "Tabla":        tabla,
            "Columna":      columna,
            "Descripcion":  descripcion,
            "Categoria":    categoria,
            "N_Total":      total,
            "N_Rellenos":   total - missing,
            "N_Missing":    missing,
            "Pct_Missing":  pct,
            "Estado":       estado,
            "FechaCalculo": fecha,
        })

        icono = "[OK]" if estado == "Completo" else "[~~]" if estado == "Aceptable" else "[!!]" if estado == "Mejorable" else "[XX]"
        log.info(f"  {icono}  {tabla:30s} | {columna:30s} | {pct:5.1f}% | {estado}")

    df = pd.DataFrame(filas)
    df.to_sql("CALIDAD_DATOS", engine, if_exists="append", index=False)

    # Resumen
    log.info("\n" + "=" * 70)
    log.info("  RESUMEN")
    log.info("=" * 70)
    log.info(f"  Total monitorizadas : {len(df)}")
    log.info(f"  Completas  (0%)     : {(df['Estado'] == 'Completo').sum()}")
    log.info(f"  Aceptables (1-5%)   : {(df['Estado'] == 'Aceptable').sum()}")
    log.info(f"  Mejorables (6-20%)  : {(df['Estado'] == 'Mejorable').sum()}")
    log.info(f"  Criticas   (>20%)   : {(df['Estado'] == 'Critico').sum()}")

    criticas = df[df['Estado'] == 'Critico']
    if not criticas.empty:
        log.info("\n  Variables criticas:")
        for _, row in criticas.iterrows():
            log.info(f"    !! {row['Tabla']:30s} | {row['Columna']:30s} | {row['Pct_Missing']:.1f}%")

    log.info("\n[OK]  Fase 6 completada.")
    return df


if __name__ == "__main__":
    run()