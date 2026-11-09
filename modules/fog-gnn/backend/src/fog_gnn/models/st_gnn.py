"""Rede Neural em Grafo Espaço-Temporal (`STGNNModel`) sobre o grafo corporal."""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence

import numpy as np

from fog_gnn.domain import Window
from fog_gnn.graph import BodyGraph
from fog_gnn.models.base import sigmoid, windows_to_node_tensor

ST_GNN_MODEL_NAME: str = "st_gnn_body_graph"
DEFAULT_GNN_HIDDEN_DIM: int = 32
DEFAULT_GNN_EPOCHS: int = 140
DEFAULT_GNN_LR: float = 0.045
DEFAULT_GNN_WEIGHT_DECAY: float = 0.004


def is_pyg_available() -> bool:
    """Verifica se `torch` e `torch_geometric` estão instalados no ambiente."""
    return (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("torch_geometric") is not None
    )


class STGNNModel:
    """GNN Espaço-Temporal que propaga mensagens pela topologia anatômica + funcional do corpo.

    Arquitetura de passagem de mensagens:
    1. Convolução de Grafo de 1-hop (`A_hat @ X`) e 2-hops (`A_hat^2 @ X`) difundindo o estado
       espectral/temporal entre segmentos cinematicamente acoplados (lombar <-> coxa <->
       canela <-> tornozelo e acoplamento bilateral esquerdo-direito).
    2. Operador relacional de aresta `w_ij * |X_i - X_j|` sobre as conexões do `BodyGraph`,
       capturando dessincronização de fase inter-membros e desacoplamento tronco-tornozelo
       típicos do episódio de Freezing of Gait (FOG).
    3. Readout hierárquico preservando representações nodais + pooling global de grafo +
       classificador neural treinado com ponderação para classe rara e semente fixa.
    """

    def __init__(
        self,
        hidden_dim: int = DEFAULT_GNN_HIDDEN_DIM,
        epochs: int = DEFAULT_GNN_EPOCHS,
        learning_rate: float = DEFAULT_GNN_LR,
        weight_decay: float = DEFAULT_GNN_WEIGHT_DECAY,
    ) -> None:
        self.hidden_dim = hidden_dim
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay

        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None
        self._w_graph1: np.ndarray | None = None
        self._b_graph1: np.ndarray | None = None
        self._w_readout: np.ndarray | None = None
        self._b_readout: float = 0.0

    @property
    def name(self) -> str:
        return ST_GNN_MODEL_NAME

    @property
    def uses_graph_topology(self) -> bool:
        return True

    @staticmethod
    def _graph_message_passing_features(
        x_tensor: np.ndarray,
        graph: BodyGraph,
    ) -> np.ndarray:
        """Executa difusão em grafo de 2 hops e agregação relacional de arestas."""
        a_hat = np.asarray(graph.normalized_adjacency, dtype=float)
        a_hat_2 = a_hat @ a_hat

        # Difusão espacial de 1-hop e 2-hops sobre os nós: (N_win, N_nodes, N_feat)
        hop1 = np.einsum("ij,wjf->wif", a_hat, x_tensor)
        hop2 = np.einsum("ij,wjf->wif", a_hat_2, x_tensor)

        # Discrepância relacional ao longo das arestas do grafo corporal
        node_idx = {node_id: idx for idx, node_id in enumerate(graph.node_order)}
        edge_diffs: list[np.ndarray] = []
        for edge in graph.edges:
            u = node_idx[edge.source]
            v = node_idx[edge.target]
            diff = edge.weight * np.abs(x_tensor[:, u, :] - x_tensor[:, v, :])
            edge_diffs.append(diff)

        if edge_diffs:
            edge_stack = np.stack(edge_diffs, axis=1)
            rel_mean = np.mean(edge_stack, axis=1)
            rel_max = np.max(edge_stack, axis=1)
        else:
            rel_mean = np.zeros((x_tensor.shape[0], x_tensor.shape[2]), dtype=float)
            rel_max = np.zeros((x_tensor.shape[0], x_tensor.shape[2]), dtype=float)

        # Concatena representação difundida por nó + estatísticas relacionais do grafo
        n_win = x_tensor.shape[0]
        hop1_flat = hop1.reshape(n_win, -1)
        hop2_mean = np.mean(hop2, axis=1)
        hop1_max = np.max(hop1, axis=1)

        out: np.ndarray = np.concatenate(
            [hop1_flat, hop2_mean, hop1_max, rel_mean, rel_max],
            axis=1,
        )
        return out

    def fit(
        self,
        train_windows: Sequence[Window],
        graph: BodyGraph,
        seed: int = 42,
    ) -> dict[str, float]:
        x_raw, y = windows_to_node_tensor(train_windows, graph.node_order)
        g_feats = self._graph_message_passing_features(x_raw, graph)

        self._mean = np.mean(g_feats, axis=0)
        self._std = np.maximum(np.std(g_feats, axis=0), 1e-6)
        x_norm = (g_feats - self._mean) / self._std

        n_samples, in_dim = x_norm.shape
        rng = np.random.default_rng(seed)
        self._w_graph1 = rng.normal(0.0, np.sqrt(2.0 / in_dim), size=(in_dim, self.hidden_dim))
        self._b_graph1 = np.zeros(self.hidden_dim, dtype=float)
        self._w_readout = rng.normal(0.0, np.sqrt(1.0 / self.hidden_dim), size=(self.hidden_dim,))
        self._b_readout = 0.0

        pos_count = float(np.sum(y == 1))
        neg_count = float(np.sum(y == 0))
        pos_weight = (neg_count / max(1.0, pos_count)) if pos_count > 0 else 1.0
        sample_weights = np.where(y == 1, pos_weight, 1.0)
        sample_weights = sample_weights / np.mean(sample_weights)

        final_loss = 0.0
        for _ in range(self.epochs):
            z1 = x_norm @ self._w_graph1 + self._b_graph1
            h1 = np.maximum(0.0, z1)
            logits = h1 @ self._w_readout + self._b_readout
            probs = sigmoid(logits)

            eps = 1e-7
            bce = -(y * np.log(probs + eps) + (1.0 - y) * np.log(1.0 - probs + eps))
            final_loss = float(np.mean(sample_weights * bce))

            d_logits = (probs - y) * sample_weights / float(n_samples)
            grad_w2 = h1.T @ d_logits + self.weight_decay * self._w_readout
            grad_b2 = float(np.sum(d_logits))

            d_h1 = np.outer(d_logits, self._w_readout)
            d_z1 = d_h1 * (z1 > 0.0)
            grad_w1 = x_norm.T @ d_z1 + self.weight_decay * self._w_graph1
            grad_b1 = np.sum(d_z1, axis=0)

            self._w_graph1 -= self.learning_rate * grad_w1
            self._b_graph1 -= self.learning_rate * grad_b1
            self._w_readout -= self.learning_rate * grad_w2
            self._b_readout -= self.learning_rate * grad_b2

        return {"train_loss": round(final_loss, 5)}

    def predict_proba(
        self,
        windows: Sequence[Window],
        graph: BodyGraph,
    ) -> np.ndarray:
        if (
            self._mean is None
            or self._std is None
            or self._w_graph1 is None
            or self._b_graph1 is None
            or self._w_readout is None
        ):
            raise RuntimeError("STGNNModel precisa ser treinado com fit() antes.")

        x_raw, _ = windows_to_node_tensor(windows, graph.node_order)
        g_feats = self._graph_message_passing_features(x_raw, graph)
        x_norm = (g_feats - self._mean) / self._std

        h1 = np.maximum(0.0, x_norm @ self._w_graph1 + self._b_graph1)
        logits = h1 @ self._w_readout + self._b_readout
        return sigmoid(logits)
