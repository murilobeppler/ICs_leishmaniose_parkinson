"""Teste arquitetural: garante a fronteira dura entre `ic_core`, `peptide_docking` e `fog_gnn`."""

from __future__ import annotations

import ast
from pathlib import Path

from ic_core.paths import find_repo_root


def collect_imported_top_packages(py_file: Path) -> set[str]:
    """Extrai o conjunto de pacotes raiz importados em um arquivo `.py` via AST."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    return imported


def find_boundary_violations(repo_root: Path) -> list[str]:
    """Verifica todos os pacotes Python do monorepo contra importações proibidas."""
    rules: list[tuple[Path, set[str]]] = [
        (repo_root / "packages" / "core", {"peptide_docking", "fog_gnn"}),
        (repo_root / "modules" / "peptide-docking" / "backend", {"fog_gnn"}),
        (repo_root / "modules" / "fog-gnn" / "backend", {"peptide_docking"}),
    ]

    violations: list[str] = []
    for pkg_dir, forbidden in rules:
        if not pkg_dir.exists():
            continue
        for py_file in pkg_dir.rglob("*.py"):
            if ".venv" in py_file.parts or "__pycache__" in py_file.parts:
                continue
            imported = collect_imported_top_packages(py_file)
            illegal = imported & forbidden
            if illegal:
                rel = py_file.relative_to(repo_root)
                violations.append(f"{rel} importa pacote(s) proibido(s): {sorted(illegal)}")
    return violations


def test_monorepo_module_boundaries() -> None:
    repo_root = find_repo_root()
    violations = find_boundary_violations(repo_root)
    assert violations == [], "Violação de fronteira entre módulos:\n" + "\n".join(violations)


def test_boundary_detector_catches_cross_module_import(tmp_path: Path) -> None:
    bad_file = (
        tmp_path / "modules" / "peptide-docking" / "backend" / "src" / "peptide_docking" / "bad.py"
    )
    bad_file.parent.mkdir(parents=True, exist_ok=True)
    bad_file.write_text("from fog_gnn.domain import Subject\n", encoding="utf-8")

    violations = find_boundary_violations(tmp_path)
    assert len(violations) == 1
    assert "fog_gnn" in violations[0]
