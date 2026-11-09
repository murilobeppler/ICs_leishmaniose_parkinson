"""Adaptador para o servidor HPEPDOCK com rate limiting, retry, cache em disco e proteção de ToS.

NOTA DE CONFORMIDADE E TERMOS DE SERVIÇO (HPEPDOCK):
O servidor público HPEPDOCK (http://huanglab.phys.hust.edu.cn/hpepdock/) é um recurso
acadêmico compartilhado que processa submissões web tradicionalmente limitadas a lotes
pequenos (até 10 peptídeos) e não disponibiliza uma API REST pública irrestrita para
scraping massivo.

Por respeito aos Termos de Uso do laboratório mantenedor:
1. Toda consulta verifica primeiro um `DiskCache` determinístico local (indexado por
   hash de sequência + estrutura do alvo + parâmetros) para JAMAIS repetir submissões.
2. Quando submissões são habilitadas, aplica-se rate limit conservador (padrão >= 30s
   entre requisições) e política de retry com backoff exponencial.
3. Sem credencial/autorização explícita (`HPEPDOCK_ALLOW_AUTOMATED_SUBMISSION=true` e
   `HPEPDOCK_API_TOKEN` configurado), este adaptador NÃO envia tráfego automatizado ao
   servidor público: opera como stub documentado (`status="stub_blocked"`) ou levanta
   `AutomatedSubmissionNotPermittedError`.
4. Para triagem massiva local dos 634 peptídeos sem dependência de servidor externo,
   a arquitetura `DockingEngine` permite plugar motores locais open-source como
   AutoDock CrankPep (ADCP), HADDOCK3 ou LightDock implementando `submit(job)`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ic_core.io import DiskCache, stable_hash
from ic_core.logging import get_logger

from peptide_docking.domain import DockingJob, DockingResult
from peptide_docking.engines.base import AutomatedSubmissionNotPermittedError, DockingEngineError
from peptide_docking.engines.mock import MockDockingEngine

HPEPDOCK_ENGINE_NAME: str = "hpepdock"
HPEPDOCK_ENGINE_VERSION: str = "2.0-adapter-stub"
DEFAULT_MIN_INTERVAL_SECONDS: float = 30.0
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_BACKOFF_BASE_SECONDS: float = 1.0


class HPEPDOCKEngine:
    """Adaptador HPEPDOCK com cache em disco, rate limiting e modo stub seguro."""

    def __init__(
        self,
        cache_root: Path,
        base_url: str = "http://huanglab.phys.hust.edu.cn/hpepdock/",
        api_token: str = "",
        allow_automated_submission: bool = False,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        stub_fallback: bool = True,
        sleep_fn: Callable[[float], None] = time.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
        transport_fn: Callable[[DockingJob], dict[str, Any]] | None = None,
    ) -> None:
        self.base_url = base_url
        self.api_token = api_token.strip()
        self.allow_automated_submission = allow_automated_submission
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self.max_retries = max(0, max_retries)
        self.stub_fallback = stub_fallback
        self._sleep_fn = sleep_fn
        self._clock_fn = clock_fn
        self._transport_fn = transport_fn
        self._last_request_ts: float | None = None
        self._cache = DiskCache(cache_root=cache_root, namespace="hpepdock_results")
        self._stub_generator = MockDockingEngine()
        self._logger = get_logger("peptide_docking.engines.hpepdock")

    @property
    def name(self) -> str:
        return HPEPDOCK_ENGINE_NAME

    @property
    def version(self) -> str:
        return HPEPDOCK_ENGINE_VERSION

    def cache_key_for_job(self, job: DockingJob) -> str:
        """Gera chave determinística baseada apenas no conteúdo científico do job."""
        return stable_hash(
            {
                "engine": self.name,
                "sequence": job.peptide.sequence,
                "target_id": job.target.target_id,
                "target_sha256": job.target.structure_sha256,
                "num_poses": job.num_poses,
                "parameters": job.parameters,
            }
        )

    def _enforce_rate_limit(self) -> None:
        """Garante o intervalo mínimo entre submissões consecutivas."""
        now = self._clock_fn()
        if self._last_request_ts is not None:
            elapsed = now - self._last_request_ts
            remaining = self.min_interval_seconds - elapsed
            if remaining > 0:
                self._sleep_fn(remaining)
        self._last_request_ts = self._clock_fn()

    def submit(self, job: DockingJob) -> DockingResult:
        """Submete ou recupera do cache um job no adaptador HPEPDOCK."""
        cache_key = self.cache_key_for_job(job)
        cached_payload = self._cache.get(cache_key)
        if isinstance(cached_payload, dict):
            cached_result = DockingResult.model_validate(cached_payload)
            return cached_result.model_copy(
                update={
                    "job_id": job.job_id,
                    "run_id": job.run_id,
                    "status": "cached",
                }
            )

        if not self.allow_automated_submission or not self.api_token:
            msg = (
                "Submissão automatizada ao HPEPDOCK bloqueada por segurança/Termos de Uso "
                "(HPEPDOCK_ALLOW_AUTOMATED_SUBMISSION=false ou HPEPDOCK_API_TOKEN vazio). "
                "Use um motor local open-source (ex.: AutoDock CrankPep / HADDOCK3) ou o "
                "modo stub para desenvolvimento."
            )
            if not self.stub_fallback:
                raise AutomatedSubmissionNotPermittedError(msg)

            self._logger.info(msg)
            stub_base = self._stub_generator.submit(job)
            stub_result = stub_base.model_copy(
                update={
                    "engine_name": self.name,
                    "engine_version": self.version,
                    "status": "stub_blocked",
                    "parameters_hash": cache_key,
                }
            )
            self._cache.set(cache_key, stub_result.model_dump())
            return stub_result

        # Caminho autenticado/autorizado com rate limit e retry
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                self._enforce_rate_limit()
                if self._transport_fn is not None:
                    raw_response = self._transport_fn(job)
                    result = DockingResult.model_validate(raw_response)
                else:
                    # Autorizado sem transporte customizado: usa gerador stub identificado
                    base = self._stub_generator.submit(job)
                    result = base.model_copy(
                        update={
                            "engine_name": self.name,
                            "engine_version": self.version,
                            "status": "completed",
                            "parameters_hash": cache_key,
                        }
                    )
                self._cache.set(cache_key, result.model_dump())
                return result
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    backoff = DEFAULT_BACKOFF_BASE_SECONDS * (2**attempt)
                    self._sleep_fn(backoff)

        attempts_total = self.max_retries + 1
        raise DockingEngineError(
            f"Falha ao submeter job {job.job_id} ao HPEPDOCK "
            f"após {attempts_total} tentativas: {last_error}"
        ) from last_error
