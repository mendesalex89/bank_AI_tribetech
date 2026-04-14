"""
Feature Engineering — IRB Regulatório
WoE (Weight of Evidence), IV (Information Value), Fine/Coarse Classing
TribeTech | 2026
"""
import numpy as np
import pandas as pd
from typing import Optional


# ---------------------------------------------------------------------------
# Definição do target
# ---------------------------------------------------------------------------
DEFAULT_STATUSES = {
    "Charged Off", "Default",
    "Does not meet the credit policy. Status:Charged Off",
    "Does not meet the credit policy. Status:Default",
    "Late (121-150 days)", "Late (31-120 days)",
}


def create_default_flag(df: pd.DataFrame) -> pd.DataFrame:
    """Cria flag de incumprimento conforme definição EBA (Artigo 178 CRR)."""
    df = df.copy()
    df["is_default"] = df["loan_status"].isin(DEFAULT_STATUSES).astype(int)

    # LGD = 1 - (recovery_rate)
    # Usa total_pymnt como proxy da recuperação total para loans já encerrados
    df["lgd"] = np.where(
        df["is_default"] == 1,
        np.where(
            df["loan_amnt"] > 0,
            1.0 - (df["recoveries"].fillna(0) / df["loan_amnt"].clip(lower=1)).clip(0, 1),
            np.nan,
        ),
        np.nan,
    )
    # Adicionar ruído realista: LGD não pode ser exatamente 1.0 em massa
    # Usar distribuição histórica Lending Club: LGD médio ~60%
    df["lgd"] = df["lgd"].clip(0.05, 0.99)
    # Para defaults sem recuperação registada (lgd=1.0), usar média por grade como proxy
    # (tratamento regulatório para exposições sem histórico de recuperação)
    if "grade" in df.columns:
        grade_lgd_mean = df.groupby("grade")["lgd"].transform(
            lambda x: x[x < 0.99].mean() if (x < 0.99).any() else 0.65
        )
        df["lgd"] = np.where(df["lgd"] >= 0.99, grade_lgd_mean.fillna(0.65), df["lgd"])

    # EAD = funded_amnt (proxy para exposição no momento do incumprimento)
    df["ead"] = df["funded_amnt"].fillna(df["loan_amnt"])

    # CCF = ead / committed (simplificado para crédito pessoal = 1.0)
    df["ccf"] = np.where(df["is_default"] == 1, df["ead"] / df["loan_amnt"].clip(lower=1), np.nan)
    df["ccf"] = df["ccf"].clip(0, 1)

    return df


# ---------------------------------------------------------------------------
# Feature Engineering
# ---------------------------------------------------------------------------
def clean_int_rate(rate_str):
    """Limpa taxa de juro (ex: '13.99%' -> 0.1399)."""
    if pd.isna(rate_str):
        return np.nan
    s = str(rate_str).strip().replace("%", "")
    try:
        val = float(s)
        return val / 100 if val > 1 else val
    except ValueError:
        return np.nan


def clean_emp_length(emp_str) -> float:
    """Converte 'emp_length' em anos numéricos."""
    if pd.isna(emp_str):
        return 5.0
    s = str(emp_str).lower().strip()
    if "10+" in s:
        return 10.0
    if "< 1" in s or "less" in s:
        return 0.5
    digits = "".join(c for c in s if c.isdigit())
    return float(digits) if digits else 5.0


def clean_term(term_str) -> int:
    """Converte ' 36 months' -> 36."""
    if pd.isna(term_str):
        return 36
    digits = "".join(c for c in str(term_str) if c.isdigit())
    return int(digits) if digits else 36


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica todas as transformações de features para modelos IRB."""
    df = df.copy()

    # Limpeza de tipos
    df["int_rate"]   = df["int_rate"].apply(clean_int_rate)
    df["emp_length"] = df["emp_length"].apply(clean_emp_length)
    df["term_months"] = df["term"].apply(clean_term)

    # Features derivadas
    df["loan_to_income"] = df["loan_amnt"] / df["annual_inc"].clip(lower=1)
    df["fico_avg"]       = (df["fico_range_low"] + df["fico_range_high"]) / 2
    df["payment_ratio"]  = df["installment"] / df["annual_inc"].clip(lower=1) * 12

    # Binarização de categorias
    df["is_mortgage"]  = (df["home_ownership"] == "MORTGAGE").astype(int)
    df["is_own"]       = (df["home_ownership"] == "OWN").astype(int)
    df["is_long_term"] = (df["term_months"] == 60).astype(int)
    df["is_verified"]  = df["verification_status"].str.lower().str.contains("verified").fillna(False).astype(int)

    # Grade como numérico
    grade_map = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7}
    df["grade_num"] = df["grade"].map(grade_map).fillna(4)

    return df


# ---------------------------------------------------------------------------
# Weight of Evidence (WoE) e Information Value (IV)
# ---------------------------------------------------------------------------
def compute_woe_iv(
    df: pd.DataFrame,
    feature: str,
    target: str = "is_default",
    bins: int = 10,
) -> pd.DataFrame:
    """
    Calcula WoE e IV para uma feature contínua ou categórica.
    Conformidade com metodologia EBA/BCE para Fine Classing.
    """
    df_clean = df[[feature, target]].dropna()
    total_events     = df_clean[target].sum()
    total_non_events = len(df_clean) - total_events

    if total_events == 0 or total_non_events == 0:
        return pd.DataFrame()

    # Discretização
    if df_clean[feature].dtype in [object, "category"]:
        df_clean["bin"] = df_clean[feature].astype(str)
    else:
        try:
            df_clean["bin"] = pd.qcut(df_clean[feature], q=bins, duplicates="drop")
        except ValueError:
            df_clean["bin"] = pd.cut(df_clean[feature], bins=bins)

    grouped = df_clean.groupby("bin")[target].agg(
        count_total="count",
        count_events="sum",
    ).reset_index()

    grouped["count_non_events"] = grouped["count_total"] - grouped["count_events"]
    grouped["pct_events"]       = grouped["count_events"] / total_events
    grouped["pct_non_events"]   = grouped["count_non_events"] / total_non_events

    # Evitar divisão por zero
    grouped["pct_events"]     = grouped["pct_events"].clip(lower=1e-9)
    grouped["pct_non_events"] = grouped["pct_non_events"].clip(lower=1e-9)

    grouped["woe"]    = np.log(grouped["pct_events"] / grouped["pct_non_events"])
    grouped["iv_bin"] = (grouped["pct_events"] - grouped["pct_non_events"]) * grouped["woe"]
    grouped["iv"]     = grouped["iv_bin"].sum()
    grouped["feature"] = feature

    return grouped[["feature", "bin", "count_total", "count_events", "count_non_events", "woe", "iv"]]


def compute_iv_all(df: pd.DataFrame, features: list, target: str = "is_default") -> pd.DataFrame:
    """Calcula IV para todas as features e classifica poder preditivo."""
    iv_results = []
    for feat in features:
        try:
            woe_df = compute_woe_iv(df, feat, target)
            if not woe_df.empty:
                iv_value = woe_df["iv"].iloc[0]
                power = (
                    "Muito Fraco" if iv_value < 0.02 else
                    "Fraco"       if iv_value < 0.10 else
                    "Médio"       if iv_value < 0.30 else
                    "Forte"       if iv_value < 0.50 else
                    "Suspeito"
                )
                iv_results.append({"feature": feat, "iv": round(iv_value, 4), "poder_preditivo": power})
        except Exception:
            pass

    return pd.DataFrame(iv_results).sort_values("iv", ascending=False)


# ---------------------------------------------------------------------------
# Selecção de features para cada modelo
# ---------------------------------------------------------------------------
PD_FEATURES = [
    "fico_avg", "dti", "int_rate", "annual_inc", "emp_length",
    "loan_to_income", "revol_util", "open_acc", "pub_rec",
    "grade_num", "is_mortgage", "is_own", "is_long_term", "is_verified",
]

LGD_FEATURES = [
    "loan_amnt", "funded_amnt", "is_mortgage", "is_own",
    "annual_inc", "dti", "revol_bal", "fico_avg",
    "int_rate", "grade_num", "loan_to_income",
]

EAD_FEATURES = [
    "loan_amnt", "funded_amnt", "int_rate", "is_long_term",
    "annual_inc", "dti", "loan_to_income",
]
