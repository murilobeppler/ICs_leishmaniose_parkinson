"use client";

import React from "react";
import { RankedCandidate } from "../types";
import { Eye, ArrowUpDown, CheckCircle, AlertTriangle } from "lucide-react";

interface CandidateTableProps {
  candidates: RankedCandidate[];
  onSelectCandidate: (candidate: RankedCandidate) => void;
}

export function CandidateTable({ candidates, onSelectCandidate }: CandidateTableProps) {
  if (candidates.length === 0) {
    return (
      <div
        className="glass-panel"
        style={{ padding: "3rem 1.5rem", textAlign: "center", color: "var(--text-secondary)" }}
      >
        <AlertTriangle size={36} color="var(--accent-amber)" style={{ margin: "0 auto 0.75rem" }} />
        <p style={{ fontSize: "1.1rem", fontWeight: 600 }}>
          Nenhum candidato peptídico encontrado com os filtros atuais.
        </p>
        <p style={{ fontSize: "0.875rem", marginTop: "0.25rem" }}>
          Tente relaxar os critérios de busca, carga ou score de corte.
        </p>
      </div>
    );
  }

  return (
    <div
      tabIndex={0}
      role="region"
      aria-labelledby="candidates-table-caption"
      className="table-container"
      style={{ maxHeight: "580px", overflow: "auto" }}
    >
      <caption id="candidates-table-caption" style={{ display: "none" }}>
        Ranking de Candidatos Peptídicos para Triagem contra Leishmania
      </caption>
      <table>
        <thead style={{ position: "sticky", insetBlockStart: 0, zIndex: 2 }}>
          <tr>
            <th>Rank</th>
            <th>ID Peptídeo</th>
            <th>Sequência</th>
            <th>Grupo / Origem</th>
            <th>Tamanho</th>
            <th>Carga (pH 7.4)</th>
            <th>GRAVY</th>
            <th>Top Score (kcal/mol)</th>
            <th>Contatos Sítio</th>
            <th>Prioridade Triagem</th>
            <th>Ações</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => {
            const isHigh = c.triage_tier === "prioridade_alta_triagem";
            const isMed = c.triage_tier === "prioridade_media_triagem";

            return (
              <tr key={c.peptide.peptide_id}>
                <td>
                  <span
                    style={{
                      fontWeight: 700,
                      color: isHigh
                        ? "var(--accent-emerald)"
                        : isMed
                          ? "var(--accent-amber)"
                          : "var(--text-muted)",
                    }}
                  >
                    #{c.rank}
                  </span>
                </td>
                <td>
                  <strong className="mono" style={{ color: "var(--text-primary)" }}>
                    {c.peptide.peptide_id}
                  </strong>
                </td>
                <td>
                  <code
                    style={{
                      background: "rgba(148, 163, 184, 0.12)",
                      padding: "0.2rem 0.45rem",
                      borderRadius: "0.25rem",
                      fontWeight: 700,
                      letterSpacing: "0.06em",
                      color: isHigh ? "var(--accent-emerald)" : "#f8fafc",
                    }}
                  >
                    {c.peptide.sequence}
                  </code>
                </td>
                <td>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    {c.peptide.source_family}
                  </span>
                </td>
                <td>{c.peptide.length} aa</td>
                <td>
                  <span
                    className="mono"
                    style={{
                      color:
                        c.peptide.net_charge_ph7 > 0
                          ? "var(--accent-cyan)"
                          : c.peptide.net_charge_ph7 < 0
                            ? "var(--accent-rose)"
                            : "inherit",
                    }}
                  >
                    {c.peptide.net_charge_ph7 > 0
                      ? `+${c.peptide.net_charge_ph7}`
                      : c.peptide.net_charge_ph7}
                  </span>
                </td>
                <td className="mono">{c.peptide.gravy_hydropathy.toFixed(2)}</td>
                <td>
                  <span
                    className="mono"
                    style={{
                      fontWeight: 700,
                      color: isHigh ? "var(--accent-emerald)" : "var(--accent-cyan)",
                    }}
                  >
                    {c.result.top_score.toFixed(2)}
                  </span>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      marginLeft: "0.3rem",
                    }}
                  >
                    (Z={c.z_score})
                  </span>
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <div
                      style={{
                        width: "42px",
                        height: "6px",
                        background: "var(--border-color)",
                        borderRadius: "3px",
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${Math.round(c.result.binding_site_contact_ratio * 100)}%`,
                          height: "100%",
                          background: "var(--accent-cyan)",
                        }}
                      />
                    </div>
                    <span style={{ fontSize: "0.75rem" }}>
                      {Math.round(c.result.binding_site_contact_ratio * 100)}%
                    </span>
                  </div>
                </td>
                <td>
                  <span
                    className={`badge ${isHigh ? "badge-high" : isMed ? "badge-medium" : "badge-low"}`}
                  >
                    {isHigh ? "Alta" : isMed ? "Média" : "Baixa"}
                  </span>
                </td>
                <td>
                  <button
                    onClick={() => onSelectCandidate(c)}
                    className="btn btn-secondary"
                    style={{ padding: "0.3rem 0.65rem", fontSize: "0.8rem" }}
                    aria-label={`Ver poses e contatos de ${c.peptide.peptide_id}`}
                  >
                    <Eye size={14} />
                    Ver Pose
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
