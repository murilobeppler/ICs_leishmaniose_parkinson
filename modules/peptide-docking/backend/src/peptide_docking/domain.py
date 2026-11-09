"""Entidades de domínio do Módulo A (`peptide-docking`)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EXPECTED_LIBRARY_SIZE: int = 634
MIN_PEPTIDE_LENGTH: int = 5
MAX_PEPTIDE_LENGTH: int = 60
DEFAULT_BATCH_SIZE: int = 10
DEFAULT_NUM_POSES: int = 5
VALID_AMINO_ACIDS: frozenset[str] = frozenset("ACDEFGHIKLMNPQRSTVWY")

HYPOTHESIS_DISCLAIMER: str = (
    "AVISO METODOLÓGICO: O score de docking molecular representa exclusivamente uma "
    "hipótese computacional de afinidade/complementaridade estérica para priorização "
    "de triagem in silico. Não constitui evidência de atividade biológica in vitro ou in vivo."
)

InteractionType = Literal["hydrogen_bond", "salt_bridge", "hydrophobic", "pi_stacking"]
JobStatus = Literal["completed", "cached", "stub_blocked", "failed"]
RunStatus = Literal["running", "completed", "partial"]
TriageTier = Literal[
    "prioridade_alta_triagem",
    "prioridade_media_triagem",
    "baixa_prioridade_triagem",
]


class Peptide(BaseModel):
    """Candidato peptídico pertencente à biblioteca de triagem contra Leishmania."""

    model_config = ConfigDict(frozen=True)

    peptide_id: str = Field(..., min_length=3, description="Identificador único (ex.: PEP_0001)")
    sequence: str = Field(
        ...,
        min_length=MIN_PEPTIDE_LENGTH,
        max_length=MAX_PEPTIDE_LENGTH,
        description="Sequência primária em código de 1 letra de aminoácidos canônicos",
    )
    length: int = Field(..., ge=MIN_PEPTIDE_LENGTH, le=MAX_PEPTIDE_LENGTH)
    molecular_weight_da: float = Field(..., gt=0.0, description="Massa molecular estimada (Da)")
    net_charge_ph7: float = Field(..., description="Carga líquida estimada em pH 7.4")
    gravy_hydropathy: float = Field(..., description="Índice GRAVY de hidropatia média")
    isoelectric_point: float = Field(..., ge=0.0, le=14.0, description="Ponto isoelétrico estimado")
    source_family: str = Field(..., min_length=2, description="Família/origem do peptídeo")
    notes: str = Field(default="", description="Observações estruturais ou de síntese")

    @field_validator("sequence")
    @classmethod
    def validate_canonical_sequence(cls, value: str) -> str:
        seq = value.strip().upper()
        invalid = set(seq) - VALID_AMINO_ACIDS
        if invalid:
            raise ValueError(
                f"Sequência contém resíduos não canônicos inválidos: {sorted(invalid)}"
            )
        return seq

    @model_validator(mode="after")
    def validate_length_matches_sequence(self) -> Peptide:
        if self.length != len(self.sequence):
            seq_len = len(self.sequence)
            raise ValueError(
                f"Comprimento declarado ({self.length}) difere de len(sequence) ({seq_len})."
            )
        return self


class BindingSiteResidue(BaseModel):
    """Resíduo catalítico ou de bolso de ligação na proteína-alvo de Leishmania."""

    model_config = ConfigDict(frozen=True)

    residue_id: str = Field(..., min_length=2, description="Ex.: CYS52, HIS461")
    chain: str = Field(default="A", min_length=1, max_length=2)
    residue_name: str = Field(..., min_length=3, max_length=3, description="Código de 3 letras")
    pocket_role: str = Field(..., description="Papel funcional/estrutural no sítio ativo")


class Target(BaseModel):
    """Proteína-alvo de Leishmania sem ortólogo humano."""

    model_config = ConfigDict(frozen=True)

    target_id: str = Field(..., min_length=3, description="Identificador único do alvo")
    name: str = Field(..., min_length=3, description="Nome bioquímico da proteína-alvo")
    organism: str = Field(..., min_length=3, description="Espécie de Leishmania")
    uniprot_id: str = Field(..., min_length=4, description="Acesso UniProt de referência")
    has_human_ortholog: bool = Field(
        default=False,
        description="False garante seletividade e menor risco de toxicidade off-target",
    )
    ortholog_Verification_note: str = Field(
        default=(
            "Ausência confirmada contra proteoma humano "
            "(Homo sapiens, taxid:9606) via BLASTp/OrthoMCL."
        ),
        description="Nota de verificação de ausência de ortólogo humano",
    )
    binding_site_residues: list[BindingSiteResidue] = Field(..., min_length=1)
    structure_sha256: str = Field(..., min_length=16, description="Hash da estrutura de referência")

    @field_validator("has_human_ortholog")
    @classmethod
    def enforce_no_human_ortholog(cls, value: bool) -> bool:
        if value:
            raise ValueError(
                "A proteína-alvo deste módulo não pode possuir ortólogo humano "
                "(critério de seletividade contra toxicidade off-target)."
            )
        return value


class PoseContact(BaseModel):
    """Contato interatômico predito entre um resíduo do peptídeo e o sítio ativo do alvo."""

    model_config = ConfigDict(frozen=True)

    peptide_residue_index: int = Field(..., ge=1)
    peptide_residue: str = Field(..., min_length=1, max_length=3)
    target_residue_id: str = Field(..., min_length=2)
    distance_angstrom: float = Field(..., gt=0.0, le=10.0)
    interaction_type: InteractionType


class DockingPose(BaseModel):
    """Pose individual gerada pelo motor de docking para um candidato peptídico."""

    model_config = ConfigDict(frozen=True)

    pose_rank: int = Field(..., ge=1)
    docking_score: float = Field(
        ...,
        description="Score do motor (valores mais negativos = maior afinidade predita)",
    )
    rmsd_to_top_pose_angstrom: float = Field(..., ge=0.0)
    interface_area_angstrom2: float = Field(..., gt=0.0)
    contacts: list[PoseContact] = Field(default_factory=list)


class DockingJob(BaseModel):
    """Unidade de submissão de docking (1 peptídeo contra 1 proteína-alvo)."""

    model_config = ConfigDict(frozen=True)

    job_id: str = Field(..., min_length=3)
    run_id: str = Field(..., min_length=3)
    peptide: Peptide
    target: Target
    engine_name: str = Field(..., min_length=2)
    seed: int = Field(default=42, ge=0)
    num_poses: int = Field(default=DEFAULT_NUM_POSES, ge=1, le=20)
    parameters: dict[str, Any] = Field(default_factory=dict)


class DockingResult(BaseModel):
    """Resultado completo e auditável de um `DockingJob`."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    run_id: str
    peptide_id: str
    target_id: str
    engine_name: str
    engine_version: str
    status: JobStatus
    seed: int
    parameters_hash: str
    top_score: float
    mean_top3_score: float
    binding_site_contact_ratio: float = Field(..., ge=0.0, le=1.0)
    poses: list[DockingPose] = Field(..., min_length=1)
    completed_at_utc: str
    hypothesis_disclaimer: str = Field(default=HYPOTHESIS_DISCLAIMER)


class DockingRunManifest(BaseModel):
    """Manifesto reprodutível de uma execução em lote sobre a biblioteca de peptídeos."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    target_id: str
    engine_name: str
    engine_version: str
    seed: int
    batch_size: int = Field(default=DEFAULT_BATCH_SIZE, ge=1)
    total_jobs: int = Field(..., ge=0)
    completed_jobs: int = Field(..., ge=0)
    cached_jobs: int = Field(..., ge=0)
    failed_jobs: int = Field(..., ge=0)
    status: RunStatus
    parameters: dict[str, Any] = Field(default_factory=dict)
    started_at_utc: str
    updated_at_utc: str
    hypothesis_disclaimer: str = Field(default=HYPOTHESIS_DISCLAIMER)
