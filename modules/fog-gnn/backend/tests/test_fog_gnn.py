"""Testes unitários e metodológicos do Módulo B (`fog-gnn`)."""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from ic_core.paths import find_repo_root
from pydantic import ValidationError

from fog_gnn.api import create_app
from fog_gnn.config import FogGnnSettings
from fog_gnn.domain import (
    CANONICAL_IMU_NODES,
    OPTIONAL_EEG_NODES,
    FOGEvent,
    Subject,
    Window,
)
from fog_gnn.evaluate import compute_auprc, evaluate_fog_predictions
from fog_gnn.graph import build_body_graph
from fog_gnn.ingest import (
    IMUSchemaError,
    load_session_dataframe,
    load_sessions,
    load_subjects,
    save_imu_dataset,
    validate_imu_dataframe,
)
from fog_gnn.models.base import FogModel
from fog_gnn.models.baseline import TemporalBaselineModel
from fog_gnn.models.pyg_st_gnn import PyGSTGNNModel
from fog_gnn.models.st_gnn import STGNNModel
from fog_gnn.synthetic import build_synthetic_subjects_and_sessions
from fog_gnn.train import load_experiment, run_loso_experiment
from fog_gnn.windowing import (
    DataLeakageError,
    assert_no_subject_leakage,
    leave_one_subject_out_splits,
    segment_session_windows,
)


def test_patient_privacy_and_domain_validation() -> None:
    subj = Subject(
        subject_id="SUBJ_001",
        age_group="65-69",
        hoehn_yahr_stage=3.0,
        disease_duration_years=8.0,
        medication_state="OFF",
    )
    assert subj.subject_id == "SUBJ_001"

    # Identificador nominal ou fora do padrão SUBJ_XXX deve falhar
    with pytest.raises(ValidationError, match="SUBJ_XXX"):
        Subject(
            subject_id="Paciente_Real_01",
            age_group="65-69",
            hoehn_yahr_stage=3.0,
            disease_duration_years=8.0,
        )

    with pytest.raises(ValidationError, match="offset_seconds"):
        FOGEvent(
            event_id="EV_1",
            session_id="SESS_001",
            subject_id="SUBJ_001",
            onset_seconds=15.0,
            offset_seconds=12.0,
        )


def test_ingest_schema_validation_and_multimodal_extensibility(tmp_path: Path) -> None:
    subjects, sessions, frames = build_synthetic_subjects_and_sessions(
        sampling_rate_hz=50,
        duration_seconds=12.0,
        seed=42,
    )
    save_imu_dataset(tmp_path / "imu", subjects, sessions, frames)

    loaded_subjects = load_subjects(tmp_path / "imu")
    loaded_sessions = load_sessions(tmp_path / "imu")
    df_s1 = load_session_dataframe(tmp_path / "imu", sessions[0].session_id)
    assert len(loaded_subjects) == 6
    assert len(loaded_sessions) == 6
    assert not df_s1.empty

    # Corromper subject_id com identificador não anonimizado deve disparar IMUSchemaError
    bad_df = df_s1.copy()
    bad_df["subject_id"] = "NOME_PACIENTE"
    with pytest.raises(IMUSchemaError, match="SUBJ_XXX"):
        validate_imu_dataframe(bad_df)

    # Acoplamento de modalidade secundária (EEG_CZ) sem reescrever o pipeline
    multimodal_nodes = (*CANONICAL_IMU_NODES, *OPTIONAL_EEG_NODES)
    mm_df = df_s1.copy()
    for ch in OPTIONAL_EEG_NODES[0].channels:
        mm_df[f"EEG_CZ__{ch}"] = 0.5
    validated_mm = validate_imu_dataframe(mm_df, node_specs=multimodal_nodes)
    mm_windows = segment_session_windows(
        validated_mm,
        sampling_rate_hz=50,
        window_size_seconds=2.0,
        window_stride_seconds=1.0,
        node_specs=multimodal_nodes,
    )
    assert len(mm_windows) > 0
    assert "EEG_CZ" in mm_windows[0].node_features
    mm_graph = build_body_graph(mm_windows, node_specs=multimodal_nodes)
    assert "EEG_CZ" in mm_graph.node_order
    assert any(e.kind == "corticospinal" for e in mm_graph.edges)


def test_subject_level_splitting_and_anti_leakage_guard() -> None:
    _, sessions, frames = build_synthetic_subjects_and_sessions(
        sampling_rate_hz=50,
        duration_seconds=16.0,
        seed=42,
    )
    windows: list[Window] = []
    for sess in sessions[:3]:
        windows.extend(
            segment_session_windows(
                frames[sess.session_id],
                sampling_rate_hz=50,
                window_size_seconds=2.0,
                window_stride_seconds=1.0,
            )
        )

    splits = leave_one_subject_out_splits(windows)
    assert len(splits) == 3
    for sp in splits:
        assert sp.held_out_subject_id not in sp.train_subject_ids
        assert_no_subject_leakage(sp.train_windows, sp.test_windows)

    # Forçar vazamento de uma janela do mesmo sujeito no treino e no teste deve falhar
    leaked_test = [splits[0].train_windows[0], *splits[0].test_windows]
    with pytest.raises(DataLeakageError, match="Vazamento metodológico"):
        assert_no_subject_leakage(splits[0].train_windows, leaked_test)


def test_loso_experiment_st_gnn_vs_baseline_and_metrics(tmp_path: Path) -> None:
    assert isinstance(TemporalBaselineModel(), FogModel)
    assert isinstance(STGNNModel(), FogModel)

    _, sessions, frames = build_synthetic_subjects_and_sessions(
        sampling_rate_hz=100,
        duration_seconds=48.0,
        seed=42,
    )
    all_windows: list[Window] = []
    events_by_subject = {}
    for sess in sessions:
        events_by_subject[sess.subject_id] = sess.events
        all_windows.extend(
            segment_session_windows(
                frames[sess.session_id],
                sampling_rate_hz=100,
                window_size_seconds=2.56,
                window_stride_seconds=1.28,
            )
        )

    exp = run_loso_experiment(
        windows=all_windows,
        events_by_subject=events_by_subject,
        seed=42,
        experiment_id="exp_test_loso",
        experiments_dir=tmp_path / "experiments",
    )

    loaded = load_experiment(tmp_path / "experiments", "exp_test_loso")
    assert loaded.experiment_id == exp.experiment_id
    assert loaded.subject_count == 6
    assert len(loaded.per_subject_folds) == 6
    assert loaded.st_gnn_overall.auprc >= loaded.baseline_overall.auprc
    assert loaded.st_gnn_overall.auprc > 0.70

    # Verifica cálculo isolado de AUPRC e avaliação
    y_true = np.array([0, 0, 1, 1, 0, 1])
    y_prob = np.array([0.1, 0.2, 0.85, 0.92, 0.3, 0.78])
    assert compute_auprc(y_true, y_prob) == 1.0
    ev_metrics = evaluate_fog_predictions(all_windows[:6], y_prob)
    assert 0.0 <= ev_metrics.sensitivity <= 1.0


def test_pyg_st_gnn_model_conformance() -> None:
    pyg_model = PyGSTGNNModel(force_fallback=True)
    assert isinstance(pyg_model, FogModel)
    assert pyg_model.uses_graph_topology is True
    assert "pyg_st_gnn" in pyg_model.name

    _, sessions, frames = build_synthetic_subjects_and_sessions(
        sampling_rate_hz=50,
        duration_seconds=12.0,
        seed=42,
    )
    windows = segment_session_windows(
        frames[sessions[0].session_id],
        sampling_rate_hz=50,
        window_size_seconds=2.0,
        window_stride_seconds=1.0,
    )
    graph = build_body_graph(windows)
    fit_res = pyg_model.fit(windows, graph, seed=42)
    assert "train_loss" in fit_res

    probs = pyg_model.predict_proba(windows, graph)
    assert len(probs) == len(windows)
    assert np.all(probs >= 0.0) and np.all(probs <= 1.0)


def test_fastapi_endpoints_on_synthetic_imu(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOG_DATASET_DIR", str(tmp_path / "imu_dataset"))
    monkeypatch.setenv("FOG_EXPERIMENTS_DIR", str(tmp_path / "experiments"))

    settings = FogGnnSettings()
    client = TestClient(create_app(settings))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["subjects_count"] == 6
    assert "pyg_available" in health.json()
    assert "active_gnn_backend" in health.json()

    model_info = client.get("/model-info")
    assert model_info.status_code == 200
    assert "pyg_available" in model_info.json()
    assert model_info.json()["validation_protocol"].startswith("Leave-One-Subject-Out")

    subj_resp = client.get("/subjects")
    assert subj_resp.status_code == 200
    assert subj_resp.json()["count"] == 6

    metrics_resp = client.get("/metrics?subject_id=SUBJ_001")
    assert metrics_resp.status_code == 200
    m_data = metrics_resp.json()
    assert len(m_data["per_subject_folds"]) == 1
    assert m_data["st_gnn_overall"]["auprc"] >= m_data["baseline_overall"]["auprc"]

    graph_resp = client.get("/graph")
    assert graph_resp.status_code == 200
    g_data = graph_resp.json()
    assert len(g_data["normal_gait_graph"]["nodes"]) == 7
    assert len(g_data["fog_episode_graph"]["edges"]) >= 6


def test_module_b_never_imports_module_a() -> None:
    repo_root = find_repo_root()
    mod_b_dir = repo_root / "modules" / "fog-gnn" / "backend"
    for py_file in mod_b_dir.rglob("*.py"):
        if ".venv" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("peptide_docking")
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("peptide_docking")
