"""Motor determinístico `MockDockingEngine` para desenvolvimento e testes automatizados."""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime

from ic_core.io import stable_hash

from peptide_docking.domain import (
    HYPOTHESIS_DISCLAIMER,
    DockingJob,
    DockingPose,
    DockingResult,
    InteractionType,
    PoseContact,
)

MOCK_ENGINE_NAME: str = "mock"
MOCK_ENGINE_VERSION: str = "1.0.0-deterministic"

BASE_SCORE_OFFSET: float = -145.0
CHARGE_COMPLEMENTARITY_WEIGHT: float = -4.2
HYDROPHOBIC_POCKET_WEIGHT: float = -7.5
AROMATIC_BONUS_WEIGHT: float = -5.8
OPTIMAL_LENGTH_CENTER: float = 18.0
LENGTH_PENALTY_FACTOR: float = 0.65
POSE_ENERGY_STEP_MIN: float = 2.8
POSE_ENERGY_STEP_MAX: float = 8.4
BASE_INTERFACE_AREA_A2: float = 680.0
AREA_PER_RESIDUE_A2: float = 24.5
MIN_CONTACT_DISTANCE_A: float = 2.4
MAX_CONTACT_DISTANCE_A: float = 4.6

_INTERACTION_TYPES: tuple[InteractionType, ...] = (
    "hydrogen_bond",
    "salt_bridge",
    "hydrophobic",
    "pi_stacking",
)


def _derive_rng_seed(job: DockingJob, params_hash: str) -> int:
    material = (
        f"{job.seed}:{job.peptide.peptide_id}:{job.peptide.sequence}:"
        f"{job.target.target_id}:{params_hash}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


class MockDockingEngine:
    """Motor sintético determinístico inspirado em complementaridade físico-química."""

    @property
    def name(self) -> str:
        return MOCK_ENGINE_NAME

    @property
    def version(self) -> str:
        return MOCK_ENGINE_VERSION

    def submit(self, job: DockingJob) -> DockingResult:
        params_payload = {
            "engine": self.name,
            "version": self.version,
            "seed": job.seed,
            "num_poses": job.num_poses,
            "target_sha256": job.target.structure_sha256,
            "parameters": job.parameters,
        }
        params_hash = stable_hash(params_payload)
        rng = random.Random(_derive_rng_seed(job, params_hash))

        pep = job.peptide
        seq = pep.sequence
        aromatic_fraction = (seq.count("W") + seq.count("F") + seq.count("Y")) / len(seq)
        length_deviation = abs(len(seq) - OPTIMAL_LENGTH_CENTER)

        # Hipótese sintética reprodutível: bolso aniônico/hidrofóbico de Leishmania
        deterministic_top_score = (
            BASE_SCORE_OFFSET
            + CHARGE_COMPLEMENTARITY_WEIGHT * max(0.0, min(6.0, pep.net_charge_ph7))
            + HYDROPHOBIC_POCKET_WEIGHT * max(-0.5, min(2.0, pep.gravy_hydropathy))
            + AROMATIC_BONUS_WEIGHT * (aromatic_fraction * 10.0)
            + LENGTH_PENALTY_FACTOR * length_deviation
            + rng.uniform(-12.0, 12.0)
        )
        top_score = round(deterministic_top_score, 2)

        target_residues = job.target.binding_site_residues
        poses: list[DockingPose] = []
        current_score = top_score
        contacted_target_residues: set[str] = set()

        for rank in range(1, job.num_poses + 1):
            if rank > 1:
                current_score = round(
                    current_score + rng.uniform(POSE_ENERGY_STEP_MIN, POSE_ENERGY_STEP_MAX),
                    2,
                )
            rmsd = 0.0 if rank == 1 else round(rng.uniform(0.85, 4.90) + 0.35 * (rank - 1), 2)
            interface_area = round(
                BASE_INTERFACE_AREA_A2 + AREA_PER_RESIDUE_A2 * len(seq) + rng.uniform(-45.0, 65.0),
                1,
            )

            num_contacts = min(len(target_residues), rng.randint(2, max(2, len(target_residues))))
            chosen_target_res = rng.sample(target_residues, k=num_contacts)
            contacts: list[PoseContact] = []
            for t_res in chosen_target_res:
                pep_idx = rng.randint(1, len(seq))
                pep_aa = seq[pep_idx - 1]
                interaction = self._infer_interaction(pep_aa, rng)
                dist = round(rng.uniform(MIN_CONTACT_DISTANCE_A, MAX_CONTACT_DISTANCE_A), 2)
                contacts.append(
                    PoseContact(
                        peptide_residue_index=pep_idx,
                        peptide_residue=pep_aa,
                        target_residue_id=t_res.residue_id,
                        distance_angstrom=dist,
                        interaction_type=interaction,
                    )
                )
                if rank == 1:
                    contacted_target_residues.add(t_res.residue_id)

            poses.append(
                DockingPose(
                    pose_rank=rank,
                    docking_score=current_score,
                    rmsd_to_top_pose_angstrom=rmsd,
                    interface_area_angstrom2=interface_area,
                    contacts=contacts,
                )
            )

        top3_scores = [p.docking_score for p in poses[:3]]
        mean_top3 = round(sum(top3_scores) / len(top3_scores), 2)
        contact_ratio = round(len(contacted_target_residues) / len(target_residues), 3)

        return DockingResult(
            job_id=job.job_id,
            run_id=job.run_id,
            peptide_id=pep.peptide_id,
            target_id=job.target.target_id,
            engine_name=self.name,
            engine_version=self.version,
            status="completed",
            seed=job.seed,
            parameters_hash=params_hash,
            top_score=poses[0].docking_score,
            mean_top3_score=mean_top3,
            binding_site_contact_ratio=contact_ratio,
            poses=poses,
            completed_at_utc=datetime.now(tz=UTC).isoformat(),
            hypothesis_disclaimer=HYPOTHESIS_DISCLAIMER,
        )

    @staticmethod
    def _infer_interaction(aa: str, rng: random.Random) -> InteractionType:
        if aa in ("K", "R", "D", "E"):
            return "salt_bridge"
        if aa in ("F", "W", "Y", "H"):
            return "pi_stacking"
        if aa in ("A", "I", "L", "M", "V"):
            return "hydrophobic"
        if aa in ("S", "T", "N", "Q"):
            return "hydrogen_bond"
        return rng.choice(_INTERACTION_TYPES)
