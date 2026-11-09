"""Janelamento deslizante, extração espectral de features e split estrito por sujeito."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from fog_gnn.domain import (
    CANONICAL_IMU_NODES,
    NODE_FEATURE_NAMES,
    SensorNodeSpec,
    Window,
)

LOCOMOTOR_BAND_HZ: tuple[float, float] = (0.5, 3.0)
FREEZE_BAND_HZ: tuple[float, float] = (3.0, 8.0)
DEFAULT_MIN_FOG_OVERLAP: float = 0.25
EPSILON: float = 1e-6


class DataLeakageError(RuntimeError):
    """Erro crítico lançado quando janelas do mesmo paciente aparecem em treino e teste."""


@dataclass(frozen=True)
class SubjectSplit:
    """Partição de validação cruzada agrupada estritamente por sujeito."""

    fold_id: str
    held_out_subject_id: str
    train_subject_ids: tuple[str, ...]
    test_subject_ids: tuple[str, ...]
    train_windows: list[Window]
    test_windows: list[Window]


def compute_node_window_features(
    node_signal: np.ndarray,
    sampling_rate_hz: int,
) -> list[float]:
    """Extrai o vetor de 6 features biomecânicas/espectrais de um nó em uma janela.

    Para um nó IMU com 6 canais (`acc_x..z`, `gyro_x..z`), calcula:
    1. Potência na banda locomotora (0.5 - 3.0 Hz)
    2. Potência na banda de congelamento / freeze (3.0 - 8.0 Hz)
    3. Freeze Index (razão freeze / locomotora — Moore et al.)
    4. RMS da aceleração resultante
    5. RMS da velocidade angular resultante
    6. Energia de jerk (derivada temporal da aceleração)
    """
    n_samples, n_channels = node_signal.shape
    if n_channels >= 6:
        acc = node_signal[:, :3]
        gyro = node_signal[:, 3:6]
    else:
        # Suporte multimodal (ex.: EEG acoplado com menos canais)
        acc = node_signal
        gyro = node_signal

    acc_mag = np.linalg.norm(acc, axis=1)
    acc_centered = acc_mag - float(np.mean(acc_mag))

    freqs = np.fft.rfftfreq(n_samples, d=1.0 / float(sampling_rate_hz))
    psd = (np.abs(np.fft.rfft(acc_centered)) ** 2) / float(max(1, n_samples))

    loco_mask = (freqs >= LOCOMOTOR_BAND_HZ[0]) & (freqs < LOCOMOTOR_BAND_HZ[1])
    freeze_mask = (freqs >= FREEZE_BAND_HZ[0]) & (freqs <= FREEZE_BAND_HZ[1])

    loco_power = float(np.sum(psd[loco_mask])) if np.any(loco_mask) else 0.0
    freeze_power = float(np.sum(psd[freeze_mask])) if np.any(freeze_mask) else 0.0
    freeze_index = freeze_power / (loco_power + EPSILON)

    acc_rms = float(np.sqrt(np.mean(acc**2)))
    gyro_rms = float(np.sqrt(np.mean(gyro**2)))
    jerk = np.diff(acc, axis=0) * float(sampling_rate_hz)
    jerk_energy = float(np.mean(jerk**2)) if jerk.size > 0 else 0.0

    features = [
        round(float(np.log1p(loco_power)), 5),
        round(float(np.log1p(freeze_power)), 5),
        round(float(min(50.0, freeze_index)), 5),
        round(acc_rms, 5),
        round(gyro_rms, 5),
        round(float(np.log1p(jerk_energy)), 5),
    ]
    assert len(features) == len(NODE_FEATURE_NAMES)
    return features


def segment_session_windows(
    df: pd.DataFrame,
    sampling_rate_hz: int = 100,
    window_size_seconds: float = 2.56,
    window_stride_seconds: float = 1.28,
    min_fog_overlap: float = DEFAULT_MIN_FOG_OVERLAP,
    node_specs: Sequence[SensorNodeSpec] = CANONICAL_IMU_NODES,
) -> list[Window]:
    """Segmenta uma sessão contínua em janelas deslizantes com features por nó corporal."""
    win_samples = max(8, int(round(window_size_seconds * sampling_rate_hz)))
    stride_samples = max(1, int(round(window_stride_seconds * sampling_rate_hz)))

    n_rows = len(df)
    if n_rows < win_samples:
        return []

    timestamps = df["timestamp_s"].to_numpy(dtype=float)
    labels = df["label_fog"].to_numpy(dtype=int)
    subject_id = str(df["subject_id"].iloc[0])
    session_id = str(df["session_id"].iloc[0])

    node_matrices: dict[str, np.ndarray] = {}
    for node in node_specs:
        cols = [f"{node.node_id}__{ch}" for ch in node.channels]
        node_matrices[node.node_id] = df[cols].to_numpy(dtype=float)

    windows: list[Window] = []
    win_idx = 1
    for start_idx in range(0, n_rows - win_samples + 1, stride_samples):
        end_idx = start_idx + win_samples
        overlap_ratio = float(np.mean(labels[start_idx:end_idx]))
        win_label: Literal[0, 1] = 1 if overlap_ratio >= min_fog_overlap else 0

        node_feats: dict[str, list[float]] = {}
        for node in node_specs:
            segment = node_matrices[node.node_id][start_idx:end_idx]
            node_feats[node.node_id] = compute_node_window_features(
                node_signal=segment,
                sampling_rate_hz=sampling_rate_hz,
            )

        windows.append(
            Window(
                window_id=f"{session_id}_W{win_idx:04d}",
                subject_id=subject_id,
                session_id=session_id,
                start_seconds=round(float(timestamps[start_idx]), 3),
                end_seconds=round(float(timestamps[end_idx - 1]), 3),
                label=win_label,
                fog_overlap_ratio=round(overlap_ratio, 4),
                node_features=node_feats,
            )
        )
        win_idx += 1

    return windows


def assert_no_subject_leakage(
    train_windows: Sequence[Window],
    test_windows: Sequence[Window],
) -> None:
    """Garante que nenhum sujeito tenha janelas simultaneamente no treino e no teste."""
    train_subjects = {w.subject_id for w in train_windows}
    test_subjects = {w.subject_id for w in test_windows}
    shared = train_subjects & test_subjects
    if shared:
        raise DataLeakageError(
            f"Vazamento metodológico detectado! Sujeito(s) presentes tanto em treino "
            f"quanto em teste: {sorted(shared)}. O split deve ser estritamente por sujeito."
        )


def split_by_subject(
    windows: Sequence[Window],
    test_subject_ids: Sequence[str],
) -> SubjectSplit:
    """Divide uma coleção de janelas mantendo sujeitos de teste 100% isolados do treino."""
    test_set = {s.strip() for s in test_subject_ids}
    if not test_set:
        raise ValueError("test_subject_ids não pode ser vazio.")

    train_wins = [w for w in windows if w.subject_id not in test_set]
    test_wins = [w for w in windows if w.subject_id in test_set]

    if not train_wins or not test_wins:
        raise ValueError("Split resultou em conjunto de treino ou de teste vazio.")

    assert_no_subject_leakage(train_wins, test_wins)
    train_subjs = tuple(sorted({w.subject_id for w in train_wins}))
    test_subjs = tuple(sorted({w.subject_id for w in test_wins}))
    held_out = test_subjs[0] if len(test_subjs) == 1 else "_".join(test_subjs)

    return SubjectSplit(
        fold_id=f"loso_{held_out}",
        held_out_subject_id=held_out,
        train_subject_ids=train_subjs,
        test_subject_ids=test_subjs,
        train_windows=train_wins,
        test_windows=test_wins,
    )


def leave_one_subject_out_splits(windows: Sequence[Window]) -> list[SubjectSplit]:
    """Gera todas as dobras Leave-One-Subject-Out (LOSO) sobre a lista de janelas."""
    all_subjects = sorted({w.subject_id for w in windows})
    if len(all_subjects) < 2:
        raise ValueError(
            f"LOSO requer pelo menos 2 sujeitos distintos, encontrado(s): {all_subjects}"
        )
    return [split_by_subject(windows, [subj_id]) for subj_id in all_subjects]

