-- =============================================================================
-- Análise de Portfólio — Credit Risk IRB Platform
-- TribeTech | 2026
-- =============================================================================

-- ----------------------------------------------------------------------------
-- 1. Resumo geral do portfólio por grade
-- ----------------------------------------------------------------------------
SELECT
    grade,
    COUNT(*)                                          AS total_emprestimos,
    SUM(loan_amnt)                                    AS exposicao_total,
    ROUND(AVG(loan_amnt), 2)                          AS ticket_medio,
    ROUND(AVG(annual_inc), 2)                         AS rendimento_medio,
    ROUND(AVG(dti), 4)                                AS dti_medio,
    ROUND(AVG(fico_range_low), 1)                     AS fico_medio,
    ROUND(AVG(int_rate), 4)                           AS taxa_juro_media,
    SUM(CASE WHEN is_default THEN 1 ELSE 0 END)       AS total_defaults,
    ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0.0 END), 4) AS taxa_default,
    ROUND(AVG(lgd), 4)                                AS lgd_media,
    ROUND(SUM(loan_amnt * COALESCE(lgd, 0.45)), 2)    AS perda_esperada,
    ROUND(
        SUM(loan_amnt * COALESCE(lgd, 0.45)) / NULLIF(SUM(loan_amnt), 0),
        4
    )                                                 AS ratio_perda_exposicao
FROM loans
WHERE grade IS NOT NULL
GROUP BY grade
ORDER BY grade;


-- ----------------------------------------------------------------------------
-- 2. Vintage Analysis — taxa de default por trimestre de emissão
-- (cohort analysis regulatório)
-- ----------------------------------------------------------------------------
SELECT
    TO_CHAR(DATE_TRUNC('quarter', issue_d), 'YYYY-Q"T"Q')  AS trimestre_emissao,
    COUNT(*)                                                 AS total,
    SUM(loan_amnt)                                           AS volume,
    SUM(CASE WHEN is_default THEN 1 ELSE 0 END)             AS defaults,
    ROUND(
        SUM(CASE WHEN is_default THEN 1.0 ELSE 0.0 END)
        / NULLIF(COUNT(*), 0),
        4
    )                                                        AS taxa_default,
    ROUND(AVG(fico_range_low), 1)                           AS fico_medio,
    ROUND(AVG(dti), 4)                                      AS dti_medio
FROM loans
WHERE issue_d IS NOT NULL
GROUP BY DATE_TRUNC('quarter', issue_d)
ORDER BY DATE_TRUNC('quarter', issue_d);


-- ----------------------------------------------------------------------------
-- 3. Distribuição por finalidade e taxa de default
-- ----------------------------------------------------------------------------
SELECT
    purpose                                                   AS finalidade,
    COUNT(*)                                                  AS total,
    SUM(loan_amnt)                                            AS volume_total,
    ROUND(AVG(loan_amnt), 2)                                  AS ticket_medio,
    ROUND(
        AVG(CASE WHEN is_default THEN 1.0 ELSE 0.0 END),
        4
    )                                                         AS taxa_default,
    ROUND(AVG(int_rate), 4)                                   AS taxa_juro_media,
    ROUND(AVG(fico_range_low), 1)                             AS fico_medio
FROM loans
WHERE purpose IS NOT NULL
GROUP BY purpose
ORDER BY taxa_default DESC;


-- ----------------------------------------------------------------------------
-- 4. Análise de concentração de risco (HHI regulatório)
-- ----------------------------------------------------------------------------
WITH grade_exposure AS (
    SELECT
        grade,
        SUM(loan_amnt) AS exposure,
        SUM(SUM(loan_amnt)) OVER () AS total_exposure
    FROM loans
    WHERE grade IS NOT NULL
    GROUP BY grade
)
SELECT
    grade,
    exposure,
    ROUND(exposure / total_exposure * 100, 2) AS peso_pct,
    ROUND(POWER(exposure / total_exposure, 2) * 10000, 2) AS hhi_contribuicao
FROM grade_exposure
ORDER BY grade;


-- ----------------------------------------------------------------------------
-- 5. Segmentação por FICO e taxa de default (para scorecard)
-- ----------------------------------------------------------------------------
SELECT
    CASE
        WHEN fico_range_low < 600 THEN '580-599'
        WHEN fico_range_low < 620 THEN '600-619'
        WHEN fico_range_low < 640 THEN '620-639'
        WHEN fico_range_low < 660 THEN '640-659'
        WHEN fico_range_low < 680 THEN '660-679'
        WHEN fico_range_low < 700 THEN '680-699'
        WHEN fico_range_low < 720 THEN '700-719'
        WHEN fico_range_low < 740 THEN '720-739'
        WHEN fico_range_low < 760 THEN '740-759'
        WHEN fico_range_low < 780 THEN '760-779'
        ELSE '780+'
    END                                               AS fico_band,
    COUNT(*)                                          AS total,
    ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0.0 END), 4) AS taxa_default,
    ROUND(AVG(loan_amnt), 2)                          AS ticket_medio,
    ROUND(AVG(int_rate), 4)                           AS taxa_juro_media
FROM loans
WHERE fico_range_low IS NOT NULL
GROUP BY fico_band
ORDER BY MIN(fico_range_low);
