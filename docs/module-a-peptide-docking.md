# Módulo A — `peptide-docking`

## 1. Visão Geral e Contexto Científico

A leishmaniose é uma doença tropical negligenciada causada por protozoários parasitas do gênero _Leishmania_. O tratamento clínico atual é limitado por alta toxicidade dos quimioterápicos (antimoniais pentavalentes, anfotericina B) e emergência progressiva de resistência farmacológica.

Este módulo foca na **descoberta computacional de novos inibidores peptídicos** contra uma proteína-alvo essencial de _Leishmania_ (_Trypanothione Reductase_ — TryR) que **não possui ortólogo humano** (o hospedeiro mamífero expressa a enzima Glutationa Redutase, cujo sítio de ligação difere drasticamente em topografia e distribuição de cargas). A ausência de ortólogo reduz o risco de toxicidade _off-target_.

### O Gargalo

Historicamente, o docking de peptídeos contra a proteína-alvo era realizado por submissões manuais no servidor web do **HPEPDOCK** (em lotes de 10 peptídeos por formulário web), gerando um gargalo severo de tempo, ausência de auditoria e risco de perda de reprodutibilidade científica.

---

## 2. Objetivos e Arquitetura do Módulo

O módulo `peptide-docking` resolve esse gargalo através de quatro pilares:

1. **Biblioteca Versionada e Validada (`library.py`):**
   - Representação da biblioteca de **634 peptídeos candidatos** com verificação de aminoácidos canônicos, unicidade de sequências, cálculo de propriedades biofísicas (massa molecular em Da, carga líquida em pH 7.4, índice GRAVY e ponto isoelétrico).
   - Validação da proteína-alvo (`Target`), impondo `has_human_ortholog == False`.
2. **Abstração de Motor de Docking (`engines/`):**
   - Protocolo comum [`DockingEngine`](file:///c:/Users/User/Documents/dev/gromacs/ic-research-lab/modules/peptide-docking/backend/src/peptide_docking/engines/base.py) com método `submit(job) -> DockingResult`.
   - `MockDockingEngine`: motor determinístico baseado em semente fixa e complementaridade físico-química com o sítio catalítico.
   - `HPEPDOCKEngine`: adaptador para o servidor web com cache em disco (`DiskCache`), _rate limiting_ conservador (`>= 30s`), _retry_ com _backoff_ exponencial e trava de segurança: opera como _stub_ documentado caso submissão automatizada não seja expressamente permitida pelos termos do serviço.
   - Interface aberta para motores locais open-source (ex.: AutoDock CrankPep / ADCP, HADDOCK3, LightDock).
3. **Pipeline em Lote Retomável e Idempotente (`pipeline.py`):**
   - Execução em lotes (padrão: 10 peptídeos por lote).
   - Persistência item a item em `runs/<run_id>/items/<peptide_id>.json`. Se uma execução for interrompida, reiniciar a mesma run carrega os peptídeos já concluídos do disco sem recomputá-los.
4. **Ranking Multifatorial e Honestidade Científica (`ranking.py`):**
   - Cálculo de Z-score, percentis na distribuição da run e categorização em níveis de triagem (`prioridade_alta_triagem`, `prioridade_media_triagem`, `baixa_prioridade_triagem`).
   - Mapeamento de resíduos _hotspots_ do bolso da enzima.
   - **Diretriz de Honestidade Científica:** Scores de docking são apresentados como **hipóteses de triagem in silico** e ordenação estatística para priorização, nunca como comprovação biológica de inibição.

---

## 3. Endpoints da API FastAPI (`:8001`)

- `GET /health`: diagnóstico de saúde, tamanho da biblioteca (634), alvo e disclaimer metodológico.
- `GET /target`: metadados da proteína-alvo e lista de resíduos do sítio catalítico.
- `GET /peptides`: listagem paginada da biblioteca com filtros por busca, tamanho, carga e família.
- `GET /runs`: lista de execuções persistidas com manifesto, semente e status.
- `POST /runs`: dispara ou retoma uma triagem em lote.
- `GET /results`: candidatos ranqueados, resumo estatístico da distribuição de scores e hotspots de contato.

---

## 4. Frontend Next.js (`:3001`)

O frontend oferece um painel completo para exploração dos resultados:

- **Resumo da Execução:** Alvo verificado sem ortólogo humano, parâmetros da run, melhor score e contagem de prioridades.
- **Filtros Dinâmicos:** Busca em tempo real, seleção de família, corte de carga líquida, score máximo e fração mínima de contato com o sítio ativo.
- **Tabela de Candidatos:** Ordenação com cabeçalhos fixos (_sticky headers_), percentis e badges de prioridade.
- **Modal de Detalhe de Poses:** Tabela das poses conformacionais preditas (scores, RMSD vs. top pose, área de interface) e lista de contatos atômicos (pontes salinas, ligações de hidrogênio, empilhamento pi, interações hidrofóbicas) com resíduos catalíticos do alvo.
- **Aviso Metodológico:** Banner persistente lembrando a natureza computacional da triagem.
