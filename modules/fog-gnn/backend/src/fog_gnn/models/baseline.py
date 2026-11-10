"""Baseline não-GNN (`TemporalBaselineModel`) para comparação metodológica honesta."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from fog_gnn.domain import Window
from fog_gnn.graph import BodyGraph
from fog_gnn.models.base import sigmoid, windows_to_node_tensor

BASELINE_MODEL_NAME: str = "baseline_temporal_1d"
DEFAULT_HIDDEN_DIM: int = 16
DEFAULT_EPOCHS: int = 90
DEFAULT_LEARNING_RATE: float = 0.025
DEFAULT_WEIGHT_DECAY: float = 0.015


class TemporalBaselineModel:
    """Baseline temporal 1D que trata os canais de forma global sem topologia de grafo.

    Recebe as features temporais/espectrais de cada janela agregadas de forma 1D
    (média global entre sensores independentes, sem mensagem entre vizinhos anatômicos
    ou diferenças bilaterais explícitas) e treina uma MLP de 2 camadas com ponderação
    de classe inversa para eventos raros de FOG.
    """

    def __init__(
        self,
        hidden_dim: int = DEFAULT_HIDDEN_DIM,
        epochs: int = DEFAULT_EPOCHS,
        learning_rate: float = DEFAULT_LEARNING_RATE,
        weight_decay: float = DEFAULT_WEIGHT_DECAY,
    ) -> None:
        self.hidden_dim = hidden_dim
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay

        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None
        self._w1: np.ndarray | None = None
        self._b1: np.ndarray | None = None
        self._w2: np.ndarray | None = None
        self._b2: float = 0.0

    @property
    def name(self) -> str:
        return BASELINE_MODEL_NAME

    @property
    def uses_graph_topology(self) -> bool:
        return False

    @staticmethod
    def _extract_1d_representation(x_tensor: np.ndarray) -> np.ndarray:
        """Agrega features temporais de forma 1D ignorando a estrutura relacional do grafo."""
        mean_pool: np.ndarray = np.mean(x_tensor, axis=1)
        return mean_pool

    def fit(
        self,
        train_windows: Sequence[Window],
        graph: BodyGraph,
        seed: int = 42,
    ) -> dict[str, float]:
        x_raw, y = windows_to_node_tensor(train_windows, graph.node_order)
        feats_1d = self._extract_1d_representation(x_raw)

        self._mean = np.mean(feats_1d, axis=0)
        self._std = np.maximum(np.std(feats_1d, axis=0), 1e-6)
        x_norm = (feats_1d - self._mean) / self._std

        n_samples, in_dim = x_norm.shape
        rng = np.random.default_rng(seed)
        self._w1 = rng.normal(0.0, np.sqrt(2.0 / in_dim), size=(in_dim, self.hidden_dim))
        self._b1 = np.zeros(self.hidden_dim, dtype=float)
        self._w2 = rng.normal(0.0, np.sqrt(1.0 / self.hidden_dim), size=(self.hidden_dim,))
        self._b2 = 0.0

        pos_count = float(np.sum(y == 1))
        neg_count = float(np.sum(y == 0))
        pos_weight = (neg_count / max(1.0, pos_count)) if pos_count > 0 else 1.0
        sample_weights = np.where(y == 1, pos_weight, 1.0)
        sample_weights = sample_weights / np.mean(sample_weights)

        final_loss = 0.0
        for _ in range(self.epochs):
            z1 = x_norm @ self._w1 + self._b1
            h1 = np.maximum(0.0, z1)
            logits = h1 @ self._w2 + self._b2
            probs = sigmoid(logits)

            eps = 1e-7
            bce = -(y * np.log(probs + eps) + (1.0 - y) * np.log(1.0 - probs + eps))
            final_loss = float(np.mean(sample_weights * bce))

            d_logits = (probs - y) * sample_weights / float(n_samples)
            grad_w2 = h1.T @ d_logits + self.weight_decay * self._w2
            grad_b2 = float(np.sum(d_logits))

            d_h1 = np.outer(d_logits, self._w2)
            d_z1 = d_h1 * (z1 > 0.0)
            grad_w1 = x_norm.T @ d_z1 + self.weight_decay * self._w1
            grad_b1 = np.sum(d_z1, axis=0)

            self._w1 -= self.learning_rate * grad_w1
            self._b1 -= self.learning_rate * grad_b1
            self._w2 -= self.learning_rate * grad_w2
            self._b2 -= self.learning_rate * grad_b2

        return {"train_loss": round(final_loss, 5)}

    def predict_proba(
        self,
        windows: Sequence[Window],
        graph: BodyGraph,
    ) -> np.ndarray:
        if (
            self._mean is None
            or self._std is None
            or self._w1 is None
            or self._b1 is None
            or self._w2 is None
        ):
            raise RuntimeError("TemporalBaselineModel precisa ser treinado com fit() antes.")

        x_raw, _ = windows_to_node_tensor(windows, graph.node_order)
        feats_1d = self._extract_1d_representation(x_raw)
        x_norm = (feats_1d - self._mean) / self._std

        h1 = np.maximum(0.0, x_norm @ self._w1 + self._b1)
        logits = h1 @ self._w2 + self._b2
        return sigmoid(logits)
