"""Resolução segura de caminhos do monorepo e de dados externos fora do Git."""

from __future__ import annotations

import os
from pathlib import Path

REPO_MARKERS: tuple[str, ...] = ("pnpm-workspace.yaml", ".env.example", ".git")


def find_repo_root(start: Path | None = None) -> Path:
    """Localiza a raiz do monorepo `ic-research-lab` subindo na árvore de diretórios."""
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if any((candidate / marker).exists() for marker in REPO_MARKERS):
            return candidate

    return Path.cwd().resolve()


def ensure_dir(path: Path) -> Path:
    """Garante que o diretório (e seus pais) exista e retorna o caminho resolvido."""
    resolved = path.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def resolve_data_path(
    raw_path: str | Path,
    base_dir: Path | None = None,
    must_exist: bool = False,
) -> Path:
    """Resolve um caminho de dados externo ou relativo à raiz do monorepo.

    Expande variáveis de ambiente e `~`. Se relativo, ancora em `base_dir`
    (ou na raiz do monorepo quando `base_dir` for `None`).
    """
    expanded = os.path.expandvars(str(raw_path))
    candidate = Path(expanded).expanduser()
    if not candidate.is_absolute():
        anchor = (base_dir or find_repo_root()).resolve()
        candidate = anchor / candidate
    resolved = candidate.resolve()

    if must_exist and not resolved.exists():
        raise FileNotFoundError(
            f"Caminho de dados não encontrado: '{resolved}'. "
            "Verifique seu arquivo .env ou gere os dados sintéticos com `make synthetic`."
        )
    return resolved
