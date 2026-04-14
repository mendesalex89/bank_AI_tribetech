"""
Chatbot IRB — TribeTech
Agente de IA com tool use para scoring e análise de portfólio de crédito.
Usa OpenRouter (DeepSeek v3) com tools que chamam a FastAPI e o PostgreSQL.
"""
import json
import logging
import os

import requests
from django.db import connection
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek/deepseek-v3.2")
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8090")

# ---------------------------------------------------------------------------
# Definição das Tools
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "predict_credit_risk",
            "description": (
                "Calcula o risco de crédito IRB completo (PD, LGD, EAD) para um empréstimo. "
                "Usa quando o utilizador descreve um empréstimo ou pede análise de risco."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "loan_amnt":      {"type": "number",  "description": "Montante do empréstimo em EUR"},
                    "int_rate":       {"type": "number",  "description": "Taxa de juro (ex: 0.128 para 12.8%)"},
                    "annual_inc":     {"type": "number",  "description": "Rendimento anual do cliente em EUR"},
                    "dti":            {"type": "number",  "description": "Debt-to-Income ratio (ex: 18.5)"},
                    "fico_range_low": {"type": "integer", "description": "FICO score mínimo (ex: 680)"},
                    "emp_length":     {"type": "number",  "description": "Anos de emprego (ex: 5)"},
                    "home_ownership": {"type": "string",  "description": "Tipo de habitação: RENT, OWN, MORTGAGE"},
                    "purpose":        {"type": "string",  "description": "Finalidade: debt_consolidation, credit_card, home_improvement, other"},
                    "grade":          {"type": "string",  "description": "Grade IRB estimada: A, B, C, D, E, F, G"},
                },
                "required": ["loan_amnt", "fico_range_low", "dti"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_portfolio",
            "description": (
                "Consulta dados reais do portfólio de crédito no PostgreSQL. "
                "Usa para responder perguntas sobre distribuição de risco, grades, vintage, FICO, exposição total, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["overview", "by_grade", "vintage", "fico_distribution", "top_defaults"],
                        "description": "Tipo de análise de portfólio a efectuar",
                    }
                },
                "required": ["query_type"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Executores das Tools
# ---------------------------------------------------------------------------
def _run_predict_credit_risk(args: dict) -> dict:
    """Chama FastAPI para obter PD, LGD, EAD."""
    payload = {
        "loan_amnt":      args.get("loan_amnt", 10000),
        "int_rate":       args.get("int_rate", 0.13),
        "annual_inc":     args.get("annual_inc", 50000),
        "dti":            args.get("dti", 18.0),
        "fico_range_low": args.get("fico_range_low", 680),
        "fico_range_high":args.get("fico_range_low", 680) + 4,
        "emp_length":     args.get("emp_length", 3),
        "home_ownership": args.get("home_ownership", "RENT"),
        "purpose":        args.get("purpose", "debt_consolidation"),
        "grade":          args.get("grade", "C"),
        "loan_status":    "Current",
        "sub_grade":      args.get("grade", "C") + "3",
        "addr_state":     "CA",
        "open_acc":       8,
        "pub_rec":        0,
        "revol_bal":      12000,
        "revol_util":     45.0,
        "total_acc":      20,
        "mort_acc":       0,
        "pub_rec_bankruptcies": 0,
    }
    results = {}
    for model in ["pd", "lgd", "ead"]:
        try:
            r = requests.post(f"{FASTAPI_URL}/predict/{model}", json=payload, timeout=10)
            if r.status_code == 200:
                results[model] = r.json()
        except Exception as e:
            results[model] = {"error": str(e)}

    # Calcular Expected Loss
    try:
        pd_val  = results.get("pd", {}).get("pd", 0.14)
        lgd_val = results.get("lgd", {}).get("lgd", 0.45)
        ead_val = results.get("ead", {}).get("ead", payload["loan_amnt"])
        el = round(pd_val * lgd_val * ead_val, 2)
        results["expected_loss"] = el
        results["input"] = {"loan_amnt": payload["loan_amnt"], "fico": payload["fico_range_low"], "dti": payload["dti"]}
    except Exception:
        pass

    return results


def _run_query_portfolio(args: dict) -> dict:
    """Executa query SQL no PostgreSQL e devolve resultados."""
    query_type = args.get("query_type", "overview")

    queries = {
        "overview": """
            SELECT
                COUNT(*)                                                        AS total_emprestimos,
                ROUND(SUM(loan_amnt)/1e6, 1)                                   AS exposicao_milhoes,
                ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0 END)*100, 2)   AS taxa_default_pct,
                ROUND(AVG((fico_range_low+fico_range_high)/2.0), 1)            AS fico_medio,
                ROUND(AVG(dti)::numeric, 1)                                    AS dti_medio,
                ROUND(AVG(int_rate)*100, 2)                                    AS taxa_juro_media_pct
            FROM loans
        """,
        "by_grade": """
            SELECT grade,
                COUNT(*)                                                       AS emprestimos,
                ROUND(SUM(loan_amnt)/1e6, 1)                                   AS exposicao_m,
                ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0 END)*100, 2)   AS taxa_default_pct,
                ROUND(AVG((fico_range_low+fico_range_high)/2.0), 0)            AS fico_medio
            FROM loans WHERE grade IS NOT NULL
            GROUP BY grade ORDER BY grade
        """,
        "vintage": """
            SELECT EXTRACT(YEAR FROM issue_d)::int AS ano,
                COUNT(*) AS emprestimos,
                ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0 END)*100, 2) AS taxa_default_pct
            FROM loans WHERE issue_d IS NOT NULL
            GROUP BY ano ORDER BY ano
        """,
        "fico_distribution": """
            SELECT
                (FLOOR((fico_range_low+fico_range_high)/2.0/20)*20)::int AS fico_bucket,
                COUNT(*) AS total,
                ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0 END)*100, 2) AS taxa_default_pct
            FROM loans WHERE fico_range_low > 0
            GROUP BY fico_bucket ORDER BY fico_bucket
        """,
        "top_defaults": """
            SELECT purpose,
                COUNT(*) AS emprestimos,
                ROUND(AVG(CASE WHEN is_default THEN 1.0 ELSE 0 END)*100, 2) AS taxa_default_pct
            FROM loans WHERE purpose IS NOT NULL
            GROUP BY purpose ORDER BY taxa_default_pct DESC LIMIT 8
        """,
    }

    try:
        with connection.cursor() as cur:
            cur.execute(queries[query_type])
            cols = [c[0] for c in cur.description]
            rows = [dict(zip(cols, [str(v) if v is not None else None for v in row]))
                    for row in cur.fetchall()]
        return {"query_type": query_type, "data": rows}
    except Exception as e:
        return {"error": str(e), "query_type": query_type}


def _execute_tool(name: str, args: dict) -> str:
    if name == "predict_credit_risk":
        result = _run_predict_credit_risk(args)
    elif name == "query_portfolio":
        result = _run_query_portfolio(args)
    else:
        result = {"error": f"Tool desconhecida: {name}"}
    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Sistema prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """És o assistente de risco de crédito IRB da TribeTech. Tens acesso a duas ferramentas REAIS que DEVES usar obrigatoriamente:

REGRA ABSOLUTA:
- Se a mensagem mencionar empréstimo, montante, FICO, DTI, crédito, scoring, PD, LGD ou EAD → chama SEMPRE a tool predict_credit_risk. NUNCA respondas com valores estimados ou inventados.
- Se a mensagem perguntar sobre portfólio, grades, distribuição, vintage, exposição, default, dados reais → chama SEMPRE a tool query_portfolio.
- NUNCA inventes valores de PD, LGD, EAD ou Expected Loss. Esses valores vêm EXCLUSIVAMENTE das tools.

Após receber os resultados das tools, apresenta-os de forma clara em português europeu com:
- PD (Probabilidade de Incumprimento) em %
- LGD (Perda Dado Incumprimento) em %
- EAD (Exposição no Incumprimento) em €
- Expected Loss = PD × LGD × EAD em €
- Contexto regulatório EBA GL/2017/06
Sê directo e conciso."""


# ---------------------------------------------------------------------------
# Views Django
# ---------------------------------------------------------------------------
def chatbot(request):
    return render(request, "chatbot/index.html")


@csrf_exempt
@require_POST
def api_chat(request):
    try:
        body = json.loads(request.body)
        messages = body.get("messages", [])
    except Exception:
        return JsonResponse({"error": "JSON inválido"}, status=400)

    if not OPENROUTER_API_KEY:
        return JsonResponse({"error": "OPENROUTER_API_KEY não configurada"}, status=500)

    # Construir histórico com system prompt
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://tribetech-creditrisk.azurewebsites.net",
        "X-Title": "TribeTech Credit Risk IRB",
    }

    # Agentic loop — máximo 5 iterações para tool calls encadeadas
    for _ in range(5):
        payload = {
            "model": MODEL_NAME,
            "messages": full_messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": 0.3,
            "max_tokens": 1024,
        }

        try:
            resp = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            return JsonResponse({"error": f"Erro OpenRouter: {e}"}, status=502)

        choice = data["choices"][0]
        msg = choice["message"]
        finish = choice.get("finish_reason", "stop")

        # Se o modelo quer chamar tools
        if finish == "tool_calls" and msg.get("tool_calls"):
            full_messages.append(msg)
            for tc in msg["tool_calls"]:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"])
                tool_result = _execute_tool(fn_name, fn_args)
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })
            continue  # próxima iteração com resultados das tools

        # Resposta final
        return JsonResponse({"reply": msg.get("content", "")})

    return JsonResponse({"reply": "Não foi possível processar o pedido. Tenta novamente."})
