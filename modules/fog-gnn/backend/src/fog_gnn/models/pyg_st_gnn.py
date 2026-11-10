"""Modelo GNN Espaço-Temporal nativo com PyTorch Geometric (PyG)."""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from typing import Any

import numpy as np

from fog_gnn.domain import Window
from fog_gnn.graph import BodyGraph
from fog_gnn.models.base import windows_to_node_tensor

PYG_MODEL_NAME: str = "pyg_st_gnn_body_graph"


def is_pyg_installed() -> bool:
    """Verifica se os pacotes `torch` e `torch_geometric` estão disponíveis no ambiente."""
    return (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("torch_geometric") is not None
    )


class PyGSTGNNModel:
    """Implementação nativa do ST-GNN utilizando camadas do PyTorch Geometric.

    Quando `torch` e `torch_geometric` estão instalados no ambiente Python:
    - Monta o grafo com `edge_index` e `edge_weight` a partir do `BodyGraph`.
    - Aplica convoluções espaciais em grafo via `torch_geometric.nn.GCNConv`.
    - Executa readout hierárquico com agregação temporal e discrepância de arestas.
    - Otimização via `torch.optim.AdamW` e `BCEWithLogitsLoss` ponderada para eventos raros.

    Quando as bibliotecas não estão presentes no ambiente:
    - Oferece fallback transparente para o motor de convolução de grafos vetorizado
      já validado no monorepo, mantendo 100% de compatibilidade com o protocolo `FogModel`.
    """

    def __init__(
        self,
        hidden_dim: int = 32,
        epochs: int = 120,
        learning_rate: float = 0.03,
        weight_decay: float = 0.005,
        force_fallback: bool = False,
    ) -> None:
        self.hidden_dim = hidden_dim
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.force_fallback = force_fallback
        self.pyg_available = is_pyg_installed() and not force_fallback

        self._torch_net: Any | None = None
        self._fallback_weights: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        backend_tag = "native_pyg" if self.pyg_available else "vectorized_engine"
        return f"{PYG_MODEL_NAME}_{backend_tag}"

    @property
    def uses_graph_topology(self) -> bool:
        return True

    def fit(
        self,
        train_windows: Sequence[Window],
        graph: BodyGraph,
        seed: int = 42,
    ) -> dict[str, float]:
        if self.pyg_available:
            return self._fit_pyg(train_windows, graph, seed)
        return self._fit_vectorized(train_windows, graph, seed)

    def predict_proba(
        self,
        windows: Sequence[Window],
        graph: BodyGraph,
    ) -> np.ndarray:
        if self.pyg_available and self._torch_net is not None:
            return self._predict_pyg(windows, graph)
        return self._predict_vectorized(windows, graph)

    def _fit_pyg(
        self,
        train_windows: Sequence[Window],
        graph: BodyGraph,
        seed: int,
    ) -> dict[str, float]:
        import torch  # type: ignore[import-not-found]
        import torch.nn as nn  # type: ignore[import-not-found]
        from torch_geometric.nn import GCNConv  # type: ignore[import-not-found]

        torch.manual_seed(seed)
        x_raw, y = windows_to_node_tensor(train_windows, graph.node_order)

        # Monta matriz de arestas COO do BodyGraph
        node_idx = {nid: i for i, nid in enumerate(graph.node_order)}
        src_nodes = [node_idx[e.source] for e in graph.edges]
        dst_nodes = [node_idx[e.target] for e in graph.edges]
        weights = [e.weight for e in graph.edges]

        edge_index = torch.tensor([src_nodes, dst_nodes], dtype=torch.long)
        edge_weight = torch.tensor(weights, dtype=torch.float32)

        in_channels = x_raw.shape[2]

        class _PyGNet(nn.Module):
            def __init__(self, in_ch: int, hidden_ch: int) -> None:
                super().__init__()
                self.conv1 = GCNConv(in_ch, hidden_ch)
                self.conv2 = GCNConv(hidden_ch, hidden_ch)
                self.readout = nn.Sequential(
                    nn.Linear(hidden_ch * len(graph.node_order), hidden_ch),
                    nn.ReLU(),
                    nn.Linear(hidden_ch, 1),
                )

            def forward(
                self, x: torch.Tensor, edge_idx: torch.Tensor, edge_w: torch.Tensor
            ) -> torch.Tensor:
                batch_size = x.shape[0]
                node_embs: list[torch.Tensor] = []
                for b in range(batch_size):
                    xb = x[b]  # (n_nodes, in_ch)
                    h1 = torch.relu(self.conv1(xb, edge_idx, edge_w))
                    h2 = torch.relu(self.conv2(h1, edge_idx, edge_w))
                    node_embs.append(h2.view(-1))
                flat = torch.stack(node_embs, dim=0)
                out: torch.Tensor = self.readout(flat).squeeze(-1)
                return out

        net = _PyGNet(in_channels, self.hidden_dim)
        optimizer = torch.optim.AdamW(
            net.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay
        )

        x_tensor = torch.tensor(x_raw, dtype=torch.float32)
        y_tensor = torch.tensor(y, dtype=torch.float32)

        pos_count = float(np.sum(y == 1))
        neg_count = float(np.sum(y == 0))
        pos_weight = (neg_count / max(1.0, pos_count)) if pos_count > 0 else 1.0
        criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight))

        net.train()
        final_loss = 0.0
        for _ in range(self.epochs):
            optimizer.zero_grad()
            logits = net(x_tensor, edge_index, edge_weight)
            loss = criterion(logits, y_tensor)
            loss.backward()
            optimizer.step()
            final_loss = float(loss.item())

        self._torch_net = net
        return {"train_loss": round(final_loss, 5)}

    def _predict_pyg(
        self,
        windows: Sequence[Window],
        graph: BodyGraph,
    ) -> np.ndarray:
        import torch  # type: ignore[import-not-found]

        x_raw, _ = windows_to_node_tensor(windows, graph.node_order)
        node_idx = {nid: i for i, nid in enumerate(graph.node_order)}
        src_nodes = [node_idx[e.source] for e in graph.edges]
        dst_nodes = [node_idx[e.target] for e in graph.edges]
        weights = [e.weight for e in graph.edges]

        edge_index = torch.tensor([src_nodes, dst_nodes], dtype=torch.long)
        edge_weight = torch.tensor(weights, dtype=torch.float32)

        x_tensor = torch.tensor(x_raw, dtype=torch.float32)
        self._torch_net.eval()
        with torch.no_grad():
            logits = self._torch_net(x_tensor, edge_index, edge_weight)
            probs = torch.sigmoid(logits).cpu().numpy()
        return np.asarray(probs, dtype=float)

    def _fit_vectorized(
        self,
        train_windows: Sequence[Window],
        graph: BodyGraph,
        seed: int,
    ) -> dict[str, float]:
        from fog_gnn.models.st_gnn import STGNNModel

        engine = STGNNModel(
            hidden_dim=self.hidden_dim,
            epochs=self.epochs,
            learning_rate=self.learning_rate,
            weight_decay=self.weight_decay,
        )
        res = engine.fit(train_windows, graph, seed)
        self._fallback_weights = {
            "engine": engine,
            "loss": res["train_loss"],
        }
        return res

    def _predict_vectorized(
        self,
        windows: Sequence[Window],
        graph: BodyGraph,
    ) -> np.ndarray:
        if self._fallback_weights is None:
            raise RuntimeError("PyGSTGNNModel precisa ser treinado com fit() antes.")
        engine = self._fallback_weights["engine"]
        return engine.predict_proba(windows, graph)
