-- =============================================================================
-- Credit Risk IRB Platform — Schema PostgreSQL
-- TribeTech | 2026
-- =============================================================================

-- Extensões
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- =============================================================================
-- TABELA: loans (dados base Lending Club)
-- =============================================================================
CREATE TABLE IF NOT EXISTS loans (
    id                  UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    loan_id             BIGINT UNIQUE,
    loan_amnt           NUMERIC(12,2),
    funded_amnt         NUMERIC(12,2),
    term                VARCHAR(20),
    int_rate            NUMERIC(6,4),
    installment         NUMERIC(10,2),
    grade               VARCHAR(2),
    sub_grade           VARCHAR(3),
    emp_length          VARCHAR(20),
    home_ownership      VARCHAR(20),
    annual_inc          NUMERIC(14,2),
    verification_status VARCHAR(30),
    issue_d             DATE,
    loan_status         VARCHAR(50),
    purpose             VARCHAR(50),
    dti                 NUMERIC(8,4),
    delinq_2yrs         SMALLINT,
    fico_range_low      SMALLINT,
    fico_range_high     SMALLINT,
    inq_last_6mths      SMALLINT,
    open_acc            SMALLINT,
    pub_rec             SMALLINT,
    revol_bal           NUMERIC(14,2),
    revol_util          NUMERIC(6,4),
    total_acc           SMALLINT,
    out_prncp           NUMERIC(12,2),
    total_pymnt         NUMERIC(12,2),
    total_rec_prncp     NUMERIC(12,2),
    total_rec_int       NUMERIC(12,2),
    recoveries          NUMERIC(12,2),
    last_pymnt_amnt     NUMERIC(12,2),
    -- Target variables IRB
    is_default          BOOLEAN,
    lgd                 NUMERIC(6,4),     -- Loss Given Default [0,1]
    ead                 NUMERIC(12,2),    -- Exposure at Default
    ccf                 NUMERIC(6,4),     -- Credit Conversion Factor
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABELA: model_predictions (scoring em tempo real)
-- =============================================================================
CREATE TABLE IF NOT EXISTS model_predictions (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    loan_ref        VARCHAR(100),
    model_type      VARCHAR(10) NOT NULL,  -- 'PD', 'LGD', 'EAD'
    model_version   VARCHAR(20),
    prediction      NUMERIC(10,6) NOT NULL,
    score           SMALLINT,              -- scorecard points (PD)
    rating          VARCHAR(5),            -- grade interno (AAA..D)
    input_features  JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABELA: model_metrics (métricas regulatórias EBA)
-- =============================================================================
CREATE TABLE IF NOT EXISTS model_metrics (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    model_type      VARCHAR(10) NOT NULL,
    model_version   VARCHAR(20),
    metric_name     VARCHAR(50) NOT NULL,  -- 'gini','ks','auc','brier','psi'
    metric_value    NUMERIC(10,6) NOT NULL,
    evaluation_date DATE DEFAULT CURRENT_DATE,
    dataset         VARCHAR(20),           -- 'train','test','oot'
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABELA: portfolio_snapshots (monitoring mensal)
-- =============================================================================
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id                  UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    snapshot_date       DATE NOT NULL,
    grade               VARCHAR(2),
    total_loans         INTEGER,
    total_exposure      NUMERIC(16,2),
    avg_pd              NUMERIC(6,4),
    avg_lgd             NUMERIC(6,4),
    expected_loss       NUMERIC(16,2),
    actual_defaults     INTEGER,
    default_rate        NUMERIC(6,4),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABELA: feature_woe (Weight of Evidence para features)
-- =============================================================================
CREATE TABLE IF NOT EXISTS feature_woe (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    feature_name    VARCHAR(100) NOT NULL,
    bin_label       VARCHAR(100),
    bin_min         NUMERIC,
    bin_max         NUMERIC,
    count_total     INTEGER,
    count_events    INTEGER,
    count_non_events INTEGER,
    woe             NUMERIC(10,6),
    iv              NUMERIC(10,6),
    model_type      VARCHAR(10),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABELA: batch_scoring_jobs (upload CSV)
-- =============================================================================
CREATE TABLE IF NOT EXISTS batch_scoring_jobs (
    id              UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    job_name        VARCHAR(200),
    model_type      VARCHAR(10),
    status          VARCHAR(20) DEFAULT 'pending',  -- pending/running/done/error
    total_records   INTEGER,
    processed       INTEGER DEFAULT 0,
    result_file     VARCHAR(500),
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- =============================================================================
-- Índices para performance analítica
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_loans_grade         ON loans(grade);
CREATE INDEX IF NOT EXISTS idx_loans_issue_d       ON loans(issue_d);
CREATE INDEX IF NOT EXISTS idx_loans_loan_status   ON loans(loan_status);
CREATE INDEX IF NOT EXISTS idx_loans_is_default    ON loans(is_default);
CREATE INDEX IF NOT EXISTS idx_predictions_type    ON model_predictions(model_type);
CREATE INDEX IF NOT EXISTS idx_predictions_created ON model_predictions(created_at);
CREATE INDEX IF NOT EXISTS idx_metrics_type_date   ON model_metrics(model_type, evaluation_date);
CREATE INDEX IF NOT EXISTS idx_portfolio_date      ON portfolio_snapshots(snapshot_date);

-- =============================================================================
-- VIEW: portfolio_summary (dashboard principal)
-- =============================================================================
CREATE OR REPLACE VIEW v_portfolio_summary AS
SELECT
    grade,
    COUNT(*)                                    AS total_loans,
    SUM(loan_amnt)                              AS total_exposure,
    AVG(annual_inc)                             AS avg_annual_income,
    AVG(dti)                                    AS avg_dti,
    AVG(fico_range_low)                         AS avg_fico,
    SUM(CASE WHEN is_default THEN 1 ELSE 0 END) AS total_defaults,
    ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0.0 END), 4) AS default_rate,
    AVG(lgd)                                    AS avg_lgd,
    SUM(loan_amnt * lgd)                        AS expected_loss
FROM loans
WHERE grade IS NOT NULL
GROUP BY grade
ORDER BY grade;

-- =============================================================================
-- VIEW: monthly_default_rates
-- =============================================================================
CREATE OR REPLACE VIEW v_monthly_default_rates AS
SELECT
    DATE_TRUNC('month', issue_d)                AS month,
    COUNT(*)                                    AS total_loans,
    SUM(CASE WHEN is_default THEN 1 ELSE 0 END) AS defaults,
    ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0.0 END), 4) AS default_rate,
    SUM(loan_amnt)                              AS total_exposure
FROM loans
WHERE issue_d IS NOT NULL
GROUP BY DATE_TRUNC('month', issue_d)
ORDER BY month;

COMMENT ON TABLE loans IS 'Dados base Lending Club — variáveis IRB (PD/LGD/EAD)';
COMMENT ON TABLE model_predictions IS 'Scoring individual e batch dos modelos IRB';
COMMENT ON TABLE model_metrics IS 'Métricas regulatórias EBA (Gini, KS, AUC, Brier)';
