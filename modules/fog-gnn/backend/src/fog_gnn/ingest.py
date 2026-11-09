"""Ingestão e validação explícita de schema para gravações multissensoriais de IMU."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from ic_core.io import read_json, read_tabular, write_json, write_tabular
from ic_core.paths import ensure_dir

from fog_gnn.domain import (
    ANON_SUBJECT_PATTERN,
    CANONICAL_IMU_NODES,
    SensorNodeSpec,
    Session,
    Subject,
)

REQUIRED_META_COLUMNS: tuple[str, ...] = (
    "timestamp_s",
    "subject_id",
    "session_id",
    "label_fog",
)


class IMUSchemaError(ValueError):
    """Erro lançado quando uma tabela de sinais IMU viola o contrato de schema ou privacidade."""


def expected_sensor_columns(
    node_specs: Sequence[SensorNodeSpec] = CANONICAL_IMU_NODES,
) -> list[str]:
    """Retorna os nomes de colunas esperados no formato `<NODE_ID>__<CHANNEL>`."""
    cols: list[str] = []
    for node in node_specs:
        for ch in node.channels:
            cols.append(f"{node.node_id}__{ch}")
    return cols


def validate_imu_dataframe(
    df: pd.DataFrame,
    node_specs: Sequence[SensorNodeSpec] = CANONICAL_IMU_NODES,
) -> pd.DataFrame:
    """Valida explicitamente o schema, integridade numérica e anonimização de um DataFrame IMU."""
    if df.empty:
        raise IMUSchemaError("DataFrame de gravação IMU está vazio.")

    missing_meta = [c for c in REQUIRED_META_COLUMNS if c not in df.columns]
    if missing_meta:
        raise IMUSchemaError(f"Colunas de metadados obrigatórias ausentes: {missing_meta}")

    sensor_cols = expected_sensor_columns(node_specs)
    missing_sensors = [c for c in sensor_cols if c not in df.columns]
    if missing_sensors:
        raise IMUSchemaError(
            f"Colunas de canais de sensores ausentes ({len(missing_sensors)}): "
            f"{missing_sensors[:5]}"
        )

    # Validação de privacidade: nenhum identificador fora do formato SUBJ_XXX
    unique_subjects = df["subject_id"].astype(str).unique().tolist()
    for subj_id in unique_subjects:
        if not ANON_SUBJECT_PATTERN.match(subj_id):
            raise IMUSchemaError(
                "Violação de schema/privacidade: subject_id fora do padrão anonimizado SUBJ_XXX."
            )

    # Validação de timestamps monotônicos por sessão
    for _, group in df.groupby("session_id", sort=False):
        diffs = np.diff(group["timestamp_s"].to_numpy(dtype=float))
        if np.any(diffs <= 0.0):
            raise IMUSchemaError("Coluna 'timestamp_s' deve ser estritamente crescente por sessão.")

    # Validação de ausência de NaN / Inf nos canais numéricos
    numeric_matrix = df[sensor_cols].to_numpy(dtype=float)
    if not np.all(np.isfinite(numeric_matrix)):
        raise IMUSchemaError("Canais de sensores contêm valores NaN ou Inf.")

    # Validação de labels binários {0, 1}
    unique_labels = set(df["label_fog"].astype(int).unique().tolist())
    if not unique_labels.issubset({0, 1}):
        raise IMUSchemaError(
            f"Coluna 'label_fog' deve conter apenas {{0, 1}}, encontrado: {sorted(unique_labels)}"
        )

    return df


def save_imu_dataset(
    dataset_dir: Path,
    subjects: Sequence[Subject],
    sessions: Sequence[Session],
    session_frames: dict[str, pd.DataFrame],
    node_specs: Sequence[SensorNodeSpec] = CANONICAL_IMU_NODES,
) -> Path:
    """Persiste metadados anonimizados e séries temporais validadas por sessão."""
    root = ensure_dir(dataset_dir)
    sessions_dir = ensure_dir(root / "sessions")

    write_json([s.model_dump() for s in subjects], root / "subjects.json")
    write_json([s.model_dump() for s in sessions], root / "sessions.json")
    write_json([n.model_dump() for n in node_specs], root / "nodes.json")

    for session in sessions:
        frame = session_frames.get(session.session_id)
        if frame is None:
            raise IMUSchemaError(f"Série temporal ausente para a sessão {session.session_id}.")
        validate_imu_dataframe(frame, node_specs=node_specs)
        write_tabular(frame, sessions_dir / f"{session.session_id}.parquet")

    return root


def load_subjects(dataset_dir: Path) -> list[Subject]:
    """Carrega a lista validada de sujeitos anonimizados."""
    raw = read_json(dataset_dir / "subjects.json")
    return [Subject.model_validate(item) for item in raw]


def load_sessions(dataset_dir: Path) -> list[Session]:
    """Carrega a lista validada de sessões de coleta e seus eventos de FOG."""
    raw = read_json(dataset_dir / "sessions.json")
    return [Session.model_validate(item) for item in raw]


def load_node_specs(dataset_dir: Path) -> list[SensorNodeSpec]:
    """Carrega a configuração de nós corporais/modalidades do dataset."""
    nodes_path = dataset_dir / "nodes.json"
    if not nodes_path.exists():
        return list(CANONICAL_IMU_NODES)
    raw = read_json(nodes_path)
    return [SensorNodeSpec.model_validate(item) for item in raw]


def load_session_dataframe(
    dataset_dir: Path,
    session_id: str,
    node_specs: Sequence[SensorNodeSpec] | None = None,
) -> pd.DataFrame:
    """Lê e valida a tabela de sinais de uma sessão específica."""
    specs = node_specs if node_specs is not None else load_node_specs(dataset_dir)
    parquet_path = dataset_dir / "sessions" / f"{session_id}.parquet"
    df = read_tabular(parquet_path)
    return validate_imu_dataframe(df, node_specs=specs)

