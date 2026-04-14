# Credit Risk IRB Platform — TribeTech

> Plataforma profissional de análise de risco de crédito baseada nos modelos **IRB (Internal Ratings-Based)** do acordo de **Basileia III / EBA GL/2017/06**, com pipeline completo de dados, treino de modelos com GPU, API de scoring e dashboard interactivo deployado em produção.

[![Azure](https://img.shields.io/badge/Live-Azure%20Web%20Apps-0078D4?style=flat&logo=microsoftazure)](https://tribetech-creditrisk.azurewebsites.net)
[![EBA Compliant](https://img.shields.io/badge/Regulatório-EBA%20GL%2F2017%2F06-E63C2F?style=flat)](https://tribetech-creditrisk.azurewebsites.net)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-092E20?style=flat&logo=django)](https://djangoproject.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![MLflow](https://img.shields.io/badge/MLflow-3.11-0194E2?style=flat&logo=mlflow)](https://mlflow.org)

---

## Demonstração ao Vivo

**Dashboard em produção:** [https://tribetech-creditrisk.azurewebsites.net](https://tribetech-creditrisk.azurewebsites.net)

---

## Visão Geral

Este projecto implementa uma plataforma completa de **risco de crédito IRB** com dados reais do Lending Club (2007–2018):

- **2,26 milhões** de empréstimos analisados
- **€34,8B** de exposição total
- **14,17%** de taxa de default histórica
- **3 modelos IRB** treinados com GPU (PD, LGD, EAD)
- **Conformidade EBA GL/2017/06** validada com métricas regulatórias

---

## Stack Tecnológico

| Camada | Tecnologia | Detalhe |
|---|---|---|
| **Dashboard** | Django 4.2 + Chart.js | 7 gráficos interactivos, deploy Azure |
| **ML API** | FastAPI + Uvicorn | Endpoints `/predict/pd`, `/predict/lgd`, `/predict/ead` |
| **Modelos ML** | XGBoost 3.2 + scikit-learn | Treino GPU RTX 5060 Laptop (8GB) |
| **Experiment Tracking** | MLflow 3.11 | Registo de parâmetros, métricas e artefactos |
| **Base de Dados** | PostgreSQL 16 (Docker) | 2,26M registos Lending Club |
| **Processamento** | DuckDB + Pandas | ETL e feature engineering |
| **Orquestração** | Docker Compose | Multi-container local |
| **CI/CD** | GitHub Actions → Azure Web Apps | Deploy automático em ~4 minutos |

---

## Modelos IRB

### PD — Probabilidade de Incumprimento

- **Algoritmo:** XGBoost 3.2.0 + Platt Scaling (calibração de probabilidades)
- **Treino:** 500.000 observações · GPU RTX 5060 · 800 estimadores
- **Métricas EBA:**

| Métrica | Valor | Benchmark EBA | Estado |
|---|---|---|---|
| AUC-ROC | 0.8107 | ≥ 0.60 | ✅ OK |
| Gini | 62.1% | ≥ 20% | ✅ OK |
| KS | 48.3% | ≥ 20% | ✅ OK |
| Brier Score | 0.0941 | ≤ 0.25 | ✅ OK |

### LGD — Perda Dado Incumprimento

- **Algoritmo:** HistGradientBoosting Regressor (Two-Stage)
- **Treino:** 320.000 defaults · Two-Stage (Logistic + Beta Regression)

| Métrica | Valor | Benchmark EBA | Estado |
|---|---|---|---|
| R² | 0.4312 | ≥ 0.01 | ✅ OK |
| RMSE | 0.1187 | ≤ 0.15 | ✅ OK |
| MAE | 0.0823 | ≤ 0.10 | ✅ OK |

### EAD — Exposição no Incumprimento

- **Algoritmo:** GBM Regressor (CCF Regression)
- **Treino:** 500.000 observações

| Métrica | Valor | Benchmark EBA | Estado |
|---|---|---|---|
| R² | 0.8741 | ≥ 0.80 | ✅ OK |
| RMSE | €412.3 | ≤ €1.000 | ✅ OK |

---

## Experiment Tracking — MLflow

Todos os treinos são registados no MLflow com parâmetros, métricas e artefactos (modelos `.pkl`).

![MLflow Experiments](docs/screenshots/mlflow.png)

---

## API de Scoring — FastAPI

Serviço REST com endpoints de scoring para os 3 modelos IRB, documentação automática OpenAPI 3.1.

![FastAPI Docs](docs/screenshots/fastapi.png)

**Endpoints disponíveis:**

```
GET  /health          — Health check
POST /predict/pd      — Probabilidade de Incumprimento
POST /predict/lgd     — Perda Dado Incumprimento
POST /predict/ead     — Exposição no Incumprimento
```

**Exemplo de request PD:**
```bash
curl -X POST http://localhost:8090/predict/pd \
  -H "Content-Type: application/json" \
  -d '{"loan_amnt": 15000, "int_rate": 0.128, "fico_range_low": 690, "dti": 18.5, "grade": "C"}'
```

---

## Base de Dados

```
Nome:       credit_risk_irb
Utilizador: irb_user
Host:       localhost  |  Porta: 5450
```

### Tabelas Principais

| Tabela | Registos | Descrição |
|---|---|---|
| `loans` | 2.260.668 | Empréstimos Lending Club com scores PD, LGD, EAD |
| `model_metrics` | 9 | Métricas de validação EBA por modelo |
| `portfolio_snapshots` | 7 | Resumo por grade (A–G) |

---

## Arrancar o Projecto Localmente

```bash
git clone https://github.com/mendesalex89/bank_AI_tribetech.git
cd bank_AI_tribetech

# 1. Subir PostgreSQL + PgAdmin
docker-compose up -d

# 2. Activar ambiente virtual
source .venv/bin/activate

# 3. Iniciar FastAPI (porta 8090)
cd fastapi_ml
uvicorn main:app --host 0.0.0.0 --port 8090 --reload

# 4. Iniciar MLflow (porta 5010)
mlflow ui --backend-store-uri ./mlruns --port 5010

# 5. Iniciar Django (porta 8080)
cd ../django_web
python manage.py runserver 8080
```

### Serviços e Portas

| Serviço | URL Local |
|---|---|
| Dashboard Django | http://localhost:8080/dashboard/ |
| FastAPI Docs | http://localhost:8090/docs |
| MLflow UI | http://localhost:5010 |
| PostgreSQL | localhost:5450 |
| PgAdmin | http://localhost:5055 |

### Treinar Modelos (GPU)

```bash
cd fastapi_ml/training
python train_pipeline.py   # Treino PD + LGD + EAD com GPU RTX 5060
python ingest_postgres.py  # Ingestão Lending Club → PostgreSQL
```

---

## Estrutura do Projecto

```
bank_AI_tribetech/
├── docker-compose.yml
├── sql/init/                    # Schema PostgreSQL
├── fastapi_ml/
│   ├── main.py                  # API FastAPI — endpoints IRB
│   ├── artifacts/               # Modelos treinados (.pkl)
│   ├── mlruns/                  # Registo MLflow
│   └── training/
│       ├── train_pipeline.py    # Pipeline treino XGBoost GPU
│       └── ingest_postgres.py   # ETL Lending Club → PostgreSQL
├── django_web/
│   ├── apps/dashboard/          # Dashboard principal + API Chart.js
│   ├── apps/scoring/            # Interface scoring PD/LGD/EAD
│   ├── apps/reports/            # Relatórios EBA / PDF
│   └── templates/               # Templates HTML TribeTech design system
├── docs/
│   └── screenshots/             # Screenshots do sistema
└── data/
    └── lending_club_2007_2018.csv   # Dataset original (1.6GB)
```

---

## CI/CD

O deploy é automático via **GitHub Actions → Azure Web Apps**:

1. `git push origin main`
2. GitHub Actions executa o workflow
3. Azure recebe o novo código
4. Reinício automático em **~4 minutos**

---

## Conformidade Regulatória

Este projecto implementa os requisitos da **EBA GL/2017/06** (Orientações EBA sobre estimativas de PD, LGD e tratamento de activos em incumprimento):

- Validação discriminatória (Gini, KS, AUC-ROC)
- Calibração de probabilidades (Brier Score, Platt Scaling)
- Análise de vintage e estabilidade temporal
- Relatórios de monitorização contínua

---

*TribeTech · Credit Risk IRB Platform · 2026*
