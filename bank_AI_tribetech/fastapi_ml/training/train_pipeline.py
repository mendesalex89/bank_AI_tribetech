"""
Pipeline de Treino IRB — PD, LGD, EAD
Usa DuckDB para processar os dados grandes (1.6GB+) de forma eficiente
TribeTech | 2026

Execução: python train_pipeline.py --model all --sample 200000
"""
import argparse
import logging
import os
import sys
from pathlib import Path

import duckdb
import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    roc_auc_score, brier_score_loss,
    mean_squared_error, r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.feature_engineering import (
    create_default_flag, engineer_features,
    PD_FEATURES, LGD_FEATURES, EAD_FEATURES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Calibração Platt (módulo-nível para pickle)
# ---------------------------------------------------------------------------
class PlattCalibratedXGB:
    """XGBoost com Platt Scaling incorporado — serializável via joblib."""

    def __init__(self, base, a: float, b: float):
        self.base = base
        self.a    = a
        self.b    = b

    def predict_proba(self, X):
        from scipy.special import expit
        raw = self.base.predict_proba(X)[:, 1]
        cal = expit(self.a * raw + self.b)
        return np.column_stack([1 - cal, cal])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] > 0.5).astype(int)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
DATA_PATH = os.getenv(
    "DATA_PATH",
    "/home/alexmendes/bank_tech/Data/accepted_2007_to_2018q4.csv/accepted_2007_to_2018Q4.csv",
)
ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))
ARTIFACTS_DIR.mkdir(exist_ok=True)

# MLflow: tenta servidor remoto, usa ficheiro local como fallback imediato
_MLFLOW_SERVER = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5010")
_MLFLOW_LOCAL  = "sqlite:///mlflow.db"   # SQLite local (evita deprecation warning)

def _setup_mlflow() -> str:
    """Verifica se o servidor MLflow está acessível; fallback para ficheiro local."""
    import socket
    try:
        host = _MLFLOW_SERVER.split("//")[-1].split(":")[0]
        port = int(_MLFLOW_SERVER.split(":")[-1])
        sock = socket.create_connection((host, port), timeout=2)
        sock.close()
        logger.info("MLflow servidor disponível: %s", _MLFLOW_SERVER)
        return _MLFLOW_SERVER
    except (OSError, ValueError):
        logger.info("MLflow servidor indisponível — a usar ficheiro local: %s", _MLFLOW_LOCAL)
        return _MLFLOW_LOCAL

MLFLOW_URI = _setup_mlflow()


# ---------------------------------------------------------------------------
# Métricas regulatórias EBA
# ---------------------------------------------------------------------------
def gini_score(y_true, y_score) -> float:
    """Gini = 2*AUC - 1 (métrica principal EBA para modelos PD)."""
    return 2 * roc_auc_score(y_true, y_score) - 1


def ks_score(y_true, y_score) -> float:
    """KS Statistic — separação entre distribuições de bons e maus."""
    from scipy.stats import ks_2samp
    pos_scores = y_score[y_true == 1]
    neg_scores = y_score[y_true == 0]
    ks_stat, _ = ks_2samp(pos_scores, neg_scores)
    return ks_stat


# ---------------------------------------------------------------------------
# Carregamento de dados via DuckDB
# ---------------------------------------------------------------------------
def load_data_duckdb(sample_n: int = 300_000) -> pd.DataFrame:
    """
    Carrega dados Lending Club usando DuckDB (eficiente para ficheiros 1.6GB+).
    Aplica filtros e amostragem directamente em SQL.
    """
    logger.info("A carregar dados via DuckDB (amostra=%d)...", sample_n)

    con = duckdb.connect()

    query = f"""
    SELECT
        loan_amnt, funded_amnt, term, int_rate, installment,
        grade, sub_grade, emp_length, home_ownership, annual_inc,
        verification_status, loan_status, purpose, dti,
        delinq_2yrs, fico_range_low, fico_range_high, inq_last_6mths,
        open_acc, pub_rec, revol_bal, revol_util, total_acc,
        recoveries, out_prncp
    FROM read_csv_auto('{DATA_PATH}', ignore_errors=true)
    WHERE loan_status IS NOT NULL
      AND annual_inc > 0
      AND loan_amnt > 0
      AND grade IS NOT NULL
    USING SAMPLE {sample_n} ROWS
    """

    df = con.execute(query).df()
    con.close()

    logger.info("Dados carregados: %d linhas, %d colunas", len(df), df.shape[1])
    return df


# ---------------------------------------------------------------------------
# Treino Modelo PD
# ---------------------------------------------------------------------------
def _run_mlflow(experiment_name, run_name, model, params, metrics, artifact_name):
    """Regista no MLflow (servidor ou ficheiro local). Nunca bloqueia."""
    try:
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name=run_name):
            mlflow.log_params(params)
            mlflow.log_metrics(metrics)
            mlflow.sklearn.log_model(model, artifact_name)
        logger.info("MLflow registado: %s / %s", experiment_name, run_name)
    except Exception as exc:
        logger.warning("MLflow falhou (%s) — métricas apenas locais", exc)


def train_pd_model(df: pd.DataFrame, experiment_name: str = "credit_risk_pd") -> dict:
    logger.info("== Treino Modelo PD ==")

    df = create_default_flag(df)
    df = engineer_features(df)

    # Apenas empréstimos resolvidos (Fully Paid ou Default)
    resolved = df[df["loan_status"].isin([
        "Fully Paid", "Charged Off", "Default",
        "Does not meet the credit policy. Status:Fully Paid",
        "Does not meet the credit policy. Status:Charged Off",
    ])].copy()

    X = resolved[PD_FEATURES].fillna(resolved[PD_FEATURES].median())
    y = resolved["is_default"]

    neg, pos = (y == 0).sum(), (y == 1).sum()
    scale_pos = neg / max(pos, 1)
    logger.info("PD — total=%d  defaults=%d  scale_pos_weight=%.1f", len(y), pos, scale_pos)

    # Split 3-vias: 60% treino / 20% calibração / 20% teste
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    X_train, X_cal, y_train, y_cal = train_test_split(
        X_trainval, y_trainval, test_size=0.25, random_state=42, stratify=y_trainval
    )  # 0.25 × 0.80 = 0.20 total

    # --- XGBoost com GPU (RTX disponível) ---
    import xgboost as xgb
    from scipy.special import expit
    from scipy.optimize import minimize

    # Detectar GPU
    _gpu_available = False
    try:
        import subprocess
        result = subprocess.run(["nvidia-smi"], capture_output=True, timeout=3)
        _gpu_available = result.returncode == 0
    except Exception:
        pass

    device = "cuda" if _gpu_available else "cpu"
    logger.info("XGBoost device: %s", device)

    xgb_base = xgb.XGBClassifier(
        n_estimators=800,
        max_depth=6,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        scale_pos_weight=scale_pos,
        eval_metric="auc",
        device=device,
        random_state=42,
        n_jobs=-1 if device == "cpu" else 1,
    )
    xgb_base.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=100,
    )
    logger.info("XGBoost (raw) — Gini no teste: %.4f",
                gini_score(y_test, xgb_base.predict_proba(X_test)[:, 1]))

    # --- Calibração Platt Scaling ---
    # Ajusta A, B tais que P(y=1) = sigmoid(A * raw_score + B)
    raw_cal = xgb_base.predict_proba(X_cal)[:, 1]
    y_cal_np = y_cal.values if hasattr(y_cal, 'values') else np.array(y_cal)

    def _platt_loss(params):
        a, b = params
        p = expit(a * raw_cal + b)
        p = np.clip(p, 1e-10, 1 - 1e-10)
        return -np.mean(y_cal_np * np.log(p) + (1 - y_cal_np) * np.log(1 - p))

    opt = minimize(_platt_loss, [1.0, 0.0], method="L-BFGS-B",
                   options={"maxiter": 200, "ftol": 1e-10})
    platt_a, platt_b = opt.x
    logger.info("Platt Scaling: A=%.4f  B=%.4f", platt_a, platt_b)

    xgb_model = PlattCalibratedXGB(xgb_base, platt_a, platt_b)
    y_pred_xgb = xgb_model.predict_proba(X_test)[:, 1]
    gini_xgb = gini_score(y_test, y_pred_xgb)
    logger.info("XGBoost+Platt — Gini: %.4f", gini_xgb)

    # --- Logistic Regression (scorecard IRB regulatório) ---
    lr_pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model",  LogisticRegression(C=0.05, class_weight="balanced",
                                       max_iter=500, random_state=42)),
    ])
    lr_pipeline.fit(X_train, y_train)
    y_pred_lr = lr_pipeline.predict_proba(X_test)[:, 1]
    gini_lr = gini_score(y_test, y_pred_lr)
    logger.info("Logistic   — Gini: %.4f", gini_lr)

    # Escolher o melhor para produção
    if gini_xgb >= gini_lr:
        best_model = xgb_model
        y_pred     = y_pred_xgb
        model_tag  = "XGBoost"
    else:
        best_model = lr_pipeline
        y_pred     = y_pred_lr
        model_tag  = "LogisticRegression"

    gini = gini_score(y_test, y_pred)
    ks   = ks_score(y_test.values, y_pred)
    auc  = roc_auc_score(y_test, y_pred)
    bs   = brier_score_loss(y_test, y_pred)

    logger.info("PD FINAL [%s] — Gini: %.4f | KS: %.4f | AUC: %.4f | Brier: %.4f",
                model_tag, gini, ks, auc, bs)

    _run_mlflow(
        experiment_name, f"pd_{model_tag.lower()}_v2",
        best_model,
        {"model": model_tag, "features": len(PD_FEATURES), "n_train": len(X_train)},
        {"gini": gini, "ks": float(ks), "auc_roc": auc, "brier_score": bs},
        "pd_model",
    )

    # Guardar ambos (XGBoost para produção, LR para scorecard)
    joblib.dump(best_model, ARTIFACTS_DIR / "pd_model.pkl")
    joblib.dump(lr_pipeline, ARTIFACTS_DIR / "pd_scorecard_lr.pkl")
    logger.info("Modelo PD guardado: %s [%s]", ARTIFACTS_DIR / "pd_model.pkl", model_tag)

    return {"gini": round(gini, 4), "ks": round(float(ks), 4),
            "auc_roc": round(auc, 4), "brier": round(bs, 4), "model": model_tag}


# ---------------------------------------------------------------------------
# Treino Modelo LGD
# ---------------------------------------------------------------------------
def train_lgd_model(df: pd.DataFrame, experiment_name: str = "credit_risk_lgd") -> dict:
    logger.info("== Treino Modelo LGD ==")

    df = create_default_flag(df)
    df = engineer_features(df)

    # Apenas incumpridores com LGD válida
    defaulted = df[(df["is_default"] == 1) & df["lgd"].notna()].copy()

    if len(defaulted) < 1000:
        logger.warning("Poucos defaults (%d) para treinar LGD.", len(defaulted))
        return {}

    X = defaulted[LGD_FEATURES].fillna(defaulted[LGD_FEATURES].median())
    y = defaulted["lgd"].clip(0.01, 0.99)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    # Gradient Boosting (Two-Stage proxy)
    from sklearn.ensemble import GradientBoostingRegressor
    model = GradientBoostingRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        random_state=42, subsample=0.8,
    )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test).clip(0, 1)
    r2   = r2_score(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae  = float(np.mean(np.abs(y_test - y_pred)))
    logger.info("LGD — R²: %.4f | RMSE: %.4f | MAE: %.4f", r2, rmse, mae)

    _run_mlflow(experiment_name, "lgd_gbm_v1", model,
                {"model": "GradientBoostingRegressor", "features": len(LGD_FEATURES)},
                {"r2": r2, "rmse": rmse, "mae": mae}, "lgd_model")

    model_path = ARTIFACTS_DIR / "lgd_model.pkl"
    joblib.dump(model, model_path)
    logger.info("Modelo LGD guardado: %s", model_path)

    return {"r2": round(r2,4), "rmse": round(float(rmse),4), "mae": round(float(mae),4)}


# ---------------------------------------------------------------------------
# Treino Modelo EAD
# ---------------------------------------------------------------------------
def train_ead_model(df: pd.DataFrame, experiment_name: str = "credit_risk_ead") -> dict:
    logger.info("== Treino Modelo EAD ==")

    df = create_default_flag(df)
    df = engineer_features(df)

    defaulted = df[(df["is_default"] == 1) & df["ead"].notna()].copy()

    if len(defaulted) < 500:
        logger.warning("Poucos defaults (%d) para treinar EAD.", len(defaulted))
        return {}

    X = defaulted[EAD_FEATURES].fillna(defaulted[EAD_FEATURES].median())
    y = defaulted["ead"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)

    from sklearn.ensemble import GradientBoostingRegressor
    model = GradientBoostingRegressor(
        n_estimators=150, max_depth=3, learning_rate=0.08, random_state=42
    )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    r2   = r2_score(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    logger.info("EAD — R²: %.4f | RMSE: %.2f", r2, rmse)

    _run_mlflow(experiment_name, "ead_gbm_v1", model,
                {"model": "GradientBoostingRegressor", "features": len(EAD_FEATURES)},
                {"r2": r2, "rmse": rmse}, "ead_model")

    model_path = ARTIFACTS_DIR / "ead_model.pkl"
    joblib.dump(model, model_path)
    logger.info("Modelo EAD guardado: %s", model_path)

    return {"r2": round(r2,4), "rmse": round(rmse,4)}


# ---------------------------------------------------------------------------
# Ingestão para PostgreSQL
# ---------------------------------------------------------------------------
def ingest_to_postgres(df: pd.DataFrame, db_url: str, batch_size: int = 10_000):
    """Insere dados processados no PostgreSQL em batches."""
    try:
        from sqlalchemy import create_engine

        logger.info("A ingerir %d registos para PostgreSQL...", len(df))
        engine = create_engine(db_url)

        df_pg = df[[
            "loan_amnt", "funded_amnt", "term_months", "int_rate",
            "installment", "grade", "emp_length", "home_ownership",
            "annual_inc", "verification_status", "loan_status",
            "purpose", "dti", "delinq_2yrs", "fico_avg",
            "open_acc", "pub_rec", "revol_bal", "revol_util",
            "total_acc", "out_prncp", "is_default", "lgd", "ead", "ccf",
        ]].rename(columns={
            "term_months": "term",
            "fico_avg": "fico_range_low",
        })

        # Inserir em batches
        rows_inserted = 0
        for i in range(0, len(df_pg), batch_size):
            chunk = df_pg.iloc[i:i+batch_size]
            chunk.to_sql("loans", engine, if_exists="append", index=False, method="multi")
            rows_inserted += len(chunk)
            if rows_inserted % 50_000 == 0:
                logger.info("  Inseridos %d / %d", rows_inserted, len(df_pg))

        logger.info("Ingestão concluída: %d registos", rows_inserted)

    except Exception as exc:
        logger.error("Falha na ingestão PostgreSQL: %s", exc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Treino de Modelos IRB — TribeTech")
    parser.add_argument("--model",  choices=["pd","lgd","ead","all"], default="all")
    parser.add_argument("--sample", type=int, default=500_000,
                        help="Número de linhas a amostrar do CSV (default: 500000)")
    parser.add_argument("--ingest", action="store_true",
                        help="Ingerir dados no PostgreSQL após treino")
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL", ""),
                        help="URL PostgreSQL")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Credit Risk IRB — Pipeline de Treino | TribeTech 2026")
    logger.info("=" * 60)

    # Carregar dados
    df_raw = load_data_duckdb(sample_n=args.sample)
    df_proc = create_default_flag(df_raw)
    df_proc = engineer_features(df_proc)

    results = {}

    if args.model in ("pd", "all"):
        results["PD"] = train_pd_model(df_proc)

    if args.model in ("lgd", "all"):
        results["LGD"] = train_lgd_model(df_proc)

    if args.model in ("ead", "all"):
        results["EAD"] = train_ead_model(df_proc)

    logger.info("\n== RESULTADOS FINAIS ==")
    for model_name, metrics in results.items():
        logger.info("  %s: %s", model_name, metrics)

    if args.ingest and args.db_url:
        ingest_to_postgres(df_proc, args.db_url)

    logger.info("Pipeline concluído.")
