"""Leitura e escrita tabular/JSON atômica, hashing determinístico e cache em disco."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd

from ic_core.paths import ensure_dir

T = TypeVar("T")


def stable_hash(payload: Mapping[str, Any]) -> str:
    """Calcula um hash SHA-256 determinístico (16 hex chars) para um dicionário de parâmetros."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def write_json(data: Any, path: Path) -> Path:
    """Persiste um objeto serializável em JSON de forma atômica."""
    target = path.expanduser().resolve()
    ensure_dir(target.parent)
    tmp_path = target.with_suffix(f"{target.suffix}.tmp")
    tmp_path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(target)
    return target


def read_json(path: Path) -> Any:
    """Lê um arquivo JSON do disco."""
    target = path.expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Arquivo JSON não encontrado: {target}")
    return json.loads(target.read_text(encoding="utf-8"))


def write_tabular(df: pd.DataFrame, path: Path) -> Path:
    """Escreve um `DataFrame` em formato `.parquet` ou `.csv` de forma atômica."""
    target = path.expanduser().resolve()
    ensure_dir(target.parent)
    suffix = target.suffix.lower()
    tmp_path = target.with_suffix(f"{target.suffix}.tmp")

    if suffix == ".parquet":
        df.to_parquet(tmp_path, index=False)
    elif suffix == ".csv":
        df.to_csv(tmp_path, index=False)
    else:
        raise ValueError(f"Formato tabular não suportado ('{suffix}'). Use '.parquet' ou '.csv'.")

    tmp_path.replace(target)
    return target


def read_tabular(path: Path) -> pd.DataFrame:
    """Lê um arquivo tabular `.parquet` ou `.csv` em um `DataFrame`."""
    target = path.expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(f"Arquivo tabular não encontrado: {target}")

    suffix = target.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(target)
    if suffix == ".csv":
        return pd.read_csv(target)
    raise ValueError(f"Formato tabular não suportado ('{suffix}'). Use '.parquet' ou '.csv'.")


class DiskCache:
    """Cache determinístico em disco para resultados computacionais custosos."""

    def __init__(self, cache_root: Path, namespace: str) -> None:
        self.namespace_dir = ensure_dir(cache_root / namespace)

    def _entry_path(self, key: str) -> Path:
        safe_key = "".join(ch for ch in key if ch.isalnum() or ch in ("-", "_"))
        if not safe_key:
            raise ValueError("Chave de cache inválida.")
        return self.namespace_dir / f"{safe_key}.json"

    def has(self, key: str) -> bool:
        """Verifica se a chave existe no cache."""
        return self._entry_path(key).exists()

    def get(self, key: str) -> Any | None:
        """Recupera o valor associado à chave ou `None` se ausente."""
        entry = self._entry_path(key)
        if not entry.exists():
            return None
        return read_json(entry)

    def set(self, key: str, value: Any) -> Path:
        """Salva um valor serializável em JSON no cache."""
        return write_json(value, self._entry_path(key))

    def get_or_compute(self, key: str, compute_fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        """Retorna do cache se existir; caso contrário computa, persiste e retorna."""
        cached = self.get(key)
        if isinstance(cached, dict):
            return cached
        result = compute_fn()
        self.set(key, result)
        return result
