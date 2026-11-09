"""Treino com semente fixa e validação cruzada Leave-One-Subject-Out (LOSO): Baseline vs. ST-GNN."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from ic_core.io import read_json, stable_hash, write_json
from ic_core.paths import ensure_dir
from pydantic import BaseModel, ConfigDict, Field

from fog_gnn.domain import CANONICAL_IMU_NODES, FOGEvent, SensorNodeSpec, Window
from fog_gnn.evaluate import METHODOLOGY_NOTE, FogEvaluationMetrics, evaluate_fog_predictions
from fog_gnn.graph import BodyGraph, build_body_graph
from fog_gnn.models.base import FogModel
from fog_gnn.models.baseline import TemporalBaselineModel
from fog_gnn.models.st_gnn import STGNNModel
from fog_gnn.windowing import assert_no_subject_leakage, leave_one_subject_out_splits


class WindowPredictionRecord(BaseModel):
    """Predição por janela temporal para visualização de série temporal no dashboard."""

    model_config = ConfigDict(frozen=True)

    window_id: str
    subject_id: str
    session_id: str
    start_seconds: float
    end_seconds: float
    true_label: int
    fog_overlap_ratio: float
    baseline_prob: float
    st_gnn_prob: float
    ankle_freeze_index: float


class SubjectFoldReport(BaseModel):
    """Métricas de uma dobra Leave-One-Subject-Out (1 sujeito isolado em teste)."""

    model_config = ConfigDict(frozen=True)

    fold_id: str
    held_out_subject_id: str
    train_subject_ids: list[str]
    train_windows_count: int
    test_windows_count: int
    test_fog_windows_count: int
    baseline_metrics: FogEvaluationMetrics
    st_gnn_metrics: FogEvaluationMetrics
    auprc_gain: float


class ExperimentResult(BaseModel):
    """Artefato completo e reprodutível de um experimento LOSO comparativo."""

    model_config = ConfigDict(frozen=True)

    experiment_id: str
    seed: int
    sampling_rate_hz: int
    window_size_seconds: float
    window_stride_seconds: float
    correlation_threshold: float
    parameters_hash: str
    created_at_utc: str
    subject_count: int
    total_windows: int
    total_fog_windows: int
    baseline_overall: FogEvaluationMetrics
    st_gnn_overall: FogEvaluationMetrics
    auprc_improvement_abs: float
    f1_improvement_abs: float
    per_subject_folds: list[SubjectFoldReport]
    window_predictions: list[WindowPredictionRecord]
    reference_body_graph: BodyGraph
    fog_episode_body_graph: BodyGraph
    methodology_note: str = Field(default=METHODOLOGY_NOTE)


def run_loso_experiment(
    windows: Sequence[Window],
    events_by_subject: dict[str, list[FOGEvent]] | None = None,
    node_specs: Sequence[SensorNodeSpec] = CANONICAL_IMU_NODES,
    seed: int = 42,
    sampling_rate_hz: int = 100,
    window_size_seconds: float = 2.56,
    window_stride_seconds: float = 1.28,
    correlation_threshold: float = 0.60,
    experiment_id: str | None = None,
    experiments_dir: Path | None = None,
    baseline_factory: Callable[[], FogModel] | None = None,
    gnn_factory: Callable[[], FogModel] | None = None,
) -> ExperimentResult:
    """Executa validação cruzada Leave-One-Subject-Out comparando Baseline 1D e ST-GNN."""
    splits = leave_one_subject_out_splits(windows)
    make_baseline = baseline_factory or (lambda: TemporalBaselineModel())
    make_gnn = gnn_factory or (lambda: STGNNModel())

    params_payload: dict[str, Any] = {
        "seed": seed,
        "sampling_rate_hz": sampling_rate_hz,
        "window_size_seconds": window_size_seconds,
        "window_stride_seconds": window_stride_seconds,
        "correlation_threshold": correlation_threshold,
        "subjects": sorted({w.subject_id for w in windows}),
        "total_windows": len(windows),
    }
    params_hash = stable_hash(params_payload)
    exp_id = experiment_id or f"exp_loso_s{seed}_{params_hash[:8]}"

    fold_reports: list[SubjectFoldReport] = []
    all_test_windows: list[Window] = []
    all_baseline_probs: list[np.ndarray] = []
    all_gnn_probs: list[np.ndarray] = []
    window_records: list[WindowPredictionRecord] = []

    for fold_idx, split in enumerate(splits):
        # Verificação explícita anti-vazamento em cada dobra
        assert_no_subject_leakage(split.train_windows, split.test_windows)

        # O grafo de passagem de mensagens da dobra é estimado APENAS nos dados de treino
        fold_graph = build_body_graph(
            windows=split.train_windows,
            node_specs=node_specs,
            correlation_threshold=correlation_threshold,
        )

        fold_seed = seed + fold_idx * 17
        baseline_model = make_baseline()
        gnn_model = make_gnn()

        baseline_model.fit(split.train_windows, fold_graph, seed=fold_seed)
        gnn_model.fit(split.train_windows, fold_graph, seed=fold_seed)

        base_probs = baseline_model.predict_proba(split.test_windows, fold_graph)
        gnn_probs = gnn_model.predict_proba(split.test_windows, fold_graph)

        subj_events = (
            events_by_subject.get(split.held_out_subject_id) if events_by_subject else None
        )
        base_metrics = evaluate_fog_predictions(
            windows=split.test_windows,
            y_prob=base_probs,
            window_stride_seconds=window_stride_seconds,
            events=subj_events,
        )
        gnn_metrics = evaluate_fog_predictions(
            windows=split.test_windows,
            y_prob=gnn_probs,
            window_stride_seconds=window_stride_seconds,
            events=subj_events,
        )

        fold_reports.append(
            SubjectFoldReport(
                fold_id=split.fold_id,
                held_out_subject_id=split.held_out_subject_id,
                train_subject_ids=list(split.train_subject_ids),
                train_windows_count=len(split.train_windows),
                test_windows_count=len(split.test_windows),
                test_fog_windows_count=sum(1 for w in split.test_windows if w.label == 1),
                baseline_metrics=base_metrics,
                st_gnn_metrics=gnn_metrics,
                auprc_gain=round(gnn_metrics.auprc - base_metrics.auprc, 4),
            )
        )

        all_test_windows.extend(split.test_windows)
        all_baseline_probs.append(base_probs)
        all_gnn_probs.append(gnn_probs)

        for win, b_p, g_p in zip(split.test_windows, base_probs, gnn_probs, strict=True):
            ankle_fi = float(win.node_features.get("ANKLE_L", [0.0, 0.0, 0.0])[2])
            window_records.append(
                WindowPredictionRecord(
                    window_id=win.window_id,
                    subject_id=win.subject_id,
                    session_id=win.session_id,
                    start_seconds=win.start_seconds,
                    end_seconds=win.end_seconds,
                    true_label=win.label,
                    fog_overlap_ratio=win.fog_overlap_ratio,
                    baseline_prob=round(float(b_p), 4),
                    st_gnn_prob=round(float(g_p), 4),
                    ankle_freeze_index=round(ankle_fi, 4),
                )
            )

    concat_base = np.concatenate(all_baseline_probs, axis=0)
    concat_gnn = np.concatenate(all_gnn_probs, axis=0)
    all_events: list[FOGEvent] | None = None
    if events_by_subject:
        all_events = [ev for ev_list in events_by_subject.values() for ev in ev_list]

    baseline_overall = evaluate_fog_predictions(
        windows=all_test_windows,
        y_prob=concat_base,
        window_stride_seconds=window_stride_seconds,
        events=all_events,
    )
    st_gnn_overall = evaluate_fog_predictions(
        windows=all_test_windows,
        y_prob=concat_gnn,
        window_stride_seconds=window_stride_seconds,
        events=all_events,
    )

    normal_windows = [w for w in windows if w.label == 0]
    fog_windows = [w for w in windows if w.label == 1]

    ref_graph = build_body_graph(
        windows=normal_windows or windows,
        node_specs=node_specs,
        correlation_threshold=correlation_threshold,
    )
    fog_graph = build_body_graph(
        windows=fog_windows or windows,
        node_specs=node_specs,
        correlation_threshold=correlation_threshold,
    )

    result = ExperimentResult(
        experiment_id=exp_id,
        seed=seed,
        sampling_rate_hz=sampling_rate_hz,
        window_size_seconds=window_size_seconds,
        window_stride_seconds=window_stride_seconds,
        correlation_threshold=correlation_threshold,
        parameters_hash=params_hash,
        created_at_utc=datetime.now(tz=UTC).isoformat(),
        subject_count=len(splits),
        total_windows=len(all_test_windows),
        total_fog_windows=sum(1 for w in all_test_windows if w.label == 1),
        baseline_overall=baseline_overall,
        st_gnn_overall=st_gnn_overall,
        auprc_improvement_abs=round(st_gnn_overall.auprc - baseline_overall.auprc, 4),
        f1_improvement_abs=round(st_gnn_overall.f1_score - baseline_overall.f1_score, 4),
        per_subject_folds=fold_reports,
        window_predictions=window_records,
        reference_body_graph=ref_graph,
        fog_episode_body_graph=fog_graph,
    )

    if experiments_dir is not None:
        out_dir = ensure_dir(experiments_dir)
        write_json(result.model_dump(), out_dir / f"{exp_id}.json")

    return result


def list_experiments(experiments_dir: Path) -> list[ExperimentResult]:
    """Lista experimentos persistidos em `experiments_dir`, do mais recente ao mais antigo."""
    if not experiments_dir.exists():
        return []
    results: list[ExperimentResult] = []
    for file_path in sorted(experiments_dir.glob("*.json")):
        results.append(ExperimentResult.model_validate(read_json(file_path)))
    results.sort(key=lambda r: r.created_at_utc, reverse=True)
    return results


def load_experiment(experiments_dir: Path, experiment_id: str) -> ExperimentResult:
    """Carrega um `ExperimentResult` específico do disco."""
    target = experiments_dir / f"{experiment_id}.json"
    if not target.exists():
        raise FileNotFoundError(f"Experimento '{experiment_id}' não encontrado em {target}")
    return ExperimentResult.model_validate(read_json(target))

