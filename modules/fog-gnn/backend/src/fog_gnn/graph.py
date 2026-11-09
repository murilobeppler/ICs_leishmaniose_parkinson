"""Construção do grafo corporal: nós multissensoriais, arestas anatômicas e correlação funcional."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import networkx as nx
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from fog_gnn.domain import CANONICAL_IMU_NODES, SensorNodeSpec, Window

EdgeKind = Literal["anatomical", "bilateral", "functional", "hybrid", "corticospinal"]

ANATOMICAL_KINEMATIC_PAIRS: tuple[tuple[str, str, EdgeKind], ...] = (
    ("LOWER_BACK", "THIGH_L", "anatomical"),
    ("LOWER_BACK", "THIGH_R", "anatomical"),
    ("THIGH_L", "SHANK_L", "anatomical"),
    ("SHANK_L", "ANKLE_L", "anatomical"),
    ("THIGH_R", "SHANK_R", "anatomical"),
    ("SHANK_R", "ANKLE_R", "anatomical"),
    ("THIGH_L", "THIGH_R", "bilateral"),
    ("SHANK_L", "SHANK_R", "bilateral"),
    ("ANKLE_L", "ANKLE_R", "bilateral"),
    ("EEG_CZ", "LOWER_BACK", "corticospinal"),
    ("EEG_CZ", "ANKLE_L", "corticospinal"),
    ("EEG_CZ", "ANKLE_R", "corticospinal"),
)

ANATOMICAL_BASE_WEIGHT: float = 1.0
BILATERAL_BASE_WEIGHT: float = 0.80


class GraphEdge(BaseModel):
    """Aresta entre dois segmentos corporais (anatômica, bilateral ou correlação funcional)."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    kind: EdgeKind
    weight: float = Field(..., ge=0.0, le=2.0)
    correlation: float = Field(default=0.0, ge=-1.0, le=1.0)


class BodyGraph(BaseModel):
    """Grafo corporal completo com nós, arestas tipadas e matriz de adjacência normalizada."""

    model_config = ConfigDict(frozen=True)

    node_order: list[str]
    nodes: list[SensorNodeSpec]
    edges: list[GraphEdge]
    correlation_threshold: float
    adjacency_matrix: list[list[float]]
    normalized_adjacency: list[list[float]]
    graph_density: float
    mean_functional_correlation: float


def compute_node_correlation_matrix(
    windows: Sequence[Window],
    node_order: Sequence[str],
) -> np.ndarray:
    """Calcula a matriz de correlação de Pearson entre os nós corporais ao longo das janelas."""
    n_nodes = len(node_order)
    if not windows:
        return np.eye(n_nodes, dtype=float)

    # Concatena a série de vetores de features de cada nó ao longo das janelas
    series_by_node: list[np.ndarray] = []
    for node_id in node_order:
        vecs = [np.asarray(w.node_features[node_id], dtype=float) for w in windows]
        flat_series = np.concatenate(vecs, axis=0)
        series_by_node.append(flat_series)

    data_matrix = np.vstack(series_by_node)
    stds = np.std(data_matrix, axis=1)
    if np.any(stds < 1e-9):
        corr = np.eye(n_nodes, dtype=float)
    else:
        corr = np.corrcoef(data_matrix)
        corr = np.nan_to_num(corr, nan=0.0, posinf=1.0, neginf=-1.0)
        np.fill_diagonal(corr, 1.0)
    return corr


def normalize_adjacency_matrix(adj: np.ndarray) -> np.ndarray:
    """Calcula a adjacência simetricamente normalizada D~^(-1/2) (A + I) D~^(-1/2)."""
    n_nodes = adj.shape[0]
    adj_self = adj + np.eye(n_nodes, dtype=float)
    degrees = np.sum(adj_self, axis=1)
    inv_sqrt_deg = np.power(np.maximum(degrees, 1e-8), -0.5)
    d_mat = np.diag(inv_sqrt_deg)
    norm_adj: np.ndarray = d_mat @ adj_self @ d_mat
    return norm_adj


def build_body_graph(
    windows: Sequence[Window] | None = None,
    node_specs: Sequence[SensorNodeSpec] = CANONICAL_IMU_NODES,
    correlation_threshold: float = 0.60,
) -> BodyGraph:
    """Constrói o grafo corporal com conexões anatômicas e correlação funcional."""
    node_order = [n.node_id for n in node_specs]
    node_index = {node_id: idx for idx, node_id in enumerate(node_order)}
    n_nodes = len(node_order)

    corr_matrix = (
        compute_node_correlation_matrix(windows, node_order)
        if windows
        else np.eye(n_nodes, dtype=float)
    )

    nx_graph = nx.Graph()
    for spec in node_specs:
        nx_graph.add_node(spec.node_id, modality=spec.modality)

    anatomical_map: dict[tuple[str, str], EdgeKind] = {}
    for src, dst, kind in ANATOMICAL_KINEMATIC_PAIRS:
        if src in node_index and dst in node_index:
            pair: tuple[str, str] = (src, dst) if src < dst else (dst, src)
            anatomical_map[pair] = kind

    adj = np.zeros((n_nodes, n_nodes), dtype=float)
    edges: list[GraphEdge] = []
    abs_corrs: list[float] = []

    for i in range(n_nodes):
        for j in range(i + 1, n_nodes):
            u = node_order[i]
            v = node_order[j]
            pair_key: tuple[str, str] = (u, v) if u < v else (v, u)
            r_val = float(corr_matrix[i, j])
            abs_r = abs(r_val)
            abs_corrs.append(abs_r)

            anat_kind = anatomical_map.get(pair_key)
            is_func = abs_r >= correlation_threshold

            if anat_kind is None and not is_func:
                continue

            if anat_kind is not None and is_func:
                edge_kind: EdgeKind = "hybrid"
                base_w = (
                    ANATOMICAL_BASE_WEIGHT if anat_kind == "anatomical" else BILATERAL_BASE_WEIGHT
                )
                weight = min(2.0, round(0.55 * base_w + 0.45 * abs_r, 4))
            elif anat_kind is not None:
                edge_kind = anat_kind
                base_w = (
                    ANATOMICAL_BASE_WEIGHT if anat_kind == "anatomical" else BILATERAL_BASE_WEIGHT
                )
                weight = round(base_w, 4)
            else:
                edge_kind = "functional"
                weight = round(abs_r, 4)

            adj[i, j] = weight
            adj[j, i] = weight
            nx_graph.add_edge(u, v, weight=weight, kind=edge_kind)
            edges.append(
                GraphEdge(
                    source=u,
                    target=v,
                    kind=edge_kind,
                    weight=weight,
                    correlation=round(r_val, 4),
                )
            )

    norm_adj = normalize_adjacency_matrix(adj)
    density = round(float(nx.density(nx_graph)), 4) if n_nodes > 1 else 0.0
    mean_corr = round(float(np.mean(abs_corrs)), 4) if abs_corrs else 0.0

    return BodyGraph(
        node_order=node_order,
        nodes=list(node_specs),
        edges=edges,
        correlation_threshold=correlation_threshold,
        adjacency_matrix=[[round(float(x), 4) for x in row] for row in adj],
        normalized_adjacency=[[round(float(x), 4) for x in row] for row in norm_adj],
        graph_density=density,
        mean_functional_correlation=mean_corr,
    )
