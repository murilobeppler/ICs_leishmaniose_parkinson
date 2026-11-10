"use client";

import React, { useState } from "react";
import { BodyGraph, SensorNodeSpec, GraphEdge } from "../types";
import { Share2, Activity, Zap, Info } from "lucide-react";

interface BodyGraphViewerProps {
  normalGraph: BodyGraph | null;
  fogGraph: BodyGraph | null;
}

export function BodyGraphViewer({ normalGraph, fogGraph }: BodyGraphViewerProps) {
  const [activeRegime, setActiveRegime] = useState<"normal" | "fog">("fog");
  const [hoveredNode, setHoveredNode] = useState<SensorNodeSpec | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<GraphEdge | null>(null);

  const graph = activeRegime === "fog" ? fogGraph : normalGraph;
  if (!graph) return null;

  // SVG viewBox coordinates: 400x520
  const svgWidth = 400;
  const svgHeight = 500;

  const nodeMap = new Map<string, SensorNodeSpec>();
  graph.nodes.forEach((n) => nodeMap.set(n.node_id, n));

  const getNodeCoords = (nodeId: string): { x: number; y: number } => {
    const spec = nodeMap.get(nodeId);
    if (!spec) return { x: svgWidth / 2, y: svgHeight / 2 };
    return {
      x: Math.round(spec.x_pos * (svgWidth - 60) + 30),
      y: Math.round(spec.y_pos * (svgHeight - 60) + 30),
    };
  };

  const getEdgeStroke = (edge: GraphEdge) => {
    if (edge.kind === "anatomical") return "#10b981"; // Emerald
    if (edge.kind === "bilateral") return "#38bdf8"; // Light Blue
    if (edge.kind === "hybrid") return "#8b5cf6"; // Purple
    if (edge.kind === "corticospinal") return "#ec4899"; // Pink
    return "#f59e0b"; // Functional Amber
  };

  return (
    <div
      className="glass-panel"
      style={{ padding: "1.25rem", height: "100%", display: "flex", flexDirection: "column" }}
    >
      {/* Header & Regime Switch */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
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
            Topologia Relacional Espaço-Temporal
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
            <Share2 size={18} color="var(--accent-purple)" />
            Grafo Corporal de Sensores IMU
          </h3>
        </div>

        {/* Regime toggle */}
        <div
          style={{
            display: "flex",
            background: "var(--bg-surface-elevated)",
            padding: "0.2rem",
            borderRadius: "0.5rem",
            border: "1px solid var(--border-color)",
          }}
        >
          <button
            onClick={() => setActiveRegime("normal")}
            style={{
              padding: "0.3rem 0.75rem",
              fontSize: "0.75rem",
              fontWeight: 600,
              borderRadius: "0.375rem",
              border: "none",
              cursor: "pointer",
              background: activeRegime === "normal" ? "var(--accent-emerald)" : "transparent",
              color: activeRegime === "normal" ? "#04140e" : "var(--text-secondary)",
              transition: "all 0.15s ease",
            }}
          >
            Marcha Normal
          </button>
          <button
            onClick={() => setActiveRegime("fog")}
            style={{
              padding: "0.3rem 0.75rem",
              fontSize: "0.75rem",
              fontWeight: 600,
              borderRadius: "0.375rem",
              border: "none",
              cursor: "pointer",
              background: activeRegime === "fog" ? "var(--accent-purple)" : "transparent",
              color: activeRegime === "fog" ? "#ffffff" : "var(--text-secondary)",
              transition: "all 0.15s ease",
            }}
          >
            Episódio de Congelamento (FOG)
          </button>
        </div>
      </div>

      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.75rem" }}>
        {activeRegime === "fog" ? (
          <span style={{ color: "var(--accent-amber)" }}>
            ⚡ <strong>Em FOG:</strong> Ocorre desacoplamento cinemático bilateral e alta densidade
            de energia de tremor (3-8 Hz) nos membros distais, capturados pelas arestas do grafo.
          </span>
        ) : (
          <span style={{ color: "var(--accent-emerald)" }}>
            ✓ <strong>Marcha Normal:</strong> Acoplamento locomotor simétrico regular entre membros
            inferiores e tronco.
          </span>
        )}
      </p>

      {/* Graph SVG canvas */}
      <div
        style={{
          position: "relative",
          flex: 1,
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: "420px",
        }}
      >
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          style={{ width: "100%", maxWidth: "380px", height: "auto", overflow: "visible" }}
        >
          {/* Subtle body silhouette background guide */}
          <line
            x1={svgWidth / 2}
            y1={90}
            x2={svgWidth / 2}
            y2={180}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={4}
          />
          <line
            x1={svgWidth / 2}
            y1={180}
            x2={getNodeCoords("THIGH_L").x}
            y2={getNodeCoords("THIGH_L").y}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={3}
          />
          <line
            x1={svgWidth / 2}
            y1={180}
            x2={getNodeCoords("THIGH_R").x}
            y2={getNodeCoords("THIGH_R").y}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={3}
          />

          {/* Edges */}
          {graph.edges.map((edge, idx) => {
            const p1 = getNodeCoords(edge.source);
            const p2 = getNodeCoords(edge.target);
            const isHovered = hoveredEdge === edge;
            const strokeColor = getEdgeStroke(edge);
            const isBilateral = edge.kind === "bilateral";

            return (
              <g key={idx}>
                <line
                  x1={p1.x}
                  y1={p1.y}
                  x2={p2.x}
                  y2={p2.y}
                  stroke={strokeColor}
                  strokeWidth={Math.max(1.5, Math.min(4.5, edge.weight * 2.8))}
                  strokeDasharray={isBilateral ? "4 3" : undefined}
                  strokeOpacity={isHovered ? 1.0 : 0.65}
                  style={{
                    transition: "stroke-width 0.2s, stroke-opacity 0.2s",
                    cursor: "pointer",
                  }}
                  onMouseEnter={() => setHoveredEdge(edge)}
                  onMouseLeave={() => setHoveredEdge(null)}
                />
              </g>
            );
          })}

          {/* Nodes */}
          {graph.nodes.map((node) => {
            const pos = getNodeCoords(node.node_id);
            const isHovered = hoveredNode === node;
            const isDistal = node.node_id.includes("ANKLE");
            const nodeFill = isDistal && activeRegime === "fog" ? "#f43f5e" : "#8b5cf6";

            return (
              <g
                key={node.node_id}
                transform={`translate(${pos.x}, ${pos.y})`}
                style={{ cursor: "pointer" }}
                onMouseEnter={() => setHoveredNode(node)}
                onMouseLeave={() => setHoveredNode(null)}
              >
                {/* Outer halo */}
                <circle
                  r={isHovered ? 18 : 13}
                  fill={nodeFill}
                  fillOpacity={0.25}
                  stroke={nodeFill}
                  strokeWidth={isHovered ? 2 : 1}
                  style={{ transition: "all 0.2s" }}
                />
                {/* Core dot */}
                <circle r={6} fill={nodeFill} />

                {/* Node Label */}
                <text
                  x={node.x_pos > 0.5 ? 18 : -18}
                  y={4}
                  textAnchor={node.x_pos > 0.5 ? "start" : "end"}
                  fill={isHovered ? "var(--text-primary)" : "var(--text-secondary)"}
                  fontSize={11}
                  fontWeight={isHovered ? 700 : 500}
                >
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover inspector badge */}
        {(hoveredNode || hoveredEdge) && (
          <div
            style={{
              position: "absolute",
              bottom: "0.5rem",
              left: "50%",
              transform: "translateX(-50%)",
              background: "rgba(17, 24, 39, 0.95)",
              border: "1px solid var(--border-color)",
              borderRadius: "0.5rem",
              padding: "0.5rem 0.85rem",
              fontSize: "0.75rem",
              whiteSpace: "nowrap",
              boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
              zIndex: 10,
            }}
          >
            {hoveredNode && (
              <div>
                <strong>{hoveredNode.label}</strong> ({hoveredNode.node_id}) • Região:{" "}
                {hoveredNode.anatomical_region}
              </div>
            )}
            {hoveredEdge && (
              <div>
                Aresta:{" "}
                <strong>
                  {hoveredEdge.source} ↔ {hoveredEdge.target}
                </strong>{" "}
                ({hoveredEdge.kind}) • Peso: <strong>{hoveredEdge.weight}</strong> • Corr:{" "}
                <strong>{hoveredEdge.correlation}</strong>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Legend */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "1rem",
          flexWrap: "wrap",
          fontSize: "0.75rem",
          borderTop: "1px solid var(--border-color)",
          paddingTop: "0.75rem",
          marginTop: "0.5rem",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#10b981" }} />{" "}
          Anatômica
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#38bdf8" }} />{" "}
          Bilateral (Inter-membros)
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#8b5cf6" }} />{" "}
          Híbrida / Funcional
        </span>
      </div>
    </div>
  );
}
