"""Gerador determinístico de dataset sintético de IMU e experimento LOSO para o Módulo B."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from ic_core.logging import get_logger

from fog_gnn.config import FogGnnSettings
from fog_gnn.domain import (
    CANONICAL_IMU_NODES,
    FOGEvent,
    MedicationState,
    SensorNodeSpec,
    Session,
    Subject,
    TriggerTask,
    Window,
)
from fog_gnn.ingest import save_imu_dataset
from fog_gnn.train import ExperimentResult, run_loso_experiment
from fog_gnn.windowing import segment_session_windows

DEFAULT_SYNTHETIC_EXPERIMENT_ID: str = "exp_loso_baseline_vs_stgnn_seed42"

_SUBJECT_PROFILES: tuple[tuple[str, str, float, float, MedicationState, TriggerTask], ...] = (
    ("SUBJ_001", "65-69", 3.0, 8.5, "OFF", "turning"),
    ("SUBJ_002", "70-74", 3.5, 11.0, "OFF", "doorway"),
    ("SUBJ_003", "60-64", 2.5, 6.0, "ON", "dual_task"),
    ("SUBJ_004", "75-79", 4.0, 14.0, "OFF", "start_hesitation"),
    ("SUBJ_005", "65-69", 3.0, 9.0, "OFF", "turning"),
    ("SUBJ_006", "70-74", 2.5, 7.5, "ON", "straight_walk"),
)


def build_synthetic_subjects_and_sessions(
    sampling_rate_hz: int = 100,
    duration_seconds: float = 48.0,
    seed: int = 42,
    node_specs: tuple[SensorNodeSpec, ...] = CANONICAL_IMU_NODES,
) -> tuple[list[Subject], list[Session], dict[str, pd.DataFrame]]:
    """Gera 6 sujeitos anonimizados (`SUBJ_001`..`SUBJ_006`) com séries IMU e FOG."""
    rng = np.random.default_rng(seed)
    n_samples = int(round(duration_seconds * sampling_rate_hz))
    t = np.arange(n_samples, dtype=float) / float(sampling_rate_hz)

    subjects: list[Subject] = []
    sessions: list[Session] = []
    frames: dict[str, pd.DataFrame] = {}

    for idx, (subj_id, age_grp, hy, dur_yr, med, task) in enumerate(_SUBJECT_PROFILES, start=1):
        subject = Subject(
            subject_id=subj_id,
            age_group=age_grp,
            hoehn_yahr_stage=hy,
            disease_duration_years=dur_yr,
            medication_state=med,
        )
        subjects.append(subject)

        session_id = f"SESS_{idx:03d}"
        # Dois episódios de FOG por sessão (~18% do tempo total -> classe minoritária realista)
        onset1 = round(10.0 + (idx % 3) * 1.2, 2)
        offset1 = round(onset1 + 4.2, 2)
        onset2 = round(29.0 + (idx % 2) * 1.5, 2)
        offset2 = round(onset2 + 4.5, 2)

        events = [
            FOGEvent(
                event_id=f"{session_id}_EV01",
                session_id=session_id,
                subject_id=subj_id,
                onset_seconds=onset1,
                offset_seconds=offset1,
                trigger_task=task,
            ),
            FOGEvent(
                event_id=f"{session_id}_EV02",
                session_id=session_id,
                subject_id=subj_id,
                onset_seconds=onset2,
                offset_seconds=offset2,
                trigger_task="turning",
            ),
        ]

        session = Session(
            session_id=session_id,
            subject_id=subj_id,
            sampling_rate_hz=sampling_rate_hz,
            duration_seconds=duration_seconds,
            modalities=["imu"],
            events=events,
        )
        sessions.append(session)

        label_fog = np.zeros(n_samples, dtype=int)
        for ev in events:
            mask = (t >= ev.onset_seconds) & (t <= ev.offset_seconds)
            label_fog[mask] = 1

        # Trecho confusor não-FOG (manobra rápida simétrica global entre 20s e 24s)
        confounder_mask = (t >= 20.0) & (t <= 24.0)
        fog_mask = label_fog == 1

        columns: dict[str, np.ndarray | list[str]] = {
            "timestamp_s": np.round(t, 4),
            "subject_id": [subj_id] * n_samples,
            "session_id": [session_id] * n_samples,
            "label_fog": label_fog,
        }

        loco_freq = 1.45 + 0.05 * (idx % 3)
        freeze_freq = 5.4 + 0.15 * (idx % 3)

        for node in node_specs:
            is_left = node.node_id.endswith("_L")
            is_right = node.node_id.endswith("_R")
            is_distal = node.node_id.startswith(("ANKLE", "SHANK"))

            # Cadência locomotora base (~1.5 Hz)
            base_wave = 1.6 * np.sin(2.0 * np.pi * loco_freq * t)
            # Tremor de congelamento (5.4 Hz)
            freeze_wave = np.sin(2.0 * np.pi * freeze_freq * t)

            for ch_idx, ch in enumerate(node.channels):
                signal = (0.8 + 0.1 * ch_idx) * base_wave.copy()

                # Na manobra não-FOG confusora, TODOS os sensores recebem a mesma perturbação
                # simétrica (logo, a diferença relacional entre membros permanece baixa)
                signal[confounder_mask] += 1.45 * freeze_wave[confounder_mask]

                # No episódio real de FOG, ocorre desacoplamento assimétrico inter-membros
                # e forte energia na banda 3-8 Hz nos membros inferiores distais
                if is_distal and is_left:
                    signal[fog_mask] = 0.25 * base_wave[fog_mask] + 3.10 * freeze_wave[fog_mask]
                elif is_distal and is_right:
                    signal[fog_mask] = 0.20 * base_wave[fog_mask] + 0.45 * freeze_wave[fog_mask]
                elif is_left:
                    signal[fog_mask] = 0.35 * base_wave[fog_mask] + 1.80 * freeze_wave[fog_mask]
                else:
                    signal[fog_mask] = 0.30 * base_wave[fog_mask] + 0.30 * freeze_wave[fog_mask]

                noise = rng.normal(0.0, 0.12, size=n_samples)
                columns[f"{node.node_id}__{ch}"] = np.round(signal + noise, 5)

        frames[session_id] = pd.DataFrame(columns)

    return subjects, sessions, frames


def generate_synthetic_imu_artifacts(
    settings: FogGnnSettings | None = None,
) -> tuple[Path, ExperimentResult]:
    """Gera e salva o dataset IMU sintético e executa o experimento LOSO padrão."""
    cfg = settings or FogGnnSettings()
    logger = get_logger("fog_gnn.synthetic", cfg)

    dataset_dir = cfg.resolved_dataset_dir(create=True)
    experiments_dir = cfg.resolved_experiments_dir(create=True)

    subjects, sessions, frames = build_synthetic_subjects_and_sessions(
        sampling_rate_hz=cfg.fog_sampling_rate_hz,
        seed=cfg.ic_random_seed,
    )
    save_imu_dataset(
        dataset_dir=dataset_dir,
        subjects=subjects,
        sessions=sessions,
        session_frames=frames,
    )

    all_windows: list[Window] = []
    events_by_subject: dict[str, list[FOGEvent]] = {}
    for sess in sessions:
        events_by_subject.setdefault(sess.subject_id, []).extend(sess.events)
        win_list = segment_session_windows(
            df=frames[sess.session_id],
            sampling_rate_hz=cfg.fog_sampling_rate_hz,
            window_size_seconds=cfg.fog_window_size_seconds,
            window_stride_seconds=cfg.fog_window_stride_seconds,
        )
        all_windows.extend(win_list)

    experiment = run_loso_experiment(
        windows=all_windows,
        events_by_subject=events_by_subject,
        seed=cfg.ic_random_seed,
        sampling_rate_hz=cfg.fog_sampling_rate_hz,
        window_size_seconds=cfg.fog_window_size_seconds,
        window_stride_seconds=cfg.fog_window_stride_seconds,
        correlation_threshold=cfg.fog_correlation_threshold,
        experiment_id=DEFAULT_SYNTHETIC_EXPERIMENT_ID,
        experiments_dir=experiments_dir,
    )

    logger.info(
        f"Dataset IMU sintético ({len(subjects)} sujeitos, {len(all_windows)} janelas) "
        f"e experimento LOSO {experiment.experiment_id} gerados: "
        f"AUPRC Baseline={experiment.baseline_overall.auprc:.3f} vs "
        f"ST-GNN={experiment.st_gnn_overall.auprc:.3f}."
    )
    return dataset_dir, experiment
