#!/bin/bash
# =============================================================================
# Credit Risk IRB Platform — Script de Arranque (Desenvolvimento)
# TribeTech | 2026
# =============================================================================
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv/bin/activate"
DJANGO_DIR="$ROOT/django_web"
FASTAPI_DIR="$ROOT/fastapi_ml"

# Cores
RED='\033[0;31m'; ORANGE='\033[0;33m'; GREEN='\033[0;32m'
BLUE='\033[0;34m'; NC='\033[0m'; BOLD='\033[1m'

banner() {
    echo ""
    echo -e "${RED}${BOLD}╔═══════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}${BOLD}║   Credit Risk IRB Platform — TribeTech 2026       ║${NC}"
    echo -e "${RED}${BOLD}╚═══════════════════════════════════════════════════╝${NC}"
    echo ""
}

check_port() {
    if ss -tlnp 2>/dev/null | grep -q ":$1 "; then
        echo -e "${ORANGE}  ⚠  Porta $1 já ocupada${NC}"
        return 1
    fi
    return 0
}

banner

# 1. PostgreSQL via Docker
echo -e "${BLUE}${BOLD}[1/4] PostgreSQL (porta 5450)${NC}"
if ! docker ps --filter "name=irb_postgres" --filter "status=running" -q | grep -q .; then
    cd "$ROOT" && docker-compose up -d postgres
    echo -e "${GREEN}  ✓  PostgreSQL iniciado${NC}"
    # Aguardar saúde
    for i in {1..20}; do
        docker exec irb_postgres pg_isready -U irb_user -q 2>/dev/null && break
        sleep 1
    done
else
    echo -e "${GREEN}  ✓  PostgreSQL já está a correr${NC}"
fi

# 2. Activar venv
source "$VENV"

# 3. Django
echo -e "${BLUE}${BOLD}[2/4] Django Dashboard (porta 8080)${NC}"
if check_port 8080; then
    cd "$DJANGO_DIR"
    python manage.py migrate --run-syncdb 2>/dev/null | grep -E "OK|Applying" || true
    python manage.py runserver 0.0.0.0:8080 2>&1 &
    DJANGO_PID=$!
    echo -e "${GREEN}  ✓  Django: http://localhost:8080${NC}"
fi

# 4. FastAPI
echo -e "${BLUE}${BOLD}[3/4] FastAPI ML Service (porta 8090)${NC}"
if check_port 8090; then
    cd "$FASTAPI_DIR"
    uvicorn main:app --host 0.0.0.0 --port 8090 --reload 2>&1 &
    FASTAPI_PID=$!
    echo -e "${GREEN}  ✓  FastAPI: http://localhost:8090/docs${NC}"
fi

echo ""
echo -e "${GREEN}${BOLD}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║   Plataforma em funcionamento!                    ║${NC}"
echo -e "${GREEN}${BOLD}╠═══════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║   Dashboard    →  http://localhost:8080           ║${NC}"
echo -e "${GREEN}║   API (Swagger)→  http://localhost:8090/docs      ║${NC}"
echo -e "${GREEN}║   MLflow       →  http://localhost:5010            ║${NC}"
echo -e "${GREEN}║   PgAdmin      →  http://localhost:5055            ║${NC}"
echo -e "${GREEN}║   PostgreSQL   →  localhost:5450                  ║${NC}"
echo -e "${GREEN}${BOLD}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Para parar: kill $DJANGO_PID $FASTAPI_PID ou Ctrl+C${NC}"

# Aguardar
wait
