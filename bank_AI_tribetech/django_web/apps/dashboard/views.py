"""
Dashboard — Análise de Portfólio IRB
Lê dados do PostgreSQL via DuckDB quando disponível
"""
import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.db import connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fetch_rows(sql, params=None):
    """Executa query e devolve lista de dicts."""
    try:
        with connection.cursor() as cur:
            cur.execute(sql, params or [])
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as exc:
        logger.warning("DB query falhou: %s", exc)
        return []


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------
def dashboard(request):
    # Métricas de topo — fallback para zeros se DB vazio
    summary_rows = _fetch_rows("""
        SELECT
            COUNT(*)                                          AS total_loans,
            COALESCE(SUM(loan_amnt), 0)                      AS total_exposure,
            ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0.0 END)::numeric, 4) AS default_rate,
            ROUND(AVG(fico_range_low)::numeric, 1)           AS avg_fico,
            ROUND(AVG(dti)::numeric, 2)                      AS avg_dti,
            ROUND(AVG(int_rate)::numeric, 4)                 AS avg_int_rate
        FROM loans
    """)

    summary = summary_rows[0] if summary_rows else {
        "total_loans": 0, "total_exposure": 0, "default_rate": 0,
        "avg_fico": 0, "avg_dti": 0, "avg_int_rate": 0,
    }

    # Distribuição por grade
    grade_rows = _fetch_rows("""
        SELECT grade,
               COUNT(*) AS total,
               ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0.0 END)::numeric, 4) AS dr
        FROM loans
        WHERE grade IS NOT NULL
        GROUP BY grade ORDER BY grade
    """)

    # Métricas do modelo mais recente
    metric_rows = _fetch_rows("""
        SELECT model_type, metric_name, metric_value
        FROM model_metrics
        WHERE evaluation_date = (SELECT MAX(evaluation_date) FROM model_metrics)
        ORDER BY model_type, metric_name
    """)

    return render(request, "dashboard/index.html", {
        "summary": summary,
        "grade_rows": json.dumps(grade_rows, default=str),
        "metric_rows": json.dumps(metric_rows, default=str),
    })


# ---------------------------------------------------------------------------
# API endpoints para gráficos Chart.js
# ---------------------------------------------------------------------------
def api_portfolio(request):
    rows = _fetch_rows("""
        SELECT grade,
               COUNT(*)         AS total,
               SUM(loan_amnt)   AS exposure,
               ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0.0 END)::numeric, 4) AS dr,
               ROUND(AVG(fico_range_low)::numeric, 1) AS avg_fico
        FROM loans
        WHERE grade IS NOT NULL
        GROUP BY grade ORDER BY grade
    """)

    if not rows:
        # Demo data quando DB vazio
        rows = [
            {"grade": g, "total": t, "exposure": e, "dr": d, "avg_fico": f}
            for g, t, e, d, f in [
                ("A", 215000, 2_800_000_000, 0.0302, 737),
                ("B", 340000, 4_100_000_000, 0.0692, 699),
                ("C", 380000, 4_300_000_000, 0.1152, 679),
                ("D", 260000, 2_900_000_000, 0.1742, 660),
                ("E", 130000, 1_500_000_000, 0.2312, 644),
                ("F",  65000,   750_000_000, 0.2892, 630),
                ("G",  25000,   290_000_000, 0.3221, 618),
            ]
        ]

    return JsonResponse({"data": rows})


def api_defaults(request):
    rows = _fetch_rows("""
        SELECT TO_CHAR(DATE_TRUNC('quarter', issue_d), 'YYYY-Q"T"Q') AS period,
               COUNT(*)                                               AS total,
               SUM(CASE WHEN is_default THEN 1 ELSE 0 END)          AS defaults,
               ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0.0 END)::numeric, 4) AS dr
        FROM loans
        WHERE issue_d IS NOT NULL
        GROUP BY DATE_TRUNC('quarter', issue_d)
        ORDER BY DATE_TRUNC('quarter', issue_d)
        LIMIT 40
    """)

    if not rows:
        import random
        random.seed(42)
        rows = []
        quarters = [f"20{y:02d}-Q{q}" for y in range(10, 19) for q in range(1, 5)]
        base_dr = 0.05
        for q in quarters:
            dr = round(max(0.02, min(0.35, base_dr + random.gauss(0, 0.02))), 4)
            rows.append({"period": q, "total": random.randint(5000, 80000),
                         "defaults": 0, "dr": dr})
            base_dr = dr * 0.95 + 0.05 * 0.05

    return JsonResponse({"data": rows})


def api_grade_dist(request):
    rows = _fetch_rows("""
        SELECT purpose, COUNT(*) AS total
        FROM loans
        WHERE purpose IS NOT NULL
        GROUP BY purpose
        ORDER BY total DESC
        LIMIT 10
    """)

    if not rows:
        rows = [
            {"purpose": p, "total": t} for p, t in [
                ("debt_consolidation", 890000),
                ("credit_card", 340000),
                ("home_improvement", 150000),
                ("other", 120000),
                ("major_purchase", 80000),
                ("small_business", 60000),
                ("car", 55000),
                ("medical", 45000),
                ("moving", 30000),
                ("vacation", 20000),
            ]
        ]

    return JsonResponse({"data": rows})


def api_summary_kpis(request):
    """KPIs principais para cartões do dashboard."""
    rows = _fetch_rows("""
        SELECT
            COUNT(*)                                                       AS total_loans,
            ROUND(SUM(loan_amnt)/1e6, 1)                                   AS total_exposure_m,
            ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0 END)*100, 2)   AS default_rate_pct,
            ROUND(AVG((fico_range_low+fico_range_high)/2.0), 1)           AS avg_fico,
            ROUND(AVG(dti)::numeric, 1)                                    AS avg_dti,
            ROUND(AVG(int_rate)*100, 2)                                    AS avg_int_rate_pct,
            ROUND(SUM(loan_amnt*COALESCE(lgd,0.45)*is_default::int)/1e6,1) AS realised_loss_m,
            ROUND(SUM(loan_amnt)*0.08/1e6, 1)                              AS min_capital_m,
            COUNT(DISTINCT grade)                                           AS n_grades,
            COUNT(DISTINCT EXTRACT(YEAR FROM issue_d))                     AS n_years
        FROM loans
    """)
    return JsonResponse({"data": rows[0] if rows else {}})


def api_vintage(request):
    """Análise de vintage por ano de emissão."""
    rows = _fetch_rows("""
        SELECT
            EXTRACT(YEAR FROM issue_d)::int             AS year,
            COUNT(*)                                     AS total_loans,
            SUM(CASE WHEN is_default THEN 1 ELSE 0 END) AS defaults,
            ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0 END)*100, 2) AS dr_pct,
            ROUND(SUM(loan_amnt)/1e6, 1)                AS exposure_m,
            ROUND(AVG((fico_range_low+fico_range_high)/2.0), 0) AS avg_fico
        FROM loans
        WHERE issue_d IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM issue_d)
        ORDER BY year
    """)
    return JsonResponse({"data": rows})


def api_fico_distribution(request):
    """Distribuição do FICO Score por bucket de 20 pontos."""
    rows = _fetch_rows("""
        SELECT
            (FLOOR((fico_range_low+fico_range_high)/2.0 / 20) * 20)::int AS fico_bucket,
            COUNT(*) AS total,
            ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0 END)*100, 2) AS dr_pct
        FROM loans
        WHERE fico_range_low > 0
        GROUP BY fico_bucket
        ORDER BY fico_bucket
    """)
    return JsonResponse({"data": rows})


def api_el_by_grade(request):
    """Expected Loss vs Realised Loss por grade."""
    rows = _fetch_rows("""
        SELECT
            grade,
            ROUND(SUM(loan_amnt)/1e6, 2)                                       AS exposure_m,
            ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0 END)*100, 2)       AS dr_pct,
            ROUND(AVG(COALESCE(lgd, 0.45))*100, 2)                            AS avg_lgd_pct,
            ROUND(SUM(loan_amnt * COALESCE(lgd,0.45) *
                      CASE WHEN is_default THEN 1.0 ELSE 0 END)/1e6, 2)       AS realised_loss_m,
            ROUND(SUM(loan_amnt) *
                  AVG(CASE WHEN is_default THEN 1.0 ELSE 0 END) *
                  AVG(COALESCE(lgd, 0.45)) / 1e6, 2)                          AS expected_loss_m
        FROM loans
        WHERE grade IS NOT NULL
        GROUP BY grade
        ORDER BY grade
    """)
    return JsonResponse({"data": rows})


def api_model_metrics(request):
    """Métricas dos modelos IRB da base de dados."""
    rows = _fetch_rows("""
        SELECT model_type, model_version, metric_name,
               ROUND(metric_value::numeric, 4) AS metric_value,
               evaluation_date::text, dataset
        FROM model_metrics
        ORDER BY model_type, metric_name
    """)
    # Estrutura por modelo para o frontend
    result = {}
    for r in rows:
        mt = r["model_type"]
        if mt not in result:
            result[mt] = {"version": r["model_version"], "dataset": r.get("dataset", ""), "metrics": {}}
        result[mt]["metrics"][r["metric_name"]] = float(r["metric_value"])
    return JsonResponse({"data": result})
