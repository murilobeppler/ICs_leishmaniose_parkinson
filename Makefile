# =============================================================================
# ic-research-lab — Makefile de Orquestração do Monorepo
# =============================================================================
# Uso principal:
#   make setup   -> instala ambientes Python (uv), pacotes JS (pnpm) e gera dados sintéticos
#   make lint    -> executa ruff + mypy nos pacotes Python e eslint + tsc + prettier nos fronts
#   make test    -> executa pytest em packages/core, peptide-docking e fog-gnn
#   make dev-a   -> sobe API (:8001) + Front Next.js (:3001) do Módulo A (peptide-docking)
#   make dev-b   -> sobe API (:8002) + Front Next.js (:3002) do Módulo B (fog-gnn)
# =============================================================================

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

CORE_DIR := packages/core
MOD_A_BACK := modules/peptide-docking/backend
MOD_A_FRONT := modules/peptide-docking/frontend
MOD_B_BACK := modules/fog-gnn/backend
MOD_B_FRONT := modules/fog-gnn/frontend

PEPTIDE_API_HOST ?= 127.0.0.1
PEPTIDE_API_PORT ?= 8001
FOG_API_HOST ?= 127.0.0.1
FOG_API_PORT ?= 8002

.PHONY: help setup setup-env setup-python setup-js synthetic \
        lint lint-python lint-js format \
        test test-core test-a test-b \
        dev-a dev-b api-a api-b front-a front-b clean

help:
	@echo "======================================================================"
	@echo " ic-research-lab — Comandos disponíveis"
	@echo "======================================================================"
	@echo "  make setup      Instala dependências (uv + pnpm) e gera dados sintéticos"
	@echo "  make synthetic  Regenera bibliotecas/datasets sintéticos dos módulos A e B"
	@echo "  make lint       Roda ruff + mypy (Python) e eslint + tsc + prettier (TS)"
	@echo "  make format     Formata código Python (ruff) e TypeScript/Markdown (prettier)"
	@echo "  make test       Roda suítes pytest (core, módulo A, módulo B + fronteira)"
	@echo "  make dev-a      Inicia backend FastAPI (:8001) + front Next.js (:3001) do Módulo A"
	@echo "  make dev-b      Inicia backend FastAPI (:8002) + front Next.js (:3002) do Módulo B"
	@echo "  make clean      Remove caches temporários (.pytest_cache, .ruff_cache, .next)"

# -----------------------------------------------------------------------------
# Setup & Dados Sintéticos
# -----------------------------------------------------------------------------
setup: setup-env setup-python setup-js synthetic
	@echo "[OK] Setup completo concluído."

setup-env:
	@if [ ! -f .env ]; then cp .env.example .env && echo "[OK] .env criado a partir de .env.example"; fi

setup-python:
	cd $(CORE_DIR) && uv sync --all-extras
	cd $(MOD_A_BACK) && uv sync --all-extras
	cd $(MOD_B_BACK) && uv sync --all-extras

setup-js:
	pnpm install

synthetic:
	cd $(MOD_A_BACK) && uv run python scripts/make_synthetic_library.py
	cd $(MOD_B_BACK) && uv run python scripts/make_synthetic_imu.py

# -----------------------------------------------------------------------------
# Qualidade: Lint, Typecheck & Formatação
# -----------------------------------------------------------------------------
lint: lint-python lint-js

lint-python:
	cd $(CORE_DIR) && uv run ruff check . && uv run ruff format --check . && uv run mypy src tests
	cd $(MOD_A_BACK) && uv run ruff check . && uv run ruff format --check . && uv run mypy src tests scripts
	cd $(MOD_B_BACK) && uv run ruff check . && uv run ruff format --check . && uv run mypy src tests scripts

lint-js:
	pnpm run lint
	pnpm run typecheck
	pnpm run format:check

format:
	cd $(CORE_DIR) && uv run ruff format . && uv run ruff check --fix .
	cd $(MOD_A_BACK) && uv run ruff format . && uv run ruff check --fix .
	cd $(MOD_B_BACK) && uv run ruff format . && uv run ruff check --fix .
	pnpm run format

# -----------------------------------------------------------------------------
# Testes Automatizados
# -----------------------------------------------------------------------------
test: test-core test-a test-b

test-core:
	cd $(CORE_DIR) && uv run pytest -v

test-a:
	cd $(MOD_A_BACK) && uv run pytest -v

test-b:
	cd $(MOD_B_BACK) && uv run pytest -v

# -----------------------------------------------------------------------------
# Ambientes de Desenvolvimento (Módulo A e Módulo B)
# -----------------------------------------------------------------------------
api-a:
	cd $(MOD_A_BACK) && uv run python scripts/make_synthetic_library.py && uv run uvicorn peptide_docking.api:app --reload --host $(PEPTIDE_API_HOST) --port $(PEPTIDE_API_PORT)

front-a:
	pnpm --filter @ic-research-lab/peptide-docking-frontend dev

dev-a:
	@echo "[Módulo A] Garantindo biblioteca sintética e iniciando FastAPI (:$(PEPTIDE_API_PORT)) + Next.js (:3001)..."
	cd $(MOD_A_BACK) && uv run python scripts/make_synthetic_library.py
	trap 'kill 0' INT TERM EXIT; \
	(cd $(MOD_A_BACK) && uv run uvicorn peptide_docking.api:app --reload --host $(PEPTIDE_API_HOST) --port $(PEPTIDE_API_PORT)) & \
	pnpm --filter @ic-research-lab/peptide-docking-frontend dev & \
	wait

api-b:
	cd $(MOD_B_BACK) && uv run python scripts/make_synthetic_imu.py && uv run uvicorn fog_gnn.api:app --reload --host $(FOG_API_HOST) --port $(FOG_API_PORT)

front-b:
	pnpm --filter @ic-research-lab/fog-gnn-frontend dev

dev-b:
	@echo "[Módulo B] Garantindo dataset IMU sintético e iniciando FastAPI (:$(FOG_API_PORT)) + Next.js (:3002)..."
	cd $(MOD_B_BACK) && uv run python scripts/make_synthetic_imu.py
	trap 'kill 0' INT TERM EXIT; \
	(cd $(MOD_B_BACK) && uv run uvicorn fog_gnn.api:app --reload --host $(FOG_API_HOST) --port $(FOG_API_PORT)) & \
	pnpm --filter @ic-research-lab/fog-gnn-frontend dev & \
	wait

clean:
	find . -type d \( -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" -o -name "__pycache__" -o -name ".next" \) -prune -exec rm -rf {} +
