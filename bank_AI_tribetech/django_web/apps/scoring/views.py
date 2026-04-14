"""
Scoring — Modelos PD, LGD, EAD interactivos
Chama FastAPI ML Service ou fallback para modelo local
"""
import json
import logging
import os

import httpx
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)
FASTAPI_URL = getattr(settings, "FASTAPI_URL", "http://localhost:8090")


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------
def scoring_pd(request):
    return render(request, "scoring/pd.html")


def scoring_lgd(request):
    return render(request, "scoring/lgd.html")


def scoring_ead(request):
    return render(request, "scoring/ead.html")


def scoring_batch(request):
    return render(request, "scoring/batch.html")


# ---------------------------------------------------------------------------
# API — proxy para FastAPI ou fallback local
# ---------------------------------------------------------------------------
def _call_fastapi(endpoint: str, payload: dict) -> dict:
    url = f"{FASTAPI_URL}{endpoint}"
    try:
        resp = httpx.post(url, json=payload, timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning("FastAPI indisponível (%s) — usando fallback local", exc)
        return None


def _pd_fallback(data: dict) -> dict:
    """Modelo logístico simples de demonstração."""
    fico    = float(data.get("fico_score", 700))
    dti     = float(data.get("dti", 15))
    int_rate = float(data.get("int_rate", 12))
    annual_inc = float(data.get("annual_inc", 60000))
    emp_len = float(data.get("emp_length", 5))

    # Logit simplificado (demonstração)
    logit = (
        -4.5
        + (700 - fico) * 0.015
        + dti * 0.04
        + int_rate * 0.07
        - min(annual_inc / 10000, 5) * 0.12
        - emp_len * 0.03
    )
    import math
    pd_val = 1 / (1 + math.exp(-logit))
    pd_val = max(0.001, min(0.999, pd_val))

    score = max(300, min(850, int(850 - pd_val * 550)))

    grade_map = [
        (0.05, "A"), (0.10, "B"), (0.15, "C"),
        (0.20, "D"), (0.25, "E"), (0.35, "F"), (1.0, "G"),
    ]
    grade = next(g for (t, g) in grade_map if pd_val <= t)

    return {
        "pd": round(pd_val, 4),
        "score": score,
        "grade": grade,
        "pd_pct": round(pd_val * 100, 2),
        "risk_label": (
            "Baixo" if pd_val < 0.05 else
            "Moderado" if pd_val < 0.15 else
            "Alto" if pd_val < 0.25 else "Muito Alto"
        ),
        "model": "fallback_logistic_v1",
    }


def _lgd_fallback(data: dict) -> dict:
    import math
    collateral  = float(data.get("collateral_value", 0))
    loan_amnt   = float(data.get("loan_amnt", 10000))
    home_own    = data.get("home_ownership", "RENT")
    recoveries  = float(data.get("recoveries", 0))

    collateral_ratio = min(collateral / max(loan_amnt, 1), 1.0)
    lgd = 0.45 - collateral_ratio * 0.30
    lgd += 0.10 if home_own == "RENT" else 0.0
    lgd -= min(recoveries / max(loan_amnt, 1), 0.3)
    lgd = max(0.01, min(0.99, lgd))

    return {
        "lgd": round(lgd, 4),
        "lgd_pct": round(lgd * 100, 2),
        "expected_loss": round(loan_amnt * lgd, 2),
        "recovery_rate": round(1 - lgd, 4),
        "risk_label": "Baixo" if lgd < 0.3 else "Médio" if lgd < 0.6 else "Alto",
        "model": "fallback_twostage_v1",
    }


def _ead_fallback(data: dict) -> dict:
    committed   = float(data.get("committed_amount", 10000))
    drawn       = float(data.get("drawn_amount", 5000))
    limit       = float(data.get("credit_limit", 20000))
    utilization = drawn / max(limit, 1)
    undrawn     = max(committed - drawn, 0)
    ccf         = 0.4 + utilization * 0.25
    ccf         = max(0.0, min(1.0, ccf))
    ead         = drawn + ccf * undrawn

    return {
        "ead": round(ead, 2),
        "ccf": round(ccf, 4),
        "ccf_pct": round(ccf * 100, 2),
        "utilization": round(utilization * 100, 2),
        "model": "fallback_ccf_v1",
    }


@csrf_exempt
def api_predict_pd(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método inválido"}, status=405)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    result = _call_fastapi("/predict/pd", data)
    if result is None:
        result = _pd_fallback(data)

    return JsonResponse(result)


@csrf_exempt
def api_predict_lgd(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método inválido"}, status=405)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    result = _call_fastapi("/predict/lgd", data)
    if result is None:
        result = _lgd_fallback(data)

    return JsonResponse(result)


@csrf_exempt
def api_predict_ead(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método inválido"}, status=405)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    result = _call_fastapi("/predict/ead", data)
    if result is None:
        result = _ead_fallback(data)

    return JsonResponse(result)


@csrf_exempt
def api_batch_upload(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método inválido"}, status=405)
    return JsonResponse({"status": "ok", "message": "Upload recebido. A processar..."})
