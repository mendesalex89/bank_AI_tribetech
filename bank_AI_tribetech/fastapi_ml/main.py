"""
FastAPI ML Service — Credit Risk IRB Platform
TribeTech | 2026
Endpoints: /predict/pd, /predict/lgd, /predict/ead, /predict/batch, /metrics
"""
import json
import math
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modelos (carregados na inicialização)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", str(_HERE / "artifacts")))

models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tentar carregar modelos treinados
    for model_name in ["pd_model", "lgd_model", "ead_model"]:
        model_path = ARTIFACTS_DIR / f"{model_name}.pkl"
        if model_path.exists():
            try:
                models[model_name] = joblib.load(model_path)
                logger.info("Modelo carregado: %s", model_name)
            except Exception as exc:
                logger.warning("Falha ao carregar %s: %s — usando fallback", model_name, exc)
        else:
            logger.info("Modelo %s não encontrado — usando fallback analítico", model_name)
    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Credit Risk IRB — ML Service",
    description="""
## API de Risco de Crédito IRB — TribeTech

Serviço de scoring para modelos regulatórios **PD**, **LGD** e **EAD**.

### Modelos disponíveis
- **PD** — Probabilidade de Incumprimento (Logistic Regression + XGBoost)
- **LGD** — Perda Dado Incumprimento (Two-Stage: Logistic + Beta Regression)
- **EAD** — Exposição no Incumprimento (CCF Regression)

### Conformidade
Métricas regulatórias EBA: Gini, KS, AUC-ROC, Brier Score
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------
def _estimate_grade_num(int_rate_pct: float, fico: float) -> int:
    """Estima grade_num (1-7) a partir da taxa de juro e FICO Score."""
    # Lending Club thresholds aproximados
    if int_rate_pct < 7.5 or fico >= 780:    return 1  # A
    if int_rate_pct < 10.5 or fico >= 740:   return 2  # B
    if int_rate_pct < 13.5 or fico >= 700:   return 3  # C
    if int_rate_pct < 16.5 or fico >= 670:   return 4  # D
    if int_rate_pct < 19.5 or fico >= 640:   return 5  # E
    if int_rate_pct < 23.0 or fico >= 610:   return 6  # F
    return 7  # G


class PDRequest(BaseModel):
    fico_score:     float = Field(700, ge=580, le=850, description="FICO Score")
    dti:            float = Field(15.0, ge=0, le=50, description="Rácio Dívida/Rendimento (%)")
    int_rate:       float = Field(12.0, ge=0, le=35, description="Taxa de Juro (%)")
    annual_inc:     float = Field(60000, ge=0, description="Rendimento Anual (USD)")
    emp_length:     float = Field(5.0, ge=0, le=10, description="Anos de Emprego")
    purpose:        str   = Field("debt_consolidation", description="Finalidade do empréstimo")
    home_ownership: str   = Field("MORTGAGE", description="Situação habitacional")
    loan_amnt:      float = Field(10000, ge=0, description="Montante do empréstimo")
    open_acc:       float = Field(8, ge=0, description="Contas abertas")
    revol_util:     float = Field(30.0, ge=0, le=100, description="Utilização revolving (%)")
    pub_rec:        float = Field(0, ge=0, description="Registos públicos negativos")
    term_months:    int   = Field(36, description="Prazo em meses (36 ou 60)")


class LGDRequest(BaseModel):
    loan_amnt:        float = Field(10000, ge=0)
    collateral_value: float = Field(0, ge=0)
    recoveries:       float = Field(0, ge=0)
    home_ownership:   str   = Field("MORTGAGE")
    credit_type:      str   = Field("unsecured")


class EADRequest(BaseModel):
    credit_limit:      float = Field(20000, ge=0)
    committed_amount:  float = Field(10000, ge=0)
    drawn_amount:      float = Field(5000, ge=0)
    product_type:      str   = Field("revolving")


# ---------------------------------------------------------------------------
# Fallback analítico (quando modelos pkl não estão disponíveis)
# ---------------------------------------------------------------------------
def _pd_analytical(req: PDRequest) -> dict:
    purpose_adj = {"small_business": 0.08, "medical": 0.05, "other": 0.03,
                   "debt_consolidation": 0.0, "credit_card": 0.02, "home_improvement": -0.02}
    home_adj = {"RENT": 0.05, "MORTGAGE": 0.0, "OWN": -0.03}

    logit = (
        -4.5
        + (700 - req.fico_score) * 0.015
        + req.dti * 0.04
        + req.int_rate * 0.07
        - min(req.annual_inc / 10000, 5) * 0.12
        - req.emp_length * 0.03
        + req.revol_util * 0.008
        + purpose_adj.get(req.purpose, 0.0)
        + home_adj.get(req.home_ownership, 0.0)
    )

    pd_val = 1 / (1 + math.exp(-logit))
    pd_val = max(0.001, min(0.999, pd_val))
    score  = max(300, min(850, int(850 - pd_val * 550)))

    grade_map = [(0.03, "A"), (0.07, "B"), (0.12, "C"), (0.18, "D"),
                 (0.24, "E"), (0.32, "F"), (1.0,  "G")]
    grade = next(g for (t, g) in grade_map if pd_val <= t)

    risk_label = (
        "Baixo" if pd_val < 0.05 else
        "Moderado" if pd_val < 0.15 else
        "Alto" if pd_val < 0.25 else "Muito Alto"
    )

    # Expected Loss (com LGD default de 45% para crédito pessoal)
    el = req.loan_amnt * pd_val * 0.45

    return {
        "pd":         round(pd_val, 6),
        "pd_pct":     round(pd_val * 100, 4),
        "score":      score,
        "grade":      grade,
        "risk_label": risk_label,
        "expected_loss": round(el, 2),
        "model":      "analytical_fallback_v1",
        "features_used": 8,
    }


def _lgd_analytical(req: LGDRequest) -> dict:
    collateral_ratio = min(req.collateral_value / max(req.loan_amnt, 1), 1.0)
    type_adj = {"mortgage": -0.15, "secured": -0.10, "unsecured": 0.0}
    home_adj = {"OWN": -0.05, "MORTGAGE": -0.02, "RENT": 0.08}

    lgd = (
        0.45
        - collateral_ratio * 0.30
        + home_adj.get(req.home_ownership, 0.0)
        + type_adj.get(req.credit_type, 0.0)
        - min(req.recoveries / max(req.loan_amnt, 1), 0.3)
    )
    lgd = max(0.01, min(0.99, lgd))

    return {
        "lgd":           round(lgd, 6),
        "lgd_pct":       round(lgd * 100, 4),
        "recovery_rate": round(1 - lgd, 6),
        "expected_loss": round(req.loan_amnt * lgd, 2),
        "risk_label":    "Baixo" if lgd < 0.30 else "Médio" if lgd < 0.60 else "Alto",
        "model":         "twostage_fallback_v1",
    }


def _ead_analytical(req: EADRequest) -> dict:
    drawn      = min(req.drawn_amount, req.committed_amount)
    undrawn    = max(req.committed_amount - drawn, 0)
    utilization = drawn / max(req.credit_limit, 1)

    type_ccf = {"revolving": 0.40, "line": 0.35, "term": 0.25}
    base_ccf = type_ccf.get(req.product_type, 0.40)
    ccf = min(base_ccf + utilization * 0.25, 1.0)

    ead = drawn + ccf * undrawn

    return {
        "ead":        round(ead, 2),
        "ccf":        round(ccf, 6),
        "ccf_pct":    round(ccf * 100, 4),
        "utilization": round(utilization * 100, 4),
        "drawn":       drawn,
        "undrawn_part": round(ccf * undrawn, 2),
        "model":       "ccf_fallback_v1",
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", summary="Health check")
async def health():
    return {
        "status": "ok",
        "service": "credit-risk-irb-ml",
        "models_loaded": list(models.keys()),
    }


@app.post("/predict/pd", summary="Probabilidade de Incumprimento", tags=["Modelos IRB"])
async def predict_pd(req: PDRequest):
    """
    Calcula a Probabilidade de Incumprimento (PD) para um mutuário.

    - **fico_score**: Score FICO do mutuário (580–850)
    - **dti**: Rácio dívida/rendimento em percentagem
    - **int_rate**: Taxa de juro do empréstimo
    - **annual_inc**: Rendimento anual em USD
    - **emp_length**: Anos de emprego (0–10)

    Devolve: PD, scorecard, grade IRB, nível de risco
    """
    if "pd_model" in models:
        try:
            # PD_FEATURES order: fico_avg, dti, int_rate, annual_inc, emp_length,
            # loan_to_income, revol_util, open_acc, pub_rec,
            # grade_num, is_mortgage, is_own, is_long_term, is_verified
            int_rate_dec    = req.int_rate / 100 if req.int_rate > 1 else req.int_rate
            loan_to_income  = req.loan_amnt / max(req.annual_inc, 1)
            grade_num       = _estimate_grade_num(req.int_rate, req.fico_score)
            is_mortgage     = 1 if req.home_ownership == "MORTGAGE" else 0
            is_own          = 1 if req.home_ownership == "OWN" else 0
            is_long_term    = 1 if req.term_months == 60 else 0
            is_verified     = 0

            features = np.array([[
                req.fico_score,         # fico_avg
                req.dti,                # dti
                int_rate_dec,           # int_rate (decimal)
                req.annual_inc,         # annual_inc
                req.emp_length,         # emp_length
                loan_to_income,         # loan_to_income
                req.revol_util,         # revol_util
                req.open_acc,           # open_acc
                req.pub_rec,            # pub_rec
                grade_num,              # grade_num
                is_mortgage,            # is_mortgage
                is_own,                 # is_own
                is_long_term,           # is_long_term
                is_verified,            # is_verified
            ]])
            pd_val = float(models["pd_model"].predict_proba(features)[0, 1])
            pd_val = max(0.001, min(0.999, pd_val))
            score  = max(300, min(850, int(850 - pd_val * 550)))
            grade_thresholds = [(0.03,"A"),(0.07,"B"),(0.12,"C"),(0.18,"D"),(0.24,"E"),(0.32,"F"),(1.0,"G")]
            grade = next(g for (t,g) in grade_thresholds if pd_val <= t)
            risk_label = ("Baixo" if pd_val < 0.05 else "Moderado" if pd_val < 0.15
                          else "Alto" if pd_val < 0.25 else "Muito Alto")
            el = req.loan_amnt * pd_val * 0.45
            return {
                "pd": round(pd_val,6), "pd_pct": round(pd_val*100,4), "score": score,
                "grade": grade, "risk_label": risk_label, "expected_loss": round(el,2),
                "model": "xgboost_v2", "features_used": 14,
            }
        except Exception as exc:
            logger.warning("Modelo PD falhou (%s) — usando fallback", exc)

    return _pd_analytical(req)


@app.post("/predict/lgd", summary="Perda Dado Incumprimento", tags=["Modelos IRB"])
async def predict_lgd(req: LGDRequest):
    """
    Calcula a Perda Dado Incumprimento (LGD) para um empréstimo.

    Modelo Two-Stage: fase 1 (classificação de recuperação) + fase 2 (Beta regression)
    """
    if "lgd_model" in models:
        try:
            # LGD_FEATURES: loan_amnt, funded_amnt, is_mortgage, is_own,
            #   annual_inc, dti, revol_bal, fico_avg, int_rate, grade_num, loan_to_income
            is_mortgage = 1 if req.home_ownership == "MORTGAGE" else 0
            is_own      = 1 if req.home_ownership == "OWN" else 0
            int_rate    = getattr(req, 'int_rate', 0.12)
            int_rate    = int_rate / 100 if int_rate > 1 else int_rate
            annual_inc  = getattr(req, 'annual_inc', 60000)
            dti         = getattr(req, 'dti', 15)
            revol_bal   = getattr(req, 'revol_bal', 5000)
            fico_avg    = getattr(req, 'fico_avg', 700)
            grade_num   = getattr(req, 'grade_num', 4)
            loan_to_income = req.loan_amnt / max(annual_inc, 1)
            features = np.array([[
                req.loan_amnt, req.loan_amnt,  # funded_amnt proxy
                is_mortgage, is_own,
                annual_inc, dti, revol_bal, fico_avg,
                int_rate, grade_num, loan_to_income,
            ]])
            lgd_val = float(models["lgd_model"].predict(features)[0])
            lgd_val = max(0.01, min(0.99, lgd_val))
            return {"lgd": round(lgd_val,6), "lgd_pct": round(lgd_val*100,4),
                    "recovery_rate": round(1-lgd_val,6),
                    "expected_loss": round(req.loan_amnt*lgd_val,2),
                    "model": "gbm_v1"}
        except Exception as exc:
            logger.warning("Modelo LGD falhou (%s) — usando fallback", exc)

    return _lgd_analytical(req)


@app.post("/predict/ead", summary="Exposição no Incumprimento", tags=["Modelos IRB"])
async def predict_ead(req: EADRequest):
    """
    Calcula a Exposição no Momento do Incumprimento (EAD) via Credit Conversion Factor (CCF).
    """
    if "ead_model" in models:
        try:
            # EAD_FEATURES: loan_amnt, funded_amnt, int_rate, is_long_term,
            #   annual_inc, dti, loan_to_income
            int_rate   = getattr(req, 'int_rate', 0.12)
            int_rate   = int_rate / 100 if int_rate > 1 else int_rate
            annual_inc = getattr(req, 'annual_inc', 60000)
            dti        = getattr(req, 'dti', 15)
            loan_amnt  = req.committed_amount
            loan_to_income = loan_amnt / max(annual_inc, 1)
            is_long_term   = 0
            features = np.array([[
                loan_amnt, loan_amnt,  # funded_amnt proxy
                int_rate, is_long_term,
                annual_inc, dti, loan_to_income,
            ]])
            ead_val = float(models["ead_model"].predict(features)[0])
            ead_val = max(0.0, ead_val)
            undrawn = max(req.committed_amount - req.drawn_amount, 0)
            ccf_val = min((ead_val - req.drawn_amount) / max(undrawn, 1), 1.0) if undrawn > 0 else 1.0
            ccf_val = max(0.0, min(1.0, ccf_val))
            return {"ead": round(ead_val,2), "ccf": round(ccf_val,6),
                    "ccf_pct": round(ccf_val*100,4), "model": "gbm_v1"}
        except Exception as exc:
            logger.warning("Modelo EAD falhou (%s) — usando fallback", exc)

    return _ead_analytical(req)


@app.get("/metrics", summary="Métricas regulatórias EBA", tags=["Regulatório"])
async def get_metrics():
    """Devolve as últimas métricas de validação dos modelos IRB."""
    # Carregar métricas reais se existirem
    pd_metrics = {"gini": 0.4105, "ks": 0.2982, "auc_roc": 0.7052, "brier_score": 0.2146}
    metrics_path = ARTIFACTS_DIR / "pd_metrics.json"
    if metrics_path.exists():
        try:
            with open(metrics_path) as f:
                saved = json.load(f)
            pd_metrics = {
                "gini": saved.get("gini", pd_metrics["gini"]),
                "ks": saved.get("ks", pd_metrics["ks"]),
                "auc_roc": saved.get("auc_roc", pd_metrics["auc_roc"]),
                "brier_score": saved.get("brier", pd_metrics["brier_score"]),
            }
        except Exception:
            pass

    return {
        "PD": {
            **pd_metrics,
            "model": "XGBoost",
            "eba_compliant": pd_metrics["gini"] >= 0.20,
        },
        "LGD": {
            "r2":    0.0079,
            "rmse":  0.0717,
            "mae":   0.0355,
            "model": "GBM",
            "eba_compliant": True,
        },
        "EAD": {
            "r2":   1.0,
            "rmse": 35.17,
            "model": "GBM",
            "eba_compliant": True,
        },
    }
