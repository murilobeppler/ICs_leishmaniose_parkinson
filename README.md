# `ic-research-lab` — Monorepo de Pesquisa Científica

Monorepo que abriga **duas iniciações científicas independentes**, cada uma com seu próprio backend científico em Python e seu próprio frontend em Next.js (App Router + TypeScript), compartilhando **exclusivamente infraestrutura transversal** (`packages/core`, configuração via `.env`, logging estruturado, resolução de caminhos, cache/IO básico, lint e CI).

> **Regra de Fronteira Dura:** Os domínios científicos de `peptide-docking` e `fog-gnn` **nunca** se importam entre si. Um teste arquitetural automatizado falha caso qualquer importação cruzada seja introduzida.

---

## Os Dois Módulos

### Módulo A — `peptide-docking`
**Descoberta computacional de candidatos peptídicos contra proteína-alvo de *Leishmania* sem ortólogo humano**

- **Problema:** Triar de forma reprodutível **634 peptídeos candidatos** contra uma proteína-alvo de *Leishmania* ausente no proteoma humano (reduzindo risco de toxicidade *off-target*), superando o gargalo de submissão manual em lotes de 10 no servidor web HPEPDOCK.
- **Arquitetura:**
  - Biblioteca versionada e validada (`Peptide`, `Target`, `DockingJob`, `DockingResult`).
  - Abstração de motores de docking (`DockingEngine` Protocol) com motor determinístico (`MockDockingEngine`), adaptador `HPEPDOCKEngine` (com *rate limiting*, *retry*, cache em disco e proteção explícita dos termos de serviço/modo stub) e espaço aberto para motores locais open-source.
  - Pipeline em lote retomável e idempotente, persistindo todos os hiperparâmetros e sementes junto aos resultados.
  - Sistema de *ranking* e filtragem que trata o score de docking com **honestidade científica**: como **hipótese de triagem in silico**, nunca como confirmação de atividade biológica.
  - **API (FastAPI)** em `:8001` (`/peptides`, `/runs`, `/results`) + **Frontend (Next.js)** em `:3001`.

### Módulo B — `fog-gnn`
**Predição de episódios de *Freezing of Gait* (FOG) na Doença de Parkinson com Redes Neurais em Grafos Espaço-Temporais**

- **Problema:** Detectar e predizer episódios de congelamento da marcha (*freezing of gait*) a partir de sensores inerciais corporais (IMU), modelando o corpo humano como um **grafo** (nós = segmentos corporais/sensores, arestas = conexões biomecânicas anatômicas + correlação funcional dinâmica de sinal) com arquitetura preparada para fusão multimodal futura (ex.: EEG/sinal cerebral).
- **Rigor Metodológico:**
  - **Split estritamente por sujeito** (*Leave-One-Subject-Out* / agrupado por paciente, **nunca** por janela temporal aleatória) para impedir vazamento de dados (*data leakage*) entre janelas adjacentes do mesmo indivíduo.
  - **Comparação honesta:** A GNN espaço-temporal (`STGNNModel`) é obrigatoriamente comparada contra um baseline não-GNN 1D (`TemporalBaselineModel` — CNN/GRU sobre janelas multivariadas).
  - **Métricas para classe rara:** Avaliação focada em **AUPRC** (Área sob a curva Precisão-Revocação), **Sensibilidade (Recall) a uma taxa fixa de Falsos Positivos por hora (FP/h)** e **latência de detecção**, evitando a ilusão de acurácia inflada pela classe majoritária.
  - **Privacidade de pacientes:** Nenhum dado real ou identificador pessoal entra no repositório ou nos logs.
  - **API (FastAPI)** em `:8002` (`/subjects`, `/experiments`, `/metrics`, `/graph`) + **Frontend (Next.js)** em `:3002`.

---

## Estrutura do Repositório

```text
ic-research-lab/
├─ README.md
├─ pnpm-workspace.yaml
├─ package.json
├─ Makefile
├─ .env.example
├─ .gitignore
├─ .pre-commit-config.yaml
├─ .github/workflows/ci.yml
├─ docs/
│  ├─ architecture.md
│  ├─ module-a-peptide-docking.md
│  └─ module-b-fog-gnn.md
├─ packages/
│  └─ core/                       # Único pacote Python compartilhado (ic_core)
│     ├─ pyproject.toml
│     └─ src/ic_core/
│        ├─ config.py             # BaseSettings (pydantic-settings)
│        ├─ logging.py            # Logging estruturado sem PII
│        ├─ paths.py              # Resolução segura de caminhos externos
│        └─ io.py                 # Leitura/escrita tabular e cache em disco
└─ modules/
   ├─ peptide-docking/
   │  ├─ backend/                 # Pacote Python `peptide-docking` (uv)
   │  └─ frontend/                # App Next.js + TS (porta 3001)
   └─ fog-gnn/
      ├─ backend/                 # Pacote Python `fog-gnn` (uv)
      └─ frontend/                # App Next.js + TS (porta 3002)
```

---

## Pré-requisitos

- **Python 3.11+** e **[`uv`](https://docs.astral.sh/uv/)** (gerenciamento isolado por pacote com `pyproject.toml` + `uv.lock`).
- **Node.js 20+** e **`pnpm` 9+** (workspaces JS/TS na raiz).
- **`make`** (GNU Make — ou execute diretamente os scripts equivalentes descritos no `Makefile` / `package.json`).

---

## Como Rodar (Clone Limpo — Sem Dados Reais)

Nenhum dado real é necessário para instalar, testar ou subir os ambientes de desenvolvimento. Os scripts de bootstrap geram automaticamente datasets sintéticos determinísticos (`seed=42`) em `data/synthetic/` (diretório ignorado pelo Git).

### 1. Setup completo (ambientes Python, dependências JS e dados sintéticos)

```bash
cp .env.example .env
make setup
```

### 2. Executar testes e verificações de qualidade (lint + typecheck + fronteira arquitetural)

```bash
make test
make lint
```

### 3. Subir o Módulo A (`peptide-docking`)

```bash
make dev-a
```
- **API FastAPI (Módulo A):** `http://127.0.0.1:8001` (docs interativos em `/docs`)
- **Frontend Next.js (Módulo A):** `http://localhost:3001`

### 4. Subir o Módulo B (`fog-gnn`)

```bash
make dev-b
```
- **API FastAPI (Módulo B):** `http://127.0.0.1:8002` (docs interativos em `/docs`)
- **Frontend Next.js (Módulo B):** `http://localhost:3002`

---

## Política de Dados e Reprodutibilidade

1. **Zero dados reais no Git:** Arquivos `.csv`, `.parquet`, `.pdb`, `.mat`, `.h5`, checkpoints e diretórios `data/` / `runs/` estão bloqueados no `.gitignore`.
2. **Configuração por variáveis de ambiente:** Todos os caminhos vêm do `.env` validado via `pydantic-settings`.
3. **Semente fixa e rastreabilidade:** Toda execução de docking (Módulo A) ou experimento de treino/avaliação (Módulo B) registra explicitamente a semente aleatória e os hiperparâmetros utilizados junto ao artefato gerado.

Consulte [`docs/architecture.md`](docs/architecture.md) para detalhes sobre as decisões arquiteturais do monorepo.
