"""Testes unitários para `ic_core` (config, logging, paths e io/cache)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import pytest

from ic_core.config import DEFAULT_RANDOM_SEED, CoreSettings
from ic_core.io import DiskCache, read_json, read_tabular, stable_hash, write_json, write_tabular
from ic_core.logging import StructuredFormatter, get_logger, sanitize_log_text
from ic_core.paths import ensure_dir, find_repo_root, resolve_data_path


def test_core_settings_defaults_and_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("IC_ENV", "test")
    monkeypatch.setenv("IC_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("IC_LOG_FORMAT", "json")
    monkeypatch.setenv("IC_RANDOM_SEED", "123")
    monkeypatch.setenv("IC_DATA_ROOT", str(tmp_path / "custom_data"))
    monkeypatch.setenv("IC_CACHE_DIR", str(tmp_path / "custom_cache"))

    settings = CoreSettings()
    assert settings.ic_env == "test"
    assert settings.ic_log_level == "DEBUG"
    assert settings.ic_log_format == "json"
    assert settings.ic_random_seed == 123
    assert DEFAULT_RANDOM_SEED == 42

    data_root = settings.resolved_data_root(create=True)
    cache_dir = settings.resolved_cache_dir(create=True)
    assert data_root.exists()
    assert cache_dir.exists()


def test_paths_resolution_and_missing_check(tmp_path: Path) -> None:
    repo_root = find_repo_root()
    assert (repo_root / "pnpm-workspace.yaml").exists()

    created = ensure_dir(tmp_path / "nested" / "folder")
    assert created.is_dir()

    resolved = resolve_data_path("sub/item.txt", base_dir=tmp_path, must_exist=False)
    assert resolved == (tmp_path / "sub" / "item.txt").resolve()

    with pytest.raises(FileNotFoundError):
        resolve_data_path("inexistente.parquet", base_dir=tmp_path, must_exist=True)


def test_structured_logging_and_redaction() -> None:
    raw = "Paciente 123.456.789-00 com api_key=segredo123"
    redacted = sanitize_log_text(raw)
    assert "123.456.789-00" not in redacted
    assert "segredo123" not in redacted
    assert "[REDACTED_ID]" in redacted
    assert "api_key=[REDACTED]" in redacted

    formatter = StructuredFormatter(fmt_mode="json")
    record = logging.LogRecord(
        name="ic_core.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Teste token: supersecreto",
        args=(),
        exc_info=None,
    )
    record.context = {"subject": "SUBJ_001", "secret": "abc"}
    formatted = formatter.format(record)
    parsed = json.loads(formatted)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "ic_core.test"
    assert "supersecreto" not in parsed["message"]
    assert parsed["context"]["subject"] == "SUBJ_001"

    logger = get_logger("ic_core.sample")
    assert logger.name == "ic_core.sample"


def test_io_tabular_json_hash_and_disk_cache(tmp_path: Path) -> None:
    h1 = stable_hash({"b": 2, "a": 1})
    h2 = stable_hash({"a": 1, "b": 2})
    assert h1 == h2
    assert len(h1) == 16

    json_path = write_json({"seed": 42, "status": "ok"}, tmp_path / "meta.json")
    assert read_json(json_path) == {"seed": 42, "status": "ok"}

    df = pd.DataFrame({"id": ["PEP_001", "PEP_002"], "score": [-185.4, -172.1]})
    parquet_path = write_tabular(df, tmp_path / "table.parquet")
    csv_path = write_tabular(df, tmp_path / "table.csv")

    df_parquet = read_tabular(parquet_path)
    df_csv = read_tabular(csv_path)
    assert list(df_parquet["id"]) == ["PEP_001", "PEP_002"]
    assert list(df_csv["id"]) == ["PEP_001", "PEP_002"]

    with pytest.raises(ValueError, match="Formato tabular não suportado"):
        write_tabular(df, tmp_path / "invalid.txt")

    cache = DiskCache(cache_root=tmp_path / "cache", namespace="test_ns")
    calls = 0

    def compute() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"value": 99}

    assert not cache.has(h1)
    first = cache.get_or_compute(h1, compute)
    second = cache.get_or_compute(h1, compute)
    assert first == {"value": 99}
    assert second == {"value": 99}
    assert calls == 1
