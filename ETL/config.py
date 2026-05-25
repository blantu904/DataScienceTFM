# -*- coding: utf-8 -*-
# =============================================================================
#  config.py  —  Configuración global del ETL Ictus Cantabria
# =============================================================================

import os

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
XLSX_PATH = os.path.join(BASE_DIR, 'source', 'datos.xlsx')  #'datos_sinteticos.xlsx'
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
LOG_DIR    = os.path.join(BASE_DIR, "logs")

# ── Conexión SQL Server ───────────────────────────────────────────────────────
SQLSERVER_CONFIG = {
    "driver":   "ODBC Driver 17 for SQL Server",
    "server":   "localhost",
    "database": "ictus_cantabria",
    "username": "",
    "password": "",
    "trusted":  True,
}

# ── Hojas del Excel ───────────────────────────────────────────────────────────
SHEET_PRINCIPAL   = "Conjunto"
SHEET_AS          = "AS"
SHEET_INFLAMACION = "Inflamación"
SHEET_2024_25     = "2024-25"
SHEET_2024        = "2024"

# ── Prefijo de columnas analíticas fusionadas en Conjunto ────────────────────
ANEXAR_PREFIX = "Anexar1."

# ── Mapeo de columnas fuente → nombre canónico ────────────────────────────────
COL_ALIASES = {

    # ── Identificadores ───────────────────────────────────────────────────────
    "PseudoID":              "NHC",
    "NHC.1":                 "NHC_real",
    "Lugar Código":          "LugarCodigo",
    "LugarCódigo":           "LugarCodigo",
    "Etiología":             "Etiologia",

    # ── Campos clínicos con doble nombre ─────────────────────────────────────
    "NIHSS24h":              "NIHSS_24h",
    "NIHSS 24h":             "NIHSS_24h",
    "NIHSSalta":             "NIHSS_alta",
    "NIHSS alta":            "NIHSS_alta",
    "mRsalta":               "mRs_alta",
    "mRs alta":              "mRs_alta",
    "mRs90días":             "mRs_90dias",
    "mRs 90 días":           "mRs_90dias",
    "FechadeAlta":           "FechadeAlta",
    "Fecha de Alta":         "FechadeAlta",
    "FechaAlta":             "FechadeAlta",
    "DestinoAlta":           "DestinoAlta",
    "Destino Alta":          "DestinoAlta",
    "FANovo":                "FA_Novo",
    "FA Novo":               "FA_Novo",
    "FA_Novo":               "FA_Novo",
    "FAnovo.1":              "FAnovo_num",
    "CausaMuerte":           "Causadelamuerte",
    "Causa de la muerte":    "Causadelamuerte",
    "Causadelamuerte":       "Causadelamuerte",
    "Complicaciones Post":   "ComplicacionesPost",
    "Infarto Establecido":   "InfartoEstablecido",


    # ── Tiempos ───────────────────────────────────────────────────────────────
    " Hora TC":              "HoraTC",
    "Hora puerta":           "Horapuerta",
    "Hora entrada Sala":     "HoraentradaSala",
    "Hora Aguja":            "HoraAguja",
    "Hora Punción":          "HoraPuncion",
    "Primer pase":           "Primerpase",
    "Llamada Neuro":         "LlamadaNeuro",
    "Valorado Neuro":        "ValoradoNeuro",
    "ultima imagen TC":      "ultimaimagenTC",
    "Nivel de Obstrucción":  "NiveldeObstruccion",
    "Tipo de Cierre":        "TipodeCierre",
    "Incincia cierre":       "IncisionCierre",
    "Desviación LM":         "DesviaciónLM",
    "Hemorragia":            "Hemoragia",

    # ── Metadatos analítica ───────────────────────────────────────────────────
    "NHC HUMV":                       "NHC_real",
    "Edad del Paciente":              "Edad_AS",
    "Sexo del Paciente":              "Sexo_AS",
    "Fecha Formato Largo":            "Fecha_solicitud",
    "Número":                         "Numero_solicitud",
    "Doctor":                         "Doctor",
    "Centro":                         "Centro",
    "Servicio":                       "Servicio",
    "Centro de Procesamiento":        "Centro_procesamiento",
    "Diagnóstico":                    "Diagnostico_solicitud",
    "Ubicación":                      "Ubicacion",
    "Observaciones petición":         "Observaciones_peticion",
    "Información Adicional: 18630-4": "Info_adicional",
    "Patología (Descripción)":        "Patologia_descripcion",

    # ── Analítica ─────────────────────────────────────────────────────────────
    "Apolipoproteina A-I":                        "ApolipoproteínaAI",
    "Apolipoproteina B100":                       "ApolipoproteínaB100",
    "Homocisteína":                               "Homocisteina",
    "Lipoproteina (a)":                           "Lipoproteina_a",
    "PCR Ultrasensible suero":                    "PCR_Ultrasensible",
    "Filtrado Glomerular estimado CKD-EPI suero": "FiltradoGlomerularCKDEPI",
    "Proteina C Reactiva (mg/dl)":                "ProteinaCReactiva",
    "Colesterol no HDL suero":                    "ColesterolNoHDL",
    "LDL Colesterol (Friedewald) suero":          "LDLColesterol",
    "Trigliceridos suero":                        "Trigliceridos",
    "Proteinas Totales suero":                    "ProteinasTotales",
    "Prealbumina suero":                          "Prealbumina",
    "Albumina suero":                             "Albumina_suero",
    "Albumina en orina miccion aislada":          "AlbuminaOrina",
    "Creatinina en orina micción aislada":        "CreatininaOrina",
    "Ac Folico suero":                            "AcidoFolico",
    "Inmunofijacion suero":                       "Inmunofijacion",
    "Hemoglobina glicada (HbA1c)":                "HbA1c",
    "Beta Globulina %":                           "BetaGlobulina",
    "Densidad":                                   "DensidadOrina",
}

# ── Valores booleanos ─────────────────────────────────────────────────────────
BOOL_TRUE  = {"sí", "si", "yes", "1", "true", "s", "x"}
BOOL_FALSE = {"no", "0", "false", "n"}

# ── Rangos de validación ──────────────────────────────────────────────────────
VALID_RANGES = {
    "mRs_inicio":            (0, 5),
    "NIHSS_inicio":          (0, 42),
    "ASPECTS":               (0, 10),
    "mRs_alta":              (0, 6),
    "mRs_90dias":            (0, 6),
    "NIHSS_24h":             (0, 42),
    "NIHSS_alta":            (0, 42),
    "Oclusion_rec":          (1, 10),
    "anticoag_prev_rec":     (1, 5),
    "anticoagHosp_rec":      (1, 5),
    "iniciodesconocido_rec": (0, 2),
    "TH_rec":                (0, 6),
}

# ── Categorías normalizadas ───────────────────────────────────────────────────

GENERO_MAP = {
    "h": "H",  "hombre": "H", "masculino": "H", "male": "H", "varón": "H", "varon": "H",
    "m": "M",  "mujer":  "M", "femenino":  "M", "female": "M",
    # Códigos numéricos
    "1": "H", "2": "M",
}

LATERALIDAD_MAP = {
    "derecho": "Derecho", "dcho": "Derecho", "dcha": "Derecho", "d": "Derecho", "right": "Derecho",
    "izquierdo": "Izquierdo", "izdo": "Izquierdo", "izda": "Izquierdo", "i": "Izquierdo",
    "izquierda": "Izquierdo", "left": "Izquierdo",
    "bilateral": "Bilateral",
}

DESTINO_ALTA_MAP = {
    "domicilio": "Domicilio",
    "residencia": "Residencia",
    "exitus": "Exitus",
    "rehab": "Rehabilitación", "rehabilitación": "Rehabilitación", "rehabilitacion": "Rehabilitación",
    "traslado": "Traslado",
    "hospital": "Traslado",
}

PROCEDIMIENTO_MAP = {
    "trombectomia": "Trombectomía", "trombectomía": "Trombectomía", "tm": "Trombectomía",
    "fibrinolisis": "Fibrinolisis", "fibrinólisis": "Fibrinolisis", "rtpa": "Fibrinolisis",
    "fibri ia": "Fibrinolisis",
    "combinado": "Combinado",
    "atp+stent+tm": "Combinado", "atp+stent": "Combinado", "tm+atp": "Combinado",
    "tm+atp+stent": "Combinado", "tm+aspiración": "Combinado",
    "estudio angiográfico": "Estudio angiográfico",
    "nottoctus": "NottoIctus", "nottoictus": "NottoIctus", "no ictus": "NottoIctus",
    "conservador": "Conservador",
}

ETIOLOGIA_MAP = {
    "cardioembólico": "Cardioembólico", "cardioemboligénico": "Cardioembólico",
    "cardioembolico": "Cardioembólico", "embólico": "Cardioembólico",
    "aterotrombótico": "Aterotrombótico", "aterotrombotico": "Aterotrombótico",
    "aterosclerótico": "Aterotrombótico",
    "ateroembólico": "Ateroembólico",
    "lacunar": "Lacunar",
    "criptogénico": "Criptogénico", "criptogenico": "Criptogénico",
    "criptogénico embólico": "Criptogénico embólico",
    "indeterminado": "Indeterminado",
}

# ── Orden de carga (respeta FK) ───────────────────────────────────────────────
TABLA_ORDER = [
    "PACIENTE",
    "ANTECEDENTES",
    "MEDICACION_PREVIA",
    "TIEMPOS_LLEGADA",
    "TIEMPOS_INTERVENCION",
    "INTERVALOS_CALCULADOS",
    "SCORES_INICIO",
    "PROCEDIMIENTO",
    "TRATAMIENTO_FARM",
    "MATERIALES_DISP",
    "INFLAMACION",
    "ANALITICA_LIPIDOS",
    "ANALITICA_METABOLICA",
    "ANALITICA_HEPATICA",
    "ANALITICA_PROTEINAS",
    "ANALITICA_ORINA",
    "ANALITICA_PETICION",
    "ALTA_HOSPITALARIA",
    "RESULTADO_RECAM",
    "SEGUIMIENTO",
]