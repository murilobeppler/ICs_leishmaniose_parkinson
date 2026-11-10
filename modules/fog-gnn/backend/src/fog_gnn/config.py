"""Configurações do Módulo B (`fog-gnn`) via `pydantic-settings`."""

from __future__ import annotations

from pathlib import Path

from ic_core.config import CoreSettings
from ic_core.paths import ensure_dir, resolve_data_path
from pydantic import Field


class FogGnnSettings(CoreSettings):
    """Settings específicos do módulo `fog-gnn`."""

    fog_dataset_dir: Path = Field(
        default=Path("./data/synthetic/fog_gnn/imu_dataset"),
        description="Diretório do dataset de sensores IMU (anonimizado, fora do Git)",
    )
    fog_experiments_dir: Path = Field(
        default=Path("./data/synthetic/fog_gnn/experiments"),
        description="Diretório onde experimentos LOSO, métricas e grafos são persistidos",
    )
    fog_sampling_rate_hz: int = Field(
        default=100,
        ge=20,
        le=1000,
        description="Taxa de amostragem dos sensores inerciais (Hz)",
    )
    fog_window_size_seconds: float = Field(
        default=2.56,
        gt=0.5,
        le=10.0,
        description="Duração da janela deslizante em segundos",
    )
    fog_window_stride_seconds: float = Field(
        default=1.28,
        gt=0.1,
        le=10.0,
        description="Passo (stride) entre janelas consecutivas em segundos",
    )
    fog_correlation_threshold: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
        description="Limiar de |r| de Pearson para criar arestas funcionais dinâmicas no grafo",
    )

    fog_api_host: str = Field(default="127.0.0.1", description="Host da API FastAPI")
    fog_api_port: int = Field(default=8002, description="Porta da API FastAPI")

    def resolved_dataset_dir(self, create: bool = False) -> Path:
        path = resolve_data_path(self.fog_dataset_dir)
        return ensure_dir(path) if create else path

    def resolved_experiments_dir(self, create: bool = True) -> Path:
        path = resolve_data_path(self.fog_experiments_dir)
        return ensure_dir(path) if create else path
