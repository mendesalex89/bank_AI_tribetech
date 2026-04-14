#!/bin/bash
# =============================================================================
# Treinar Modelos IRB — PD, LGD, EAD
# TribeTech | 2026
# =============================================================================
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT/.venv/bin/activate"

cd "$ROOT/fastapi_ml"

echo "=============================================="
echo "  Credit Risk IRB — Treino de Modelos"
echo "  TribeTech | 2026"
echo "=============================================="
echo ""

# Criar pasta de artefactos
mkdir -p artifacts

echo "[1/3] A treinar Modelo PD (Probabilidade de Incumprimento)..."
python training/train_pipeline.py --model pd --sample 300000

echo ""
echo "[2/3] A treinar Modelo LGD (Perda Dado Incumprimento)..."
python training/train_pipeline.py --model lgd --sample 300000

echo ""
echo "[3/3] A treinar Modelo EAD (Exposição no Incumprimento)..."
python training/train_pipeline.py --model ead --sample 300000

echo ""
echo "=============================================="
echo "  Modelos treinados e guardados em artifacts/"
echo "  Reinicia a FastAPI para carregar os modelos"
echo "=============================================="
