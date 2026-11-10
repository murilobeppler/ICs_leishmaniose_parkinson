# `ic-research-lab` — Monorepo de Pesquisa Científica & Iniciação Científica

Monorepo de alto rigor acadêmico e reprodutibilidade computacional abrigando **duas Iniciações Científicas (ICs) independentes**, cada uma composta por seu próprio backend científico em Python (gerenciado com [`uv`](https://docs.astral.sh/uv/)) e seu frontend moderno em Next.js 14 (App Router + TypeScript), compartilhando **exclusivamente infraestrutura transversal e agnóstica** (`packages/core`, `.env`, logging estruturado sem PII, cache em disco e automações de CI/CD).

> [!IMPORTANT]
> **Regra de Fronteira Dura:** Os domínios científicos de `peptide-docking` e `fog-gnn` **nunca** se importam entre si. Um teste arquitetural automatizado baseado em análise sintática abstrata (AST) é executado na pipeline de CI para garantir isolamento e independência total.

---

## Índice

- [Os Dois Módulos Científicos](#os-dois-módulos-científicos)
  - [Módulo A: Docking Peptídico contra *Leishmania*](#módulo-a--peptide-docking)
  - [Módulo B: Predição de Freezing of Gait (Parkinson) com ST-GNN & PyTorch Geometric](#módulo-b--fog-gnn)
- [Arquitetura do Repositório](#arquitetura-do-repositório)
- [Recursos Recentes Implementados](#recursos-recentes-implementados)
  - [Visualização Molecular com PyMOL (Módulo A)](#1-visualização-molecular-com-pymol)
  - [Integração de PyTorch Geometric — PyG (Módulo B)](#2-integração-com-pytorch-geometric-pyg)
  - [Dataset Real com Scores do Servidor HPEPDOCK](#3-dados-reais-de-screening-do-hpepdock)
- [Como Rodar o Projeto](#como-rodar-o-projeto)
  - [Scripts Rápidos (Windows PowerShell)](#opção-1--powershell-scripts-recomendado-no-windows)
  - [Via Make / pnpm / uv](#opção-2--via-make--pnpm)
- [Endpoints das APIs FastAPI](#endpoints-das-apis-fastapi)
- [Validação, Testes e Qualidade](#validação-testes-e-qualidade)

---

## Os Dois Módulos Científicos

```
                         ic-research-lab (Monorepo)
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           ▼                                                   ▼
┌──────────────────────┐                           ┌──────────────────────┐
│  Módulo A (Peptídeos)│                           │   Módulo B (FOG-GNN) │
│  Docking Leishmania  │                           │  Parkinson IMU GNN   │
├──────────────────────┤                           ├──────────────────────┤
│ • Backend (:8001)    │                           │ • Backend (:8002)    │
│ • Frontend (:3001)   │                           │ • Frontend (:3002)   │
│ • HPEPDOCK Real Data │                           │ • PyTorch Geometric  │
│ • Export PyMOL (.pml)│                           │ • Validação LOSO     │
└──────────┬───────────┘                           └──────────┬───────────┘
           │                                                   │
           └─────────────────────────┬─────────────────────────┘
                                     ▼
                       ┌───────────────────────────┐
                       │   packages/core (ic_core) │
                       │ • BaseSettings (Pydantic) │
                       │ • Redacted Logger         │
                       │ • Atomic Tabular I/O      │
                       └───────────────────────────┘
```

### Módulo A — `peptide-docking`

**Descoberta computacional e triagem virtual de candidatos peptídicos contra proteína-alvo de *Leishmania infantum* sem ortólogo humano.**

* **Proteína-Alvo Seletiva:** Tripanotiona Redutase (`LINJ_TRYR_01`) — enzima homodimérica essencial no metabolismo antioxidante de tripanossomatídeos. **Ausente no genoma humano** (que utiliza Glutationa Redutase com geometria e carga de bolso ativo distintas), eliminando riscos de toxicidade *off-target*.
* **Resíduos Catalíticos Mapeados:** Ditiol catalítico redox-ativo `CYS52` e `CYS57` (Cadeia A), e díade ácido-base `HIS461` e `GLU466` (Cadeia B).
* **Biblioteca Oficial do HPEPDOCK:** 627 hexapeptídeos candidatos distribuídos em 63 grupos combinatórios, avaliados pelo algoritmo de docking peptídeo-proteína *ensemble* do servidor web HPEPDOCK (função de pontuação empírica iterativa `ITScorePep`).
* **Ranking Multifatorial e Triagem:**
  * Cálculo dinâmico de Z-score, percentil e faixas de priorização (`prioridade_alta_triagem` para scores $\le -210$ kcal/mol).
  * Propriedades físico-químicas calculadas: Massa molecular (Da), Carga líquida em pH 7.4, Índice GRAVY de hidropatia (Kyte & Doolittle) e Ponto Isoelétrico (pI).
* **Diretriz de Honestidade Científica:** O score de docking molecular é explicitamente tratado como hipótese in silico de complementaridade estérica, nunca como comprovação biológica antes do teste in vitro.

---

### Módulo B — `fog-gnn`

**Predição e detecção precoce de episódios de Freezing of Gait (FOG) em pacientes com Doença de Parkinson usando Redes Neurais em Grafos Espaço-Temporais.**

* **Topologia Biomecânica Corporal:** O corpo humano é modelado como um grafo espaciotemporal de 7 nós canônicos (`CANONICAL_IMU_NODES`): tornozelo esquerdo/direito, coxa esquerda/direita, tronco lombar (L5) e punho esquerdo/direito.
* **Arestas Anatômicas e Dinâmicas:** Conexões anatômicas biomecânicas fixas somadas a arestas funcionais dinâmicas baseadas na matriz de correlação de Pearson de janelas temporais de 2.56 s (stride 1.28 s) a 100 Hz.
* **Validação Cruzada Estrita *Leave-One-Subject-Out* (LOSO):**
  * Para evitar vazamento de dados (*data leakage*), o particionamento é agrupado por paciente (`SUBJ_XXX`). Nenhuma janela do sujeito sob teste entra no conjunto de treino.
  * O grafo da dobra é construído **exclusivamente com os dados de treino**.
* **Métricas Clínicas para Eventos Raros:**
  * Episódios de congelamento são eventos raros e assimétricos: o modelo é avaliado primariamente por **AUPRC** (Área sob a curva Precisão-Revocação), **Sensibilidade**, **Taxa de Falsos Positivos por Hora (FP/h)** e **Latência de Detecção**, e não por acurácia global inflada pela classe majoritária.
* **Comparação com Baseline Temporal 1D:** Todo experimento avalia lado a lado o modelo GNN contra um baseline não-estruturado de séries temporais.

---

## Recursos Recentes Implementados

### 1. Visualização Molecular com PyMOL

Implementado em [`src/peptide_docking/visualization/pymol_export.py`](modules/peptide-docking/backend/src/peptide_docking/visualization/pymol_export.py):

* **Scripts de Publicação (`.pml`):** Gera scripts reproduzíveis com fundo branco (`bg_color white`), antialiasing, alvo em cartoon semi-transparente, resíduos catalíticos (`CYS52`, `CYS57`, `HIS461`, `GLU466`) em *sticks* ciano com CPK, e o peptídeo em *sticks* magenta.
* **Distâncias e Contatos Interatômicos:** Traçado de pontes de hidrogênio e pontes salinas com linhas tracejadas (`distance`, marine/amarelo) com medidas reais em Ångströms.
* **Exportação Automatizada de Imagens e Sessões:** Comandos incorporados para gerar PNG em alta resolução (1600x1200, 150 DPI, `ray=1`) e salvar sessões de trabalho (`.pse`).
* **Interface Web:** Aba dedicada **"PyMOL (.pml)"** no modal de cada candidato peptídico com pré-visualizador de código e botão de download `docking_<pep_id>.pml`.
* **Endpoint na API:** `GET /results/{run_id}/{peptide_id}/pymol?download=true`.

### 2. Integração com PyTorch Geometric (PyG)

Implementado em [`src/fog_gnn/models/pyg_st_gnn.py`](modules/fog-gnn/backend/src/fog_gnn/models/pyg_st_gnn.py):

* **Camadas Espaciais Nativas:** Convoluções de grafos via `torch_geometric.nn.GCNConv` com topologia em formato COO (`edge_index`) e ponderação de arestas (`edge_weight`).
* **Otimizador & Função de Perda:** Treinamento com `torch.optim.AdamW` e `nn.BCEWithLogitsLoss(pos_weight=...)` balanceada para o desbalanceamento de classes do FOG.
* **Arquitetura Híbrida Inteligente:** A função `is_pyg_installed()` detecta se os pacotes compilados C++/CUDA estão no ambiente. Caso positivo, usa o PyG nativo; em ambientes sem CUDA/C++, chaveia de forma transparente para o motor de convolução vetorizado (NumPy/SciPy), garantindo 100% de conformidade com o protocolo `FogModel` sem quebras de execução.
* **Diagnóstico em Tempo Real:** Endpoint `GET /model-info` e indicador dinâmico no cabeçalho do dashboard web (`http://localhost:3002`).

### 3. Dados Reais de Screening do HPEPDOCK

Adicionado em [`data/hpepdock_screen_real.csv`](modules/peptide-docking/backend/data/hpepdock_screen_real.csv):

* **627 Peptídeos Candidatos Reais:** Substituídos dados sintéticos pelos dados do screening original do servidor HPEPDOCK.
* **Distribuição de Afinidade Real:**
  * Melhor score de docking: **-244.292 kcal/mol** (`VTRWVH`, Grupo 37)
  * Outros candidatos de altíssima afinidade: `HVHVGW` (-235.59), `WVHVGW` (-232.32), `NHYRSG` (-230.20), `FGRYHW` (-226.33).
* **Tabela Completa no Frontend:** Coluna dedicada **Sequência** com código monospace, coluna **Grupo** e scores oficiais exibidos diretamente na tela.

---

## Estrutura do Repositório

```text
ic-research-lab/
├─ README.md                                 # Este documento
├─ pnpm-workspace.yaml                       # Workspace PNPM (Next.js frontends)
├─ package.json                              # Scripts unificados de desenvolvimento
├─ Makefile                                  # Alvos Make para ambientes Linux/macOS
├─ dev-a.ps1 / dev-b.ps1                     # Scripts nativos Windows PowerShell
├─ .env.example / .env                       # Configurações tipadas
├─ .gitignore                                # Bloqueio rígido de dados, runs e PII
├─ .pre-commit-config.yaml                   # Verificações de estilo e fronteira AST
├─ .github/workflows/ci.yml                  # Matriz de CI do GitHub Actions
├─ docs/                                     # Documentação de arquitetura detalhada
│  ├─ architecture.md
│  ├─ module-a-peptide-docking.md
│  └─ module-b-fog-gnn.md
├─ packages/
│  └─ core/                                  # Pacote compartilhado `ic-core`
│     ├─ pyproject.toml
│     ├─ src/ic_core/                        # Config, Logging estruturado, I/O atômico
│     └─ tests/                              # Testes de unidade e teste de fronteira AST
└─ modules/
   ├─ peptide-docking/
   │  ├─ backend/                            # FastAPI + Pipeline + Ranking + PyMOL
   │  │  ├─ pyproject.toml
   │  │  ├─ data/hpepdock_screen_real.csv    # Dataset oficial do HPEPDOCK (627 peptídeos)
   │  │  ├─ src/peptide_docking/
   │  │  │  ├─ domain.py                     # Entidades Pydantic imutáveis
   │  │  │  ├─ library.py                    # Propriedades e carga de dados
   │  │  │  ├─ pipeline.py                   # Orquestração em lotes
   │  │  │  ├─ ranking.py                    # Z-score, percentil e triage tiers
   │  │  │  ├─ visualization/pymol_export.py # Gerador de scripts PyMOL
   │  │  │  └─ api.py                        # Rotas FastAPI (:8001)
   │  │  └─ tests/                           # 8 testes automatizados
   │  └─ frontend/                           # Dashboard Next.js 14 (:3001)
   │     ├─ package.json
   │     └─ src/components/                  # CandidateTable, PoseDetailModal com PyMOL
   └─ fog-gnn/
      ├─ backend/                            # FastAPI + GNN + PyTorch Geometric + LOSO
      │  ├─ pyproject.toml
      │  ├─ src/fog_gnn/
      │  │  ├─ domain.py                     # Sujeitos anonimizados, IMUs canônicos
      │  │  ├─ graph.py                      # Grafo biomecânico e correlação dinâmica
      │  │  ├─ windowing.py                  # Janelas 2.56s, Freeze Index, split LOSO
      │  │  ├─ models/
      │  │  │  ├─ baseline.py                # Modelo temporal 1D
      │  │  │  ├─ st_gnn.py                  # GNN analítica vetorizada
      │  │  │  └─ pyg_st_gnn.py              # ST-GNN nativo com PyTorch Geometric
      │  │  ├─ evaluate.py                   # AUPRC, Sensibilidade, FP/h, Latência
      │  │  ├─ train.py                      # Validação cruzada estrita LOSO
      │  │  └─ api.py                        # Rotas FastAPI (:8002)
      │  └─ tests/                           # 7 testes automatizados (anti-leakage)
      └─ frontend/                           # Dashboard Next.js 14 (:3002)
         ├─ package.json
         └─ src/components/                  # BodyGraphViewer, MetricsComparisonCard
```

---

## Como Rodar o Projeto

### Opção 1 — PowerShell Scripts (Recomendado no Windows)

Você pode executar diretamente da raiz ou da pasta `ic-research-lab`:

* **Iniciar Módulo A (Docking Peptídico + PyMOL):**
  ```powershell
  .\dev-a.ps1
  ```
  * **Frontend:** `http://localhost:3001`
  * **Swagger API:** `http://127.0.0.1:8001/docs`

* **Iniciar Módulo B (Parkinson + GNN/PyG):**
  ```powershell
  .\dev-b.ps1
  ```
  * **Frontend:** `http://localhost:3002`
  * **Swagger API:** `http://127.0.0.1:8002/docs`

*Pressione `Enter` no terminal a qualquer momento para encerrar de forma limpa o FastAPI e o Next.js.*

---

### Opção 2 — Via Make / pnpm

```bash
# 1. Configurar variáveis de ambiente
cp .env.example .env

# 2. Instalar dependências JS na raiz
pnpm install

# 3. Subir Módulo A (FastAPI :8001 + Next.js :3001)
make dev-a

# 4. Subir Módulo B (FastAPI :8002 + Next.js :3002)
make dev-b
```

---

## Endpoints das APIs FastAPI

### Módulo A (`:8001`)

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/health` | Status operacional do serviço e biblioteca |
| `GET` | `/target` | Metadados do alvo (*Leishmania*, sem ortólogo humano) |
| `GET` | `/peptides` | Lista paginada dos peptídeos e propriedades físico-químicas |
| `GET` | `/runs` | Histórico de execuções de triagem molecular |
| `GET` | `/results` | Resultados com scores HPEPDOCK, Z-score, percentil e ranking |
| `GET` | `/results/{run_id}/{peptide_id}/pymol` | Download ou JSON do script PyMOL (`.pml`) |

### Módulo B (`:8002`)

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/health` | Status do serviço, contagem de sujeitos e backend GNN |
| `GET` | `/model-info` | Diagnóstico de PyTorch Geometric, nós IMU e protocolo |
| `GET` | `/subjects` | Sujeitos anonimizados (`SUBJ_XXX`), sessões e episódios |
| `GET` | `/experiments` | Experimentos de validação cruzada LOSO executados |
| `GET` | `/metrics` | Métricas comparativas (Baseline 1D vs ST-GNN), AUPRC e FP/h |
| `GET` | `/graph` | Grafo biomecânico normal vs em episódio de FOG |

---

## Validação, Testes e Qualidade

O repositório possui uma suíte completa de **21 testes automatizados**:

```bash
# Rodar todos os testes Python (Core, Módulo A e Módulo B)
make test

# Ou diretamente via uv em cada diretório:
uv run --directory packages/core pytest tests
uv run --directory modules/peptide-docking/backend pytest tests
uv run --directory modules/fog-gnn/backend pytest tests

# Typecheck dos frontends Next.js
pnpm --filter @ic-research-lab/peptide-docking-frontend run typecheck
pnpm --filter @ic-research-lab/fog-gnn-frontend run typecheck
```

* **Testes de Fronteira Arquitetural:** `tests/test_architecture_boundaries.py` inspeciona a AST de todo o código e garante que `peptide_docking` e `fog_gnn` jamais se importem.
* **Testes Anti-Vazamento (Anti-Leakage):** `test_fog_gnn.py` valida que forçar uma janela temporal do sujeito de teste no treino dispara erro metodológico imediato.

---

## Licença e Atribuição

* Monorepo acadêmico desenvolvido para pesquisas de Iniciação Científica.
* PyMOL é software comercial/open-source mantido pela Schrödinger, Inc. Consulte `.licenses/pymol_LICENSE.txt`.
* Algoritmo de docking por HPEPDOCK Web Server (Huang Lab, HUST).
