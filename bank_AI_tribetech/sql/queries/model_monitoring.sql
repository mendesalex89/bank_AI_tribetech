-- =============================================================================
-- Monitorização de Modelos IRB — EBA Compliant
-- TribeTech | 2026
-- =============================================================================

-- ----------------------------------------------------------------------------
-- 1. Últimas métricas por modelo
-- ----------------------------------------------------------------------------
SELECT
    model_type,
    model_version,
    metric_name,
    metric_value,
    evaluation_date,
    CASE
        WHEN metric_name = 'gini'        AND metric_value >= 0.50 THEN 'CONFORME'
        WHEN metric_name = 'ks'          AND metric_value >= 0.30 THEN 'CONFORME'
        WHEN metric_name = 'auc_roc'     AND metric_value >= 0.75 THEN 'CONFORME'
        WHEN metric_name = 'brier_score' AND metric_value <= 0.25 THEN 'CONFORME'
        WHEN metric_name = 'gini'        AND metric_value < 0.40  THEN 'CRÍTICO'
        WHEN metric_name = 'gini'        AND metric_value < 0.50  THEN 'ATENÇÃO'
        ELSE 'CONFORME'
    END AS status_regulatorio
FROM model_metrics
WHERE evaluation_date = (
    SELECT MAX(evaluation_date) FROM model_metrics
)
ORDER BY model_type, metric_name;


-- ----------------------------------------------------------------------------
-- 2. Evolução do Gini ao longo do tempo (por modelo)
-- ----------------------------------------------------------------------------
SELECT
    model_type,
    evaluation_date,
    metric_value AS gini,
    LAG(metric_value) OVER (
        PARTITION BY model_type ORDER BY evaluation_date
    ) AS gini_anterior,
    ROUND(
        metric_value - LAG(metric_value) OVER (
            PARTITION BY model_type ORDER BY evaluation_date
        ),
        4
    ) AS variacao_gini
FROM model_metrics
WHERE metric_name = 'gini'
ORDER BY model_type, evaluation_date;


-- ----------------------------------------------------------------------------
-- 3. PSI por modelo (Population Stability Index)
-- Alert: PSI > 0.10 = atenção, PSI > 0.25 = recalibração necessária
-- ----------------------------------------------------------------------------
SELECT
    model_type,
    evaluation_date,
    metric_value AS psi,
    CASE
        WHEN metric_value < 0.10 THEN 'Estável'
        WHEN metric_value < 0.25 THEN 'Ligeira Alteração — Monitorizar'
        ELSE 'Alteração Significativa — Recalibrar'
    END AS interpretacao_psi
FROM model_metrics
WHERE metric_name = 'psi'
ORDER BY model_type, evaluation_date DESC;


-- ----------------------------------------------------------------------------
-- 4. Backtesting PD — Prevista vs. Observada por grade
-- ----------------------------------------------------------------------------
SELECT
    l.grade,
    COUNT(*)                                           AS total_observacoes,
    ROUND(AVG(p.prediction), 4)                        AS pd_prevista_media,
    ROUND(AVG(CASE WHEN l.is_default THEN 1.0 ELSE 0.0 END), 4) AS pd_observada,
    ROUND(
        ABS(AVG(p.prediction) - AVG(CASE WHEN l.is_default THEN 1.0 ELSE 0.0 END)),
        4
    ) AS desvio_absoluto,
    CASE
        WHEN ABS(
            AVG(p.prediction) - AVG(CASE WHEN l.is_default THEN 1.0 ELSE 0.0 END)
        ) < 0.02 THEN 'BOA CALIBRAÇÃO'
        WHEN ABS(
            AVG(p.prediction) - AVG(CASE WHEN l.is_default THEN 1.0 ELSE 0.0 END)
        ) < 0.05 THEN 'CALIBRAÇÃO ACEITÁVEL'
        ELSE 'RECALIBRAR'
    END AS status_calibracao
FROM loans l
JOIN model_predictions p ON p.model_type = 'PD'
WHERE l.grade IS NOT NULL
GROUP BY l.grade
ORDER BY l.grade;


-- ----------------------------------------------------------------------------
-- 5. Alertas de drift — empréstimos recentes vs. dados de treino
-- ----------------------------------------------------------------------------
SELECT
    'DTI'       AS variavel,
    ROUND(AVG(CASE WHEN issue_d >= '2017-01-01' THEN dti END), 4)  AS media_recente,
    ROUND(AVG(CASE WHEN issue_d <  '2017-01-01' THEN dti END), 4)  AS media_treino,
    ROUND(
        ABS(
            AVG(CASE WHEN issue_d >= '2017-01-01' THEN dti END) -
            AVG(CASE WHEN issue_d <  '2017-01-01' THEN dti END)
        ) / NULLIF(AVG(CASE WHEN issue_d < '2017-01-01' THEN dti END), 0) * 100,
        2
    ) AS variacao_pct

FROM loans

UNION ALL

SELECT
    'FICO' AS variavel,
    ROUND(AVG(CASE WHEN issue_d >= '2017-01-01' THEN fico_range_low END), 1),
    ROUND(AVG(CASE WHEN issue_d <  '2017-01-01' THEN fico_range_low END), 1),
    ROUND(
        ABS(
            AVG(CASE WHEN issue_d >= '2017-01-01' THEN fico_range_low END) -
            AVG(CASE WHEN issue_d <  '2017-01-01' THEN fico_range_low END)
        ) / NULLIF(AVG(CASE WHEN issue_d < '2017-01-01' THEN fico_range_low END), 0) * 100,
        2
    )
FROM loans

UNION ALL

SELECT
    'INT_RATE' AS variavel,
    ROUND(AVG(CASE WHEN issue_d >= '2017-01-01' THEN int_rate END), 4),
    ROUND(AVG(CASE WHEN issue_d <  '2017-01-01' THEN int_rate END), 4),
    ROUND(
        ABS(
            AVG(CASE WHEN issue_d >= '2017-01-01' THEN int_rate END) -
            AVG(CASE WHEN issue_d <  '2017-01-01' THEN int_rate END)
        ) / NULLIF(AVG(CASE WHEN issue_d < '2017-01-01' THEN int_rate END), 0) * 100,
        2
    )
FROM loans;
