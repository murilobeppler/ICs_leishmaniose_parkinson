"use client";

import React from "react";
import { FogEvaluationMetrics } from "../types";
import { Award, TrendingUp, Clock, AlertTriangle, ShieldCheck, Check } from "lucide-react";

interface MetricsComparisonCardProps {
  baselineMetrics: FogEvaluationMetrics;
  stGnnMetrics: FogEvaluationMetrics;
  auprcGain: number;
  f1Gain: number;
}

export function MetricsComparisonCard({
  baselineMetrics,
  stGnnMetrics,
  auprcGain,
  f1Gain,
}: MetricsComparisonCardProps) {
  return (
    <div className="glass-panel" style={{ padding: "1.25rem", marginBottom: "1.5rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "1rem",
          flexWrap: "wrap",
          gap: "0.5rem",
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
            Validação Cruzada Leave-One-Subject-Out (LOSO)
          </span>
          <h2
            style={{
              fontSize: "1.25rem",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
            }}
          >
            <TrendingUp size={20} color="var(--accent-purple)" />
            Comparativo Metodológico Honesto: Baseline 1D vs. ST-GNN
          </h2>
        </div>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <span
            className="badge badge-purple"
            style={{ fontSize: "0.8rem", padding: "0.3rem 0.75rem" }}
          >
            Ganho AUPRC: +{(auprcGain * 100).toFixed(1)} pp
          </span>
          <span
            className="badge badge-emerald"
            style={{ fontSize: "0.8rem", padding: "0.3rem 0.75rem" }}
          >
            Ganho F1: +{(f1Gain * 100).toFixed(1)} pp
          </span>
        </div>
      </div>

      {/* Grid of metrics */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "1rem",
        }}
      >
        {/* Baseline Card */}
        <div
          style={{
            background: "rgba(15, 23, 42, 0.6)",
            border: "1px solid var(--border-color)",
            borderRadius: "0.5rem",
            padding: "1rem",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "0.75rem",
            }}
          >
            <span style={{ fontWeight: 700, color: "var(--text-secondary)", fontSize: "0.95rem" }}>
              Baseline Temporal 1D
            </span>
            <span
              className="badge"
              style={{ background: "rgba(148, 163, 184, 0.15)", color: "#94a3b8" }}
            >
              Sem Grafo
            </span>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "0.75rem",
              fontSize: "0.85rem",
            }}
          >
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                AUPRC (Classe Rara)
              </span>
              <div
                className="mono"
                style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-primary)" }}
              >
                {baselineMetrics.auprc.toFixed(3)}
              </div>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>F1-Score</span>
              <div
                className="mono"
                style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--text-primary)" }}
              >
                {baselineMetrics.f1_score.toFixed(3)}
              </div>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                Sensibilidade (Recall)
              </span>
              <div className="mono" style={{ fontSize: "1rem", color: "var(--text-secondary)" }}>
                {(baselineMetrics.sensitivity * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                Especificidade
              </span>
              <div className="mono" style={{ fontSize: "1rem", color: "var(--text-secondary)" }}>
                {(baselineMetrics.specificity * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                Taxa Falsos Positivos
              </span>
              <div className="mono" style={{ fontSize: "1rem", color: "var(--accent-amber)" }}>
                {baselineMetrics.false_positives_per_hour.toFixed(1)} FP/h
              </div>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                Latência de Detecção
              </span>
              <div className="mono" style={{ fontSize: "1rem", color: "var(--text-secondary)" }}>
                {baselineMetrics.mean_detection_latency_seconds.toFixed(2)} s
              </div>
            </div>
          </div>
        </div>

        {/* ST-GNN Card */}
        <div
          style={{
            background: "rgba(139, 92, 246, 0.08)",
            border: "1px solid rgba(139, 92, 246, 0.4)",
            borderRadius: "0.5rem",
            padding: "1rem",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "0.75rem",
            }}
          >
            <span
              style={{
                fontWeight: 700,
                color: "var(--accent-purple)",
                fontSize: "0.95rem",
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
              }}
            >
              <Award size={16} /> ST-GNN Espaço-Temporal
            </span>
            <span className="badge badge-purple">Grafo Corporal</span>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "0.75rem",
              fontSize: "0.85rem",
            }}
          >
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                AUPRC (Classe Rara)
              </span>
              <div
                className="mono"
                style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--accent-emerald)" }}
              >
                {stGnnMetrics.auprc.toFixed(3)}
              </div>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>F1-Score</span>
              <div
                className="mono"
                style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--accent-emerald)" }}
              >
                {stGnnMetrics.f1_score.toFixed(3)}
              </div>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                Sensibilidade (Recall)
              </span>
              <div className="mono" style={{ fontSize: "1rem", color: "var(--accent-cyan)" }}>
                {(stGnnMetrics.sensitivity * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                Especificidade
              </span>
              <div className="mono" style={{ fontSize: "1rem", color: "var(--accent-cyan)" }}>
                {(stGnnMetrics.specificity * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                Taxa Falsos Positivos
              </span>
              <div className="mono" style={{ fontSize: "1rem", color: "var(--accent-emerald)" }}>
                {stGnnMetrics.false_positives_per_hour.toFixed(1)} FP/h
              </div>
            </div>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>
                Latência de Detecção
              </span>
              <div className="mono" style={{ fontSize: "1rem", color: "var(--accent-purple)" }}>
                {stGnnMetrics.mean_detection_latency_seconds.toFixed(2)} s
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
