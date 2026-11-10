"use client";

import React from "react";
import { Search, Filter, RotateCcw } from "lucide-react";

interface FilterBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  selectedFamily: string;
  onFamilyChange: (value: string) => void;
  families: string[];
  minCharge: string;
  onMinChargeChange: (value: string) => void;
  maxScore: string;
  onMaxScoreChange: (value: string) => void;
  minContactRatio: string;
  onMinContactRatioChange: (value: string) => void;
  onReset: () => void;
}

export function FilterBar({
  search,
  onSearchChange,
  selectedFamily,
  onFamilyChange,
  families,
  minCharge,
  onMinChargeChange,
  maxScore,
  onMaxScoreChange,
  minContactRatio,
  onMinContactRatioChange,
  onReset,
}: FilterBarProps) {
  return (
    <div className="glass-panel" style={{ padding: "1rem", marginBottom: "1.25rem" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "0.75rem",
          alignItems: "end",
        }}
      >
        {/* Search */}
        <div>
          <label
            style={{
              display: "block",
              fontSize: "0.75rem",
              color: "var(--text-secondary)",
              marginBottom: "0.25rem",
              fontWeight: 600,
            }}
          >
            Busca (ID / Sequência / Família)
          </label>
          <div style={{ position: "relative" }}>
            <input
              type="text"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Ex.: PEP_0012, FLPLI..."
              style={{
                width: "100%",
                padding: "0.45rem 0.6rem 0.45rem 2rem",
                background: "var(--bg-surface-elevated)",
                border: "1px solid var(--border-color)",
                borderRadius: "0.375rem",
                color: "var(--text-primary)",
                fontSize: "0.85rem",
              }}
            />
            <Search
              size={14}
              color="var(--text-muted)"
              style={{
                position: "absolute",
                left: "0.6rem",
                top: "50%",
                transform: "translateY(-50%)",
              }}
            />
          </div>
        </div>

        {/* Family dropdown */}
        <div>
          <label
            style={{
              display: "block",
              fontSize: "0.75rem",
              color: "var(--text-secondary)",
              marginBottom: "0.25rem",
              fontWeight: 600,
            }}
          >
            Família Peptídica
          </label>
          <select
            value={selectedFamily}
            onChange={(e) => onFamilyChange(e.target.value)}
            style={{
              width: "100%",
              padding: "0.45rem 0.6rem",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-color)",
              borderRadius: "0.375rem",
              color: "var(--text-primary)",
              fontSize: "0.85rem",
            }}
          >
            <option value="">Todas as famílias</option>
            {families.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>

        {/* Carga mínima */}
        <div>
          <label
            style={{
              display: "block",
              fontSize: "0.75rem",
              color: "var(--text-secondary)",
              marginBottom: "0.25rem",
              fontWeight: 600,
            }}
          >
            Carga Líquida Mín. (pH 7.4)
          </label>
          <input
            type="number"
            step="0.5"
            value={minCharge}
            onChange={(e) => onMinChargeChange(e.target.value)}
            placeholder="Ex.: 1.0"
            style={{
              width: "100%",
              padding: "0.45rem 0.6rem",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-color)",
              borderRadius: "0.375rem",
              color: "var(--text-primary)",
              fontSize: "0.85rem",
            }}
          />
        </div>

        {/* Score máximo de corte */}
        <div>
          <label
            style={{
              display: "block",
              fontSize: "0.75rem",
              color: "var(--text-secondary)",
              marginBottom: "0.25rem",
              fontWeight: 600,
            }}
          >
            Score Máx. (mais negativo = melhor)
          </label>
          <input
            type="number"
            step="5"
            value={maxScore}
            onChange={(e) => onMaxScoreChange(e.target.value)}
            placeholder="Ex.: -170"
            style={{
              width: "100%",
              padding: "0.45rem 0.6rem",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-color)",
              borderRadius: "0.375rem",
              color: "var(--text-primary)",
              fontSize: "0.85rem",
            }}
          />
        </div>

        {/* Contato mínimo com bolso */}
        <div>
          <label
            style={{
              display: "block",
              fontSize: "0.75rem",
              color: "var(--text-secondary)",
              marginBottom: "0.25rem",
              fontWeight: 600,
            }}
          >
            Contatos com Sítio Mín. (%)
          </label>
          <input
            type="number"
            min="0"
            max="100"
            value={minContactRatio}
            onChange={(e) => onMinContactRatioChange(e.target.value)}
            placeholder="Ex.: 40"
            style={{
              width: "100%",
              padding: "0.45rem 0.6rem",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-color)",
              borderRadius: "0.375rem",
              color: "var(--text-primary)",
              fontSize: "0.85rem",
            }}
          />
        </div>

        {/* Reset */}
        <div>
          <button
            onClick={onReset}
            className="btn btn-secondary"
            style={{ width: "100%", justifyContent: "center" }}
            title="Limpar todos os filtros"
          >
            <RotateCcw size={14} /> Limpar
          </button>
        </div>
      </div>
    </div>
  );
}
