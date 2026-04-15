from django.shortcuts import render


def home(request):
    phases = [
        {"num": 1, "days": "3 dias", "title": "Dados, EDA e Gestão",
         "desc": "Download Lending Club, EDA completo, WoE, IV, Fine/Coarse classing regulatório.",
         "tags": [{"type": "data", "label": "Pandas"}, {"type": "data", "label": "DuckDB"}]},
        {"num": 2, "days": "5 dias", "title": "Modelos IRB",
         "desc": "PD → Logistic + XGBoost + Scorecard. LGD → Two-stage. EAD → CCF Regression.",
         "tags": [{"type": "ml", "label": "scikit-learn"}, {"type": "ml", "label": "XGBoost"}]},
        {"num": 3, "days": "2 dias", "title": "Validação Regulatória EBA",
         "desc": "Gini, KS, AUC, Brier Score. Backtesting e calibração dos modelos.",
         "tags": [{"type": "reg", "label": "EBA"}, {"type": "reg", "label": "Backtesting"}]},
        {"num": 4, "days": "1 dia", "title": "SQL Analytics",
         "desc": "Queries de portfólio em PostgreSQL. Taxas de default, safadas, vintage analysis.",
         "tags": [{"type": "data", "label": "PostgreSQL"}, {"type": "data", "label": "SQL"}]},
        {"num": 5, "days": "2 dias", "title": "FastAPI ML Service",
         "desc": "/predict/pd, /predict/batch, /metrics — Swagger UI automático.",
         "tags": [{"type": "api", "label": "FastAPI"}, {"type": "api", "label": "Swagger"}]},
        {"num": 6, "days": "4 dias", "title": "Django Dashboard",
         "desc": "Dashboard interactivo com scoring em tempo real para PD, LGD e EAD.",
         "tags": [{"type": "web", "label": "Django"}, {"type": "web", "label": "Chart.js"}]},
        {"num": 7, "days": "1 dia", "title": "Docker",
         "desc": "docker-compose.yml — um comando e tudo arranca.",
         "tags": [{"type": "infra", "label": "Docker"}, {"type": "infra", "label": "Compose"}]},
        {"num": 8, "days": "1 dia", "title": "Deploy Azure",
         "desc": "GitHub → Azure App Service. Link público azurewebsites.net.",
         "tags": [{"type": "infra", "label": "Azure"}, {"type": "infra", "label": "CI/CD"}]},
        {"num": 9, "days": "1 dia", "title": "Documentação",
         "desc": "README profissional, model_validation_report.pdf estilo EBA.",
         "tags": [{"type": "reg", "label": "PDF EBA"}, {"type": "data", "label": "Docs"}]},
    ]

    stack = [
        {"icon": "🐍", "name": "Python 3.12", "desc": "Base do projecto", "color": "card-icon blue"},
        {"icon": "🧠", "name": "scikit-learn + XGBoost", "desc": "Modelos PD, LGD, EAD", "color": "card-icon red"},
        {"icon": "🐼", "name": "Pandas + NumPy", "desc": "Manipulação de dados", "color": "card-icon orange"},
        {"icon": "🦆", "name": "DuckDB", "desc": "ETL ficheiros grandes (1.6GB+)", "color": "card-icon yellow"},
        {"icon": "🐘", "name": "PostgreSQL", "desc": "Base de dados analítica", "color": "card-icon blue"},
        {"icon": "⚡", "name": "FastAPI", "desc": "API REST para os modelos", "color": "card-icon green"},
        {"icon": "🌐", "name": "Django 5", "desc": "Dashboard e interface web", "color": "card-icon orange"},
        {"icon": "📊", "name": "Chart.js + Plotly", "desc": "Visualizações interactivas", "color": "card-icon red"},
        {"icon": "🔬", "name": "MLflow", "desc": "Tracking de experimentos (≈Databricks)", "color": "card-icon blue"},
        {"icon": "🐳", "name": "Docker Compose", "desc": "Containerização completa", "color": "card-icon green"},
        {"icon": "☁️", "name": "Azure App Service", "desc": "Hosting público", "color": "card-icon yellow"},
        {"icon": "📄", "name": "ReportLab", "desc": "Relatórios PDF estilo EBA", "color": "card-icon red"},
    ]

    return render(request, "home/index.html", {"phases": phases, "stack": stack})


def guide(request):
    return render(request, "home/guide.html")
