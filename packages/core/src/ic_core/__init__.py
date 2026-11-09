"""Pacote `ic_core`: infraestrutura compartilhada enxuta para `ic-research-lab`."""

from ic_core.config import DEFAULT_RANDOM_SEED, CoreSettings
from ic_core.io import DiskCache, read_json, read_tabular, stable_hash, write_json, write_tabular
from ic_core.logging import get_logger, sanitize_log_text
from ic_core.paths import ensure_dir, find_repo_root, resolve_data_path

__all__ = [
    "CoreSettings",
    "DEFAULT_RANDOM_SEED",
    "DiskCache",
    "ensure_dir",
    "find_repo_root",
    "get_logger",
    "read_json",
    "read_tabular",
    "resolve_data_path",
    "sanitize_log_text",
    "stable_hash",
    "write_json",
    "write_tabular",
]
