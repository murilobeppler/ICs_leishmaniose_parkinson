"""Métricas clínicas para eventos raros de FOG: AUPRC, sensibilidade, FP/h e latência."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from fog_gnn.domain import FOGEvent, Window

SECONDS_PER_HOUR: float = 3600.0
DEFAULT_DECISION_THRESHOLD: float = 0.50

METHODOLOGY_NOTE: str = (
    "Episódios de Freezing of Gait (FOG) são eventos minoritários. Acurácia global não é "
    "reportada como métrica primária por ser inflada pela classe negativa. A avaliação "
    "baseia-se em AUPRC, Sensibilidade (Recall), Falsos Positivos por Hora (FP/h) e "
    "Latência de Detecção (s) sob validação Leave-One-Subject-Out (LOSO)."
)


class FogEvaluationMetrics(BaseModel):
    """Métricas de avaliação sensíveis a desbalanceamento e orientadas ao uso clínico."""

    model_config = ConfigDict(frozen=True)

    auprc: float = Field(..., ge=0.0, le=1.0, description="Área sob a curva Precisão-Revocação")
    f1_score: float = Field(..., ge=0.0, le=1.0)
    sensitivity: float = Field(..., ge=0.0, le=1.0, description="Recall / Sensibilidade de FOG")
    specificity: float = Field(..., ge=0.0, le=1.0)
    precision: float = Field(..., ge=0.0, le=1.0)
    false_positives_per_hour: float = Field(
        ..., ge=0.0, description="Taxa de alarmes falsos (FP/h)"
    )
    mean_detection_latency_seconds: float = Field(
        ...,
        ge=0.0,
        description="Atraso médio (s) desde o início do episódio até a primeira janela detectada",
    )
    event_detection_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fração de episódios de FOG com ao menos uma janela detectada",
    )
    threshold: float = Field(default=DEFAULT_DECISION_THRESHOLD)
    total_windows: int = Field(..., ge=0)
    positive_windows: int = Field(..., ge=0)
    methodology_note: str = Field(default=METHODOLOGY_NOTE)


def compute_auprc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calcula a Área sob a Curva Precisão-Revocação (Average Precision) para classe rara."""
    y_bin = np.asarray(y_true, dtype=int)
    scores = np.asarray(y_prob, dtype=float)
    total_pos = int(np.sum(y_bin == 1))
    if total_pos == 0 or len(y_bin) == 0:
        return 0.0

    desc_idx = np.argsort(-scores, kind="mergesort")
    y_sorted = y_bin[desc_idx]

    tp_cum = np.cumsum(y_sorted == 1).astype(float)
    fp_cum = np.cumsum(y_sorted == 0).astype(float)

    precisions = tp_cum / np.maximum(tp_cum + fp_cum, 1.0)
    recalls = tp_cum / float(total_pos)

    # Integração exata por degraus de revocação (Average Precision)
    recall_prev = np.concatenate(([0.0], recalls[:-1]))
    auprc = float(np.sum((recalls - recall_prev) * precisions))
    return round(max(0.0, min(1.0, auprc)), 4)


def _extract_contiguous_episodes(windows: Sequence[Window]) -> list[tuple[float, float]]:
    """Reconstrói intervalos contíguos `(onset_s, offset_s)` a partir das janelas positivas."""
    episodes: list[tuple[float, float]] = []
    current_start: float | None = None
    current_end: float = 0.0

    for win in sorted(windows, key=lambda w: (w.session_id, w.start_seconds)):
        if win.label == 1:
            if current_start is None:
                current_start = win.start_seconds
                current_end = win.end_seconds
            else:
                current_end = max(current_end, win.end_seconds)
        elif current_start is not None:
            episodes.append((current_start, current_end))
            current_start = None

    if current_start is not None:
        episodes.append((current_start, current_end))
    return episodes


def compute_detection_latency_seconds(
    windows: Sequence[Window],
    y_pred: np.ndarray,
    events: Sequence[FOGEvent] | None = None,
) -> tuple[float, float]:
    """Calcula a latência média de detecção (s) e a taxa de episódios de FOG detectados."""
    preds = np.asarray(y_pred, dtype=int)
    if events:
        intervals = [(ev.onset_seconds, ev.offset_seconds) for ev in events]
    else:
        intervals = _extract_contiguous_episodes(windows)

    if not intervals:
        return 0.0, 1.0

    latencies: list[float] = []
    detected_count = 0

    for onset_s, offset_s in intervals:
        episode_detect_times: list[float] = []
        for win, pred in zip(windows, preds, strict=True):
            overlaps = win.end_seconds >= onset_s and win.start_seconds <= offset_s
            if overlaps and pred == 1:
                latency = max(0.0, win.start_seconds - onset_s)
                episode_detect_times.append(latency)

        if episode_detect_times:
            detected_count += 1
            latencies.append(min(episode_detect_times))

    detection_rate = round(detected_count / len(intervals), 4)
    mean_latency = (
        round(float(np.mean(latencies)), 4)
        if latencies
        else round(float(np.mean([end - start for start, end in intervals])), 4)
    )
    return mean_latency, detection_rate


def evaluate_fog_predictions(
    windows: Sequence[Window],
    y_prob: np.ndarray,
    threshold: float = DEFAULT_DECISION_THRESHOLD,
    window_stride_seconds: float = 1.28,
    events: Sequence[FOGEvent] | None = None,
) -> FogEvaluationMetrics:
    """Avalia probabilidades preditas de FOG com métricas orientadas a evento raro."""
    y_true = np.asarray([w.label for w in windows], dtype=int)
    probs = np.asarray(y_prob, dtype=float)
    y_pred = (probs >= threshold).astype(int)

    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))

    sensitivity = tp / float(tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / float(tn + fp) if (tn + fp) > 0 else 0.0
    precision = tp / float(tp + fp) if (tp + fp) > 0 else 0.0
    f1 = (
        2.0 * precision * sensitivity / (precision + sensitivity)
        if (precision + sensitivity) > 0.0
        else 0.0
    )

    auprc = compute_auprc(y_true, probs)

    # Falsos positivos por hora (FP/h) sobre o tempo monitorado
    total_hours = max(len(windows) * window_stride_seconds / SECONDS_PER_HOUR, 1e-6)
    fp_per_hour = round(fp / total_hours, 2)

    mean_latency, event_rate = compute_detection_latency_seconds(
        windows=windows,
        y_pred=y_pred,
        events=events,
    )

    return FogEvaluationMetrics(
        auprc=auprc,
        f1_score=round(f1, 4),
        sensitivity=round(sensitivity, 4),
        specificity=round(specificity, 4),
        precision=round(precision, 4),
        false_positives_per_hour=fp_per_hour,
        mean_detection_latency_seconds=mean_latency,
        event_detection_rate=event_rate,
        threshold=threshold,
        total_windows=len(windows),
        positive_windows=int(np.sum(y_true == 1)),
    )
