-- =============================================================================
--  ddl_sqlserver_recrear.sql  —  Modelo de datos Ictus Cantabria
--  Elimina y recrea todas las tablas en orden correcto (respeta FK)
-- =============================================================================

-- USE ictusTFM;   


-- =============================================================================
--  1. DROP en orden inverso a las FK (hijos antes que padres)
-- =============================================================================
IF OBJECT_ID('SEGUIMIENTO',           'U') IS NOT NULL DROP TABLE SEGUIMIENTO;
IF OBJECT_ID('RESULTADO_RECAM',       'U') IS NOT NULL DROP TABLE RESULTADO_RECAM;
IF OBJECT_ID('ALTA_HOSPITALARIA',     'U') IS NOT NULL DROP TABLE ALTA_HOSPITALARIA;
IF OBJECT_ID('ANALITICA_PETICION',    'U') IS NOT NULL DROP TABLE ANALITICA_PETICION;
IF OBJECT_ID('ANALITICA_ORINA',       'U') IS NOT NULL DROP TABLE ANALITICA_ORINA;
IF OBJECT_ID('ANALITICA_PROTEINAS',   'U') IS NOT NULL DROP TABLE ANALITICA_PROTEINAS;
IF OBJECT_ID('ANALITICA_HEPATICA',    'U') IS NOT NULL DROP TABLE ANALITICA_HEPATICA;
IF OBJECT_ID('ANALITICA_METABOLICA',  'U') IS NOT NULL DROP TABLE ANALITICA_METABOLICA;
IF OBJECT_ID('ANALITICA_LIPIDOS',     'U') IS NOT NULL DROP TABLE ANALITICA_LIPIDOS;
IF OBJECT_ID('INFLAMACION',           'U') IS NOT NULL DROP TABLE INFLAMACION;
IF OBJECT_ID('MATERIALES_DISP',       'U') IS NOT NULL DROP TABLE MATERIALES_DISP;
IF OBJECT_ID('TRATAMIENTO_FARM',      'U') IS NOT NULL DROP TABLE TRATAMIENTO_FARM;
IF OBJECT_ID('PROCEDIMIENTO',         'U') IS NOT NULL DROP TABLE PROCEDIMIENTO;
IF OBJECT_ID('SCORES_INICIO',         'U') IS NOT NULL DROP TABLE SCORES_INICIO;
IF OBJECT_ID('INTERVALOS_CALCULADOS', 'U') IS NOT NULL DROP TABLE INTERVALOS_CALCULADOS;
IF OBJECT_ID('TIEMPOS_INTERVENCION',  'U') IS NOT NULL DROP TABLE TIEMPOS_INTERVENCION;
IF OBJECT_ID('TIEMPOS_LLEGADA',       'U') IS NOT NULL DROP TABLE TIEMPOS_LLEGADA;
IF OBJECT_ID('MEDICACION_PREVIA',     'U') IS NOT NULL DROP TABLE MEDICACION_PREVIA;
IF OBJECT_ID('ANTECEDENTES',          'U') IS NOT NULL DROP TABLE ANTECEDENTES;
IF OBJECT_ID('PACIENTE',              'U') IS NOT NULL DROP TABLE PACIENTE;
IF OBJECT_ID('CALIDAD_DATOS',         'U') IS NOT NULL DROP TABLE CALIDAD_DATOS;
-- =============================================================================
--  2. CREATE TABLE en orden correcto (padres antes que hijos)
-- =============================================================================

-- ── PACIENTE ─────────────────────────────────────────────────────────────────
CREATE TABLE PACIENTE (
    NHC        INT          NOT NULL,
    Edad       INT,
    Genero     NVARCHAR(1),          -- 'H' = hombre, 'M' = mujer
    Hemisferio NVARCHAR(20),
    FOP        INT,
    CONSTRAINT PK_PACIENTE PRIMARY KEY (NHC)
);

-- ── ANTECEDENTES ─────────────────────────────────────────────────────────────
CREATE TABLE ANTECEDENTES (
    ID_Antecedente INT IDENTITY(1,1) NOT NULL,
    NHC            INT           NOT NULL,
    FAconocida     NVARCHAR(100),
    FA_num         INT,
    HTA            NVARCHAR(10),
    DM             NVARCHAR(10),
    Dislipemia     NVARCHAR(10),
    Tabaquismo     NVARCHAR(30),
    Obesidad       NVARCHAR(10),
    CardiopatiaIsq NVARCHAR(10),
    IC             NVARCHAR(10),
    EPOC           NVARCHAR(10),
    IRC            NVARCHAR(10),
    ACV_previo     NVARCHAR(10),
    AIT_previo     NVARCHAR(10),
    Etiologia      NVARCHAR(100),
    CONSTRAINT PK_ANTECEDENTES   PRIMARY KEY (ID_Antecedente),
    CONSTRAINT FK_ANTEC_PACIENTE FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);

-- ── MEDICACION_PREVIA ─────────────────────────────────────────────────────────
CREATE TABLE MEDICACION_PREVIA (
    ID_MedPrev        INT IDENTITY(1,1) NOT NULL,
    NHC               INT           NOT NULL,
    anticoag_prev_rec INT,
    AnticoagPrev      NVARCHAR(100),
    anticoag_num      INT,
    AntiagrePrev      NVARCHAR(100),
    CONSTRAINT PK_MEDPREV     PRIMARY KEY (ID_MedPrev),
    CONSTRAINT FK_MEDPREV_PAC FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);

-- ── TIEMPOS_LLEGADA ───────────────────────────────────────────────────────────
CREATE TABLE TIEMPOS_LLEGADA (
    NHC            INT          NOT NULL,
    FECHA          NVARCHAR(20) NOT NULL,
    InicioSintomas NVARCHAR(20),
    Despertar      NVARCHAR(20),
    Horapuerta     NVARCHAR(20),
    HoraTriaje     NVARCHAR(20),
    LlamadaNeuro   NVARCHAR(20),
    ValoradoNeuro  NVARCHAR(20),
    HoraTC         NVARCHAR(20),
    ultimaimagenTC NVARCHAR(20),
    Turno          VARCHAR(20)  NULL,
    Horario        VARCHAR(20)  NULL,
    Dia            VARCHAR(20)  NULL,
    CONSTRAINT PK_TIEMPOS_LLEGADA PRIMARY KEY (NHC, FECHA),
    CONSTRAINT FK_TLLG_PAC        FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);

-- ── TIEMPOS_INTERVENCION ──────────────────────────────────────────────────────
CREATE TABLE TIEMPOS_INTERVENCION (
    NHC             INT          NOT NULL,
    FECHA           NVARCHAR(20) NOT NULL,
    HoraentradaSala NVARCHAR(20),
    HoraPuncion     NVARCHAR(20),
    HoraAguja       NVARCHAR(20),
    Perfusionfibri  VARCHAR(255) NULL,
    Primerpase      NVARCHAR(20),
    CONSTRAINT PK_TIEMPOS_INT  PRIMARY KEY (NHC, FECHA),
    CONSTRAINT FK_TINT_LLEGADA FOREIGN KEY (NHC, FECHA) REFERENCES TIEMPOS_LLEGADA(NHC, FECHA)
);

-- ── INTERVALOS_CALCULADOS ─────────────────────────────────────────────────────
CREATE TABLE INTERVALOS_CALCULADOS (
    NHC                      INT          NOT NULL,
    FECHA                    NVARCHAR(20) NOT NULL,
    T_SintomasPuerta         INT,
    T_PuertaValoracion       INT,
    T_LlamadaValoracion      INT,
    T_ValoraciónTC           INT,
    T_PuertaTC               INT,
    T_TC                     INT,
    T_PuertaSala             INT,
    T_TCSala                 INT,
    T_PuertaPuncion          INT,
    T_SalaPuncion            INT,
    T_PuertaRecanalizacion   VARCHAR(20)  NULL,
    T_Puncion1Pase           INT,
    T_PuncionRecanalizacion  INT,
    T_SintomasRecanalizacion INT,
    CONSTRAINT PK_INTERVALOS   PRIMARY KEY (NHC, FECHA),
    CONSTRAINT FK_INTV_LLEGADA FOREIGN KEY (NHC, FECHA) REFERENCES TIEMPOS_LLEGADA(NHC, FECHA)
);

-- ── SCORES_INICIO ─────────────────────────────────────────────────────────────
CREATE TABLE SCORES_INICIO (
    NHC          INT          NOT NULL,
    FECHA        NVARCHAR(20) NOT NULL,
    mRs_inicio   INT,
    NIHSS_inicio INT,
    ASPECTS      INT,
    CONSTRAINT PK_SCORES         PRIMARY KEY (NHC, FECHA),
    CONSTRAINT FK_SCORES_LLEGADA FOREIGN KEY (NHC, FECHA) REFERENCES TIEMPOS_LLEGADA(NHC, FECHA)
);

-- ── PROCEDIMIENTO ─────────────────────────────────────────────────────────────
CREATE TABLE PROCEDIMIENTO (
    NHC                    INT           NOT NULL,
    FECHA                  NVARCHAR(20)  NOT NULL,
    Oclusion_rec           INT,
    NivelObstruccion       VARCHAR(255)  NULL,
    iniciodesconocido_rec  INT,
    Missmatch              NVARCHAR(10),
    Lateralidad            NVARCHAR(20),
    Procedimiento          NVARCHAR(60),
    NottoIctus             INT,
    TICI                   NVARCHAR(10),
    TICIfinal              INT,   
    Recanalizacion         VARCHAR(50)   NULL,
    RecanalizacionCarotida VARCHAR(100)  NULL,
    TH_rec                 INT,
    Hemoragia_texto        VARCHAR(255)  NULL,
    InfartoEstablecido     NVARCHAR(20),
    Edema                  NVARCHAR(20),
    DesviaciónLM           NVARCHAR(20),
    Complicaciones         VARCHAR(500)  NULL,
    LugarCodigo            NVARCHAR(200),
    ATP                    INT,
    CONSTRAINT PK_PROC    PRIMARY KEY (NHC, FECHA),
    CONSTRAINT FK_PROC_PAC FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);




-- ── TRATAMIENTO_FARM ──────────────────────────────────────────────────────────
CREATE TABLE TRATAMIENTO_FARM (
    NHC              INT          NOT NULL,
    FECHA            NVARCHAR(20) NOT NULL,
    Fibrinolitico    NVARCHAR(60),
    FIV              INT,
    FIVia            INT,
    anticoagHosp_rec INT,
    AnticoaIntrahosp NVARCHAR(100),
    NuevoAnticoaAlta NVARCHAR(100),
    CONSTRAINT PK_TRAT      PRIMARY KEY (NHC, FECHA),
    CONSTRAINT FK_TRAT_PROC FOREIGN KEY (NHC, FECHA) REFERENCES PROCEDIMIENTO(NHC, FECHA)
);

-- ── MATERIALES_DISP ───────────────────────────────────────────────────────────
-- SALA4o32, salaocupada, BB: sin datos en el Excel fuente
CREATE TABLE MATERIALES_DISP (
    NHC          INT          NOT NULL,
    FECHA        NVARCHAR(20) NOT NULL,
    Pases        INT,
    Stent        NVARCHAR(200),
    Stentriever  NVARCHAR(60),
    TipodeCierre NVARCHAR(60),
    SALA4o32     NVARCHAR(10),
    salaocupada  NVARCHAR(10),
    BB           NVARCHAR(10),
    CONSTRAINT PK_MAT      PRIMARY KEY (NHC, FECHA),
    CONSTRAINT FK_MAT_PROC FOREIGN KEY (NHC, FECHA) REFERENCES PROCEDIMIENTO(NHC, FECHA)
);

-- ── INFLAMACION ───────────────────────────────────────────────────────────────
CREATE TABLE INFLAMACION (
    ID_Inflamacion  INT IDENTITY(1,1) NOT NULL,
    NHC             INT  NOT NULL,
    Neutrofilos_pre FLOAT, Linfocitos_pre FLOAT, Monocitos_pre  FLOAT,
    Plaquetas_pre   FLOAT, PCR_pre        FLOAT,
    NLR_pre         FLOAT, PMR_pre        FLOAT, PLR_pre        FLOAT,
    Neutrofilos_post FLOAT, Linfocitos_post FLOAT, Monocitos_post FLOAT,
    Plaquetas_post  FLOAT, PCR_post       FLOAT,
    NLR_post        FLOAT, PMR_post       FLOAT, PLR_post       FLOAT,
    Neutrofilos_90d FLOAT, Linfocitos_90d FLOAT, Monocitos_90d  FLOAT,
    Plaquetas_90d   FLOAT, PCR_90d        FLOAT,
    CONSTRAINT PK_INFLAMACION PRIMARY KEY (ID_Inflamacion),
    CONSTRAINT FK_INFL_PAC    FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);

-- ── ANALITICA_LIPIDOS ─────────────────────────────────────────────────────────
CREATE TABLE ANALITICA_LIPIDOS (
    ID_Lipidos          INT IDENTITY(1,1) NOT NULL,
    NHC                 INT          NOT NULL,
    Fecha               NVARCHAR(20),
    ApolipoproteínaAI   FLOAT,
    ApolipoproteínaB100 FLOAT,
    Lipoproteina_a      FLOAT,
    ColesterolNoHDL     FLOAT,
    Colesterol_suero    FLOAT,
    HDLColesterol       FLOAT,
    LDLColesterol       FLOAT,
    Trigliceridos       FLOAT,
    CONSTRAINT PK_AN_LIP    PRIMARY KEY (ID_Lipidos),
    CONSTRAINT FK_ANLIP_PAC FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);

-- ── ANALITICA_METABOLICA ──────────────────────────────────────────────────────
CREATE TABLE ANALITICA_METABOLICA (
    ID_Metabolica            INT IDENTITY(1,1) NOT NULL,
    NHC                      INT          NOT NULL,
    Fecha                    NVARCHAR(20),
    Glucosa_suero            FLOAT,
    HbA1c                    FLOAT,
    Homocisteina             FLOAT,
    Creatinina_suero         FLOAT,
    FiltradoGlomerularCKDEPI FLOAT,
    Urea_suero               FLOAT,
    Sodio_suero              FLOAT,
    Potasio_suero            FLOAT,
    Cloro_suero              FLOAT,
    CalcioTotal              FLOAT,
    Magnesio_suero           FLOAT,
    Zinc_suero               FLOAT,
    VitaminaB12              FLOAT,
    AcidoFolico              FLOAT,
    TSH_suero                FLOAT,
    T4libre_suero            FLOAT,
    PCR_Ultrasensible        FLOAT,
    ProteinaCReactiva        FLOAT,
    CONSTRAINT PK_AN_MET    PRIMARY KEY (ID_Metabolica),
    CONSTRAINT FK_ANMET_PAC FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);

-- ── ANALITICA_HEPATICA ────────────────────────────────────────────────────────
CREATE TABLE ANALITICA_HEPATICA (
    ID_Hepatica           INT IDENTITY(1,1) NOT NULL,
    NHC                   INT          NOT NULL,
    Fecha                 NVARCHAR(20),
    ALT_suero             FLOAT,
    AST_suero             FLOAT,
    GGT_suero             FLOAT,
    FosfatasaAlcalina     FLOAT,
    BilirrubinaTotal      FLOAT,
    BilirrubinaDirect     FLOAT,
    CK_suero              FLOAT,
    LactatoDeshidrogenasa FLOAT,
    CONSTRAINT PK_AN_HEP    PRIMARY KEY (ID_Hepatica),
    CONSTRAINT FK_ANHEP_PAC FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);

-- ── ANALITICA_PROTEINAS ───────────────────────────────────────────────────────
CREATE TABLE ANALITICA_PROTEINAS (
    ID_Proteinas     INT IDENTITY(1,1) NOT NULL,
    NHC              INT          NOT NULL,
    Fecha            NVARCHAR(20),
    ProteinasTotales FLOAT,
    Prealbumina      FLOAT,
    Albumina_suero   FLOAT,
    Transferrina     FLOAT,
    BetaGlobulina    FLOAT,
    Inmunofijacion   NVARCHAR(60),
    CONSTRAINT PK_AN_PROT    PRIMARY KEY (ID_Proteinas),
    CONSTRAINT FK_ANPROT_PAC FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);

-- ── ANALITICA_ORINA ───────────────────────────────────────────────────────────
CREATE TABLE ANALITICA_ORINA (
    ID_Orina           INT IDENTITY(1,1) NOT NULL,
    NHC                INT          NOT NULL,
    Fecha              NVARCHAR(20),
    AlbuminaOrina      FLOAT,
    CreatininaOrina    FLOAT,
    AlbuminaTira       NVARCHAR(20),
    AlbuminaCreatinina FLOAT,
    CreatininaTira     NVARCHAR(20),
    DensidadOrina      FLOAT,
    CONSTRAINT PK_AN_ORINA    PRIMARY KEY (ID_Orina),
    CONSTRAINT FK_ANORINA_PAC FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);

-- ── ANALITICA_PETICION ────────────────────────────────────────────────────────
CREATE TABLE ANALITICA_PETICION (
    ID_Peticion            INT IDENTITY(1,1) NOT NULL,
    NHC                    INT          NOT NULL,
    Fecha                  NVARCHAR(20),
    Fecha_solicitud        NVARCHAR(30),
    Numero_solicitud       NVARCHAR(30),
    Doctor                 NVARCHAR(100),
    Centro                 NVARCHAR(100),
    Servicio               NVARCHAR(100),
    Centro_procesamiento   NVARCHAR(100),
    Diagnostico_solicitud  NVARCHAR(200),
    Ubicacion              NVARCHAR(100),
    Observaciones_peticion NVARCHAR(500),
    Info_adicional         NVARCHAR(500),
    Patologia_descripcion  NVARCHAR(200),
    CONSTRAINT PK_AN_PET    PRIMARY KEY (ID_Peticion),
    CONSTRAINT FK_ANPET_PAC FOREIGN KEY (NHC) REFERENCES PACIENTE(NHC)
);

-- ── ALTA_HOSPITALARIA ─────────────────────────────────────────────────────────
CREATE TABLE ALTA_HOSPITALARIA (
    NHC                INT          NOT NULL,
    FECHA              NVARCHAR(20) NOT NULL,
    FechadeAlta        NVARCHAR(20),
    DestinoAlta        NVARCHAR(60),
    FA_Novo            NVARCHAR(10),
    FAnovo_num         INT,
    ComplicacionesPost NVARCHAR(300),
    Causadelamuerte    NVARCHAR(200),
    CONSTRAINT PK_ALTA      PRIMARY KEY (NHC, FECHA),
    CONSTRAINT FK_ALTA_PROC FOREIGN KEY (NHC, FECHA) REFERENCES PROCEDIMIENTO(NHC, FECHA)
);

-- ── RESULTADO_RECAM ───────────────────────────────────────────────────────────
CREATE TABLE RESULTADO_RECAM (
    NHC           INT          NOT NULL,
    FECHA         NVARCHAR(20) NOT NULL,
    Pases         INT,
    Recanalizacion NVARCHAR(20),
    TICI          NVARCHAR(10),
    NIHSS_24h     INT,
    NIHSS_alta    INT,
    mRs_alta      INT,
    CONSTRAINT PK_RECAM      PRIMARY KEY (NHC, FECHA),
    CONSTRAINT FK_RECAM_PROC FOREIGN KEY (NHC, FECHA) REFERENCES PROCEDIMIENTO(NHC, FECHA)
);





-- ── SEGUIMIENTO ───────────────────────────────────────────────────────────────
CREATE TABLE SEGUIMIENTO (
    NHC             INT          NOT NULL,
    FECHA           NVARCHAR(20) NOT NULL,
    mRs_90dias      INT,
    AcudenVisita90d NVARCHAR(10),
    Observaciones   NVARCHAR(300),
    CONSTRAINT PK_SEGUIMIENTO PRIMARY KEY (NHC, FECHA),
    CONSTRAINT FK_SEG_PROC    FOREIGN KEY (NHC, FECHA) REFERENCES PROCEDIMIENTO(NHC, FECHA)
);



-- ── CALIDAD_DATOS ───────────────────────────────────────────────────────────────
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
);

-- =============================================================================
--  3. Índices
-- =============================================================================
CREATE INDEX IX_PROC_FECHA        ON PROCEDIMIENTO(FECHA);
CREATE INDEX IX_ALTA_FECHAALTA    ON ALTA_HOSPITALARIA(FechadeAlta);
CREATE INDEX IX_SEG_MRS90         ON SEGUIMIENTO(mRs_90dias);
CREATE INDEX IX_SCORES_NIHSS      ON SCORES_INICIO(NIHSS_inicio);
CREATE INDEX IX_INFL_NHC          ON INFLAMACION(NHC);
CREATE INDEX IX_ANLIP_NHC_FECHA   ON ANALITICA_LIPIDOS(NHC, Fecha);
CREATE INDEX IX_ANMET_NHC_FECHA   ON ANALITICA_METABOLICA(NHC, Fecha);
CREATE INDEX IX_ANHEP_NHC_FECHA   ON ANALITICA_HEPATICA(NHC, Fecha);
CREATE INDEX IX_ANPROT_NHC_FECHA  ON ANALITICA_PROTEINAS(NHC, Fecha);
CREATE INDEX IX_ANORINA_NHC_FECHA ON ANALITICA_ORINA(NHC, Fecha);
CREATE INDEX IX_ANPET_NHC_FECHA   ON ANALITICA_PETICION(NHC, Fecha);