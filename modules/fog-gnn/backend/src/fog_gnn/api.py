"""API FastAPI do Módulo B (`fog-gnn`): `/subjects`, `/experiments`, `/metrics`, `/graph`."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from fog_gnn.config import FogGnnSettings
from fog_gnn.domain import Session, Subject
from fog_gnn.evaluate import METHODOLOGY_NOTE, FogEvaluationMetrics
from fog_gnn.graph import BodyGraph
from fog_gnn.ingest import load_sessions, load_subjects
from fog_gnn.models.pyg_st_gnn import is_pyg_installed
from fog_gnn.synthetic import (
    DEFAULT_SYNTHETIC_EXPERIMENT_ID,
    generate_synthetic_imu_artifacts,
)
from fog_gnn.train import (
    ExperimentResult,
    SubjectFoldReport,
    WindowPredictionRecord,
    list_experiments,
    load_experiment,
)


class SubjectSummaryItem(BaseModel):
    """Resumo anonimizado de um sujeito de Parkinson com suas sessões e episódios de FOG."""

    model_config = ConfigDict(frozen=True)

    subject: Subject
    sessions: list[Session]
    total_fog_events: int
    total_fog_duration_seconds: float


class SubjectsResponse(BaseModel):
    """Resposta do endpoint `/subjects`."""

    model_config = ConfigDict(frozen=True)

    count: int
    items: list[SubjectSummaryItem]
    privacy_note: str = Field(
        default="Todos os sujeitos são estritamente anonimizados (SUBJ_XXX). Zero PII."
    )


class MetricsResponse(BaseModel):
    """Resposta do endpoint `/metrics` com métricas globais, por sujeito (LOSO) e por janela."""

    model_config = ConfigDict(frozen=True)

    experiment_id: str
    seed: int
    window_size_seconds: float
    window_stride_seconds: float
    correlation_threshold: float
    baseline_overall: FogEvaluationMetrics
    st_gnn_overall: FogEvaluationMetrics
    auprc_improvement_abs: float
    f1_improvement_abs: float
    per_subject_folds: list[SubjectFoldReport]
    window_predictions: list[WindowPredictionRecord]
    methodology_note: str = Field(default=METHODOLOGY_NOTE)


class GraphResponse(BaseModel):
    """Resposta do endpoint `/graph` com topologia corporal em marcha normal vs. episódio de FOG."""

    model_config = ConfigDict(frozen=True)

    experiment_id: str
    regime: Literal["normal", "fog", "both"]
    normal_gait_graph: BodyGraph
    fog_episode_graph: BodyGraph


def ensure_module_b_data(
    settings: FogGnnSettings,
) -> tuple[list[Subject], list[Session], list[ExperimentResult]]:
    """Garante que o dataset IMU sintético anonimizado e o experimento LOSO padrão existam."""
    dataset_dir = settings.resolved_dataset_dir(create=True)
    experiments_dir = settings.resolved_experiments_dir(create=True)

    subjects_file = dataset_dir / "subjects.json"
    sessions_file = dataset_dir / "sessions.json"
    if not subjects_file.exists() or not sessions_file.exists():
        generate_synthetic_imu_artifacts(settings)

    subjects = load_subjects(dataset_dir)
    sessions = load_sessions(dataset_dir)
    experiments = list_experiments(experiments_dir)
    if not experiments:
        _, exp = generate_synthetic_imu_artifacts(settings)
        experiments = [exp]

    return subjects, sessions, experiments


def create_app(settings: FogGnnSettings | None = None) -> FastAPI:
    """Cria a aplicação FastAPI do Módulo B (`fog-gnn`)."""
    cfg = settings or FogGnnSettings()

    app = FastAPI(
        title="ic-research-lab | Módulo B — FOG Spatio-Temporal GNN API",
        version="0.1.0",
        description=(
            "API para predição de episódios de Freezing of Gait (FOG) em Parkinson "
            "com GNN espaço-temporal, split estrito por sujeito (LOSO) e baseline 1D."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def get_health() -> dict[str, Any]:
        subjects, sessions, experiments = ensure_module_b_data(cfg)
        pyg_ok = is_pyg_installed()
        return {
            "status": "ok",
            "module": "fog-gnn",
            "subjects_count": len(subjects),
            "sessions_count": len(sessions),
            "experiments_count": len(experiments),
            "default_experiment_id": experiments[0].experiment_id,
            "pyg_available": pyg_ok,
            "active_gnn_backend": "torch_geometric (PyG)" if pyg_ok else "vectorized_engine",
            "methodology_note": METHODOLOGY_NOTE,
        }

    @app.get("/model-info")
    def get_model_info() -> dict[str, Any]:
        pyg_ok = is_pyg_installed()
        return {
            "model_type": "Spatio-Temporal Graph Neural Network (ST-GNN)",
            "pyg_available": pyg_ok,
            "backend": "torch_geometric.nn.GCNConv + AdamW" if pyg_ok else "Vectorized Spatial GCN (NumPy/SciPy fallback)",
            "sensor_nodes_count": len(cfg.fog_sampling_rate_hz and [
                "left_ankle", "right_ankle", "left_thigh", "right_thigh", "trunk", "left_wrist", "right_wrist"
            ]),
            "validation_protocol": "Leave-One-Subject-Out (LOSO) Cross-Validation",
            "rare_event_criterion": "Weighted BCEWithLogitsLoss (class-balanced for freezing episodes)",
            "canonical_sensors": [
                "Tornozelo Esquerdo",
                "Tornozelo Direito",
                "Coxa Esquerda",
                "Coxa Direita",
                "Tronco (Lombar L5)",
                "Punho Esquerdo",
                "Punho Direito",
            ],
        }

    @app.get("/subjects", response_model=SubjectsResponse)
    def get_subjects() -> SubjectsResponse:
        subjects, sessions, _ = ensure_module_b_data(cfg)
        sessions_by_subj: dict[str, list[Session]] = {}
        for sess in sessions:
            sessions_by_subj.setdefault(sess.subject_id, []).append(sess)

        items: list[SubjectSummaryItem] = []
        for subj in subjects:
            subj_sessions = sessions_by_subj.get(subj.subject_id, [])
            ev_count = sum(len(s.events) for s in subj_sessions)
            ev_dur = round(
                sum(ev.duration_seconds for s in subj_sessions for ev in s.events),
                2,
            )
            items.append(
                SubjectSummaryItem(
                    subject=subj,
                    sessions=subj_sessions,
                    total_fog_events=ev_count,
                    total_fog_duration_seconds=ev_dur,
                )
            )
        return SubjectsResponse(count=len(items), items=items)

    @app.get("/experiments", response_model=list[ExperimentResult])
    def get_experiments() -> list[ExperimentResult]:
        _, _, experiments = ensure_module_b_data(cfg)
        return experiments

    @app.get("/metrics", response_model=MetricsResponse)
    def get_metrics(
        experiment_id: str | None = Query(default=None),
        subject_id: str | None = Query(default=None),
    ) -> MetricsResponse:
        _, _, experiments = ensure_module_b_data(cfg)
        experiments_dir = cfg.resolved_experiments_dir(create=True)

        selected_id = experiment_id or experiments[0].experiment_id
        try:
            exp = load_experiment(experiments_dir, selected_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        folds = exp.per_subject_folds
        preds = exp.window_predictions
        if subject_id:
            clean_subj = subject_id.strip().upper()
            folds = [f for f in folds if f.held_out_subject_id.upper() == clean_subj]
            preds = [p for p in preds if p.subject_id.upper() == clean_subj]

        return MetricsResponse(
            experiment_id=exp.experiment_id,
            seed=exp.seed,
            window_size_seconds=exp.window_size_seconds,
            window_stride_seconds=exp.window_stride_seconds,
            correlation_threshold=exp.correlation_threshold,
            baseline_overall=exp.baseline_overall,
            st_gnn_overall=exp.st_gnn_overall,
            auprc_improvement_abs=exp.auprc_improvement_abs,
            f1_improvement_abs=exp.f1_improvement_abs,
            per_subject_folds=folds,
            window_predictions=preds,
        )

    @app.get("/graph", response_model=GraphResponse)
    def get_graph(
        experiment_id: str | None = Query(default=None),
        regime: Literal["normal", "fog", "both"] = Query(default="both"),
    ) -> GraphResponse:
        _, _, experiments = ensure_module_b_data(cfg)
        experiments_dir = cfg.resolved_experiments_dir(create=True)

        selected_id = (
            experiment_id or experiments[0].experiment_id or DEFAULT_SYNTHETIC_EXPERIMENT_ID
        )
        try:
            exp = load_experiment(experiments_dir, selected_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return GraphResponse(
            experiment_id=exp.experiment_id,
            regime=regime,
            normal_gait_graph=exp.reference_body_graph,
            fog_episode_graph=exp.fog_episode_body_graph,
        )

    return app


app = create_app()
