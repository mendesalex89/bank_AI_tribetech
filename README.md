# bank_AI_tribetech — Credit Risk IRB Platform

Plataforma de análise de risco de crédito baseada nos modelos IRB (Internal Ratings-Based) do acordo de Basileia III / EBA GL/2017/06.  
Dados reais: **Lending Club 2007–2018** · 199.825 empréstimos · $3.008M de exposição.

---

## Stack Tecnológico

| Camada | Tecnologia |
|---|---|
| Base de Dados | PostgreSQL 16 (Docker) |
| ML Service | FastAPI + XGBoost + scikit-learn |
| Dashboard | Django 4 + Chart.js |
| Experiment Tracking | MLflow |
| Treino | XGBoost GPU (RTX 5060) + DuckDB |
| Orquestração | Docker Compose |

---

## Base de Dados

```
Nome:       credit_risk_irb
Utilizador: irb_user
Password:   irb_secure_2026
Host:       localhost
Porta:      5450
```

Ligação psql:
```bash
psql -h localhost -p 5450 -U irb_user -d credit_risk_irb
```

### Tabelas principais

| Tabela | Registos | Descrição |
|---|---|---|
| `loans` | 199.825 | Empréstimos Lending Club com PD, LGD, EAD |
| `model_metrics` | 9 | Métricas de validação PD/LGD/EAD |
| `portfolio_snapshots` | 7 | Resumo por grade (A–G) |

---

## Portas dos Serviços

| Serviço | Porta | URL |
|---|---|---|
| Django Dashboard | 8080 | http://localhost:8080/dashboard/ |
| FastAPI ML | 8090 | http://localhost:8090/docs |
| PostgreSQL | 5450 | — |
| MLflow | 5010 | http://localhost:5010 |
| PgAdmin | 5055 | http://localhost:5055 |

---

## Modelos IRB

### PD — Probability of Default
- **Algoritmo:** XGBoost 3.2.0 + Platt Scaling
- **Treino:** 500.000 observações, GPU RTX 5060, 800 estimadores
- **AUC-ROC:** 0.710 | **Gini:** 42.0% | **KS:** 30.2% | **Brier:** 0.145

### LGD — Loss Given Default
- **Algoritmo:** GBM Regressor (HistGradientBoosting)
- **R²:** 0.0084 | **RMSE:** 0.073 | **MAE:** 0.036

### EAD — Exposure at Default
- **Algoritmo:** GBM Regressor
- **R²:** 1.00 | **RMSE:** $37.97

---

## Arrancar o Projecto

```bash
cd bank_AI_tribetech

# Subir todos os serviços
docker-compose up -d

# Ver logs
docker-compose logs -f django

# Treinar modelos (com GPU)
bash train_models.sh

# Ingerir dados no PostgreSQL
python fastapi_ml/training/ingest_postgres.py
```

---

## Dashboard

O dashboard Django em `/dashboard/` apresenta:

- **6 KPI cards** — empréstimos, exposição, taxa default, FICO médio, perda realizada, capital Basel
- **7 gráficos interactivos** (Chart.js)
  - Default Rate + EL/RL por Grade
  - Distribuição por Grade (Doughnut)
  - Análise de Vintage 2007–2018
  - Finalidade do Empréstimo (Top 8)
  - Distribuição FICO Score
  - FICO Médio vs DR por Grade
- **Painel de métricas IRB** com badges EBA (OK/WARN/BAD)
- **Tabela de portfólio** com Expected Loss por grade

---

## Relatórios EBA

- `/relatorios/eba/` — Validação EBA GL/2017/06 (PD, LGD, EAD)
- `/relatorios/monitoring/` — Monitorização de performance
- `/relatorios/pdf/` — Download PDF do relatório

---

## Estrutura do Projecto

```
bank_AI_tribetech/
├── docker-compose.yml
├── sql/init/              # Schema PostgreSQL
├── fastapi_ml/
│   ├── main.py            # Endpoints PD/LGD/EAD
│   ├── artifacts/         # Modelos treinados (.pkl)
│   └── training/
│       ├── train_pipeline.py   # Treino XGBoost GPU
│       └── ingest_postgres.py  # Ingestão Lending Club → PostgreSQL
├── django_web/
│   ├── apps/dashboard/    # Dashboard principal
│   ├── apps/reports/      # Relatórios EBA/PDF
│   └── templates/         # Templates HTML TribeTech
├── notebooks/
│   ├── 01_eda.ipynb
│   ├── 02_feature_engineering.ipynb
│   └── 03_pd_model.ipynb
└── data/
    └── lending_club_2007_2018.csv   # 1.6GB dataset
```

---

*TribeTech · Credit Risk IRB Platform · 2026*
