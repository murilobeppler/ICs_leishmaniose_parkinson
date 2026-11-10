"""Entidades de domínio do Módulo B (`fog-gnn`): Subject, Session, Window, FOGEvent e nós."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ANON_SUBJECT_PATTERN: re.Pattern[str] = re.compile(r"^SUBJ_\d{3,}$")

ModalityType = Literal["imu", "eeg", "emg"]
MedicationState = Literal["ON", "OFF"]
TriggerTask = Literal[
    "turning",
    "doorway",
    "dual_task",
    "start_hesitation",
    "straight_walk",
]

IMU_CHANNELS: tuple[str, ...] = ("acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z")
NODE_FEATURE_NAMES: tuple[str, ...] = (
    "locomotor_band_power",
    "freeze_band_power",
    "freeze_index",
    "acc_rms",
    "gyro_rms",
    "jerk_energy",
)


class SensorNodeSpec(BaseModel):
    """Especificação de um nó corporal (sensor IMU ou modalidade acoplada)."""

    model_config = ConfigDict(frozen=True)

    node_id: str = Field(..., min_length=2)
    label: str = Field(..., min_length=2)
    anatomical_region: str = Field(..., min_length=2)
    modality: ModalityType = Field(default="imu")
    channels: tuple[str, ...] = Field(default=IMU_CHANNELS)
    x_pos: float = Field(..., ge=0.0, le=1.0, description="Posição horizontal normalizada no grafo")
    y_pos: float = Field(..., ge=0.0, le=1.0, description="Posição vertical normalizada no grafo")


CANONICAL_IMU_NODES: tuple[SensorNodeSpec, ...] = (
    SensorNodeSpec(
        node_id="LOWER_BACK",
        label="Lombar (L4-L5)",
        anatomical_region="tronco_inferior",
        modality="imu",
        x_pos=0.50,
        y_pos=0.32,
    ),
    SensorNodeSpec(
        node_id="THIGH_L",
        label="Coxa Esquerda",
        anatomical_region="membro_inferior_esq",
        modality="imu",
        x_pos=0.34,
        y_pos=0.52,
    ),
    SensorNodeSpec(
        node_id="THIGH_R",
        label="Coxa Direita",
        anatomical_region="membro_inferior_dir",
        modality="imu",
        x_pos=0.66,
        y_pos=0.52,
    ),
    SensorNodeSpec(
        node_id="SHANK_L",
        label="Canela Esquerda",
        anatomical_region="membro_inferior_esq",
        modality="imu",
        x_pos=0.31,
        y_pos=0.73,
    ),
    SensorNodeSpec(
        node_id="SHANK_R",
        label="Canela Direita",
        anatomical_region="membro_inferior_dir",
        modality="imu",
        x_pos=0.69,
        y_pos=0.73,
    ),
    SensorNodeSpec(
        node_id="ANKLE_L",
        label="Tornozelo Esquerdo",
        anatomical_region="membro_inferior_esq",
        modality="imu",
        x_pos=0.28,
        y_pos=0.91,
    ),
    SensorNodeSpec(
        node_id="ANKLE_R",
        label="Tornozelo Direito",
        anatomical_region="membro_inferior_dir",
        modality="imu",
        x_pos=0.72,
        y_pos=0.91,
    ),
)

OPTIONAL_EEG_NODES: tuple[SensorNodeSpec, ...] = (
    SensorNodeSpec(
        node_id="EEG_CZ",
        label="Córtex Motor (Cz)",
        anatomical_region="cranio_central",
        modality="eeg",
        channels=("theta_power", "alpha_power", "beta_power"),
        x_pos=0.50,
        y_pos=0.08,
    ),
)


class Subject(BaseModel):
    """Sujeito anonimizado do estudo de Parkinson (nenhum PII permitido)."""

    model_config = ConfigDict(frozen=True)

    subject_id: str = Field(..., description="Código anonimizado no formato SUBJ_XXX")
    age_group: str = Field(..., min_length=3, description="Faixa etária agregada (ex.: 65-69)")
    hoehn_yahr_stage: float = Field(..., ge=1.0, le=5.0, description="Estágio Hoehn & Yahr")
    disease_duration_years: float = Field(..., ge=0.0, le=50.0)
    medication_state: MedicationState = Field(default="OFF")

    @field_validator("subject_id")
    @classmethod
    def validate_anonymized_subject_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not ANON_SUBJECT_PATTERN.match(cleaned):
            raise ValueError(
                f"Identificador de sujeito inválido ('{cleaned}'). "
                "Por privacidade, use estritamente o padrão anonimizado 'SUBJ_XXX'."
            )
        return cleaned


class FOGEvent(BaseModel):
    """Episódio anotado de Freezing of Gait (FOG) dentro de uma sessão clínica."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(..., min_length=3)
    session_id: str = Field(..., min_length=3)
    subject_id: str = Field(..., min_length=8)
    onset_seconds: float = Field(..., ge=0.0)
    offset_seconds: float = Field(..., gt=0.0)
    trigger_task: TriggerTask = Field(default="turning")

    @field_validator("subject_id")
    @classmethod
    def check_subject_id(cls, value: str) -> str:
        if not ANON_SUBJECT_PATTERN.match(value.strip()):
            raise ValueError("subject_id em FOGEvent deve seguir o padrão 'SUBJ_XXX'.")
        return value.strip()

    @model_validator(mode="after")
    def check_interval(self) -> FOGEvent:
        if self.offset_seconds <= self.onset_seconds:
            raise ValueError("offset_seconds deve ser estritamente maior que onset_seconds.")
        return self

    @property
    def duration_seconds(self) -> float:
        return round(self.offset_seconds - self.onset_seconds, 3)


def _default_modalities() -> list[ModalityType]:
    return ["imu"]


class Session(BaseModel):
    """Sessão de coleta contínua de marcha com sensores inerciais (e modalidades extras)."""

    model_config = ConfigDict(frozen=True)

    session_id: str = Field(..., min_length=3)
    subject_id: str = Field(..., min_length=8)
    sampling_rate_hz: int = Field(default=100, ge=20, le=1000)
    duration_seconds: float = Field(..., gt=0.0)
    modalities: list[ModalityType] = Field(default_factory=_default_modalities)
    events: list[FOGEvent] = Field(default_factory=list)

    @field_validator("subject_id")
    @classmethod
    def check_subject_id(cls, value: str) -> str:
        if not ANON_SUBJECT_PATTERN.match(value.strip()):
            raise ValueError("subject_id em Session deve seguir o padrão 'SUBJ_XXX'.")
        return value.strip()


class Window(BaseModel):
    """Janela temporal extraída de uma sessão, com features por nó corporal e label de FOG."""

    model_config = ConfigDict(frozen=True)

    window_id: str = Field(..., min_length=3)
    subject_id: str = Field(..., min_length=8)
    session_id: str = Field(..., min_length=3)
    start_seconds: float = Field(..., ge=0.0)
    end_seconds: float = Field(..., gt=0.0)
    label: Literal[0, 1] = Field(
        ...,
        description="1 = episódio de FOG presente na janela; 0 = marcha sem FOG",
    )
    fog_overlap_ratio: float = Field(..., ge=0.0, le=1.0)
    node_features: dict[str, list[float]] = Field(
        ...,
        description="Mapa node_id -> vetor de features espaço-temporais da janela",
    )

    @field_validator("subject_id")
    @classmethod
    def check_subject_id(cls, value: str) -> str:
        if not ANON_SUBJECT_PATTERN.match(value.strip()):
            raise ValueError("subject_id em Window deve seguir o padrão 'SUBJ_XXX'.")
        return value.strip()

    @model_validator(mode="after")
    def validate_window_bounds_and_features(self) -> Window:
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds deve ser maior que start_seconds.")
        if not self.node_features:
            raise ValueError("node_features não pode ser vazio.")
        feature_lengths = {len(vec) for vec in self.node_features.values()}
        if len(feature_lengths) > 1 or 0 in feature_lengths:
            raise ValueError(
                "Todos os nós em `node_features` devem ter vetores de mesmo tamanho > 0."
            )
        return self
