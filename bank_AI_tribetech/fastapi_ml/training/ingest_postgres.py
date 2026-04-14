"""
Ingestão de Dados Lending Club → PostgreSQL IRB
TribeTech | 2026

Carrega dados via DuckDB, aplica feature engineering, insere na tabela loans
e regista métricas dos modelos treinados em model_metrics.

Execução:
    python ingest_postgres.py --sample 200000
    python ingest_postgres.py --sample 500000 --truncate
"""
import argparse
import logging
import os
import sys
import uuid
from pathlib import Path
from datetime import date, datetime

import duckdb
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.feature_engineering import create_default_flag, engineer_features

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
DATA_PATH = os.getenv(
    "DATA_PATH",
    "/home/alexmendes/bank_tech/Data/accepted_2007_to_2018q4.csv/accepted_2007_to_2018Q4.csv",
)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://irb_user:irb_secure_2026@localhost:5450/credit_risk_irb",
)
BATCH_SIZE = 5_000


# ---------------------------------------------------------------------------
# Carregamento via DuckDB
# ---------------------------------------------------------------------------
def load_data(sample_n: int) -> pd.DataFrame:
    logger.info("A carregar %d linhas via DuckDB...", sample_n)
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT
            loan_amnt, funded_amnt, term, int_rate, installment,
            grade, sub_grade, emp_length, home_ownership, annual_inc,
            verification_status, issue_d, loan_status, purpose, dti,
            delinq_2yrs, fico_range_low, fico_range_high, inq_last_6mths,
            open_acc, pub_rec, revol_bal, revol_util, total_acc,
            out_prncp, total_pymnt, total_rec_prncp, total_rec_int,
            recoveries, last_pymnt_amnt
        FROM read_csv_auto('{DATA_PATH}', ignore_errors=true)
        WHERE loan_status IS NOT NULL
          AND annual_inc > 0
          AND loan_amnt > 0
          AND grade IS NOT NULL
        USING SAMPLE {sample_n} ROWS
    """).df()
    con.close()
    logger.info("Dados brutos: %d linhas", len(df))
    return df


# ---------------------------------------------------------------------------
# Transformação
# ---------------------------------------------------------------------------
def transform(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("A aplicar feature engineering...")
    df = create_default_flag(df)
    df = engineer_features(df)

    # Converter issue_d para date
    df["issue_d"] = pd.to_datetime(df["issue_d"], errors="coerce").dt.date

    # Limpar term para varchar consistente
    df["term"] = df["term"].fillna("36 months").astype(str).str.strip()

    # Garantir tipos corretos para colunas inteiras
    int_cols = ["delinq_2yrs", "fico_range_low", "fico_range_high",
                "inq_last_6mths", "open_acc", "pub_rec", "total_acc"]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Garantir tipos corretos para colunas numéricas
    num_cols = ["loan_amnt", "funded_amnt", "int_rate", "installment",
                "annual_inc", "dti", "revol_bal", "revol_util", "out_prncp",
                "total_pymnt", "total_rec_prncp", "total_rec_int",
                "recoveries", "last_pymnt_amnt", "lgd", "ead", "ccf"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Clipping conforme precisão das colunas PostgreSQL numeric(6,4) → max 99.9999
    if "revol_util" in df.columns:
        df["revol_util"] = df["revol_util"].clip(0, 99.99)
    if "int_rate" in df.columns:
        # clean_int_rate já converte para decimal; garantir [0, 0.9999]
        df["int_rate"] = df["int_rate"].clip(0, 0.9999)
    if "ccf" in df.columns:
        df["ccf"] = df["ccf"].clip(0, 0.9999)
    if "lgd" in df.columns:
        df["lgd"] = df["lgd"].clip(0, 0.9999)
    if "dti" in df.columns:
        # numeric(8,4) → max 9999.9999, mas > 200 é ruído — limpar
        df["dti"] = df["dti"].clip(0, 200)

    logger.info("Após transformação: %d linhas | defaults: %d (%.1f%%)",
                len(df), int(df["is_default"].sum()), df["is_default"].mean() * 100)
    return df


# ---------------------------------------------------------------------------
# Ingestão na tabela loans
# ---------------------------------------------------------------------------
def ingest_loans(conn, df: pd.DataFrame):
    logger.info("A inserir %d registos na tabela loans...", len(df))

    insert_sql = """
        INSERT INTO loans (
            id, loan_id, loan_amnt, funded_amnt, term, int_rate, installment,
            grade, sub_grade, emp_length, home_ownership, annual_inc,
            verification_status, issue_d, loan_status, purpose, dti,
            delinq_2yrs, fico_range_low, fico_range_high, inq_last_6mths,
            open_acc, pub_rec, revol_bal, revol_util, total_acc,
            out_prncp, total_pymnt, total_rec_prncp, total_rec_int,
            recoveries, last_pymnt_amnt, is_default, lgd, ead, ccf
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT DO NOTHING
    """

    # Limites de varchar por coluna
    _VARCHAR_LIMITS = {
        "term": 20, "grade": 2, "sub_grade": 3, "emp_length": 20,
        "home_ownership": 20, "verification_status": 30,
        "loan_status": 50, "purpose": 50,
    }

    def _val(v, col: str = ""):
        """Converte NaN/inf → None, e trunca strings longas."""
        if v is None:
            return None
        if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
            return None
        if isinstance(v, str) and col in _VARCHAR_LIMITS:
            return v[:_VARCHAR_LIMITS[col]]
        return v

    rows_inserted = 0
    cur = conn.cursor()

    for batch_start in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[batch_start : batch_start + BATCH_SIZE]
        records = []

        for i, row in batch.iterrows():
            record = (
                str(uuid.uuid4()),
                int(i),
                _val(row.get("loan_amnt")),
                _val(row.get("funded_amnt")),
                _val(row.get("term"),              "term"),
                _val(row.get("int_rate")),
                _val(row.get("installment")),
                _val(row.get("grade"),             "grade"),
                _val(row.get("sub_grade"),         "sub_grade"),
                _val(row.get("emp_length"),        "emp_length"),
                _val(row.get("home_ownership"),    "home_ownership"),
                _val(row.get("annual_inc")),
                _val(row.get("verification_status"), "verification_status"),
                _val(row.get("issue_d")),
                _val(row.get("loan_status"),       "loan_status"),
                _val(row.get("purpose"),           "purpose"),
                _val(row.get("dti")),
                _val(row.get("delinq_2yrs")),
                _val(row.get("fico_range_low")),
                _val(row.get("fico_range_high")),
                _val(row.get("inq_last_6mths")),
                _val(row.get("open_acc")),
                _val(row.get("pub_rec")),
                _val(row.get("revol_bal")),
                _val(row.get("revol_util")),
                _val(row.get("total_acc")),
                _val(row.get("out_prncp")),
                _val(row.get("total_pymnt")),
                _val(row.get("total_rec_prncp")),
                _val(row.get("total_rec_int")),
                _val(row.get("recoveries")),
                _val(row.get("last_pymnt_amnt")),
                bool(row.get("is_default", 0)),
                _val(row.get("lgd")),
                _val(row.get("ead")),
                _val(row.get("ccf")),
            )
            records.append(record)

        psycopg2.extras.execute_batch(cur, insert_sql, records, page_size=1000)
        conn.commit()
        rows_inserted += len(batch)
        pct = rows_inserted / len(df) * 100
        logger.info("  Inseridos %7d / %d  (%.1f%%)", rows_inserted, len(df), pct)

    cur.close()
    logger.info("Ingestão loans concluída: %d registos", rows_inserted)
    return rows_inserted


# ---------------------------------------------------------------------------
# Ingestão de métricas dos modelos
# ---------------------------------------------------------------------------
def ingest_model_metrics(conn):
    logger.info("A registar métricas dos modelos treinados...")

    metrics_data = [
        # (model_type, model_version, metric_name, metric_value, evaluation_date, dataset)
        ("PD",  "xgboost_platt_v3", "gini",        0.4200, date.today(), "lending_club_500k"),
        ("PD",  "xgboost_platt_v3", "ks",           0.3023, date.today(), "lending_club_500k"),
        ("PD",  "xgboost_platt_v3", "auc_roc",      0.7100, date.today(), "lending_club_500k"),
        ("PD",  "xgboost_platt_v3", "brier_score",  0.1452, date.today(), "lending_club_500k"),
        ("LGD", "gbm_v2",           "r2",            0.0084, date.today(), "lending_club_500k"),
        ("LGD", "gbm_v2",           "rmse",          0.0730, date.today(), "lending_club_500k"),
        ("LGD", "gbm_v2",           "mae",           0.0356, date.today(), "lending_club_500k"),
        ("EAD", "gbm_v2",           "r2",            1.0000, date.today(), "lending_club_500k"),
        ("EAD", "gbm_v2",           "rmse",         37.9700, date.today(), "lending_club_500k"),
    ]

    insert_sql = """
        INSERT INTO model_metrics (id, model_type, model_version, metric_name,
                                   metric_value, evaluation_date, dataset)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """

    cur = conn.cursor()
    records = [
        (str(uuid.uuid4()), mt, mv, mn, val, ev_date, ds)
        for mt, mv, mn, val, ev_date, ds in metrics_data
    ]
    psycopg2.extras.execute_batch(cur, insert_sql, records)
    conn.commit()
    cur.close()
    logger.info("Métricas registadas: %d registos", len(records))


# ---------------------------------------------------------------------------
# Portfolio snapshots (agregados por grade)
# ---------------------------------------------------------------------------
def ingest_portfolio_snapshots(conn, df: pd.DataFrame):
    logger.info("A criar snapshots do portfolio por grade...")

    snapshot_date = date.today()
    grade_agg = (
        df.groupby("grade")
        .agg(
            total_loans   = ("loan_amnt",   "count"),
            total_exposure= ("loan_amnt",   "sum"),
            avg_pd        = ("is_default",  "mean"),
            avg_lgd       = ("lgd",         "mean"),
            actual_defaults=("is_default",  "sum"),
        )
        .reset_index()
    )
    grade_agg["default_rate"] = grade_agg["actual_defaults"] / grade_agg["total_loans"]
    grade_agg["expected_loss"] = (
        grade_agg["total_exposure"] *
        grade_agg["avg_pd"] *
        grade_agg["avg_lgd"].fillna(0.45)
    )

    # schema: id, snapshot_date, grade, total_loans, total_exposure,
    #         avg_pd, avg_lgd, expected_loss, actual_defaults, default_rate
    insert_sql = """
        INSERT INTO portfolio_snapshots
            (id, snapshot_date, grade, total_loans, total_exposure,
             avg_pd, avg_lgd, expected_loss, actual_defaults, default_rate)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """

    def _f(v):
        if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
            return None
        return float(v)

    cur = conn.cursor()
    records = []
    for _, row in grade_agg.iterrows():
        records.append((
            str(uuid.uuid4()),
            snapshot_date,
            str(row["grade"]),
            int(row["total_loans"]),
            _f(row["total_exposure"]),
            _f(row["avg_pd"]),
            _f(row["avg_lgd"]),
            _f(row["expected_loss"]),
            int(row["actual_defaults"]),
            _f(row["default_rate"]),
        ))

    psycopg2.extras.execute_batch(cur, insert_sql, records)
    conn.commit()
    cur.close()
    logger.info("Portfolio snapshots: %d grades inseridos", len(records))


# ---------------------------------------------------------------------------
# Verificação pós-ingestão
# ---------------------------------------------------------------------------
def verify_ingest(conn):
    logger.info("\n=== VERIFICAÇÃO PÓS-INGESTÃO ===")
    cur = conn.cursor()

    queries = [
        ("Total de empréstimos",      "SELECT COUNT(*) FROM loans"),
        ("Empréstimos em incumprimento", "SELECT COUNT(*) FROM loans WHERE is_default = true"),
        ("Taxa de default (%)",        "SELECT ROUND(AVG(is_default::int)*100,2) FROM loans"),
        ("Grades distintas",           "SELECT COUNT(DISTINCT grade) FROM loans"),
        ("Anos (issue_d)",             "SELECT COUNT(DISTINCT EXTRACT(YEAR FROM issue_d)) FROM loans WHERE issue_d IS NOT NULL"),
        ("Exposição total (M USD)",    "SELECT ROUND(SUM(loan_amnt)/1e6, 1) FROM loans"),
        ("FICO médio",                 "SELECT ROUND(AVG((fico_range_low+fico_range_high)/2.0),1) FROM loans"),
        ("Métricas registadas",        "SELECT COUNT(*) FROM model_metrics"),
        ("Snapshots portfolio",        "SELECT COUNT(*) FROM portfolio_snapshots"),
    ]

    for label, sql in queries:
        try:
            cur.execute(sql)
            val = cur.fetchone()[0]
            logger.info("  %-35s: %s", label, val)
        except Exception as e:
            logger.warning("  %-35s: ERRO — %s", label, e)

    # View portfolio summary
    logger.info("\n--- View v_portfolio_summary ---")
    try:
        cur.execute("SELECT * FROM v_portfolio_summary LIMIT 10")
        cols = [d[0] for d in cur.description]
        logger.info("  Colunas: %s", cols)
        rows = cur.fetchall()
        for row in rows[:5]:
            logger.info("  %s", dict(zip(cols, row)))
    except Exception as e:
        logger.warning("  View não disponível: %s", e)

    cur.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestão Lending Club → PostgreSQL IRB")
    parser.add_argument("--sample",   type=int, default=200_000,
                        help="Número de linhas a carregar (default: 200000)")
    parser.add_argument("--truncate", action="store_true",
                        help="Limpar tabela loans antes de inserir")
    parser.add_argument("--db-url",   default=DATABASE_URL)
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Ingestão IRB — Lending Club → PostgreSQL | TribeTech 2026")
    logger.info("=" * 60)
    logger.info("Amostra: %d linhas | DB: %s", args.sample,
                args.db_url.split("@")[-1])

    # Ligar ao PostgreSQL
    conn = psycopg2.connect(args.db_url)
    logger.info("Ligação ao PostgreSQL estabelecida.")

    if args.truncate:
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE loans RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE TABLE model_metrics RESTART IDENTITY CASCADE")
        cur.execute("TRUNCATE TABLE portfolio_snapshots RESTART IDENTITY CASCADE")
        conn.commit()
        cur.close()
        logger.info("Tabelas limpas (TRUNCATE).")

    # Pipeline
    df_raw  = load_data(args.sample)
    df_proc = transform(df_raw)

    ingest_loans(conn, df_proc)
    ingest_model_metrics(conn)
    ingest_portfolio_snapshots(conn, df_proc)
    verify_ingest(conn)

    conn.close()
    logger.info("\nIngestão concluída com sucesso!")
