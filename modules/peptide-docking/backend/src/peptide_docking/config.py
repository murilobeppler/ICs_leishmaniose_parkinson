"""Configurações do Módulo A (`peptide-docking`) via `pydantic-settings`."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from ic_core.config import CoreSettings
from ic_core.paths import ensure_dir, resolve_data_path
from pydantic import Field

EngineChoice = Literal["mock", "hpepdock"]


class PeptideDockingSettings(CoreSettings):
    """Settings específicos do módulo `peptide-docking`."""

    peptide_library_path: Path = Field(
        default=Path("./data/synthetic/peptide_docking/peptides_634.parquet"),
        description="Caminho para o arquivo Parquet/CSV da biblioteca de 634 peptídeos",
    )
    peptide_target_path: Path = Field(
        default=Path("./data/synthetic/peptide_docking/leishmania_target.json"),
        description="Caminho para o arquivo JSON de metadados do alvo de Leishmania",
    )
    peptide_runs_dir: Path = Field(
        default=Path("./data/synthetic/peptide_docking/runs"),
        description="Diretório onde runs e resultados de docking são persistidos",
    )
    peptide_docking_engine: EngineChoice = Field(
        default="mock",
        description="Engine padrão de docking (mock | hpepdock)",
    )

    hpepdock_base_url: str = Field(
        default="http://huanglab.phys.hust.edu.cn/hpepdock/",
        description="URL base do servidor HPEPDOCK",
    )
    hpepdock_api_token: str = Field(
        default="",
        description="Token/credencial opcional caso exista autorização institucional",
    )
    hpepdock_allow_automated_submission: bool = Field(
        default=False,
        description="Habilita submissão HTTP real apenas se autorizado pelos termos do serviço",
    )
    hpepdock_min_interval_seconds: float = Field(
        default=30.0,
        ge=1.0,
        description="Intervalo mínimo em segundos entre submissões ao HPEPDOCK (rate limit)",
    )
    hpepdock_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Número máximo de tentativas em falhas transitórias de rede",
    )
    hpepdock_batch_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Tamanho do lote de submissão (padrão histórico do HPEPDOCK = 10)",
    )

    peptide_api_host: str = Field(default="127.0.0.1", description="Host da API FastAPI")
    peptide_api_port: int = Field(default=8001, description="Porta da API FastAPI")

    def resolved_library_path(self, must_exist: bool = False) -> Path:
        return resolve_data_path(self.peptide_library_path, must_exist=must_exist)

    def resolved_target_path(self, must_exist: bool = False) -> Path:
        return resolve_data_path(self.peptide_target_path, must_exist=must_exist)

    def resolved_runs_dir(self, create: bool = True) -> Path:
        path = resolve_data_path(self.peptide_runs_dir)
        return ensure_dir(path) if create else path
