"use client";

import React from "react";
import { DockingRunManifest, RunRankingSummary, Target } from "../types";
import { CheckCircle2, Cpu, Database, Flame, HelpCircle, ShieldCheck } from "lucide-react";

interface RunSummaryCardProps {
  manifest: DockingRunManifest | null;
  summary: RunRankingSummary | null;
  target: Target | null;
}

export function RunSummaryCard({ manifest, summary, target }: RunSummaryCardProps) {
  if (!manifest || !summary) return null;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
        gap: "1rem",
        marginBottom: "1.5rem",
      }}
    >
      {/* Target & Selectivity */}
      <div className="glass-panel" style={{ padding: "1.25rem" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "0.5rem",
          }}
        >
          <span
            style={{
              fontSize: "0.75rem",
              textTransform: "uppercase",
              color: "var(--text-muted)",
              fontWeight: 600,
            }}
          >
            Alvo Seletivo de Leishmania
          </span>
          <span className="badge badge-high" style={{ fontSize: "0.65rem" }}>
            <ShieldCheck size={12} /> Sem Ortólogo Humano
          </span>
        </div>
        <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--accent-cyan)" }}>
          {target?.name ?? "Tripanotiona Redutase (TryR)"}
        </div>
        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>
          Organismo: <em>{target?.organism ?? "Leishmania infantum"}</em> • UniProt:{" "}
          <strong>{target?.uniprot_id ?? "A4HSF7"}</strong>
        </p>
        <p style={{ fontSize: "0.75rem", color: "var(--accent-emerald)", marginTop: "0.4rem" }}>
          ✓ {target?.ortholog_Verification_note ?? "Ausência de ortólogo humano verificada"}
        </p>
      </div>

      {/* Docking Run Manifest */}
      <div className="glass-panel" style={{ padding: "1.25rem" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "0.5rem",
          }}
        >
          <span
            style={{
              fontSize: "0.75rem",
              textTransform: "uppercase",
              color: "var(--text-muted)",
              fontWeight: 600,
            }}
          >
            Execução de Docking
          </span>
          <span className="badge badge-blue mono" style={{ fontSize: "0.65rem" }}>
            <Cpu size={12} /> {manifest.engine_name.toUpperCase()} (seed={manifest.seed})
          </span>
        </div>
        <div style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--text-primary)" }}>
          {manifest.completed_jobs} / {manifest.total_jobs} peptídeos
        </div>
        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
          Run ID: <code className="mono">{manifest.run_id}</code> • Status:{" "}
          <strong>{manifest.status}</strong>
        </p>
        <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.4rem" }}>
          Lotes de {manifest.batch_size} • Cache: {manifest.cached_jobs} recuperados
        </p>
      </div>

      {/* Triage Stats */}
      <div className="glass-panel" style={{ padding: "1.25rem" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "0.5rem",
          }}
        >
          <span
            style={{
              fontSize: "0.75rem",
              textTransform: "uppercase",
              color: "var(--text-muted)",
              fontWeight: 600,
            }}
          >
            Estatísticas da Triagem
          </span>
          <span className="badge badge-cyan" style={{ fontSize: "0.65rem" }}>
            {summary.filtered_count} filtrados
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: "0.75rem" }}>
          <div>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Melhor Score:</span>
            <div
              className="mono"
              style={{ fontSize: "1.2rem", fontWeight: 700, color: "var(--accent-emerald)" }}
            >
              {summary.best_top_score.toFixed(2)}
            </div>
          </div>
          <div>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Mediana:</span>
            <div className="mono" style={{ fontSize: "1rem", color: "var(--text-secondary)" }}>
              {summary.median_top_score.toFixed(2)}
            </div>
          </div>
          <div>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Média:</span>
            <div className="mono" style={{ fontSize: "1rem", color: "var(--text-secondary)" }}>
              {summary.mean_top_score.toFixed(2)}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.6rem" }}>
          <span className="badge badge-high">{summary.high_priority_count} Alta</span>
          <span className="badge badge-medium">{summary.medium_priority_count} Média</span>
          <span className="badge badge-low">{summary.low_priority_count} Baixa</span>
        </div>
      </div>
    </div>
  );
}
