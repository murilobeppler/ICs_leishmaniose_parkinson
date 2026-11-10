"""Script gerador de dados sintéticos do Módulo A (`peptide-docking`).

Gera:
1. Biblioteca validada de 634 peptídeos candidatos (`peptides_634.parquet`).
2. Metadados estruturais do alvo seletivo de Leishmania (`leishmania_target.json`).
3. Uma run completa de referência com o `MockDockingEngine` em lotes de 10.
"""

from __future__ import annotations

from pathlib import Path

from ic_core.io import write_json
from ic_core.logging import get_logger

from peptide_docking.config import PeptideDockingSettings
from peptide_docking.domain import EXPECTED_LIBRARY_SIZE
from peptide_docking.engines.mock import MockDockingEngine
from peptide_docking.library import (
    build_real_hpepdock_run,
    build_synthetic_peptide_library,
    build_synthetic_target,
    load_real_hpepdock_screen,
    save_peptide_library,
    save_target,
)
from peptide_docking.pipeline import DockingPipeline

DEFAULT_BASELINE_RUN_ID: str = "run_hpepdock_screen_real"


def generate_synthetic_artifacts(
    settings: PeptideDockingSettings | None = None,
) -> tuple[Path, Path, str]:
    """Cria a biblioteca validada de peptídeos, o alvo e a run baseline/real."""
    cfg = settings or PeptideDockingSettings()
    logger = get_logger("peptide_docking.synthetic", cfg)

    library_path = cfg.resolved_library_path(must_exist=False)
    target_path = cfg.resolved_target_path(must_exist=False)
    runs_dir = cfg.resolved_runs_dir(create=True)

    target = build_synthetic_target()
    save_target(target, target_path)

    # Verifica se o arquivo CSV real com scores originais do HPEPDOCK está presente
    backend_root = Path(__file__).resolve().parent.parent
    real_csv_path = backend_root / "resources" / "hpepdock_screen_real.csv"
    if not real_csv_path.exists():
        real_csv_path = backend_root / "data" / "hpepdock_screen_real.csv"

    if real_csv_path.exists():
        logger.info(f"Carregando dataset oficial do HPEPDOCK a partir de {real_csv_path.name}...")
        peptides, scores_map = load_real_hpepdock_screen(real_csv_path)
        save_peptide_library(peptides, library_path)

        manifest, results = build_real_hpepdock_run(
            peptides=peptides,
            scores_map=scores_map,
            target=target,
            run_id=DEFAULT_BASELINE_RUN_ID,
        )
        run_folder = runs_dir / manifest.run_id
        run_folder.mkdir(parents=True, exist_ok=True)
        write_json(manifest.model_dump(), run_folder / "manifest.json")
        write_json([r.model_dump() for r in results], run_folder / "results.json")

        logger.info(
            f"Triagem oficial HPEPDOCK carregada com sucesso: {len(peptides)} peptídeos "
            f"em {library_path.name}, alvo {target.target_id} e run {manifest.run_id} "
            f"({manifest.completed_jobs}/{manifest.total_jobs} jobs com scores reais)."
        )
        return library_path, target_path, manifest.run_id

    # Fallback para gerador sintético controlado
    peptides = build_synthetic_peptide_library(
        count=EXPECTED_LIBRARY_SIZE,
        seed=cfg.ic_random_seed,
    )
    save_peptide_library(peptides, library_path)

    engine = MockDockingEngine()
    pipeline = DockingPipeline(
        runs_dir=runs_dir,
        engine=engine,
        batch_size=cfg.hpepdock_batch_size,
    )
    manifest, _ = pipeline.run_batch_screening(
        peptides=peptides,
        target=target,
        seed=cfg.ic_random_seed,
        run_id="run_baseline_mock_seed42",
        parameters={
            "receptor_flexibility": "semi-flexible-pocket",
            "exhaustiveness": 8,
            "scoring_function": "knowledge_based_iterative",
            "note": "Triagem sintética reprodutível (hipótese computacional)",
        },
    )

    logger.info(
        f"Dados sintéticos gerados: {len(peptides)} peptídeos em {library_path.name}, "
        f"alvo {target.target_id} e run {manifest.run_id} "
        f"({manifest.completed_jobs}/{manifest.total_jobs} jobs)."
    )
    return library_path, target_path, manifest.run_id



if __name__ == "__main__":
    generate_synthetic_artifacts()
