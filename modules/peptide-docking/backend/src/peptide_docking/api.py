"""API FastAPI do Módulo A (`peptide-docking`): `/peptides`, `/runs`, `/results`, `/target`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from ic_core.io import write_json

from peptide_docking.config import EngineChoice, PeptideDockingSettings
from peptide_docking.domain import (
    EXPECTED_LIBRARY_SIZE,
    HYPOTHESIS_DISCLAIMER,
    DockingRunManifest,
    Peptide,
    Target,
)
from peptide_docking.engines.base import DockingEngine
from peptide_docking.engines.hpepdock import HPEPDOCKEngine
from peptide_docking.engines.mock import MockDockingEngine
from peptide_docking.library import (
    build_real_hpepdock_run,
    build_synthetic_peptide_library,
    build_synthetic_target,
    load_peptide_library,
    load_real_hpepdock_screen,
    load_target,
    save_peptide_library,
    save_target,
)
from peptide_docking.pipeline import (
    DockingPipeline,
    list_runs,
    load_run_manifest,
    load_run_results,
)
from peptide_docking.ranking import (
    RankedCandidate,
    RankingCriteria,
    RunRankingSummary,
    rank_docking_results,
    summarize_run_ranking,
)
from peptide_docking.visualization.pymol_export import generate_pymol_script

DEFAULT_BASELINE_RUN_ID: str = "run_hpepdock_screen_real"


class PeptidesResponse(BaseModel):
    """Resposta paginada e filtrável do endpoint `/peptides`."""

    model_config = ConfigDict(frozen=True)

    total_library_size: int
    filtered_count: int
    families: list[str]
    items: list[Peptide]
    hypothesis_disclaimer: str = Field(default=HYPOTHESIS_DISCLAIMER)


class ResultsResponse(BaseModel):
    """Resposta consolidada do endpoint `/results` com manifesto, resumo e candidatos ranqueados."""

    model_config = ConfigDict(frozen=True)

    manifest: DockingRunManifest
    target: Target
    summary: RunRankingSummary
    candidates: list[RankedCandidate]
    hypothesis_disclaimer: str = Field(default=HYPOTHESIS_DISCLAIMER)


class TriggerRunRequest(BaseModel):
    """Parâmetros para iniciar ou retomar uma run de docking em lote."""

    model_config = ConfigDict(frozen=True)

    engine: EngineChoice = Field(default="mock")
    seed: int = Field(default=42, ge=0)
    batch_size: int = Field(default=10, ge=1, le=200)
    run_id: str | None = Field(default=None)
    max_batches: int | None = Field(default=None, ge=1)
    exhaustiveness: int = Field(default=8, ge=1, le=32)


def ensure_module_a_data(
    settings: PeptideDockingSettings,
) -> tuple[list[Peptide], Target, list[DockingRunManifest]]:
    """Garante que a biblioteca de peptídeos (real ou sintética), o alvo e a run base existam."""
    lib_path = settings.resolved_library_path(must_exist=False)
    target_path = settings.resolved_target_path(must_exist=False)
    runs_dir = settings.resolved_runs_dir(create=True)

    if not target_path.exists():
        save_target(build_synthetic_target(), target_path)
    target = load_target(target_path)

    # Verifica se há o CSV oficial de triagem com scores reais do HPEPDOCK
    backend_root = Path(__file__).resolve().parent.parent
    real_csv_path = backend_root / "resources" / "hpepdock_screen_real.csv"
    if not real_csv_path.exists():
        real_csv_path = backend_root / "data" / "hpepdock_screen_real.csv"

    if real_csv_path.exists():
        peptides, scores_map = load_real_hpepdock_screen(real_csv_path)
        save_peptide_library(peptides, lib_path)

        real_run_dir = runs_dir / DEFAULT_BASELINE_RUN_ID
        manifest_file = real_run_dir / "manifest.json"
        results_file = real_run_dir / "results.json"

        if not manifest_file.exists() or not results_file.exists():
            manifest, results = build_real_hpepdock_run(
                peptides=peptides,
                scores_map=scores_map,
                target=target,
                run_id=DEFAULT_BASELINE_RUN_ID,
            )
            real_run_dir.mkdir(parents=True, exist_ok=True)
            write_json(manifest.model_dump(), manifest_file)
            write_json([r.model_dump() for r in results], results_file)

        manifests = list_runs(runs_dir)
        return peptides, target, manifests

    if not lib_path.exists():
        peptides = build_synthetic_peptide_library(
            count=EXPECTED_LIBRARY_SIZE,
            seed=settings.ic_random_seed,
        )
        save_peptide_library(peptides, lib_path)
    else:
        peptides = load_peptide_library(lib_path, expected_count=None)

    manifests = list_runs(runs_dir)
    if not manifests:
        pipeline = DockingPipeline(
            runs_dir=runs_dir,
            engine=MockDockingEngine(),
            batch_size=settings.hpepdock_batch_size,
        )
        manifest, _ = pipeline.run_batch_screening(
            peptides=peptides,
            target=target,
            seed=settings.ic_random_seed,
            run_id="run_baseline_mock_seed42",
            parameters={
                "receptor_flexibility": "semi-flexible-pocket",
                "exhaustiveness": 8,
                "scoring_function": "knowledge_based_iterative",
            },
        )
        manifests = [manifest]

    return peptides, target, manifests


def create_app(settings: PeptideDockingSettings | None = None) -> FastAPI:
    """Cria a aplicação FastAPI do Módulo A (`peptide-docking`)."""
    cfg = settings or PeptideDockingSettings()

    app = FastAPI(
        title="ic-research-lab | Módulo A — Peptide Docking API",
        version="0.1.0",
        description=(
            "API para triagem computacional de 634 peptídeos candidatos contra "
            "proteína-alvo de Leishmania sem ortólogo humano."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def get_health() -> dict[str, Any]:
        peptides, target, manifests = ensure_module_a_data(cfg)
        return {
            "status": "ok",
            "module": "peptide-docking",
            "library_size": len(peptides),
            "target_id": target.target_id,
            "has_human_ortholog": target.has_human_ortholog,
            "runs_count": len(manifests),
            "hypothesis_disclaimer": HYPOTHESIS_DISCLAIMER,
        }

    @app.get("/target", response_model=Target)
    def get_target() -> Target:
        _, target, _ = ensure_module_a_data(cfg)
        return target

    @app.get("/peptides", response_model=PeptidesResponse)
    def get_peptides(
        search: str | None = Query(default=None),
        source_family: str | None = Query(default=None),
        min_length: int | None = Query(default=None, ge=5),
        max_length: int | None = Query(default=None, le=60),
        min_charge: float | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=634),
        offset: int = Query(default=0, ge=0),
    ) -> PeptidesResponse:
        peptides, _, _ = ensure_module_a_data(cfg)
        families = sorted({p.source_family for p in peptides})

        filtered = peptides
        if search:
            q = search.strip().upper()
            filtered = [
                p
                for p in filtered
                if q in p.peptide_id.upper()
                or q in p.sequence.upper()
                or q in p.source_family.upper()
            ]
        if source_family:
            fam_lower = source_family.strip().lower()
            filtered = [p for p in filtered if p.source_family.lower() == fam_lower]
        if min_length is not None:
            filtered = [p for p in filtered if p.length >= min_length]
        if max_length is not None:
            filtered = [p for p in filtered if p.length <= max_length]
        if min_charge is not None:
            filtered = [p for p in filtered if p.net_charge_ph7 >= min_charge]

        sliced = filtered[offset : offset + limit]
        return PeptidesResponse(
            total_library_size=len(peptides),
            filtered_count=len(filtered),
            families=families,
            items=sliced,
        )

    @app.get("/runs", response_model=list[DockingRunManifest])
    def get_runs() -> list[DockingRunManifest]:
        _, _, manifests = ensure_module_a_data(cfg)
        return manifests

    @app.post("/runs", response_model=DockingRunManifest)
    def post_run(req: TriggerRunRequest) -> DockingRunManifest:
        peptides, target, _ = ensure_module_a_data(cfg)
        runs_dir = cfg.resolved_runs_dir(create=True)

        engine: DockingEngine
        if req.engine == "hpepdock":
            engine = HPEPDOCKEngine(
                cache_root=cfg.resolved_cache_dir(create=True),
                base_url=cfg.hpepdock_base_url,
                api_token=cfg.hpepdock_api_token,
                allow_automated_submission=cfg.hpepdock_allow_automated_submission,
                min_interval_seconds=cfg.hpepdock_min_interval_seconds,
                max_retries=cfg.hpepdock_max_retries,
                stub_fallback=True,
            )
        else:
            engine = MockDockingEngine()

        pipeline = DockingPipeline(
            runs_dir=runs_dir,
            engine=engine,
            batch_size=req.batch_size,
        )
        manifest, _ = pipeline.run_batch_screening(
            peptides=peptides,
            target=target,
            seed=req.seed,
            run_id=req.run_id,
            parameters={
                "receptor_flexibility": "semi-flexible-pocket",
                "exhaustiveness": req.exhaustiveness,
                "engine_mode": req.engine,
            },
            max_batches=req.max_batches,
        )
        return manifest

    @app.get("/results", response_model=ResultsResponse)
    def get_results(
        run_id: str | None = Query(default=None),
        max_top_score: float | None = Query(default=None),
        min_contact_ratio: float = Query(default=0.0, ge=0.0, le=1.0),
        min_charge: float | None = Query(default=None),
        source_family: str | None = Query(default=None),
        search: str | None = Query(default=None),
        top_k: int = Query(default=100, ge=1, le=634),
    ) -> ResultsResponse:
        peptides, target, manifests = ensure_module_a_data(cfg)
        runs_dir = cfg.resolved_runs_dir(create=True)

        selected_run_id = run_id or manifests[0].run_id
        try:
            manifest = load_run_manifest(runs_dir, selected_run_id)
            raw_results = load_run_results(runs_dir, selected_run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        criteria = RankingCriteria(
            max_top_score=max_top_score,
            min_binding_site_contact_ratio=min_contact_ratio,
            min_net_charge_ph7=min_charge,
            source_family=source_family,
            search_query=search,
            top_k=top_k,
        )
        ranked = rank_docking_results(peptides, raw_results, criteria=criteria)
        summary = summarize_run_ranking(
            run_id=manifest.run_id,
            engine_name=manifest.engine_name,
            seed=manifest.seed,
            peptides=peptides,
            results=raw_results,
            criteria=criteria,
        )
        return ResultsResponse(
            manifest=manifest,
            target=target,
            summary=summary,
            candidates=ranked,
        )

    @app.get("/results/{run_id}/{peptide_id}/pymol")
    def get_pymol_script(
        run_id: str,
        peptide_id: str,
        pose_rank: int = Query(default=1, ge=1),
        download: bool = Query(default=False),
    ) -> Any:
        peptides, target, manifests = ensure_module_a_data(cfg)
        runs_dir = cfg.resolved_runs_dir(create=True)

        selected_run_id = manifests[0].run_id if run_id in ("latest", "default") else run_id
        try:
            raw_results = load_run_results(runs_dir, selected_run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        matched_res = next(
            (r for r in raw_results if r.peptide_id.upper() == peptide_id.upper()), None
        )
        if matched_res is None:
            raise HTTPException(
                status_code=404,
                detail=f"Peptídeo '{peptide_id}' não encontrado na run '{selected_run_id}'.",
            )

        matched_pep = next(
            (p for p in peptides if p.peptide_id.upper() == peptide_id.upper()), None
        )
        if matched_pep is None:
            raise HTTPException(
                status_code=404, detail=f"Metadados de '{peptide_id}' não encontrados."
            )

        target_pose = next(
            (p for p in matched_res.poses if p.pose_rank == pose_rank), matched_res.poses[0]
        )
        script_text = generate_pymol_script(matched_pep, target, target_pose)

        if download:
            filename = f"{matched_pep.peptide_id}_pose{target_pose.pose_rank}_pymol.pml"
            return PlainTextResponse(
                script_text,
                media_type="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

        return {
            "peptide_id": matched_pep.peptide_id,
            "target_id": target.target_id,
            "pose_rank": target_pose.pose_rank,
            "docking_score": target_pose.docking_score,
            "script": script_text,
            "disclaimer": HYPOTHESIS_DISCLAIMER,
        }

    return app


app = create_app()
