# Módulo B — `fog-gnn`

## 1. Visão Geral e Contexto Científico

O **Freezing of Gait (FOG)** — ou congelamento da marcha — é um sintoma motor incapacitante e imprevisível característico de estágios intermediários a avançados da Doença de Parkinson. Durante o episódio, os pacientes relatam a sensação de que "seus pés ficaram colados ao chão", resultando em perda de equilíbrio, quedas frequentes e perda de autonomia.

A maioria dos trabalhos da literatura aborda a detecção de FOG aplicando modelos clássicos (SVM, Random Forest) ou redes neurais 1D (CNN/LSTM) sobre janelas temporais de sensores inerciais isolados (IMU), ignorando as relações biomecânicas entre os diferentes segmentos corporais.

### Contribuição Própria

Este módulo modela o corpo humano como um **grafo espaço-temporal**:

- **Nós:** 7 posições de sensores IMU (Lombar L4-L5, Coxa E/D, Canela E/D, Tornozelo E/D). O desenho desacoplado permite conectar facilmente modalidades fisiológicas adicionais (ex.: eletroencefalografia — EEG motor central em Cz).
- **Arestas:** Combinação de conexões cinemáticas anatômicas rígidas, acoplamento bilateral inter-membros e arestas funcionais dinâmicas baseadas na correlação cruzada de sinais durante as fases da marcha.
- **Arquitetura Neural:** Rede Neural em Grafo Espaço-Temporal (**ST-GNN**), comparada obrigatoriamente contra um baseline temporal 1D não-GNN.

---

## 2. Rigor Metodológico e Princípios Científicos

1. **Split Estrito por Sujeito (Leave-One-Subject-Out — LOSO):**
   - Janelas temporais de um mesmo paciente possuem forte autocorrelação. Particionar janelas aleatoriamente em treino e teste gera **vazamento de dados (_data leakage_)** grave, inflando artificialmente os resultados reportados na literatura.
   - Todo treinamento e teste neste módulo utiliza **LOSO**: em cada dobra, um sujeito inteiro é isolado para teste e nunca visto durante o ajuste dos pesos ou na construção da matriz de adjacência funcional do grafo de treino. Uma trava em código (`assert_no_subject_leakage`) dispara `DataLeakageError` se essa regra for violada.
2. **Comparação Honesta com Baseline Não-GNN:**
   - A tese de usar representações em grafo só se sustenta se o modelo em grafo superar de forma consistente um baseline 1D sob exatamente o mesmo protocolo experimental e semente aleatória.
3. **Métricas Apropriadas para Evento Raro:**
   - FOG é uma classe minoritária (< 20% do tempo de caminhada). Reportar acurácia global mascara classificadores triviais que nunca detectam FOG.
   - Métricas reportadas:
     - **AUPRC** (Área sob a Curva Precisão-Revocação) como métrica primária.
     - **Sensibilidade (Recall)** e **Especificidade**.
     - **Falsos Positivos por Hora (FP/h)** sobre o tempo total monitorado.
     - **Latência Média de Detecção (s)** entre o início cinemático do episódio e o primeiro alarme.
4. **Privacidade Rigorosa de Pacientes:**
   - Nenhum dado real de paciente, gravação bruta ou identificador pessoal (PII) entra no repositório Git. Todos os dados são referenciados fora do repo via `.env`. Todos os sujeitos usam identificadores sintéticos/anonimizados (`SUBJ_001` .. `SUBJ_006`).

---

## 3. Endpoints da API FastAPI (`:8002`)

- `GET /health`: diagnóstico de integridade, contagem de sujeitos e sessões, disclaimer metodológico.
- `GET /subjects`: lista da coorte anonimizada de Parkinson, estágios Hoehn & Yahr, estado medicamentoso (ON/OFF), contagem de episódios e duração de FOG.
- `GET /experiments`: lista de experimentos LOSO executados e persistidos em disco com metadados reprodutíveis.
- `GET /metrics`: métricas globais e por sujeito comparando Baseline 1D vs. ST-GNN, além das predições por janela temporal.
- `GET /graph`: topologia do grafo corporal em marcha normal vs. episódio de congelamento (FOG).

---

## 4. Frontend Next.js (`:3002`)

- **Seletor de Sujeitos:** Visão dos pacientes anonimizados com características clínicas e botão para filtrar o dashboard por paciente.
- **Card Comparativo:** AUPRC, F1-Score, Sensibilidade, Especificidade, FP/h e Latência comparando lado a lado o Baseline 1D e a ST-GNN.
- **Visualizador de Grafo Corporal Interativo:** Diagrama em SVG dos 7 sensores corporais com representação visual das arestas anatômicas, bilaterais e funcionais, com chave seletora entre marcha normal e congelamento da marcha (evidenciando o desacoplamento bilateral inter-membros).
- **Série Temporal Contínua por Janela:** Gráfico interativo com a probabilidade predita pelo ST-GNN e pelo Baseline ao longo do tempo, sobreposta às faixas de episódios reais de FOG e ao Freeze Index distal.
- **Tabela de Dobras LOSO:** Inspeção detalhada do desempenho do modelo em cada paciente isolado.
