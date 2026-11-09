"""Orquestração em lote, retomável e idempotente para triagem de docking peptídico."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ic_core.io import read_json, stable_hash, write_json
from ic_core.paths import ensure_dir

from peptide_docking.domain import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_NUM_POSES,
    HYPOTHESIS_DISCLAIMER,
    DockingJob,
    DockingResult,
    DockingRunManifest,
    Peptide,
    RunStatus,
    Target,
)
from peptide_docking.engines.base import DockingEngine


def _chunked(items: Sequence[Peptide], batch_size: int) -> Iterable[Sequence[Peptide]]:
    for idx in range(0, len(items), batch_size):
        yield items[idx : idx + batch_size]


def build_deterministic_run_id(
    target: Target,
    engine: DockingEngine,
    seed: int,
    parameters: dict[str, Any],
) -> str:
    """Gera um `run_id` determinístico a partir do alvo, motor, semente e parâmetros."""
    digest = stable_hash(
        {
            "target_id": target.target_id,
            "target_sha256": target.structure_sha256,
            "engine_name": engine.name,
            "engine_version": engine.version,
            "seed": seed,
            "parameters": parameters,
        }
    )
    return f"run_{engine.name}_s{seed}_{digest[:8]}"


class DockingPipeline:
    """Pipeline em lote retomável e idempotente para docking de bibliotecas peptídicas."""

    def __init__(
        self,
        runs_dir: Path,
        engine: DockingEngine,
        batch_size: int = DEFAULT_BATCH_SIZE,
        num_poses: int = DEFAULT_NUM_POSES,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size deve ser >= 1.")
        self.runs_dir = ensure_dir(runs_dir)
        self.engine = engine
        self.batch_size = batch_size
        self.num_poses = num_poses

    def run_batch_screening(
        self,
        peptides: Sequence[Peptide],
        target: Target,
        seed: int = 42,
        run_id: str | None = None,
        parameters: dict[str, Any] | None = None,
        max_batches: int | None = None,
    ) -> tuple[DockingRunManifest, list[DockingResult]]:
        """Executa (ou retoma) o docking da biblioteca de peptídeos em lotes.

        Idempotência e retomada:
        - Resultados individuais são gravados em `<runs_dir>/<run_id>/items/<peptide_id>.json`.
        - Se a run for interrompida (ou limitada por `max_batches`) e chamada novamente com o
          mesmo `run_id`, os peptídeos já processados são carregados do disco sem reexecutar
          o motor de docking (`cached_jobs` incrementado).
        """
        params = dict(parameters or {})
        effective_run_id = run_id or build_deterministic_run_id(
            target=target,
            engine=self.engine,
            seed=seed,
            parameters=params,
        )

        run_dir = ensure_dir(self.runs_dir / effective_run_id)
        items_dir = ensure_dir(run_dir / "items")
        manifest_path = run_dir / "manifest.json"
        consolidated_path = run_dir / "results.json"

        now_iso = datetime.now(tz=UTC).isoformat()
        started_at = now_iso
        if manifest_path.exists():
            old_manifest = DockingRunManifest.model_validate(read_json(manifest_path))
            started_at = old_manifest.started_at_utc

        results_by_peptide: dict[str, DockingResult] = {}
        cached_count = 0
        failed_count = 0

        # Carrega itens já persistidos em execução anterior (retomada idempotente)
        for pep in peptides:
            item_file = items_dir / f"{pep.peptide_id}.json"
            if item_file.exists():
                existing = DockingResult.model_validate(read_json(item_file))
                results_by_peptide[pep.peptide_id] = existing.model_copy(
                    update={"status": "cached"}
                )
                cached_count += 1

        pending_peptides = [p for p in peptides if p.peptide_id not in results_by_peptide]

        for batches_processed, batch in enumerate(_chunked(pending_peptides, self.batch_size)):
            if max_batches is not None and batches_processed >= max_batches:
                break

            for pep in batch:
                job_id = f"{effective_run_id}_{pep.peptide_id}"
                job = DockingJob(
                    job_id=job_id,
                    run_id=effective_run_id,
                    peptide=pep,
                    target=target,
                    engine_name=self.engine.name,
                    seed=seed,
                    num_poses=self.num_poses,
                    parameters=params,
                )
                result = self.engine.submit(job)
                if result.status == "failed":
                    failed_count += 1
                elif result.status == "cached":
                    cached_count += 1

                results_by_peptide[pep.peptide_id] = result
                write_json(result.model_dump(), items_dir / f"{pep.peptide_id}.json")

            self._persist_checkpoint(
                manifest_path=manifest_path,
                consolidated_path=consolidated_path,
                run_id=effective_run_id,
                target=target,
                seed=seed,
                params=params,
                total_jobs=len(peptides),
                results_by_peptide=results_by_peptide,
                cached_jobs=cached_count,
                failed_jobs=failed_count,
                started_at_utc=started_at,
                peptides_order=peptides,
                write_consolidated=False,
            )

        manifest, ordered_results = self._persist_checkpoint(
            manifest_path=manifest_path,
            consolidated_path=consolidated_path,
            run_id=effective_run_id,
            target=target,
            seed=seed,
            params=params,
            total_jobs=len(peptides),
            results_by_peptide=results_by_peptide,
            cached_jobs=cached_count,
            failed_jobs=failed_count,
            started_at_utc=started_at,
            peptides_order=peptides,
            write_consolidated=True,
        )
        return manifest, ordered_results

    def _persist_checkpoint(
        self,
        manifest_path: Path,
        consolidated_path: Path,
        run_id: str,
        target: Target,
        seed: int,
        params: dict[str, Any],
        total_jobs: int,
        results_by_peptide: dict[str, DockingResult],
        cached_jobs: int,
        failed_jobs: int,
        started_at_utc: str,
        peptides_order: Sequence[Peptide],
        write_consolidated: bool = True,
    ) -> tuple[DockingRunManifest, list[DockingResult]]:
        ordered_results = [
            results_by_peptide[p.peptide_id]
            for p in peptides_order
            if p.peptide_id in results_by_peptide
        ]
        completed_jobs = len(ordered_results)
        status: RunStatus = "completed" if completed_jobs == total_jobs else "partial"

        manifest = DockingRunManifest(
            run_id=run_id,
            target_id=target.target_id,
            engine_name=self.engine.name,
            engine_version=self.engine.version,
            seed=seed,
            batch_size=self.batch_size,
            total_jobs=total_jobs,
            completed_jobs=completed_jobs,
            cached_jobs=cached_jobs,
            failed_jobs=failed_jobs,
            status=status,
            parameters=params,
            started_at_utc=started_at_utc,
            updated_at_utc=datetime.now(tz=UTC).isoformat(),
            hypothesis_disclaimer=HYPOTHESIS_DISCLAIMER,
        )
        write_json(manifest.model_dump(), manifest_path)
        if write_consolidated:
            write_json([r.model_dump() for r in ordered_results], consolidated_path)
        return manifest, ordered_results


def list_runs(runs_dir: Path) -> list[DockingRunManifest]:
    """Lista todas as runs persistidas em `runs_dir`, da mais recente para a mais antiga."""
    if not runs_dir.exists():
        return []
    manifests: list[DockingRunManifest] = []
    for child in sorted(runs_dir.iterdir()):
        manifest_file = child / "manifest.json"
        if child.is_dir() and manifest_file.exists():
            manifests.append(DockingRunManifest.model_validate(read_json(manifest_file)))
    manifests.sort(key=lambda m: m.updated_at_utc, reverse=True)
    return manifests


def load_run_manifest(runs_dir: Path, run_id: str) -> DockingRunManifest:
    """Carrega o manifesto de uma run específica."""
    manifest_file = runs_dir / run_id / "manifest.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifesto da run '{run_id}' não encontrado em {manifest_file}")
    return DockingRunManifest.model_validate(read_json(manifest_file))


def load_run_results(runs_dir: Path, run_id: str) -> list[DockingResult]:
    """Carrega a lista de `DockingResult` de uma run específica."""
    results_file = runs_dir / run_id / "results.json"
    if not results_file.exists():
        raise FileNotFoundError(f"Resultados da run '{run_id}' não encontrados em {results_file}")
    raw_list = read_json(results_file)
    return [DockingResult.model_validate(item) for item in raw_list]
