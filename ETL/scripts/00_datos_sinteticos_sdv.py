# -*- coding: utf-8 -*-
# =============================================================================
#  00_datos_sinteticos_sdv.py  --  Generación de datos sintéticos con SDV
# =============================================================================

import os
import re
import random
import warnings
import logging
from datetime import datetime, timedelta

import pandas as pd
from sdv.single_table import GaussianCopulaSynthesizer
from sdv.metadata import SingleTableMetadata

warnings.filterwarnings("ignore")

# ── Configuración ─────────────────────────────────────────────────────────────
XLSX_ORIGEN = os.path.join(os.path.dirname(__file__), "RegistroDatosIctus.xlsx")
XLSX_SALIDA = r"C:\Users\noebt\OneDrive\Escritorio\TFM\documentos\modelo\etl_ictus\source\datos_sinteticos.xlsx"

N_CONJUNTO    = 400
N_AS          = 2400
N_INFLAMACION = 140

COLS_ID_CONJUNTO    = ["PseudoID"]
COLS_ID_AS          = ["NHC HUMV"]
COLS_ID_INFLAMACION = ["NHC"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SINTÉTICOS] %(levelname)s -- %(message)s"
)
log = logging.getLogger(__name__)


# ── Utilidades ────────────────────────────────────────────────────────────────

def limpiar_para_sdv(df: pd.DataFrame) -> pd.DataFrame:
    n_antes = df.shape[1]
    df = df.dropna(axis=1, how="all")
    n_vacias = n_antes - df.shape[1]
    if n_vacias:
        log.info(f"  Eliminadas {n_vacias} columnas 100% vacías")

    UMBRAL_CATEGORIAS = 50
    cols_texto_libre = [
        col for col in df.select_dtypes(include="object").columns
        if df[col].nunique() > UMBRAL_CATEGORIAS
    ]
    if cols_texto_libre:
        log.info(f"  Columnas de texto libre descartadas ({len(cols_texto_libre)}): "
                 f"{cols_texto_libre[:5]}{'...' if len(cols_texto_libre) > 5 else ''}")
        df = df.drop(columns=cols_texto_libre)

    for col in df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
        df[col] = df[col].dt.strftime("%Y-%m-%d").fillna("")

    return df


def generar_hoja(df_real, n_filas, nombre, cols_id):
    log.info(f"\n{'='*60}")
    log.info(f"  Procesando hoja: {nombre} ({df_real.shape[0]} filas reales → {n_filas} sintéticas)")
    log.info(f"{'='*60}")

    cols_id_presentes = [c for c in cols_id if c in df_real.columns]
    df_train = df_real.drop(columns=cols_id_presentes, errors="ignore").copy()
    df_train = limpiar_para_sdv(df_train)
    log.info(f"  Shape tras limpieza: {df_train.shape}")

    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(df_train)
    log.info(f"  Metadatos detectados: {len(metadata.columns)} columnas")

    log.info("  Entrenando GaussianCopulaSynthesizer...")
    synthesizer = GaussianCopulaSynthesizer(
        metadata,
        enforce_min_max_values=True,
        enforce_rounding=True,
        default_distribution="norm",
    )
    synthesizer.fit(df_train)
    log.info("  Entrenamiento completado.")

    log.info(f"  Generando {n_filas} filas sintéticas...")
    df_sint = synthesizer.sample(num_rows=n_filas)
    log.info(f"  Generación completada. Shape: {df_sint.shape}")

    for col in cols_id_presentes:
        df_sint.insert(0, col, range(900000, 900000 + len(df_sint)))
    log.info(f"  IDs ficticios añadidos: {cols_id_presentes}")

    return df_sint


def verificar_similitud(df_real, df_sint, nombre):
    log.info(f"\n  --- Verificación estadística: {nombre} ---")
    cols_num     = df_real.select_dtypes(include="number").columns.tolist()
    cols_comunes = [c for c in cols_num if c in df_sint.columns][:8]
    for col in cols_comunes:
        log.info(f"    {col:30s} | Real: μ={df_real[col].mean():.2f} σ={df_real[col].std():.2f} | "
                 f"Sint: μ={df_sint[col].mean():.2f} σ={df_sint[col].std():.2f}")


# ── Pipeline principal ────────────────────────────────────────────────────────

def run():
    log.info("=" * 60)
    log.info("GENERACIÓN DE DATOS SINTÉTICOS CON SDV")
    log.info("=" * 60)

    if not os.path.exists(XLSX_ORIGEN):
        raise FileNotFoundError(f"No se encuentra el Excel original: {XLSX_ORIGEN}")

    os.makedirs(os.path.dirname(XLSX_SALIDA), exist_ok=True)

    # ── 1. Leer hojas reales ──────────────────────────────────────────────────
    log.info(f"\nLeyendo Excel real: {XLSX_ORIGEN}")
    df_conjunto    = pd.read_excel(XLSX_ORIGEN, sheet_name="Conjunto")
    df_as          = pd.read_excel(XLSX_ORIGEN, sheet_name="AS")
    df_inflamacion = pd.read_excel(XLSX_ORIGEN, sheet_name="Inflamación")
    log.info(f"  Conjunto: {df_conjunto.shape} | AS: {df_as.shape} | Inflamación: {df_inflamacion.shape}")

    # ── 2. Generar hoja Conjunto ──────────────────────────────────────────────
    df_sint_conjunto = generar_hoja(df_conjunto, N_CONJUNTO, "Conjunto", COLS_ID_CONJUNTO)
    verificar_similitud(df_conjunto, df_sint_conjunto, "Conjunto")

    # ── GARANTIZAR que TODOS los NHCs son ficticios y únicos ─────────────────
    # SDV puede generar valores numéricos que coincidan con NHCs reales
    nhc_cols = [c for c in df_sint_conjunto.columns
                if re.search(r'nhc|pseudo|nhc\.1', c, re.IGNORECASE)]
    log.info(f"  Columnas NHC a sobreescribir: {nhc_cols}")
    for col in nhc_cols:
        df_sint_conjunto[col] = range(900000, 900000 + len(df_sint_conjunto))
    df_sint_conjunto["PseudoID"] = range(900000, 900000 + len(df_sint_conjunto))
    log.info("   Todos los NHCs sobreescritos con valores ficticios únicos (900000+)")

    # ── Generar FECHA única por (PseudoID, FECHA) ─────────────────────────────
    n         = len(df_sint_conjunto)
    inicio_dt = datetime(2023, 1, 1)
    delta     = (datetime(2025, 12, 31) - inicio_dt).days

    nhcs          = df_sint_conjunto["PseudoID"].tolist()
    fechas_usadas = set()
    fechas        = []
    for nhc in nhcs:
        intentos = 0
        while True:
            fecha = (inicio_dt + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")
            clave = (nhc, fecha)
            if clave not in fechas_usadas:
                fechas_usadas.add(clave)
                fechas.append(fecha)
                break
            intentos += 1
            if intentos > 1000:
                fechas.append(f"{2023 + (len(fechas) % 3)}-01-01")
                break

    df_sint_conjunto["FECHA"]         = fechas
    df_sint_conjunto["Despertar"]     = random.choices(["Sí", "No", None], weights=[0.3, 0.6, 0.1], k=n)
    df_sint_conjunto["HoraTriaje"]    = [f"{random.randint(0,23):02d}:{random.randint(0,59):02d}" for _ in range(n)]
    df_sint_conjunto["ValoradoNeuro"] = [f"{random.randint(0,23):02d}:{random.randint(0,59):02d}" for _ in range(n)]
    log.info("  Columnas obligatorias reañadidas: FECHA, Despertar, HoraTriaje, ValoradoNeuro")

    # ── Campos de hora: muestreo desde datos reales con conversión de formato ─────

    def hora_a_string(val):
        """Convierte cualquier formato de hora a string HH:MM."""
        import datetime
        try:
            if isinstance(val, datetime.time):
                return f"{val.hour:02d}:{val.minute:02d}"
            if isinstance(val, float):
                # Fracción de día de Excel → HH:MM
                total_min = round(val * 24 * 60)
                return f"{(total_min // 60) % 24:02d}:{total_min % 60:02d}"
            if isinstance(val, str):
                # Limpiar espacios y tomar solo HH:MM
                val = val.strip().split(".")[0].strip()
                partes = val.split(":")
                if len(partes) >= 2:
                    return f"{int(partes[0]):02d}:{int(partes[1]):02d}"
        except:
            pass
        return None

    cols_horas = [
        "Horapuerta",
        "HoraTC",
        "LlamadaNeuro",
        "ultimaimagenTC",
        "HoraentradaSala",
        "HoraAguja",
        "Primerpase",
        "Perfusiónfibri",
    ]

    for col in cols_horas:
        if col in df_conjunto.columns:
            # Convertir todos los valores reales a HH:MM string
            valores_convertidos = [
                hora_a_string(v) 
                for v in df_conjunto[col].dropna().tolist()
            ]
            valores_limpios = [v for v in valores_convertidos if v is not None]
            
            if valores_limpios:
                if len(valores_limpios) >= n:
                    df_sint_conjunto[col] = random.sample(valores_limpios, k=n)
                else:
                    df_sint_conjunto[col] = random.choices(valores_limpios, k=n)
                log.info(f"   '{col}': {len(valores_limpios)} valores reales → formato HH:MM")
            else:
                log.warning(f"    '{col}': sin valores convertibles")
        else:
            log.warning(f"    '{col}': no existe en Conjunto real")


    cols_desde_real = [
            # ── PROCEDIMIENTO ─────────────────────────────────────────────────────
            "NiveldeObstrucción",     # → NivelObstruccion en SQL
            "Lugar Código",           # → LugarCodigo en SQL
            "LugarCódigo",            # → LugarCodigo en SQL (alias fusionado)
            "LugarCodigo",            # por si ya viene renombrado
            "Tipo de Cierre",         # → TipodeCierre
            "TipodeCierre",
            "TICI",
            "TICIfinal",
            "Complicaciones",         # → Complicaciones en SQL
            "ATP",
            "Recanalización",         # → Recanalizacion
            "RecanalizaciónCarótida", # → RecanalizacionCarotida
            "Hemoragia",              # → Hemoragia_texto
            "InfartoEstablecido",
            "Edema",
            "DesviaciónLM",
            "NottoIctus",
            "Missmatch",

            # ── MATERIALES_DISP ───────────────────────────────────────────────────
            "Stent",
            "Stentriever",

            # ── ALTA_HOSPITALARIA ─────────────────────────────────────────────────
            "FechadeAlta",
            "Fecha de Alta",          # nombre original en Excel
            "DestinoAlta",
            "Destino Alta",
            "ComplicacionesPost",     # → ComplicacionesPost en SQL
            "Complicaciones Post",    # nombre original en Excel
            "FA_Novo",
            "Causadelamuerte",

            # ── TRATAMIENTO_FARM ──────────────────────────────────────────────────
            "Fibrinolítico",
            "AnticoaIntrahosp",
            "NuevoAnticoaAlta",
        ]
    # Crear columnas que SDV eliminó completamente
    for col in cols_desde_real:
        if col in df_conjunto.columns and col not in df_sint_conjunto.columns:
            df_sint_conjunto[col] = None
            log.info(f"  Columna '{col}' creada (no existía en sintético)")

    # Rellenar nulos con valores reales muestreados
    for col in cols_desde_real:
        if col in df_conjunto.columns and col in df_sint_conjunto.columns:
            valores_reales = df_conjunto[col].dropna().tolist()
            if valores_reales:
                mask_nulos = df_sint_conjunto[col].isnull()
                n_nulos = mask_nulos.sum()
                if n_nulos > 0:
                    df_sint_conjunto.loc[mask_nulos, col] = random.choices(
                        valores_reales, k=n_nulos
                    )
                    log.info(f"   '{col}': {n_nulos} nulos rellenados con valores reales")

    # ── Campos clínicos con distribuciones específicas — muestrear del real ──
    cols_clinicos_desde_real = [
        # Tiempos — SDV no respeta rangos clínicos
        "TiempoPuertaTC",
        "TiempoPuertaSala",
        "TiempoPuertaPunción",
        "TiempoTCSala",
        "TiempoSalaPunción",
        "Tiempopuertarecanalización",
        "Tiempopunción1ºpase",
        "Tiempopunciónrecanalización",
        "TiempoSintomasPuerta",
        "TiempollamadaValoración",
        "TiempoValoraciónTC",
        "TiempoTC",
        "Tiemposíntomasrecanalización",

        # Resultados clínicos — distribuciones muy específicas
        "mRs90días",       
        "mRs inicio",
        "mRsalta",         
        "NIHSS inicio",
        "NIHSS24h",
        "NIHSSalta",
        "NIHSS alta",

        # NLR/PLR/PMR — valores con distribución sesgada
        "NLR_pre",
        "NLR_post",
        "PLR_pre",
        "PLR_post",
        "PMR_pre",
        "PMR_post",
    ]

    

    log.info("\n  Sobreescribiendo campos clínicos con muestreo del real...")
    for col in cols_clinicos_desde_real:
        if col in df_conjunto.columns:
            valores_reales = df_conjunto[col].dropna().tolist()
            if valores_reales:
                df_sint_conjunto[col] = random.choices(valores_reales, k=n)
                log.info(f"   '{col}': sobreescrito con muestreo real ({len(valores_reales)} valores)")
        else:
            log.warning(f"    '{col}': no existe en el Excel real — revisar nombre")

    # ── Garantizar FechadeAlta >= FECHA y estancia razonable ─────────────────
    if "FechadeAlta" in df_sint_conjunto.columns and "FECHA" in df_sint_conjunto.columns:
        
        # Obtener distribución real de estancias
        if "FechadeAlta" in df_conjunto.columns:
            estancias_reales = []
            for _, row in df_conjunto.iterrows():
                try:
                    fa = pd.to_datetime(row.get("FechadeAlta") or row.get("Fecha de Alta"))
                    fi = pd.to_datetime(row.get("FECHA"))
                    dias = (fa - fi).days
                    if 0 < dias <= 60:
                        estancias_reales.append(dias)
                except:
                    pass
            if not estancias_reales:
                estancias_reales = list(range(1, 20))
            log.info(f"  Estancias reales: min={min(estancias_reales)}, max={max(estancias_reales)}, media={sum(estancias_reales)/len(estancias_reales):.1f}")
        else:
            estancias_reales = list(range(1, 15))

        def ajustar_fecha_alta(row):
            try:
                fecha_ingreso = pd.to_datetime(row["FECHA"])
                estancia = random.choice(estancias_reales)
                return (fecha_ingreso + timedelta(days=estancia)).strftime("%Y-%m-%d")
            except:
                return None

        df_sint_conjunto["FechadeAlta"] = df_sint_conjunto.apply(ajustar_fecha_alta, axis=1)
        log.info("   FechadeAlta recalculada desde FECHA + estancia real muestreada")

    # ── SALVAGUARDA: eliminar duplicados (PseudoID, FECHA) residuales ─────────
    n_antes = len(df_sint_conjunto)
    df_sint_conjunto = df_sint_conjunto.drop_duplicates(subset=["PseudoID", "FECHA"])
    n_despues = len(df_sint_conjunto)
    if n_antes != n_despues:
        log.warning(f"    Eliminados {n_antes - n_despues} duplicados residuales")
    else:
        log.info("   Sin duplicados (NHC, FECHA) — integridad garantizada")

    # ── 3. Generar hoja AS ────────────────────────────────────────────────────
    df_sint_as = generar_hoja(df_as, N_AS, "AS", COLS_ID_AS)
    verificar_similitud(df_as, df_sint_as, "AS")

    # FIX: NHCs de AS = subconjunto de Conjunto (permite repeticiones → varios análisis por paciente)
    nhcs_conjunto = df_sint_conjunto["PseudoID"].tolist()
    df_sint_as["NHC HUMV"] = random.choices(nhcs_conjunto, k=len(df_sint_as))
    log.info(f"  NHCs de AS sincronizados con Conjunto ({len(df_sint_as)} filas)")


    # ── Rellenar columnas analíticas de AS con valores reales muestreados ─────
    cols_desde_real_as = [
        "PCR Ultrasensible suero",
         "Proteina C Reactiva (mg/dl)", 
        "Colesterol no HDL suero",
        "Colesterol suero",
        "HDL Colesterol suero",
        "LDL Colesterol (Friedewald) suero",
        "Trigliceridos suero",
        "Glucosa suero",
        "Hemoglobina glicada (HbA1c)",
        "Filtrado Glomerular estimado CKD-EPI suero",
    ]

    for col in cols_desde_real_as:
        # Si la columna existe en real pero no en sintético → crearla
        if col in df_as.columns and col not in df_sint_as.columns:
            valores_reales = df_as[col].dropna().tolist()
            if valores_reales:
                df_sint_as[col] = random.choices(valores_reales, k=len(df_sint_as))
                log.info(f"   AS '{col}': columna creada con valores reales")
        # Si existe en ambos → rellenar solo los nulos
        elif col in df_as.columns and col in df_sint_as.columns:
            valores_reales = df_as[col].dropna().tolist()
            if valores_reales:
                mask_nulos = df_sint_as[col].isnull()
                n_nulos = mask_nulos.sum()
                if n_nulos > 0:
                    df_sint_as.loc[mask_nulos, col] = random.choices(
                        valores_reales, k=n_nulos
                    )
                    log.info(f"   AS '{col}': {n_nulos} nulos rellenados")

    # ── 4. Generar hoja Inflamación ───────────────────────────────────────────
    df_sint_inflamacion = generar_hoja(df_inflamacion, N_INFLAMACION, "Inflamación", COLS_ID_INFLAMACION)
    verificar_similitud(df_inflamacion, df_sint_inflamacion, "Inflamación")

    # FIX: NHCs de Inflamación = subconjunto único de Conjunto
    df_sint_inflamacion["NHC"] = random.sample(nhcs_conjunto, k=len(df_sint_inflamacion))
    log.info(f"  NHCs de Inflamación sincronizados con Conjunto ({len(df_sint_inflamacion)} filas)")


    # ── Renombrar columnas para que coincidan con aliases del ETL ─────────────
    renombres_conjunto = {
        "Nivel de Obstrucción":   "NiveldeObstrucción",
        "Lugar Código":           "LugarCodigo",
        "LugarCódigo":            "LugarCodigo",
        "Tipo de Cierre":         "TipodeCierre",
        "Complicaciones Post":    "ComplicacionesPost",
        "Destino Alta":           "DestinoAlta",
        "Fecha de Alta":          "FechadeAlta",
        "FA Novo":                "FA_Novo",
    }
    for original, alias in renombres_conjunto.items():
        if original in df_sint_conjunto.columns and alias not in df_sint_conjunto.columns:
            df_sint_conjunto = df_sint_conjunto.rename(columns={original: alias})
            log.info(f"  Renombrada '{original}' → '{alias}'")

    # ── 5. Exportar a Excel ───────────────────────────────────────────────────
    log.info(f"\nExportando a: {XLSX_SALIDA}")
    with pd.ExcelWriter(XLSX_SALIDA, engine="openpyxl") as writer:
        df_sint_conjunto.to_excel(writer,   sheet_name="Conjunto",    index=False)
        df_sint_as.to_excel(writer,          sheet_name="AS",          index=False)
        df_sint_inflamacion.to_excel(writer, sheet_name="Inflamación", index=False)

    log.info("\n" + "=" * 60)
    log.info(" DATOS SINTÉTICOS GENERADOS CORRECTAMENTE")
    log.info(f"   Fichero: {XLSX_SALIDA}")
    log.info(f"   Conjunto:    {len(df_sint_conjunto)} filas, {df_sint_conjunto.shape[1]} columnas")
    log.info(f"   AS:          {len(df_sint_as)} filas, {df_sint_as.shape[1]} columnas")
    log.info(f"   Inflamación: {len(df_sint_inflamacion)} filas, {df_sint_inflamacion.shape[1]} columnas")
    log.info("=" * 60)
    log.info("\nPara usar los datos sintéticos en el ETL, modifica config.py:")
    log.info("  XLSX_PATH = os.path.join(BASE_DIR, 'source', 'datos_sinteticos.xlsx')")


if __name__ == "__main__":
    run()