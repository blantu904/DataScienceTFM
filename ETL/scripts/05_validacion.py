# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# =============================================================================
#  05_validacion.py  --  FASE 5: Validación post-carga
#  VERSIÓN 2.0  —  SQL Server
# =============================================================================

import os
import sys
import logging
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OUTPUT_DIR, LOG_DIR, VALID_RANGES, SQLSERVER_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [VALIDACIÓN] %(levelname)s -- %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "05_validacion.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)
SEPARATOR = "-" * 60


# =============================================================================
#  Conexión SQL Server
# =============================================================================

def get_engine():
    cfg = SQLSERVER_CONFIG
    if cfg.get("trusted", True):
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
    return create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str)}")


# =============================================================================
#  Helpers
# =============================================================================

def q(conn, sql: str) -> pd.DataFrame:
    return pd.read_sql_query(text(sql), conn)


def check(conn, nombre: str, sql: str, esperado=None) -> bool:
    try:
        df = q(conn, sql)
        n   = len(df)
        val = df.iloc[0, 0] if (n == 1 and df.shape[1] == 1) else n

        if esperado is not None:
            ok = (val == esperado)
            log.info(f"  {'[OK]   ' if ok else '[ERROR]'}  {nombre}: {val}  (esperado: {esperado})")
            return ok
        else:
            ok = (n == 0)
            log.info(f"  {'[OK]   ' if ok else '[WARN] '}  {nombre}: {n} problemas")
            if n > 0:
                log.warning(f"         -> {df.to_string(index=False)}")
            return ok
    except Exception as e:
        log.error(f"  [ERROR]  {nombre}: {e}")
        return False


# =============================================================================
#  Pipeline de validación
# =============================================================================

def run():
    log.info("=" * 60)
    log.info("FASE 5 -- VALIDACIÓN POST-CARGA (SQL Server)")
    log.info("=" * 60)

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    log.info("  Conexión SQL Server OK\n")

    resultados = []

    with engine.connect() as conn:

        # -- 1. Conteos -------------------------------------------------------
        log.info(f"{SEPARATOR}")
        log.info("1. CONTEOS")
        log.info(SEPARATOR)

        checks_conteo = [
            ("Pacientes totales",             "SELECT COUNT(*) FROM PACIENTE",             400),
            ("Procedimientos",                "SELECT COUNT(*) FROM PROCEDIMIENTO",         None),
            ("Tiempos llegada",               "SELECT COUNT(*) FROM TIEMPOS_LLEGADA",       None),
            ("Tiempos intervención",          "SELECT COUNT(*) FROM TIEMPOS_INTERVENCION",  None),
            ("Intervalos calculados",         "SELECT COUNT(*) FROM INTERVALOS_CALCULADOS", None),
            ("Scores inicio",                 "SELECT COUNT(*) FROM SCORES_INICIO",         None),
            ("Antecedentes",                  "SELECT COUNT(*) FROM ANTECEDENTES",          None),
            ("Medicación previa",             "SELECT COUNT(*) FROM MEDICACION_PREVIA",     None),
            ("Tratamiento farmacológico",     "SELECT COUNT(*) FROM TRATAMIENTO_FARM",      None),
            ("Materiales",                    "SELECT COUNT(*) FROM MATERIALES_DISP",       None),
            ("Inflamación",                   "SELECT COUNT(*) FROM INFLAMACION",           None),
            ("Analítica lípidos",             "SELECT COUNT(*) FROM ANALITICA_LIPIDOS",     None),
            ("Analítica metabólica",          "SELECT COUNT(*) FROM ANALITICA_METABOLICA",  None),
            ("Analítica hepática",            "SELECT COUNT(*) FROM ANALITICA_HEPATICA",    None),
            ("Analítica proteínas",           "SELECT COUNT(*) FROM ANALITICA_PROTEINAS",   None),
            ("Analítica orina",               "SELECT COUNT(*) FROM ANALITICA_ORINA",       None),
            ("Analítica petición",            "SELECT COUNT(*) FROM ANALITICA_PETICION",    None),
            ("Alta hospitalaria",             "SELECT COUNT(*) FROM ALTA_HOSPITALARIA",     None),
            ("Resultado RECAM",               "SELECT COUNT(*) FROM RESULTADO_RECAM",       None),
            ("Seguimiento",                   "SELECT COUNT(*) FROM SEGUIMIENTO",           None),
        ]

        for nombre, sql, esperado in checks_conteo:
            df  = q(conn, sql)
            val = df.iloc[0, 0]
            if esperado:
                ok = (val == esperado)
                log.info(f"  {'[OK]   ' if ok else '[ERROR]'}  {nombre}: {val}  (esperado: {esperado})")
            else:
                log.info(f"  [INFO]   {nombre}: {val}")
            resultados.append({"check": nombre, "valor": val, "esperado": esperado,
                                "ok": (val == esperado) if esperado else None})

        # -- 2. Pacientes con >1 procedimiento --------------------------------
        log.info(f"\n{SEPARATOR}")
        log.info("2. PACIENTES CON >1 PROCEDIMIENTO")
        log.info(SEPARATOR)

        df_multi = q(conn, """
            SELECT NHC, COUNT(*) as n_proc
            FROM PROCEDIMIENTO
            GROUP BY NHC
            HAVING COUNT(*) > 1
            ORDER BY n_proc DESC
        """)
        log.info(f"  Pacientes con >1 procedimiento: {len(df_multi)}")
        if len(df_multi):
            log.info(f"\n{df_multi.to_string(index=False)}")

        # -- 3. Integridad referencial ----------------------------------------
        log.info(f"\n{SEPARATOR}")
        log.info("3. INTEGRIDAD REFERENCIAL (deben ser 0 huérfanos)")
        log.info(SEPARATOR)

        checks_fk = [
            ("Huérfanos ANTECEDENTES -> PACIENTE",
             "SELECT NHC FROM ANTECEDENTES WHERE NHC NOT IN (SELECT NHC FROM PACIENTE)"),
            ("Huérfanos MEDICACION_PREVIA -> PACIENTE",
             "SELECT NHC FROM MEDICACION_PREVIA WHERE NHC NOT IN (SELECT NHC FROM PACIENTE)"),
            ("Huérfanos TIEMPOS_LLEGADA -> PACIENTE",
             "SELECT NHC FROM TIEMPOS_LLEGADA WHERE NHC NOT IN (SELECT NHC FROM PACIENTE)"),
            ("Huérfanos PROCEDIMIENTO -> PACIENTE",
             "SELECT NHC FROM PROCEDIMIENTO WHERE NHC NOT IN (SELECT NHC FROM PACIENTE)"),
            ("Huérfanos INFLAMACION -> PACIENTE",
             "SELECT NHC FROM INFLAMACION WHERE NHC NOT IN (SELECT NHC FROM PACIENTE)"),
            ("Huérfanos ALTA_HOSPITALARIA -> PROCEDIMIENTO",
             """SELECT NHC FROM ALTA_HOSPITALARIA
                WHERE NHC NOT IN (SELECT NHC FROM PROCEDIMIENTO)"""),
            ("Huérfanos SEGUIMIENTO -> PROCEDIMIENTO",
             """SELECT NHC FROM SEGUIMIENTO
                WHERE NHC NOT IN (SELECT NHC FROM PROCEDIMIENTO)"""),
            ("Huérfanos RESULTADO_RECAM -> PROCEDIMIENTO",
             """SELECT NHC FROM RESULTADO_RECAM
                WHERE NHC NOT IN (SELECT NHC FROM PROCEDIMIENTO)"""),
        ]
        for nombre, sql in checks_fk:
            ok = check(conn, nombre, sql)
            resultados.append({"check": nombre, "ok": ok})

        # -- 4. Rangos --------------------------------------------------------
        log.info(f"\n{SEPARATOR}")
        log.info("4. VALIDACIÓN DE RANGOS")
        log.info(SEPARATOR)

        range_checks = [
            ("NIHSS_inicio [0-42]",
             "SELECT NHC, NIHSS_inicio FROM SCORES_INICIO WHERE NIHSS_inicio NOT BETWEEN 0 AND 42 AND NIHSS_inicio IS NOT NULL"),
            ("ASPECTS [0-10]",
             "SELECT NHC, ASPECTS FROM SCORES_INICIO WHERE ASPECTS NOT BETWEEN 0 AND 10 AND ASPECTS IS NOT NULL"),
            ("mRs_inicio [0-5]",
             "SELECT NHC, mRs_inicio FROM SCORES_INICIO WHERE mRs_inicio NOT BETWEEN 0 AND 5 AND mRs_inicio IS NOT NULL"),
            ("mRs_alta [0-6]",
             "SELECT NHC, mRs_alta FROM RESULTADO_RECAM WHERE mRs_alta NOT BETWEEN 0 AND 6 AND mRs_alta IS NOT NULL"),
            ("mRs_90dias [0-6]",
             "SELECT NHC, mRs_90dias FROM SEGUIMIENTO WHERE mRs_90dias NOT BETWEEN 0 AND 6 AND mRs_90dias IS NOT NULL"),
            ("NIHSS_24h [0-42]",
             "SELECT NHC, NIHSS_24h FROM RESULTADO_RECAM WHERE NIHSS_24h NOT BETWEEN 0 AND 42 AND NIHSS_24h IS NOT NULL"),
            ("Oclusion_rec [1-10]",
             "SELECT NHC, Oclusion_rec FROM PROCEDIMIENTO WHERE Oclusion_rec NOT BETWEEN 1 AND 10 AND Oclusion_rec IS NOT NULL"),
            ("anticoag_prev_rec [1-5]",
             "SELECT NHC, anticoag_prev_rec FROM MEDICACION_PREVIA WHERE anticoag_prev_rec NOT BETWEEN 1 AND 5 AND anticoag_prev_rec IS NOT NULL"),
            ("anticoagHosp_rec [1-5]",
             "SELECT NHC, anticoagHosp_rec FROM TRATAMIENTO_FARM WHERE anticoagHosp_rec NOT BETWEEN 1 AND 5 AND anticoagHosp_rec IS NOT NULL"),
            ("TH_rec [0-6]",
             "SELECT NHC, TH_rec FROM PROCEDIMIENTO WHERE TH_rec NOT BETWEEN 0 AND 6 AND TH_rec IS NOT NULL"),
            ("iniciodesconocido_rec [0-2]",
             "SELECT NHC, iniciodesconocido_rec FROM PROCEDIMIENTO WHERE iniciodesconocido_rec NOT BETWEEN 0 AND 2 AND iniciodesconocido_rec IS NOT NULL"),
        ]
        for nombre, sql in range_checks:
            ok = check(conn, nombre, sql)
            resultados.append({"check": nombre, "ok": ok})

        # -- 5. Campos requeridos ---------------------------------------------
        log.info(f"\n{SEPARATOR}")
        log.info("5. CAMPOS REQUERIDOS")
        log.info(SEPARATOR)

        req_checks = [
            ("PACIENTE.NHC no nulo",
             "SELECT COUNT(*) FROM PACIENTE WHERE NHC IS NULL"),
            ("PACIENTE.Edad no nulo",
             "SELECT COUNT(*) FROM PACIENTE WHERE Edad IS NULL"),
            ("PROCEDIMIENTO.Procedimiento no nulo",
             "SELECT COUNT(*) FROM PROCEDIMIENTO WHERE Procedimiento IS NULL OR Procedimiento = ''"),
            ("SCORES_INICIO.NIHSS_inicio no nulo",
             "SELECT COUNT(*) FROM SCORES_INICIO WHERE NIHSS_inicio IS NULL"),
            ("SCORES_INICIO.ASPECTS no nulo",
             "SELECT COUNT(*) FROM SCORES_INICIO WHERE ASPECTS IS NULL"),
            ("TIEMPOS_LLEGADA.T_SintomasPuerta no nulo",
             "SELECT COUNT(*) FROM INTERVALOS_CALCULADOS WHERE T_SintomasPuerta IS NULL"),
        ]
        for nombre, sql in req_checks:
            df     = q(conn, sql)
            n_null = df.iloc[0, 0]
            ok     = (n_null == 0)
            log.info(f"  {'[OK]   ' if ok else '[WARN] '}  {nombre}: {n_null} NULL")
            resultados.append({"check": nombre, "valor": n_null, "ok": ok})

        # -- 6. Distribuciones campos REC -------------------------------------
        log.info(f"\n{SEPARATOR}")
        log.info("6. DISTRIBUCIONES CAMPOS REC")
        log.info(SEPARATOR)

        dist_checks = [
            ("anticoag_prev_rec",     "MEDICACION_PREVIA"),
            ("Oclusion_rec",          "PROCEDIMIENTO"),
            ("iniciodesconocido_rec", "PROCEDIMIENTO"),
            ("anticoagHosp_rec",      "TRATAMIENTO_FARM"),
            ("TH_rec",                "PROCEDIMIENTO"),
            ("mRs_90dias",            "SEGUIMIENTO"),
            ("mRs_alta",              "RESULTADO_RECAM"),
        ]
        for campo, tabla in dist_checks:
            try:
                df_dist = q(conn, f"""
                    SELECT {campo}, COUNT(*) as n
                    FROM {tabla}
                    WHERE {campo} IS NOT NULL
                    GROUP BY {campo}
                    ORDER BY {campo}
                """)
                n_null = q(conn, f"SELECT COUNT(*) FROM {tabla} WHERE {campo} IS NULL").iloc[0, 0]
                log.info(f"\n  {campo} ({tabla}):")
                if not df_dist.empty:
                    log.info(f"\n{df_dist.to_string(index=False)}")
                log.info(f"    NULL: {n_null}")
            except Exception as e:
                log.warning(f"  {campo}: no se pudo calcular — {e}")

    # -- 7. Resumen final -----------------------------------------------------
    log.info(f"\n{SEPARATOR}")
    log.info("RESUMEN")
    log.info(SEPARATOR)

    df_res        = pd.DataFrame(resultados)
    checks_con_ok = df_res[df_res["ok"].notna()]
    n_ok  = (checks_con_ok["ok"] == True).sum()
    n_ko  = (checks_con_ok["ok"] == False).sum()
    log.info(f"  Checks OK  : {n_ok}")
    log.info(f"  Checks FAIL: {n_ko}")

    ruta_informe = os.path.join(OUTPUT_DIR, "informe_validacion.csv")
    df_res.to_csv(ruta_informe, index=False)
    log.info(f"\n  Informe exportado -> {ruta_informe}")

    if n_ko > 0:
        log.warning(f"\n[WARN]  {n_ko} validaciones fallaron — revisar logs.")
    else:
        log.info("\n[OK]  Fase 5 completada — todas las validaciones pasaron.")

    return n_ko == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)