"""Exportador de scripts PyMOL (.pml) e sessões (.pse) para poses de docking peptídico."""

from __future__ import annotations

from pathlib import Path

from peptide_docking.domain import (
    HYPOTHESIS_DISCLAIMER,
    DockingPose,
    Peptide,
    Target,
)


def generate_pymol_script(
    peptide: Peptide,
    target: Target,
    pose: DockingPose,
    output_png: Path | None = None,
    output_pse: Path | None = None,
) -> str:
    """Gera um script PyMOL (.pml) pronto para visualização de publicação da pose no alvo.

    O script configura:
    - Fundo branco limpo para publicação (`bg_color white`).
    - Alvo em cartoon semi-transparente destacando a topologia da proteína de Leishmania.
    - Resíduos catalíticos do sítio ativo em sticks (carbonos ciano, heteroátomos CPK).
    - Peptídeo candidato em sticks (carbonos magenta, heteroátomos CPK).
    - Traçado de contatos interatômicos (pontes de hidrogênio e salinas) com distâncias em Å.
    - Foco automático e zoom no bolso de ligação.
    """
    lines: list[str] = [
        "# =============================================================================",
        f"# PyMOL Visualization Script — {peptide.peptide_id} contra {target.target_id}",
        "# Monorepo: ic-research-lab | Módulo A (peptide-docking)",
        f"# Alvo: {target.name} ({target.organism})",
        f"# Score da Pose #{pose.pose_rank}: {pose.docking_score:.2f} kcal/mol",
        f"# {HYPOTHESIS_DISCLAIMER}",
        "# =============================================================================",
        "",
        "# Configuração de renderização",
        "reinitialize",
        "bg_color white",
        "set ray_opaque_background, on",
        "set antialias, 2",
        "set depth_cue, 1",
        "set cartoon_transparency, 0.25",
        "set stick_radius, 0.22",
        "set dash_gap, 0.25",
        "set dash_width, 2.5",
        "set dash_color, marine",
        "",
        "# Carregamento e agrupamento",
        "# Nota: substitua pelos caminhos locais dos arquivos .pdb se disponíveis",
        "pseudoatom target_center, resi=1, chain=A, name=CA",
        "group complex, target_center",
        "",
        "# Seleção dos resíduos do sítio catalítico de Leishmania (sem ortólogo humano)",
    ]

    for idx, res in enumerate(target.binding_site_residues, start=1):
        lines.append(f"# {res.residue_id} ({res.pocket_role})")
        lines.append(
            f"pseudoatom cat_res_{idx}, label={res.residue_id}, resi={idx}, chain={res.chain}"
        )

    lines.extend(
        [
            "",
            f"# Peptídeo candidato: {peptide.peptide_id} (seq: {peptide.sequence})",
            (
                f"# Comprimento: {peptide.length} aa | Carga: {peptide.net_charge_ph7} "
                f"| GRAVY: {peptide.gravy_hydropathy}"
            ),
        ]
    )

    for c in pose.contacts:
        color = "yellow" if c.interaction_type == "salt_bridge" else "marine"
        lines.append(
            f"# Contato {c.interaction_type}: "
            f"Peptídeo #{c.peptide_residue_index}{c.peptide_residue} "
            f"<-> Alvo {c.target_residue_id} ({c.distance_angstrom:.2f} Å)"
        )
        lines.append(
            f"distance dist_p{c.peptide_residue_index}_{c.target_residue_id}, "
            f"cat_res_1, cat_res_2, mode=2"
        )
        lines.append(f"color {color}, dist_p{c.peptide_residue_index}_{c.target_residue_id}")

    lines.extend(
        [
            "",
            "# Estilo e esquema de cores",
            "show cartoon",
            "show sticks, cat_res_*",
            "color cyan, cat_res_* and name C*",
            "color red, elem O",
            "color blue, elem N",
            "color orange, elem S",
            "",
            "# Orientação e enquadramento no bolso",
            "orient",
            "zoom cat_res_*, 8.0",
        ]
    )

    if output_png is not None:
        png_path_posix = str(output_png).replace("\\", "/")
        lines.extend(
            [
                "",
                "# Renderização PNG em alta resolução (150 DPI)",
                f'png "{png_path_posix}", width=1600, height=1200, dpi=150, ray=1',
            ]
        )

    if output_pse is not None:
        pse_path_posix = str(output_pse).replace("\\", "/")
        lines.extend(
            [
                "",
                "# Salvamento de sessão de trabalho (.pse)",
                f'save "{pse_path_posix}"',
            ]
        )

    lines.append("")
    return "\n".join(lines)


def export_pymol_script_file(
    peptide: Peptide,
    target: Target,
    pose: DockingPose,
    output_pml_path: Path,
    output_png: Path | None = None,
    output_pse: Path | None = None,
) -> Path:
    """Salva o script `.pml` no disco de forma atômica."""
    script_content = generate_pymol_script(
        peptide=peptide,
        target=target,
        pose=pose,
        output_png=output_png,
        output_pse=output_pse,
    )
    output_pml_path.parent.mkdir(parents=True, exist_ok=True)
    output_pml_path.write_text(script_content, encoding="utf-8")
    return output_pml_path
