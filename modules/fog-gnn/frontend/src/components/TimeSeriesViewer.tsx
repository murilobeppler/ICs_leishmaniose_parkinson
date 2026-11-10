"use client";

import React, { useState } from "react";
import { WindowPredictionRecord } from "../types";
import { Activity, Radio, AlertOctagon } from "lucide-react";

interface TimeSeriesViewerProps {
  predictions: WindowPredictionRecord[];
  selectedSubject: string;
}

export function TimeSeriesViewer({ predictions, selectedSubject }: TimeSeriesViewerProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null);

  const subjectWindows = predictions
    .filter((p) => p.subject_id === selectedSubject)
    .sort((a, b) => a.start_seconds - b.start_seconds);

  if (subjectWindows.length === 0) {
    return (
      <div
        className="glass-panel"
        style={{ padding: "2rem", textAlign: "center", color: "var(--text-muted)" }}
      >
        Nenhuma janela temporal registrada para o sujeito {selectedSubject}.
      </div>
    );
  }

  const chartHeight = 220;
  const paddingX = 40;
  const paddingY = 25;
  const usableHeight = chartHeight - paddingY * 2;

  const maxTime = subjectWindows[subjectWindows.length - 1].end_seconds || 48;
  const minTime = subjectWindows[0].start_seconds || 0;
  const timeSpan = Math.max(1, maxTime - minTime);

  // SVG scaling functions
  const getX = (seconds: number, svgWidth: number) => {
    const usableWidth = svgWidth - paddingX * 2;
    return paddingX + ((seconds - minTime) / timeSpan) * usableWidth;
  };

  const getY = (prob: number) => {
    return paddingY + (1.0 - Math.max(0, Math.min(1, prob))) * usableHeight;
  };

  const hoveredItem = hoveredIdx !== null ? subjectWindows[hoveredIdx] : null;

  return (
    <div className="glass-panel" style={{ padding: "1.25rem", marginBottom: "1.5rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "0.75rem",
          flexWrap: "wrap",
          gap: "0.5rem",
        }}
      >
        <div>
          <span
            style={{
              fontSize: "0.75rem",
              textTransform: "uppercase",
              color: "var(--accent-cyan)",
              fontWeight: 700,
            }}
          >
            Série Temporal Contínua • Janelas Deslizantes de 2.56s (Stride 1.28s)
          </span>
          <h3
            style={{
              fontSize: "1.1rem",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <Activity size={18} color="var(--accent-cyan)" />
            Predição de Freezing of Gait vs. Ground Truth ({selectedSubject})
          </h3>
        </div>

        {/* Legend */}
        <div style={{ display: "flex", gap: "1rem", fontSize: "0.75rem", flexWrap: "wrap" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
            <span style={{ width: 12, height: 3, background: "#8b5cf6" }} /> ST-GNN (Grafo)
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
            <span style={{ width: 12, height: 3, background: "#94a3b8", borderStyle: "dashed" }} />{" "}
            Baseline 1D
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
            <span
              style={{
                width: 12,
                height: 10,
                background: "rgba(244, 63, 94, 0.35)",
                border: "1px solid #f43f5e",
              }}
            />{" "}
            Episódio Real de FOG
          </span>
        </div>
      </div>

      {/* SVG Time Series Chart */}
      <div style={{ position: "relative", width: "100%", overflowX: "auto" }}>
        <svg
          viewBox={`0 0 880 ${chartHeight}`}
          style={{ width: "100%", minWidth: "600px", height: "auto" }}
          preserveAspectRatio="none"
        >
          {/* Horizontal grid lines & probability labels */}
          {[0.0, 0.25, 0.5, 0.75, 1.0].map((level) => {
            const y = getY(level);
            return (
              <g key={level}>
                <line
                  x1={paddingX}
                  y1={y}
                  x2={880 - paddingX}
                  y2={y}
                  stroke="rgba(255,255,255,0.08)"
                  strokeDasharray={level === 0.5 ? "4 4" : undefined}
                />
                <text
                  x={paddingX - 8}
                  y={y + 4}
                  textAnchor="end"
                  fill="var(--text-muted)"
                  fontSize={10}
                  className="mono"
                >
                  {level.toFixed(2)}
                </text>
              </g>
            );
          })}

          {/* FOG Ground Truth background bands */}
          {subjectWindows.map((w, idx) => {
            if (w.true_label !== 1) return null;
            const x1 = getX(w.start_seconds, 880);
            const x2 = getX(w.end_seconds, 880);
            return (
              <rect
                key={idx}
                x={x1}
                y={paddingY}
                width={Math.max(4, x2 - x1)}
                height={usableHeight}
                fill="rgba(244, 63, 94, 0.22)"
                stroke="rgba(244, 63, 94, 0.4)"
                strokeWidth={0.5}
              />
            );
          })}

          {/* Baseline 1D probability line */}
          <polyline
            fill="none"
            stroke="#94a3b8"
            strokeWidth={1.75}
            strokeDasharray="4 3"
            points={subjectWindows
              .map((w) => {
                const mid = (w.start_seconds + w.end_seconds) / 2;
                return `${getX(mid, 880)},${getY(w.baseline_prob)}`;
              })
              .join(" ")}
          />

          {/* ST-GNN probability line */}
          <polyline
            fill="none"
            stroke="#8b5cf6"
            strokeWidth={2.75}
            points={subjectWindows
              .map((w) => {
                const mid = (w.start_seconds + w.end_seconds) / 2;
                return `${getX(mid, 880)},${getY(w.st_gnn_prob)}`;
              })
              .join(" ")}
          />

          {/* Interactive data points */}
          {subjectWindows.map((w, idx) => {
            const mid = (w.start_seconds + w.end_seconds) / 2;
            const cx = getX(mid, 880);
            const cy = getY(w.st_gnn_prob);
            const isHovered = hoveredIdx === idx;

            return (
              <circle
                key={idx}
                cx={cx}
                cy={cy}
                r={isHovered ? 6 : 3.5}
                fill={w.true_label === 1 ? "#f43f5e" : "#8b5cf6"}
                stroke="#ffffff"
                strokeWidth={isHovered ? 2 : 0.5}
                style={{ cursor: "pointer", transition: "r 0.15s" }}
                onMouseEnter={() => setHoveredIdx(idx)}
                onMouseLeave={() => setHoveredIdx(null)}
              />
            );
          })}
        </svg>

        {/* Hover Inspector tooltip */}
        {hoveredItem && (
          <div
            style={{
              position: "absolute",
              top: "10px",
              right: "20px",
              background: "rgba(17, 24, 39, 0.95)",
              border: "1px solid var(--border-color)",
              borderRadius: "0.5rem",
              padding: "0.6rem 0.9rem",
              fontSize: "0.8rem",
              boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
              zIndex: 10,
            }}
          >
            <div style={{ fontWeight: 700, color: "var(--accent-purple)", marginBottom: "0.2rem" }}>
              Janela: {hoveredItem.window_id} ({hoveredItem.start_seconds}s -{" "}
              {hoveredItem.end_seconds}s)
            </div>
            <div>
              Prob. ST-GNN: <strong>{(hoveredItem.st_gnn_prob * 100).toFixed(1)}%</strong>
            </div>
            <div>
              Prob. Baseline 1D: <strong>{(hoveredItem.baseline_prob * 100).toFixed(1)}%</strong>
            </div>
            <div>
              Freeze Index (Tornozelo): <strong>{hoveredItem.ankle_freeze_index.toFixed(2)}</strong>
            </div>
            <div>
              Ground Truth FOG:{" "}
              <strong>{hoveredItem.true_label === 1 ? "Sim (Episódio Ativo)" : "Não"}</strong>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
