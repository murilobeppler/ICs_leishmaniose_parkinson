"use client";

import React from "react";
import { SubjectSummaryItem } from "../types";
import { User, Activity, ShieldCheck, HeartPulse } from "lucide-react";

interface SubjectOverviewListProps {
  subjects: SubjectSummaryItem[];
  selectedSubjectId: string;
  onSelectSubject: (subjectId: string) => void;
}

export function SubjectOverviewList({
  subjects,
  selectedSubjectId,
  onSelectSubject,
}: SubjectOverviewListProps) {
  return (
    <div style={{ marginBottom: "1.5rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "0.75rem",
        }}
      >
        <h3
          style={{
            fontSize: "1rem",
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            gap: "0.4rem",
          }}
        >
          <User size={16} color="var(--accent-purple)" />
          Coorte Anonimizada de Parkinson ({subjects.length} Sujeitos LOSO)
        </h3>
        <span
          style={{
            fontSize: "0.75rem",
            color: "var(--accent-emerald)",
            display: "flex",
            alignItems: "center",
            gap: "0.25rem",
          }}
        >
          <ShieldCheck size={14} /> Zero PII • Padrão SUBJ_XXX
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "0.75rem",
        }}
      >
        {subjects.map((item) => {
          const isSelected = item.subject.subject_id === selectedSubjectId;

          return (
            <button
              key={item.subject.subject_id}
              onClick={() => onSelectSubject(item.subject.subject_id)}
              style={{
                background: isSelected ? "rgba(139, 92, 246, 0.18)" : "var(--bg-surface-elevated)",
                border: isSelected
                  ? "2px solid var(--accent-purple)"
                  : "1px solid var(--border-color)",
                borderRadius: "0.5rem",
                padding: "0.85rem",
                textAlign: "left",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "0.3rem",
                }}
              >
                <span
                  className="mono"
                  style={{
                    fontWeight: 700,
                    color: isSelected ? "var(--accent-purple)" : "var(--text-primary)",
                  }}
                >
                  {item.subject.subject_id}
                </span>
                <span
                  className={`badge ${item.subject.medication_state === "ON" ? "badge-emerald" : "badge-amber"}`}
                  style={{ fontSize: "0.65rem" }}
                >
                  {item.subject.medication_state}
                </span>
              </div>

              <div
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-secondary)",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.15rem",
                }}
              >
                <div>
                  H&Y: <strong>Estágio {item.subject.hoehn_yahr_stage}</strong>
                </div>
                <div>
                  Idade: <strong>{item.subject.age_group} anos</strong>
                </div>
                <div
                  style={{
                    marginTop: "0.25rem",
                    color: item.total_fog_events > 0 ? "var(--accent-rose)" : "var(--text-muted)",
                  }}
                >
                  Episódios FOG: <strong>{item.total_fog_events}</strong> (
                  {item.total_fog_duration_seconds}s)
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
