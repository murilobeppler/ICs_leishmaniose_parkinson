"""Ranking, filtragem multifatorial e agregação estatística para triagem de docking."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from peptide_docking.domain import (
    HYPOTHESIS_DISCLAIMER,
    DockingResult,
    Peptide,
    TriageTier,
)

HIGH_PRIORITY_PERCENTILE_CUTOFF: float = 10.0
MEDIUM_PRIORITY_PERCENTILE_CUTOFF: float = 30.0
MIN_CONTACT_RATIO_FOR_HIGH_PRIORITY: float = 0.50


class RankingCriteria(BaseModel):
    """Critérios de filtragem e corte para priorização de candidatos na triagem."""

    model_config = ConfigDict(frozen=True)

    max_top_score: float | None = Field(
        default=None,
        description="Corte superior de score energético (ex.: -175.0 filtra scores <= -175.0)",
    )
    min_binding_site_contact_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fração mínima de resíduos do sítio ativo contatados pela pose #1",
    )
    min_length: int | None = Field(default=None, ge=5)
    max_length: int | None = Field(default=None, le=60)
    min_net_charge_ph7: float | None = Field(default=None)
    max_gravy_hydropathy: float | None = Field(default=None)
    source_family: str | None = Field(default=None)
    search_query: str | None = Field(default=None)
    top_k: int | None = Field(default=None, ge=1)


class RankedCandidate(BaseModel):
    """Item ranqueado combinando metadados do peptídeo, resultado de docking e nível de triagem."""

    model_config = ConfigDict(frozen=True)

    rank: int = Field(..., ge=1)
    peptide: Peptide
    result: DockingResult
    z_score: float = Field(
        ...,
        description="Z-score do top_score na distribuição da run (mais negativo = mais favorável)",
    )
    percentile: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentil na distribuição da run (menor valor = topo da triagem)",
    )
    triage_tier: TriageTier
    hypothesis_note: str = Field(
        default=(
            "Candidato priorizado exclusivamente para triagem in silico; "
            "requer validação experimental ortogonal in vitro."
        )
    )


class ResidueHotspotSummary(BaseModel):
    """Frequência de contatos preditos em cada resíduo do bolso da proteína-alvo."""

    model_config = ConfigDict(frozen=True)

    target_residue_id: str
    contact_count: int
    candidate_fraction: float


class RunRankingSummary(BaseModel):
    """Resumo agregado de uma run de docking para inspeção científica."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    engine_name: str
    seed: int
    total_evaluated: int
    filtered_count: int
    best_top_score: float
    median_top_score: float
    mean_top_score: float
    std_top_score: float
    high_priority_count: int
    medium_priority_count: int
    low_priority_count: int
    residue_hotspots: list[ResidueHotspotSummary]
    hypothesis_disclaimer: str = Field(default=HYPOTHESIS_DISCLAIMER)


def _compute_mean_std(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    mean_val = sum(values) / len(values)
    if len(values) < 2:
        return mean_val, 1.0
    variance = sum((v - mean_val) ** 2 for v in values) / len(values)
    std_val = math.sqrt(variance)
    return mean_val, std_val if std_val > 1e-9 else 1.0


def _assign_triage_tier(percentile: float, contact_ratio: float) -> TriageTier:
    if (
        percentile <= HIGH_PRIORITY_PERCENTILE_CUTOFF
        and contact_ratio >= MIN_CONTACT_RATIO_FOR_HIGH_PRIORITY
    ):
        return "prioridade_alta_triagem"
    if percentile <= MEDIUM_PRIORITY_PERCENTILE_CUTOFF:
        return "prioridade_media_triagem"
    return "baixa_prioridade_triagem"


def rank_docking_results(
    peptides: Sequence[Peptide],
    results: Sequence[DockingResult],
    criteria: RankingCriteria | None = None,
) -> list[RankedCandidate]:
    """Ordena (menor `top_score` primeiro), normaliza e filtra resultados de docking."""
    active_criteria = criteria or RankingCriteria()
    peptides_by_id = {p.peptide_id: p for p in peptides}

    valid_pairs: list[tuple[Peptide, DockingResult]] = []
    for res in results:
        if res.status == "failed":
            continue
        pep = peptides_by_id.get(res.peptide_id)
        if pep is not None:
            valid_pairs.append((pep, res))

    if not valid_pairs:
        return []

    # Ordenação determinística global: top_score ascendente, mean_top3_score ascendente, peptide_id
    valid_pairs.sort(
        key=lambda item: (item[1].top_score, item[1].mean_top3_score, item[0].peptide_id)
    )

    all_scores = [res.top_score for _, res in valid_pairs]
    mean_score, std_score = _compute_mean_std(all_scores)
    total_valid = len(valid_pairs)

    ranked_all: list[RankedCandidate] = []
    for idx, (pep, res) in enumerate(valid_pairs, start=1):
        percentile = round((idx / total_valid) * 100.0, 2)
        z_score = round((res.top_score - mean_score) / std_score, 3)
        tier = _assign_triage_tier(percentile, res.binding_site_contact_ratio)
        ranked_all.append(
            RankedCandidate(
                rank=idx,
                peptide=pep,
                result=res,
                z_score=z_score,
                percentile=percentile,
                triage_tier=tier,
            )
        )

    # Aplica filtros preservando o rank e percentil originais da run
    filtered: list[RankedCandidate] = []
    for item in ranked_all:
        pep = item.peptide
        res = item.result

        if (
            active_criteria.max_top_score is not None
            and res.top_score > active_criteria.max_top_score
        ):
            continue
        if res.binding_site_contact_ratio < active_criteria.min_binding_site_contact_ratio:
            continue
        if active_criteria.min_length is not None and pep.length < active_criteria.min_length:
            continue
        if active_criteria.max_length is not None and pep.length > active_criteria.max_length:
            continue
        if (
            active_criteria.min_net_charge_ph7 is not None
            and pep.net_charge_ph7 < active_criteria.min_net_charge_ph7
        ):
            continue
        if (
            active_criteria.max_gravy_hydropathy is not None
            and pep.gravy_hydropathy > active_criteria.max_gravy_hydropathy
        ):
            continue
        if (
            active_criteria.source_family
            and pep.source_family.lower() != active_criteria.source_family.strip().lower()
        ):
            continue
        if active_criteria.search_query:
            q = active_criteria.search_query.strip().upper()
            if (
                q not in pep.peptide_id.upper()
                and q not in pep.sequence.upper()
                and q not in pep.source_family.upper()
            ):
                continue

        filtered.append(item)

    if active_criteria.top_k is not None:
        filtered = filtered[: active_criteria.top_k]

    return filtered


def summarize_run_ranking(
    run_id: str,
    engine_name: str,
    seed: int,
    peptides: Sequence[Peptide],
    results: Sequence[DockingResult],
    criteria: RankingCriteria | None = None,
) -> RunRankingSummary:
    """Gera estatísticas globais e hotspots de contato para a run de docking."""
    all_ranked = rank_docking_results(peptides, results, criteria=None)
    filtered_ranked = (
        rank_docking_results(peptides, results, criteria=criteria)
        if criteria is not None
        else all_ranked
    )

    if not all_ranked:
        return RunRankingSummary(
            run_id=run_id,
            engine_name=engine_name,
            seed=seed,
            total_evaluated=0,
            filtered_count=0,
            best_top_score=0.0,
            median_top_score=0.0,
            mean_top_score=0.0,
            std_top_score=0.0,
            high_priority_count=0,
            medium_priority_count=0,
            low_priority_count=0,
            residue_hotspots=[],
        )

    scores = [item.result.top_score for item in all_ranked]
    mean_score, std_score = _compute_mean_std(scores)
    mid = len(scores) // 2
    median_score = scores[mid] if len(scores) % 2 == 1 else (scores[mid - 1] + scores[mid]) / 2.0

    tier_counts = Counter(item.triage_tier for item in all_ranked)
    residue_counter: Counter[str] = Counter()
    for item in all_ranked:
        top_pose = item.result.poses[0]
        unique_res_in_top_pose = {c.target_residue_id for c in top_pose.contacts}
        for r_id in unique_res_in_top_pose:
            residue_counter[r_id] += 1

    total_eval = len(all_ranked)
    hotspots = [
        ResidueHotspotSummary(
            target_residue_id=res_id,
            contact_count=count,
            candidate_fraction=round(count / total_eval, 3),
        )
        for res_id, count in residue_counter.most_common()
    ]

    return RunRankingSummary(
        run_id=run_id,
        engine_name=engine_name,
        seed=seed,
        total_evaluated=total_eval,
        filtered_count=len(filtered_ranked),
        best_top_score=round(scores[0], 2),
        median_top_score=round(median_score, 2),
        mean_top_score=round(mean_score, 2),
        std_top_score=round(std_score, 2),
        high_priority_count=tier_counts["prioridade_alta_triagem"],
        medium_priority_count=tier_counts["prioridade_media_triagem"],
        low_priority_count=tier_counts["baixa_prioridade_triagem"],
        residue_hotspots=hotspots,
    )
