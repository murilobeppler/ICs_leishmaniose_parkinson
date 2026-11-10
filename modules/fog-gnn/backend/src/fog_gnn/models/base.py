"""Interface comum `FogModel` e utilitários de tensores para modelos do Módulo B."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import numpy as np

from fog_gnn.domain import Window
from fog_gnn.graph import BodyGraph


def windows_to_node_tensor(
    windows: Sequence[Window],
    node_order: Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Converte uma sequência de `Window` em tensor `(N_win, N_nodes, N_feat)` e vetor `y`."""
    if not windows:
        raise ValueError("Lista de janelas vazia ao construir tensor de entrada.")

    n_win = len(windows)
    n_nodes = len(node_order)
    first_vec = windows[0].node_features[node_order[0]]
    n_feat = len(first_vec)

    x_tensor = np.zeros((n_win, n_nodes, n_feat), dtype=float)
    y_vec = np.zeros(n_win, dtype=int)

    for w_idx, win in enumerate(windows):
        y_vec[w_idx] = int(win.label)
        for n_idx, node_id in enumerate(node_order):
            x_tensor[w_idx, n_idx, :] = np.asarray(win.node_features[node_id], dtype=float)

    return x_tensor, y_vec


def sigmoid(z: np.ndarray) -> np.ndarray:
    """Função logística numericamente estável."""
    clipped = np.clip(z, -35.0, 35.0)
    out: np.ndarray = 1.0 / (1.0 + np.exp(-clipped))
    return out


@runtime_checkable
class FogModel(Protocol):
    """Contrato comum para o baseline não-GNN e para a GNN espaço-temporal."""

    @property
    def name(self) -> str:
        """Identificador do modelo."""
        ...

    @property
    def uses_graph_topology(self) -> bool:
        """Indica se o modelo explora a topologia do grafo corporal."""
        ...

    def fit(
        self,
        train_windows: Sequence[Window],
        graph: BodyGraph,
        seed: int = 42,
    ) -> dict[str, float]:
        """Treina o modelo exclusivamente nas janelas de treino com semente fixa."""
        ...

    def predict_proba(
        self,
        windows: Sequence[Window],
        graph: BodyGraph,
    ) -> np.ndarray:
        """Retorna a probabilidade predita de FOG `P(y=1|x)` para cada janela."""
        ...
