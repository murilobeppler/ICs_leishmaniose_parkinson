"use client";

import React, { useEffect, useState } from "react";
import {
  SubjectsResponse,
  MetricsResponse,
  GraphResponse,
  SubjectSummaryItem,
  SubjectFoldReport,
} from "../types";
import { BodyGraphViewer } from "../components/BodyGraphViewer";
import { MetricsComparisonCard } from "../components/MetricsComparisonCard";
import { TimeSeriesViewer } from "../components/TimeSeriesViewer";
import { SubjectOverviewList } from "../components/SubjectOverviewList";
import { Activity, RefreshCw, AlertCircle, ShieldAlert, Network, UserCheck } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_FOG_API_URL || "http://127.0.0.1:8002";

export default function FogGnnPage() {
  const [subjectsData, setSubjectsData] = useState<SubjectsResponse | null>(null);
  const [metricsData, setMetricsData] = useState<MetricsResponse | null>(null);
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>("SUBJ_001");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAllData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [subjRes, metRes, graphRes] = await Promise.all([
        fetch(`${API_BASE}/subjects`, { cache: "no-store" }),
        fetch(`${API_BASE}/metrics`, { cache: "no-store" }),
        fetch(`${API_BASE}/graph`, { cache: "no-store" }),
      ]);

      if (!subjRes.ok || !metRes.ok || !graphRes.ok) {
        throw new Error("Falha ao consultar endpoints da API FOG-GNN.");
      }

      const [subjJson, metJson, graphJson] = await Promise.all([
        subjRes.json(),
        metRes.json(),
        graphRes.json(),
      ]);

      setSubjectsData(subjJson);
      setMetricsData(metJson);
      setGraphData(graphJson);
      if (subjJson.items && subjJson.items.length > 0) {
        setSelectedSubjectId(subjJson.items[0].subject.subject_id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Falha ao conectar na API do Módulo B.";
      setError(
        `${msg} Verifique se o backend está ativo em ${API_BASE} (execute 'make api-b' ou 'make dev-b').`,
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, []);

  return (
    <main style={{ maxWidth: "1380px", margin: "0 auto", padding: "1.75rem 1.25rem 4rem" }}>
      {/* Top Header */}
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "1.5rem",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <div
              style={{
                background: "rgba(139, 92, 246, 0.15)",
                padding: "0.4rem",
                borderRadius: "0.5rem",
              }}
            >
              <Network size={26} color="var(--accent-purple)" />
            </div>
            <div>
              <span
                style={{
                  fontSize: "0.75rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--accent-purple)",
                  fontWeight: 700,
                }}
              >
                Iniciação Científica — Módulo B
              </span>
              <h1 style={{ fontSize: "1.65rem", fontWeight: 800, letterSpacing: "-0.02em" }}>
                Predição de Freezing of Gait com GNN Espaço-Temporal
              </h1>
            </div>
          </div>
          <p
            style={{
              fontSize: "0.875rem",
              color: "var(--text-secondary)",
              marginTop: "0.35rem",
              maxWidth: "880px",
            }}
          >
            Modelagem do corpo humano como <strong>grafo cinemático e funcional</strong> sobre
            sensores inerciais corporais (IMU) para detecção antecipada de episódios de congelamento
            da marcha em pacientes com Parkinson, avaliado sob protocolo estrito{" "}
            <strong>Leave-One-Subject-Out (LOSO)</strong>.
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            onClick={fetchAllData}
            disabled={loading}
            className="btn btn-secondary"
            title="Recarregar dados da API"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            Atualizar
          </button>
        </div>
      </header>

      {/* Methodology & Privacy Banner */}
      <section
        style={{
          background: "rgba(30, 41, 59, 0.7)",
          border: "1px solid rgba(139, 92, 246, 0.35)",
          borderRadius: "0.625rem",
          padding: "0.85rem 1.2rem",
          marginBottom: "1.5rem",
          display: "flex",
          alignItems: "center",
          gap: "0.85rem",
          fontSize: "0.825rem",
          color: "#e2e8f0",
        }}
      >
        <ShieldAlert size={22} style={{ flexShrink: 0, color: "var(--accent-purple)" }} />
        <div>
          <strong>Rigor Metodológico & Privacidade Clínica:</strong> Particionamento estritamente
          por sujeito (LOSO) — nenhuma janela temporal do paciente em teste jamais entra no treino
          (anti-data-leakage). Métricas focadas em <strong>AUPRC</strong>,{" "}
          <strong>Sensibilidade</strong> e <strong>Falsos Positivos por Hora (FP/h)</strong> para
          classe rara. Todos os dados são 100% anonimizados (<code>SUBJ_XXX</code>).
        </div>
      </section>

      {/* Error state */}
      {error && (
        <div
          className="glass-panel"
          style={{
            padding: "1.25rem",
            borderColor: "rgba(244, 63, 94, 0.5)",
            background: "rgba(244, 63, 94, 0.1)",
            marginBottom: "1.5rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", color: "#fca5a5" }}>
            <AlertCircle size={20} />
            <span style={{ fontWeight: 600 }}>{error}</span>
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && !metricsData && (
        <div style={{ textAlign: "center", padding: "4rem 1rem", color: "var(--text-muted)" }}>
          <Activity
            size={40}
            className="animate-spin"
            style={{ margin: "0 auto 1rem", color: "var(--accent-purple)" }}
          />
          <p>Carregando coorte anonimizada de sensores IMU e métricas LOSO...</p>
        </div>
      )}

      {subjectsData && metricsData && graphData && (
        <>
          {/* Cohort selection */}
          <SubjectOverviewList
            subjects={subjectsData.items}
            selectedSubjectId={selectedSubjectId}
            onSelectSubject={setSelectedSubjectId}
          />

          {/* Metrics comparison: Baseline vs ST-GNN */}
          <MetricsComparisonCard
            baselineMetrics={metricsData.baseline_overall}
            stGnnMetrics={metricsData.st_gnn_overall}
            auprcGain={metricsData.auprc_improvement_abs}
            f1Gain={metricsData.f1_improvement_abs}
          />

          {/* Time Series Viewer for selected subject */}
          <TimeSeriesViewer
            predictions={metricsData.window_predictions}
            selectedSubject={selectedSubjectId}
          />

          {/* Two-column layout: Body Graph Viewer & Per-Subject LOSO Table */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))",
              gap: "1.5rem",
            }}
          >
            {/* Body Graph */}
            <div>
              <BodyGraphViewer
                normalGraph={graphData.normal_gait_graph}
                fogGraph={graphData.fog_episode_graph}
              />
            </div>

            {/* Per-Subject LOSO Table */}
            <div className="glass-panel" style={{ padding: "1.25rem" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "0.75rem",
                }}
              >
                <div>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      textTransform: "uppercase",
                      color: "var(--accent-purple)",
                      fontWeight: 700,
                    }}
                  >
                    Avaliação Granular
                  </span>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>
                    Métricas por Dobra de Sujeito (LOSO)
                  </h3>
                </div>
                <span className="badge badge-purple" style={{ fontSize: "0.75rem" }}>
                  {metricsData.per_subject_folds.length} dobras isoladas
                </span>
              </div>

              <div
                className="table-container"
                tabIndex={0}
                role="region"
                aria-label="Tabela de métricas por sujeito LOSO"
                style={{ maxHeight: "440px", overflow: "auto" }}
              >
                <table>
                  <thead style={{ position: "sticky", insetBlockStart: 0, zIndex: 1 }}>
                    <tr>
                      <th>Sujeito (Teste)</th>
                      <th>Janelas (FOG / Total)</th>
                      <th>AUPRC Baseline</th>
                      <th>AUPRC ST-GNN</th>
                      <th>Sensibilidade</th>
                      <th>FP / Hora</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metricsData.per_subject_folds.map((fold: SubjectFoldReport) => {
                      const isSelected = fold.held_out_subject_id === selectedSubjectId;

                      return (
                        <tr
                          key={fold.fold_id}
                          style={{
                            background: isSelected ? "rgba(139, 92, 246, 0.12)" : "transparent",
                            cursor: "pointer",
                          }}
                          onClick={() => setSelectedSubjectId(fold.held_out_subject_id)}
                        >
                          <td>
                            <strong
                              className="mono"
                              style={{ color: isSelected ? "var(--accent-purple)" : "inherit" }}
                            >
                              {fold.held_out_subject_id}
                            </strong>
                          </td>
                          <td>
                            {fold.test_fog_windows_count} / {fold.test_windows_count}
                          </td>
                          <td className="mono">{fold.baseline_metrics.auprc.toFixed(3)}</td>
                          <td>
                            <strong className="mono" style={{ color: "var(--accent-emerald)" }}>
                              {fold.st_gnn_metrics.auprc.toFixed(3)}
                            </strong>
                            <span
                              style={{
                                fontSize: "0.75rem",
                                color: "var(--text-muted)",
                                marginLeft: "0.25rem",
                              }}
                            >
                              (+{(fold.auprc_gain * 100).toFixed(1)}pp)
                            </span>
                          </td>
                          <td className="mono">
                            {(fold.st_gnn_metrics.sensitivity * 100).toFixed(1)}%
                          </td>
                          <td className="mono" style={{ color: "var(--accent-amber)" }}>
                            {fold.st_gnn_metrics.false_positives_per_hour.toFixed(1)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
