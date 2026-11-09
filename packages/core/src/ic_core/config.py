"""Configuração base compartilhada via `pydantic-settings`."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from ic_core.paths import ensure_dir, find_repo_root, resolve_data_path

EnvMode = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
LogFormat = Literal["console", "json"]

DEFAULT_RANDOM_SEED: int = 42


def _default_env_file() -> Path:
    return find_repo_root() / ".env"


class CoreSettings(BaseSettings):
    """Settings base compartilhados entre os pacotes do monorepo.

    Módulos específicos devem herdar de `CoreSettings` apenas no seu próprio pacote,
    adicionando variáveis do seu domínio sem poluir o `ic_core`.
    """

    model_config = SettingsConfigDict(
        env_file=_default_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    ic_env: EnvMode = Field(default="development", description="Ambiente de execução")
    ic_log_level: LogLevel = Field(default="INFO", description="Nível de log estruturado")
    ic_log_format: LogFormat = Field(default="console", description="Formato de saída dos logs")
    ic_random_seed: int = Field(
        default=DEFAULT_RANDOM_SEED,
        ge=0,
        description="Semente global padrão para reprodutibilidade científica",
    )
    ic_data_root: Path = Field(
        default=Path("./data"),
        description="Diretório raiz para dados externos ou sintéticos (fora do Git)",
    )
    ic_cache_dir: Path = Field(
        default=Path("./.cache"),
        description="Diretório para cache determinístico em disco",
    )

    def resolved_data_root(self, create: bool = False) -> Path:
        """Retorna o caminho absoluto de `ic_data_root`."""
        path = resolve_data_path(self.ic_data_root)
        return ensure_dir(path) if create else path

    def resolved_cache_dir(self, create: bool = True) -> Path:
        """Retorna o caminho absoluto de `ic_cache_dir`."""
        path = resolve_data_path(self.ic_cache_dir)
        return ensure_dir(path) if create else path
