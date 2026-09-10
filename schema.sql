-- =============================================================================
-- NVIDIA Startup AI Radar — Database Schema
-- TAPI: Ferramenta de inteligência para NVIDIA Inception Manager
-- Atrair + Qualificar + Nutrir startups AI-native
-- =============================================================================

-- -----------------------------------------------------------------------------
-- STARTUPS
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS startups (
    id               SERIAL PRIMARY KEY,
    uuid             UUID DEFAULT gen_random_uuid() UNIQUE NOT NULL,
    nome             TEXT NOT NULL,
    site             TEXT,
    setor            TEXT,
    estagio          TEXT CHECK (estagio IN ('pre-seed', 'seed', 'serie_a', 'serie_b', 'serie_c', 'serie_d', 'serie_later', 'desconhecido')),
    localizacao      TEXT,
    descricao_curta  TEXT,
    ano_fundacao     INT CHECK (ano_fundacao BETWEEN 1990 AND 2030),
    tamanho_time     INT CHECK (tamanho_time > 0),
    fontes_scraping  TEXT[] DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- DOCUMENTOS  (conteúdo textual não estruturado)
-- TAPI §5.2: rastreabilidade via url_fonte
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documentos (
    id               SERIAL PRIMARY KEY,
    uuid             UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    startup_id       INT REFERENCES startups(id) ON DELETE CASCADE,
    tipo             TEXT CHECK (tipo IN ('site_institucional', 'blog', 'noticia', 'vaga', 'perfil_founder', 'release', 'careers', 'linkedin', 'outro')),
    titulo           TEXT,
    conteudo_texto   TEXT,
    url_fonte        TEXT NOT NULL,
    data_publicacao  DATE,
    source_meta      JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(startup_id, url_fonte)
);

-- -----------------------------------------------------------------------------
-- CANDIDATES  — Pipeline de Atração / Qualificação / Nutrição Inception
-- TAPI §1: "atrair, qualificar e nutrir startups para o NVIDIA Inception"
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidates (
    id                    SERIAL PRIMARY KEY,
    startup_id            INT NOT NULL REFERENCES startups(id) ON DELETE CASCADE,
    inception_fit_score   REAL DEFAULT 0.0,

    status               TEXT DEFAULT 'identificado'
        CHECK (status IN ('identificado', 'contatado', 'engajado', 'onboarding', 'declined')),

    -- Classificação AI
    categoria_ai         TEXT DEFAULT 'desconhecido'
        CHECK (categoria_ai IN ('ai_native', 'ai_enabled', 'wrapper_llm', 'non_ai', 'desconhecido')),
    wrapper_warning       BOOLEAN DEFAULT FALSE,
    fit_justification     TEXT,

    -- Breakdown do fit score (0-1 cada)
    moat_score           REAL DEFAULT 0.0,
    tech_score            REAL DEFAULT 0.0,
    sector_score          REAL DEFAULT 0.0,
    traction_score        REAL DEFAULT 0.0,

    -- Nutrição
    nurture_cadence      TEXT DEFAULT 'mensal'
        CHECK (nurture_cadence IN ('semanal', 'quinzenal', 'mensal', 'inativo')),
    next_action_date     DATE,
    next_action_type     TEXT,
    next_action_desc     TEXT,

    -- CRM
    notes                TEXT,
    assigned_to          TEXT,
    last_contacted_at    TIMESTAMPTZ,
    last_contacted_type  TEXT,

    -- Metadados
    source_query         TEXT,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(startup_id)
);

-- -----------------------------------------------------------------------------
-- NURTURE LOG  — Histórico de engajamento
-- TAPI §1: "nutrir startups"
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nurture_log (
    id              SERIAL PRIMARY KEY,
    candidate_id    INT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    action_type     TEXT NOT NULL
        CHECK (action_type IN ('email', 'call', 'meetup', 'gtc', 'workshop', 'demo_day', 'linkedin', 'introduction', 'pitch', 'follow_up')),
    channel         TEXT
        CHECK (channel IN ('email', 'call', 'whatsapp', 'linkedin', 'in_person', 'event', 'online')),
    outcome         TEXT
        CHECK (outcome IN ('positive', 'negative', 'no_response', 'scheduled', 'pending')),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- INDEXES
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_startups_setor     ON startups(setor);
CREATE INDEX IF NOT EXISTS idx_startups_estagio  ON startups(estagio);
CREATE INDEX IF NOT EXISTS idx_startups_local    ON startups(localizacao);

CREATE INDEX IF NOT EXISTS idx_docs_startup_id   ON documentos(startup_id);
CREATE INDEX IF NOT EXISTS idx_docs_tipo         ON documentos(tipo);
CREATE INDEX IF NOT EXISTS idx_docs_data         ON documentos(data_publicacao);

CREATE INDEX IF NOT EXISTS idx_candidates_status    ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_candidates_next_date  ON candidates(next_action_date);
CREATE INDEX IF NOT EXISTS idx_candidates_fit       ON candidates(inception_fit_score DESC);
CREATE INDEX IF NOT EXISTS idx_candidates_startup   ON candidates(startup_id);

CREATE INDEX IF NOT EXISTS idx_nurture_candidate  ON nurture_log(candidate_id);
CREATE INDEX IF NOT EXISTS idx_nurture_action     ON nurture_log(action_type);
CREATE INDEX IF NOT EXISTS idx_nurture_outcome    ON nurture_log(outcome);
