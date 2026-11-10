"use client";

import React, { useEffect, useRef, useState } from "react";
import { RankedCandidate, PoseContact } from "../types";
import { X, ShieldAlert, Award, Layers, Sparkles, Download, Code, Check } from "lucide-react";

interface PoseDetailModalProps {
  candidate: RankedCandidate | null;
  onClose: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_PEPTIDE_API_URL || "http://127.0.0.1:8001";

export function PoseDetailModal({ candidate, onClose }: PoseDetailModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [showPymolCode, setShowPymolCode] = useState(false);
  const [pymolScript, setPymolScript] = useState<string>("");
  const [copied, setCopied] = useState(false);
  const [loadingScript, setLoadingScript] = useState(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (candidate) {
      if (!dialog.open) {
        dialog.showModal();
      }
      setShowPymolCode(false);
      setCopied(false);
      // Fetch PyMOL script preview
      setLoadingScript(true);
      fetch(`${API_BASE}/results/${candidate.result.run_id}/${candidate.peptide.peptide_id}/pymol`)
        .then((r) => r.json())
        .then((data) => {
          if (data.script) setPymolScript(data.script);
        })
        .catch(() => {})
        .finally(() => setLoadingScript(false));
    } else if (dialog.open) {
      dialog.close();
    }
  }, [candidate]);

  const handleCopyScript = () => {
    if (!pymolScript) return;
    navigator.clipboard.writeText(pymolScript);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!candidate) return null;

  const { peptide, result } = candidate;
  const topPose = result.poses[0];

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="modal-candidate-title"
      className="p-0 backdrop:bg-black/70"
    >
      <div className="glass-panel" style={{ padding: "1.75rem", background: "var(--bg-surface)" }}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: "1.25rem",
            borderBottom: "1px solid var(--border-color)",
            paddingBottom: "1rem",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
              <span
                className={`badge ${candidate.triage_tier === "prioridade_alta_triagem" ? "badge-high" : candidate.triage_tier === "prioridade_media_triagem" ? "badge-medium" : "badge-low"}`}
              >
                Rank #{candidate.rank} • {candidate.triage_tier.replace(/_/g, " ")}
              </span>
              <span className="badge badge-cyan">{peptide.source_family}</span>
            </div>
            <h2
              id="modal-candidate-title"
              style={{ fontSize: "1.35rem", fontWeight: 700, marginTop: "0.4rem" }}
            >
              {peptide.peptide_id} — Pose & Análise Estrutural de Triagem
            </h2>
          </div>
          <button
            onClick={onClose}
            className="btn btn-secondary"
            aria-label="Fechar modal de pose"
            style={{ padding: "0.4rem 0.6rem" }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Hypothesis Disclaimer Banner */}
        <div
          style={{
            background: "rgba(245, 158, 11, 0.12)",
            border: "1px solid rgba(245, 158, 11, 0.35)",
            borderRadius: "0.5rem",
            padding: "0.75rem 1rem",
            marginBottom: "1.25rem",
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            color: "#fde68a",
            fontSize: "0.85rem",
          }}
        >
          <ShieldAlert size={20} style={{ flexShrink: 0, color: "#f59e0b" }} />
          <div>
            <strong>Aviso Metodológico de Triagem In Silico:</strong> O score energético (-
            {Math.abs(result.top_score)} kcal/mol) representa estritamente uma hipótese
            computacional de ancoramento. Não comprova afinidade biofísica sem ensaio ortogonal in
            vitro.
          </div>
        </div>

        {/* Peptide Sequence & Biophy Properties */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "1rem",
            marginBottom: "1.25rem",
          }}
        >
          <div
            style={{
              background: "var(--bg-surface-elevated)",
              padding: "0.85rem",
              borderRadius: "0.5rem",
            }}
          >
            <span
              style={{
                fontSize: "0.75rem",
                color: "var(--text-muted)",
                textTransform: "uppercase",
              }}
            >
              Sequência Primária ({peptide.length} aa)
            </span>
            <div
              className="mono"
              style={{
                fontSize: "0.85rem",
                wordBreak: "break-all",
                color: "var(--accent-cyan)",
                marginTop: "0.25rem",
              }}
            >
              {peptide.sequence}
            </div>
          </div>
          <div
            style={{
              background: "var(--bg-surface-elevated)",
              padding: "0.85rem",
              borderRadius: "0.5rem",
            }}
          >
            <span
              style={{
                fontSize: "0.75rem",
                color: "var(--text-muted)",
                textTransform: "uppercase",
              }}
            >
              Propriedades Físico-Químicas
            </span>
            <div
              style={{
                fontSize: "0.85rem",
                marginTop: "0.25rem",
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "0.2rem",
              }}
            >
              <div>
                Massa: <strong>{peptide.molecular_weight_da} Da</strong>
              </div>
              <div>
                Carga (pH 7.4):{" "}
                <strong>
                  {peptide.net_charge_ph7 > 0
                    ? `+${peptide.net_charge_ph7}`
                    : peptide.net_charge_ph7}
                </strong>
              </div>
              <div>
                GRAVY: <strong>{peptide.gravy_hydropathy}</strong>
              </div>
              <div>
                pI: <strong>{peptide.isoelectric_point}</strong>
              </div>
            </div>
          </div>
        </div>

        {/* Poses Table */}
        <h3
          style={{
            fontSize: "1rem",
            fontWeight: 600,
            marginBottom: "0.6rem",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <Layers size={18} color="var(--accent-cyan)" />
          Poses Conformacionais Preditas ({result.poses.length} poses geradas)
        </h3>

        <div
          className="table-container"
          style={{ maxHeight: "180px", marginBottom: "1.25rem" }}
          tabIndex={0}
          role="region"
          aria-label="Tabela de poses conformacionais"
        >
          <table>
            <thead>
              <tr>
                <th>Pose #</th>
                <th>Score de Docking</th>
                <th>RMSD vs Pose 1</th>
                <th>Área de Interface</th>
                <th>Contatos com Sítio</th>
              </tr>
            </thead>
            <tbody>
              {result.poses.map((p) => (
                <tr key={p.pose_rank}>
                  <td>
                    <strong>Pose {p.pose_rank}</strong>
                  </td>
                  <td
                    className="mono"
                    style={{ color: p.pose_rank === 1 ? "var(--accent-emerald)" : "inherit" }}
                  >
                    {p.docking_score.toFixed(2)}
                  </td>
                  <td>{p.rmsd_to_top_pose_angstrom.toFixed(2)} Å</td>
                  <td>{p.interface_area_angstrom2.toFixed(1)} Å²</td>
                  <td>{p.contacts.length} contatos</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Interatomic Contacts on Target Pocket */}
        <h3
          style={{
            fontSize: "1rem",
            fontWeight: 600,
            marginBottom: "0.6rem",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <Sparkles size={18} color="var(--accent-amber)" />
          Contatos Interatômicos no Sítio Ativo do Alvo (Pose #1)
        </h3>

        <div
          className="table-container"
          style={{ maxHeight: "200px" }}
          tabIndex={0}
          role="region"
          aria-label="Contatos interatômicos no bolso catalítico"
        >
          <table>
            <thead>
              <tr>
                <th>Resíduo Peptídeo</th>
                <th>Resíduo no Alvo de Leishmania</th>
                <th>Distância (Å)</th>
                <th>Tipo de Interação</th>
              </tr>
            </thead>
            <tbody>
              {topPose.contacts.map((c: PoseContact, idx: number) => (
                <tr key={idx}>
                  <td className="mono">
                    #{c.peptide_residue_index} {c.peptide_residue}
                  </td>
                  <td>
                    <strong>{c.target_residue_id}</strong>
                  </td>
                  <td>{c.distance_angstrom.toFixed(2)} Å</td>
                  <td>
                    <span
                      className="badge"
                      style={{
                        background:
                          c.interaction_type === "salt_bridge"
                            ? "rgba(244, 63, 94, 0.2)"
                            : c.interaction_type === "hydrogen_bond"
                              ? "rgba(59, 130, 246, 0.2)"
                              : c.interaction_type === "pi_stacking"
                                ? "rgba(245, 158, 11, 0.2)"
                                : "rgba(16, 185, 129, 0.2)",
                        color:
                          c.interaction_type === "salt_bridge"
                            ? "#fb7185"
                            : c.interaction_type === "hydrogen_bond"
                              ? "#60a5fa"
                              : c.interaction_type === "pi_stacking"
                                ? "#fcd34d"
                                : "#34d399",
                      }}
                    >
                      {c.interaction_type.replace(/_/g, " ")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* PyMOL Visualization & Export Section */}
        <div style={{ marginTop: "1.25rem", padding: "1rem", background: "rgba(6, 182, 212, 0.08)", border: "1px solid rgba(6, 182, 212, 0.25)", borderRadius: "0.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
            <div>
              <div style={{ fontSize: "0.9rem", fontWeight: 700, color: "var(--accent-cyan)", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <span>Visualização PyMOL (Publication-Ready)</span>
                <span className="badge badge-cyan" style={{ fontSize: "0.65rem" }}>.PML Script</span>
              </div>
              <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.15rem" }}>
                Gera script de renderização com sítio catalítico em sticks, peptídeo contrastante e contatos polares mapeados.
              </p>
            </div>

            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                onClick={() => setShowPymolCode(!showPymolCode)}
                className="btn btn-secondary"
                style={{ fontSize: "0.8rem", padding: "0.35rem 0.65rem" }}
              >
                <Code size={14} />
                {showPymolCode ? "Ocultar Script" : "Inspecionar Script"}
              </button>
              <a
                href={`${API_BASE}/results/${result.run_id}/${peptide.peptide_id}/pymol?download=true`}
                download={`${peptide.peptide_id}_docking.pml`}
                className="btn btn-primary"
                style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
              >
                <Download size={14} />
                Baixar .pml
              </a>
            </div>
          </div>

          {showPymolCode && pymolScript && (
            <div style={{ marginTop: "0.75rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.3rem" }}>
                <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Código do Script PyMOL</span>
                <button
                  onClick={handleCopyScript}
                  className="btn btn-secondary"
                  style={{ fontSize: "0.7rem", padding: "0.2rem 0.5rem" }}
                >
                  {copied ? <Check size={12} color="var(--accent-emerald)" /> : null}
                  {copied ? "Copiado!" : "Copiar Código"}
                </button>
              </div>
              <pre
                className="mono"
                style={{
                  fontSize: "0.75rem",
                  background: "#080c14",
                  padding: "0.75rem",
                  borderRadius: "0.375rem",
                  border: "1px solid var(--border-color)",
                  overflowX: "auto",
                  maxHeight: "180px",
                  color: "#e2e8f0",
                }}
              >
                {pymolScript}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ marginTop: "1.25rem", display: "flex", justifyContent: "flex-end" }}>
          <button onClick={onClose} className="btn btn-secondary">
            Fechar Detalhes
          </button>
        </div>
      </div>
    </dialog>
  );
}
