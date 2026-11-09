"""Módulo B (`fog_gnn`): predição de Freezing of Gait em Parkinson com GNN espaço-temporal."""

from fog_gnn.config import FogGnnSettings
from fog_gnn.domain import (
    CANONICAL_IMU_NODES,
    IMU_CHANNELS,
    NODE_FEATURE_NAMES,
    OPTIONAL_EEG_NODES,
    FOGEvent,
    SensorNodeSpec,
    Session,
    Subject,
    Window,
)

__all__ = [
    "CANONICAL_IMU_NODES",
    "FOGEvent",
    "FogGnnSettings",
    "IMU_CHANNELS",
    "NODE_FEATURE_NAMES",
    "OPTIONAL_EEG_NODES",
    "SensorNodeSpec",
    "Session",
    "Subject",
    "Window",
]

