"use client";

import React, { useEffect, useState, useMemo } from "react";
import {
  RankedCandidate,
  ResultsResponse,
  DockingRunManifest,
  RunRankingSummary,
  Target,
} from "../types";
import { RunSummaryCard } from "../components/RunSummaryCard";
import { FilterBar } from "../components/FilterBar";
import { CandidateTable } from "../components/CandidateTable";
import { PoseDetailModal } from "../components/PoseDetailModal";
import { Dna, RefreshCw, AlertCircle, ShieldAlert, ExternalLink } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_PEPTIDE_API_URL || "http://127.0.0.1:8001";

export default function PeptideDockingPage() {
  const [data, setData] = useState<ResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters state
  const [search, setSearch] = useState("");
  const [selectedFamily, setSelectedFamily] = useState("");
  const [minCharge, setMinCharge] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [minContactRatio, setMinContactRatio] = useState("");

  // Selected candidate for pose modal
  const [selectedCandidate, setSelectedCandidate] = useState<RankedCandidate | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const url = new URL(`${API_BASE}/results`);
      url.searchParams.set("top_k", "634");
      const resp = await fetch(url.toString(), { cache: "no-store" });
      if (!resp.ok) {
        throw new Error(`Erro na API (${resp.status}): ${resp.statusText}`);
      }
      const json: ResultsResponse = await resp.json();
      setData(json);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Falha ao conectar na API de docking.";
      setError(
        `${msg} Verifique se o backend está ativo em ${API_BASE} (execute 'make api-a' ou 'make dev-a').`,
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const families = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>();
    data.candidates.forEach((c) => set.add(c.peptide.source_family));
    return Array.from(set).sort();
  }, [data]);

  const filteredCandidates = useMemo(() => {
    if (!data) return [];
    return data.candidates.filter((c) => {
      const pep = c.peptide;
      const res = c.result;

      if (search) {
        const q = search.trim().toUpperCase();
        const match =
          pep.peptide_id.toUpperCase().includes(q) ||
          pep.sequence.toUpperCase().includes(q) ||
          pep.source_family.toUpperCase().includes(q);
        if (!match) return false;
      }

      if (selectedFamily && pep.source_family.toLowerCase() !== selectedFamily.toLowerCase()) {
        return false;
      }

      if (minCharge !== "") {
        const val = parseFloat(minCharge);
        if (!isNaN(val) && pep.net_charge_ph7 < val) return false;
      }

      if (maxScore !== "") {
        const val = parseFloat(maxScore);
        if (!isNaN(val) && res.top_score > val) return false;
      }

      if (minContactRatio !== "") {
        const val = parseFloat(minContactRatio) / 100.0;
        if (!isNaN(val) && res.binding_site_contact_ratio < val) return false;
      }

      return true;
    });
  }, [data, search, selectedFamily, minCharge, maxScore, minContactRatio]);

  const handleResetFilters = () => {
    setSearch("");
    setSelectedFamily("");
    setMinCharge("");
    setMaxScore("");
    setMinContactRatio("");
  };

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
                background: "rgba(6, 182, 212, 0.15)",
                padding: "0.4rem",
                borderRadius: "0.5rem",
              }}
            >
              <Dna size={26} color="var(--accent-cyan)" />
            </div>
            <div>
              <span
                style={{
                  fontSize: "0.75rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--accent-cyan)",
                  fontWeight: 700,
                }}
              >
                Iniciação Científica — Módulo A
              </span>
              <h1 style={{ fontSize: "1.65rem", fontWeight: 800, letterSpacing: "-0.02em" }}>
                Triagem Computacional de Peptídeos Anti-Leishmania
              </h1>
            </div>
          </div>
          <p
            style={{
              fontSize: "0.875rem",
              color: "var(--text-secondary)",
              marginTop: "0.35rem",
              maxWidth: "860px",
            }}
          >
            Triagem virtual e ranking multifatorial de peptídeos candidatos ancorados contra o sítio
            catalítico redox-ativo da Tripanotiona Redutase de <em>Leishmania</em> (alvo seletivo sem ortólogo humano),
            com scores oficiais do servidor <strong>HPEPDOCK</strong>, visualização de contatos e exportação PyMOL.
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            onClick={fetchData}
            disabled={loading}
            className="btn btn-secondary"
            title="Recarregar dados da API"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            Atualizar
          </button>
        </div>
      </header>

      {/* Prominent Scientific Hypothesis Banner */}
      <section
        style={{
          background: "rgba(30, 41, 59, 0.7)",
          border: "1px solid rgba(6, 182, 212, 0.35)",
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
        <ShieldAlert size={22} style={{ flexShrink: 0, color: "var(--accent-cyan)" }} />
        <div>
          <strong>Diretriz de Honestidade Científica:</strong> O score de docking molecular
          representa exclusivamente uma hipótese computacional de ancoramento/estabilidade estérica
          para priorização de triagem in silico. Não constitui ensaio de inibição nem comprovação de
          atividade biológica.
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
      {loading && !data && (
        <div style={{ textAlign: "center", padding: "4rem 1rem", color: "var(--text-muted)" }}>
          <Dna
            size={40}
            className="animate-spin"
            style={{ margin: "0 auto 1rem", color: "var(--accent-cyan)" }}
          />
          <p>Carregando biblioteca de 634 candidatos e resultados de docking...</p>
        </div>
      )}

      {data && (
        <>
          <RunSummaryCard manifest={data.manifest} summary={data.summary} target={data.target} />

          <FilterBar
            search={search}
            onSearchChange={setSearch}
            selectedFamily={selectedFamily}
            onFamilyChange={setSelectedFamily}
            families={families}
            minCharge={minCharge}
            onMinChargeChange={setMinCharge}
            maxScore={maxScore}
            onMaxScoreChange={setMaxScore}
            minContactRatio={minContactRatio}
            onMinContactRatioChange={setMinContactRatio}
            onReset={handleResetFilters}
          />

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "0.6rem",
            }}
          >
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>
              Candidatos Priorizados ({filteredCandidates.length} de {data.manifest.total_jobs})
            </h2>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              Ordenado por: Score de Afinidade Predita (menor = mais favorável)
            </span>
          </div>

          <CandidateTable
            candidates={filteredCandidates}
            onSelectCandidate={setSelectedCandidate}
          />
        </>
      )}

      {/* Pose Detail Modal */}
      <PoseDetailModal candidate={selectedCandidate} onClose={() => setSelectedCandidate(null)} />
    </main>
  );
}
