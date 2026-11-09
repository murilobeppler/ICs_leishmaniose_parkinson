"""Protocolo base `DockingEngine` e exceções de motores de docking."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from peptide_docking.domain import DockingJob, DockingResult


class DockingEngineError(RuntimeError):
    """Erro geral de execução em um motor de docking."""


class AutomatedSubmissionNotPermittedError(DockingEngineError):
    """Exceção lançada quando submissão automatizada não está autorizada ou sem credenciais."""


@runtime_checkable
class DockingEngine(Protocol):
    """Interface comum para qualquer backend de docking peptídeo-proteína."""

    @property
    def name(self) -> str:
        """Identificador curto do engine (ex.: 'mock', 'hpepdock', 'adcp')."""
        ...

    @property
    def version(self) -> str:
        """Versão rastreável do adaptador/motor."""
        ...

    def submit(self, job: DockingJob) -> DockingResult:
        """Executa ou recupera do cache o docking de um `DockingJob`."""
        ...
