"""Carregamento, validação e propriedades físico-químicas da biblioteca de 634 peptídeos."""

from __future__ import annotations

import hashlib
import random
from pathlib import Path

import pandas as pd
from ic_core.io import read_json, read_tabular, write_json, write_tabular

from peptide_docking.domain import (
    EXPECTED_LIBRARY_SIZE,
    BindingSiteResidue,
    Peptide,
    Target,
)

# Massas de resíduos anidros (Da) + H2O terminal (18.015 Da)
_AA_WEIGHT_DA: dict[str, float] = {
    "A": 71.08,
    "C": 103.14,
    "D": 115.09,
    "E": 129.12,
    "F": 147.18,
    "G": 57.05,
    "H": 137.14,
    "I": 113.16,
    "K": 128.17,
    "L": 113.16,
    "M": 131.20,
    "N": 114.10,
    "P": 97.12,
    "Q": 128.13,
    "R": 156.19,
    "S": 87.08,
    "T": 101.11,
    "V": 99.13,
    "W": 186.21,
    "Y": 163.18,
}

# Escala de hidropatia de Kyte & Doolittle
_KYTE_DOOLITTLE: dict[str, float] = {
    "A": 1.8,
    "C": 2.5,
    "D": -3.5,
    "E": -3.5,
    "F": 2.8,
    "G": -0.4,
    "H": -3.2,
    "I": 4.5,
    "K": -3.9,
    "L": 3.8,
    "M": 1.9,
    "N": -3.5,
    "P": -1.6,
    "Q": -3.5,
    "R": -4.5,
    "S": -0.8,
    "T": -0.7,
    "V": 4.2,
    "W": -0.9,
    "Y": -1.3,
}

WATER_TERMINAL_MASS_DA: float = 18.015


def compute_peptide_properties(sequence: str) -> dict[str, float]:
    """Calcula massa molecular, carga líquida (pH 7.4), GRAVY e ponto isoelétrico estimado."""
    seq = sequence.strip().upper()
    if not seq:
        raise ValueError("Sequência peptídica vazia.")

    mw = WATER_TERMINAL_MASS_DA + sum(_AA_WEIGHT_DA[aa] for aa in seq)
    gravy = sum(_KYTE_DOOLITTLE[aa] for aa in seq) / len(seq)

    pos = seq.count("K") + seq.count("R") + 0.1 * seq.count("H")
    neg = seq.count("D") + seq.count("E")
    net_charge = round(pos - neg, 2)

    base_pi = 6.8 + 0.55 * (seq.count("K") + seq.count("R") - seq.count("D") - seq.count("E"))
    isoelectric_point = round(max(2.5, min(12.5, base_pi)), 2)

    return {
        "molecular_weight_da": round(mw, 2),
        "net_charge_ph7": net_charge,
        "gravy_hydropathy": round(gravy, 3),
        "isoelectric_point": isoelectric_point,
    }


def save_peptide_library(peptides: list[Peptide], path: Path) -> Path:
    """Persiste uma lista validada de `Peptide` em formato Parquet ou CSV."""
    records = [p.model_dump() for p in peptides]
    df = pd.DataFrame(records)
    return write_tabular(df, path)


def load_peptide_library(
    path: Path,
    expected_count: int | None = EXPECTED_LIBRARY_SIZE,
) -> list[Peptide]:
    """Carrega e valida a biblioteca de peptídeos a partir de Parquet ou CSV.

    Verifica unicidade de `peptide_id`, unicidade de `sequence`, validade de cada
    resíduo e, quando `expected_count` não for `None`, exige exatamente a contagem esperada
    (padrão = 634 peptídeos candidatos).
    """
    df = read_tabular(path)
    peptides: list[Peptide] = []
    seen_ids: set[str] = set()
    seen_sequences: set[str] = set()

    for row in df.to_dict(orient="records"):
        record = {str(k): v for k, v in row.items()}
        peptide = Peptide.model_validate(record)
        if peptide.peptide_id in seen_ids:
            raise ValueError(f"ID de peptídeo duplicado na biblioteca: {peptide.peptide_id}")
        if peptide.sequence in seen_sequences:
            raise ValueError(
                f"Sequência peptídica duplicada ({peptide.sequence}) em {peptide.peptide_id}"
            )
        seen_ids.add(peptide.peptide_id)
        seen_sequences.add(peptide.sequence)
        peptides.append(peptide)

    if expected_count is not None and len(peptides) != expected_count:
        raise ValueError(
            f"A biblioteca em '{path}' possui {len(peptides)} peptídeos, "
            f"mas o esperado é exatamente {expected_count}."
        )
    return peptides


def save_target(target: Target, path: Path) -> Path:
    """Salva os metadados da proteína-alvo de Leishmania em JSON."""
    return write_json(target.model_dump(), path)


def load_target(path: Path) -> Target:
    """Carrega e valida os metadados da proteína-alvo de Leishmania."""
    raw = read_json(path)
    return Target.model_validate(raw)


_SYNTHETIC_FAMILIES: tuple[tuple[str, str, str], ...] = (
    ("Temporin-like", "FLPLIGRVLSGIL", "Anfipático curto derivado de anfíbios"),
    ("Dermaseptin-like", "ALWKTMLKKLGTMALHAGKAALGAAADTISQGTQ", "Catiônico alfa-helicoidal"),
    ("Bombinin-like", "GIGGALLSAAKVGLKGLAKGLAEHFAN", "Peptídeo antimicrobiano seletivo"),
    ("Magainin-like", "GIGKFLHSAKKFGKAFVGEIMNS", "Hélice anfipática clássica"),
    ("Cathelicidin-like", "LLGDFFRKSKEKIGKEFKRIVQRIKDFLRNLVPRTES", "Rico em arginina/lisina"),
    ("Cecropin-like", "KWKLFKKIEKVGQNIRDGIIKAGPAVAVVGQATQIAK", "Domínio N-terminal básico"),
    (
        "Defensin-beta-mimetico",
        "GIINTLQKYYCRVRGGRCAVLSCLPKEEQIGKCSTRGRKCCRRKK",
        "Motivo rico em cisteína/básico",
    ),
    ("DeNovo-AntiLeish", "RWKIFKKIEKVGRNIRDGIIKAGP", "Desenho racional focado em bolso aniônico"),
)

_CANONICAL_ALPHABET: str = "ACDEFGHIKLMNPQRSTVWY"


def build_synthetic_target() -> Target:
    """Gera a definição sintética reprodutível da proteína-alvo de Leishmania sem ortólogo humano.

    Alvo modelado: Tripanotiona Redutase (TryR) de Leishmania infantum — enzima essencial
    do metabolismo redox tripanossomatídeo, ausente em mamíferos (que utilizam Glutationa Redutase
    com geometria e carga de sítio ativo distintas).
    """
    residues = [
        BindingSiteResidue(
            residue_id="CYS52",
            chain="A",
            residue_name="CYS",
            pocket_role="Ditiol catalítico redox-ativo (nucleófilo)",
        ),
        BindingSiteResidue(
            residue_id="CYS57",
            chain="A",
            residue_name="CYS",
            pocket_role="Ditiol catalítico redox-ativo (par dissulfeto)",
        ),
        BindingSiteResidue(
            residue_id="HIS461",
            chain="B",
            residue_name="HIS",
            pocket_role="Base catalítica de transferência de prótons",
        ),
        BindingSiteResidue(
            residue_id="GLU466",
            chain="B",
            residue_name="GLU",
            pocket_role="Estabilização eletrostática da díade His461",
        ),
        BindingSiteResidue(
            residue_id="TRP21",
            chain="A",
            residue_name="TRP",
            pocket_role="Parede hidrofóbica/aromática do sub-bolso espermidina",
        ),
        BindingSiteResidue(
            residue_id="MET113",
            chain="A",
            residue_name="MET",
            pocket_role="Ancoragem hidrofóbica da fenda específica de tripanotiona",
        ),
        BindingSiteResidue(
            residue_id="TYR110",
            chain="A",
            residue_name="TYR",
            pocket_role="Reconhecimento por ligação de hidrogênio na entrada do sítio",
        ),
        BindingSiteResidue(
            residue_id="GLU18",
            chain="A",
            residue_name="GLU",
            pocket_role="Borda aniônica seletiva ausente no bolso humano",
        ),
    ]
    structure_signature = "SYNTHETIC_LEISHMANIA_INFANTUM_TRYR_DIMER_POCKET_V1"
    sha = hashlib.sha256(structure_signature.encode("utf-8")).hexdigest()

    return Target(
        target_id="LINJ_TRYR_01",
        name="Tripanotiona Redutase (TryR) — Sítio Catalítico Exclusivo",
        organism="Leishmania infantum",
        uniprot_id="A4HSF7",
        has_human_ortholog=False,
        ortholog_Verification_note=(
            "Enzima do sistema tripanotiona exclusiva de Kinetoplastida; "
            "sem ortólogo funcional direto em Homo sapiens (ausência validada)."
        ),
        binding_site_residues=residues,
        structure_sha256=sha,
    )


def build_synthetic_peptide_library(
    count: int = EXPECTED_LIBRARY_SIZE,
    seed: int = 42,
) -> list[Peptide]:
    """Gera de forma determinística a biblioteca sintética de `count` (634) peptídeos."""
    rng = random.Random(seed)
    peptides: list[Peptide] = []
    seen_sequences: set[str] = set()

    idx = 1
    attempt = 0
    while len(peptides) < count:
        family_name, template, note = _SYNTHETIC_FAMILIES[attempt % len(_SYNTHETIC_FAMILIES)]
        attempt += 1

        # Gera variante sintética controlada com comprimento entre 10 e 38 resíduos
        target_len = rng.randint(10, 38)
        chars: list[str] = []
        for pos in range(target_len):
            base_aa = template[pos % len(template)]
            if rng.random() < 0.38:
                # Mutação pontual favorecendo resíduos anfipáticos/catiônicos ou aromáticos
                pool = "KKRRLLIIFFWWYYAAVVGGSSTT" + _CANONICAL_ALPHABET
                chars.append(rng.choice(pool))
            else:
                chars.append(base_aa)

        seq = "".join(chars)
        if seq in seen_sequences:
            continue

        seen_sequences.add(seq)
        props = compute_peptide_properties(seq)
        pep_id = f"PEP_{idx:04d}"
        peptides.append(
            Peptide(
                peptide_id=pep_id,
                sequence=seq,
                length=len(seq),
                molecular_weight_da=props["molecular_weight_da"],
                net_charge_ph7=props["net_charge_ph7"],
                gravy_hydropathy=props["gravy_hydropathy"],
                isoelectric_point=props["isoelectric_point"],
                source_family=family_name,
                notes=f"{note} (variante sintética seed={seed})",
            )
        )
        idx += 1

    return peptides
