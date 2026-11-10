"""Testes unitários e de integração do Módulo A (`peptide-docking`)."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from ic_core.paths import find_repo_root
from pydantic import ValidationError

from peptide_docking.api import create_app
from peptide_docking.config import PeptideDockingSettings
from peptide_docking.domain import (
    EXPECTED_LIBRARY_SIZE,
    HYPOTHESIS_DISCLAIMER,
    DockingJob,
    Peptide,
)
from peptide_docking.engines.base import (
    AutomatedSubmissionNotPermittedError,
    DockingEngine,
    DockingEngineError,
)
from peptide_docking.engines.hpepdock import HPEPDOCKEngine
from peptide_docking.engines.mock import MockDockingEngine
from peptide_docking.library import (
    build_synthetic_peptide_library,
    build_synthetic_target,
    compute_peptide_properties,
    load_peptide_library,
    load_target,
    save_peptide_library,
    save_target,
)
from peptide_docking.pipeline import DockingPipeline, list_runs, load_run_results
from peptide_docking.ranking import RankingCriteria, rank_docking_results, summarize_run_ranking


def test_domain_validation_and_selectivity_rule() -> None:
    props = compute_peptide_properties("FLPLIGRVLSGIL")
    pep = Peptide(
        peptide_id="PEP_0001",
        sequence="FLPLIGRVLSGIL",
        length=13,
        molecular_weight_da=props["molecular_weight_da"],
        net_charge_ph7=props["net_charge_ph7"],
        gravy_hydropathy=props["gravy_hydropathy"],
        isoelectric_point=props["isoelectric_point"],
        source_family="Temporin-like",
    )
    assert pep.length == 13

    # Sequência com caractere não canônico ('X' ou 'B') deve falhar
    with pytest.raises(ValidationError):
        Peptide(
            peptide_id="PEP_BAD",
            sequence="FLPLXGRVLSGIL",
            length=13,
            molecular_weight_da=1400.0,
            net_charge_ph7=1.0,
            gravy_hydropathy=1.2,
            isoelectric_point=9.5,
            source_family="Invalid",
        )

    # Alvo com ortólogo humano deve ser rejeitado (regra de seletividade anti-Leishmania)
    target = build_synthetic_target()
    assert target.has_human_ortholog is False
    with pytest.raises(ValidationError, match="ortólogo humano"):
        target.model_copy(update={"has_human_ortholog": True}).model_validate(
            {**target.model_dump(), "has_human_ortholog": True}
        )


def test_synthetic_library_634_roundtrip(tmp_path: Path) -> None:
    peptides = build_synthetic_peptide_library(count=EXPECTED_LIBRARY_SIZE, seed=42)
    assert len(peptides) == 634

    lib_path = save_peptide_library(peptides, tmp_path / "peptides_634.parquet")
    loaded = load_peptide_library(lib_path, expected_count=EXPECTED_LIBRARY_SIZE)
    assert len(loaded) == 634
    assert loaded[0].peptide_id == "PEP_0001"
    assert loaded[-1].peptide_id == "PEP_0634"

    target = build_synthetic_target()
    target_path = save_target(target, tmp_path / "target.json")
    loaded_target = load_target(target_path)
    assert loaded_target.target_id == target.target_id

    # Contagem incorreta deve levantar ValueError quando expected_count=634
    subset_path = save_peptide_library(peptides[:15], tmp_path / "subset.parquet")
    with pytest.raises(ValueError, match="esperado é exatamente 634"):
        load_peptide_library(subset_path, expected_count=EXPECTED_LIBRARY_SIZE)


def test_mock_engine_determinism_and_protocol() -> None:
    engine = MockDockingEngine()
    assert isinstance(engine, DockingEngine)

    peptides = build_synthetic_peptide_library(count=2, seed=42)
    target = build_synthetic_target()
    job = DockingJob(
        job_id="job_1",
        run_id="run_test",
        peptide=peptides[0],
        target=target,
        engine_name=engine.name,
        seed=42,
        num_poses=5,
        parameters={"exhaustiveness": 8},
    )

    res1 = engine.submit(job)
    res2 = engine.submit(job)
    assert res1.top_score == res2.top_score
    assert res1.mean_top3_score == res2.mean_top3_score
    assert len(res1.poses) == 5
    assert res1.poses[0].rmsd_to_top_pose_angstrom == 0.0
    assert res1.hypothesis_disclaimer == HYPOTHESIS_DISCLAIMER


def test_hpepdock_adapter_tos_guard_cache_and_rate_limit(tmp_path: Path) -> None:
    peptides = build_synthetic_peptide_library(count=2, seed=42)
    target = build_synthetic_target()
    job = DockingJob(
        job_id="job_hpep_1",
        run_id="run_hpep",
        peptide=peptides[0],
        target=target,
        engine_name="hpepdock",
        seed=42,
    )

    # 1. Sem credencial e stub_fallback=False -> bloqueia explicitamente por Termos de Uso
    strict_engine = HPEPDOCKEngine(
        cache_root=tmp_path / "cache_strict",
        allow_automated_submission=False,
        stub_fallback=False,
    )
    with pytest.raises(AutomatedSubmissionNotPermittedError, match="Termos de Uso"):
        strict_engine.submit(job)

    # 2. Modo stub padrão documentado + cache em disco na segunda chamada
    stub_engine = HPEPDOCKEngine(
        cache_root=tmp_path / "cache_stub",
        allow_automated_submission=False,
        stub_fallback=True,
    )
    first = stub_engine.submit(job)
    second = stub_engine.submit(job)
    assert first.status == "stub_blocked"
    assert second.status == "cached"
    assert first.top_score == second.top_score

    # 3. Rate limit e retry quando autorizado
    slept: list[float] = []
    clock_now = [100.0]
    attempts = 0

    def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        clock_now[0] += seconds

    def fake_clock() -> float:
        return clock_now[0]

    def flaky_transport(j: DockingJob) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("Falha transitória simulada")
        base_res = MockDockingEngine().submit(j)
        return base_res.model_copy(update={"engine_name": "hpepdock"}).model_dump()

    auth_engine = HPEPDOCKEngine(
        cache_root=tmp_path / "cache_auth",
        api_token="token_institucional_teste",
        allow_automated_submission=True,
        min_interval_seconds=30.0,
        max_retries=2,
        sleep_fn=fake_sleep,
        clock_fn=fake_clock,
        transport_fn=flaky_transport,
    )
    res_auth = auth_engine.submit(job)
    assert res_auth.status == "completed"
    assert attempts == 2
    assert len(slept) >= 1

    # Submissão de um segundo peptídeo distinto logo em seguida deve acionar rate limit de 30s
    job2 = job.model_copy(update={"job_id": "job_hpep_2", "peptide": peptides[1]})
    auth_engine.submit(job2)
    assert any(s >= 29.9 for s in slept)

    # Exaustão de retries levanta DockingEngineError
    failing_engine = HPEPDOCKEngine(
        cache_root=tmp_path / "cache_fail",
        api_token="token_institucional_teste",
        allow_automated_submission=True,
        min_interval_seconds=1.0,
        max_retries=1,
        sleep_fn=fake_sleep,
        clock_fn=fake_clock,
        transport_fn=lambda _: (_ for _ in ()).throw(RuntimeError("Servidor indisponível")),
    )
    with pytest.raises(DockingEngineError, match="após 2 tentativas"):
        failing_engine.submit(job)


def test_pipeline_resumable_and_idempotent_batches(tmp_path: Path) -> None:
    peptides = build_synthetic_peptide_library(count=25, seed=42)
    target = build_synthetic_target()
    engine = MockDockingEngine()
    pipeline = DockingPipeline(runs_dir=tmp_path / "runs", engine=engine, batch_size=10)

    # Executa apenas o primeiro lote de 10 peptídeos (simulando interrupção após lote 1)
    manifest_part, results_part = pipeline.run_batch_screening(
        peptides=peptides,
        target=target,
        seed=42,
        run_id="run_resumable_test",
        max_batches=1,
    )
    assert manifest_part.status == "partial"
    assert manifest_part.completed_jobs == 10
    assert manifest_part.cached_jobs == 0
    assert len(results_part) == 10

    # Retoma a mesma run sem limite de lotes: os 10 primeiros vêm do cache e os 15 restantes rodam
    manifest_full, results_full = pipeline.run_batch_screening(
        peptides=peptides,
        target=target,
        seed=42,
        run_id="run_resumable_test",
    )
    assert manifest_full.status == "completed"
    assert manifest_full.total_jobs == 25
    assert manifest_full.completed_jobs == 25
    assert manifest_full.cached_jobs == 10
    assert len(results_full) == 25

    runs = list_runs(tmp_path / "runs")
    assert len(runs) == 1
    assert runs[0].run_id == "run_resumable_test"
    disk_results = load_run_results(tmp_path / "runs", "run_resumable_test")
    assert len(disk_results) == 25


def test_ranking_filtering_and_summary(tmp_path: Path) -> None:
    peptides = build_synthetic_peptide_library(count=40, seed=42)
    target = build_synthetic_target()
    pipeline = DockingPipeline(
        runs_dir=tmp_path / "runs",
        engine=MockDockingEngine(),
        batch_size=10,
    )
    manifest, results = pipeline.run_batch_screening(
        peptides=peptides,
        target=target,
        seed=42,
        run_id="run_rank_test",
    )

    ranked = rank_docking_results(peptides, results)
    assert len(ranked) == 40
    assert ranked[0].rank == 1
    assert ranked[0].result.top_score <= ranked[-1].result.top_score
    assert "triagem" in ranked[0].triage_tier

    criteria = RankingCriteria(
        min_binding_site_contact_ratio=0.25,
        min_net_charge_ph7=1.0,
        top_k=5,
    )
    filtered = rank_docking_results(peptides, results, criteria=criteria)
    assert 1 <= len(filtered) <= 5
    assert all(item.peptide.net_charge_ph7 >= 1.0 for item in filtered)

    summary = summarize_run_ranking(
        run_id=manifest.run_id,
        engine_name=manifest.engine_name,
        seed=manifest.seed,
        peptides=peptides,
        results=results,
        criteria=criteria,
    )
    assert summary.total_evaluated == 40
    assert summary.filtered_count == len(filtered)
    assert len(summary.residue_hotspots) > 0
    assert summary.hypothesis_disclaimer == HYPOTHESIS_DISCLAIMER


def test_fastapi_endpoints_on_synthetic_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PEPTIDE_LIBRARY_PATH", str(tmp_path / "peptides_634.parquet"))
    monkeypatch.setenv("PEPTIDE_TARGET_PATH", str(tmp_path / "target.json"))
    monkeypatch.setenv("PEPTIDE_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("IC_CACHE_DIR", str(tmp_path / "cache"))

    settings = PeptideDockingSettings()
    client = TestClient(create_app(settings))

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["library_size"] == 634
    assert health.json()["has_human_ortholog"] is False

    pep_resp = client.get("/peptides?limit=15&min_charge=1.0")
    assert pep_resp.status_code == 200
    pep_data = pep_resp.json()
    assert pep_data["total_library_size"] == 634
    assert len(pep_data["items"]) <= 15

    runs_resp = client.get("/runs")
    assert runs_resp.status_code == 200
    assert len(runs_resp.json()) >= 1

    res_resp = client.get("/results?top_k=10")
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["summary"]["total_evaluated"] == 634
    assert len(res_data["candidates"]) == 10
    assert "hipótese computacional" in res_data["hypothesis_disclaimer"]

    # Test PyMOL export endpoint
    first_pep_id = res_data["candidates"][0]["peptide"]["peptide_id"]
    first_run_id = res_data["manifest"]["run_id"]
    pymol_resp = client.get(f"/results/{first_run_id}/{first_pep_id}/pymol")
    assert pymol_resp.status_code == 200
    pymol_data = pymol_resp.json()
    assert "reinitialize" in pymol_data["script"]
    assert "cat_res" in pymol_data["script"]
    assert "zoom" in pymol_data["script"]

    # Test PyMOL script download attachment
    dl_resp = client.get(f"/results/{first_run_id}/{first_pep_id}/pymol?download=true")
    assert dl_resp.status_code == 200
    assert "attachment" in dl_resp.headers.get("Content-Disposition", "")
    assert dl_resp.text.startswith("# ===")


def test_module_a_never_imports_module_b() -> None:
    repo_root = find_repo_root()
    mod_a_dir = repo_root / "modules" / "peptide-docking" / "backend"
    for py_file in mod_a_dir.rglob("*.py"):
        if ".venv" in py_file.parts:
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("fog_gnn")
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("fog_gnn")
