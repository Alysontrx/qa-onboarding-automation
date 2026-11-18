"""Gerenciador de execução concorrente e escalabilidade para testes de QA.

Controla concorrência via semáforos/filas, aplica pacing de carga (rate limiting),
protege contra execuções duplicadas, realiza retentativas em falhas transitórias
e garante encerramento seguro (sem vazamento de sessões) sob interrupção.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any, Callable, List, Optional, Set

from config.settings import Settings, get_settings
from core.adspower import AdsPowerConnectionError, AdsPowerProfileError
from core.browser_manager import BrowserManager, BrowserSession
from core.csv_loader import UserData
from core.onboarding import ExecutionResult, ExecutionStatus, execute_onboarding
from core.reporter import QAReporter

logger = logging.getLogger("qa_framework.executor")


class QAExecutor:
    """Orquestrador concorrente de testes de QA para o fluxo de onboarding."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        browser_manager: Optional[BrowserManager] = None,
        reporter: Optional[QAReporter] = None,
        on_progress: Optional[Callable[[int, int, ExecutionResult], Any]] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.browser_manager = browser_manager or BrowserManager(self.settings)
        self.reporter = reporter or QAReporter(self.settings.report_dir, self.settings.log_dir)
        self.on_progress = on_progress

        self._semaphore = asyncio.Semaphore(self.settings.max_concurrency)
        self._processed_records: Set[str] = set()
        self._shutdown_event = asyncio.Event()
        self._completed_count = 0
        self._total_records = 0

    def _setup_signal_handlers(self) -> None:
        """Configura captura de sinais para encerramento gracioso."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._handle_shutdown_signal)
            except (NotImplementedError, RuntimeError):
                # Ambientes Windows ou threads secundárias
                pass

    def _handle_shutdown_signal(self) -> None:
        """Manipulador de interrupção graciosa."""
        logger.warning("Sinal de interrupção recebido. Iniciando encerramento seguro...")
        self._shutdown_event.set()

    async def _execute_single_with_retry(self, user: UserData) -> ExecutionResult:
        """Executa o onboarding para um usuário com controle de tentativas e exceções."""
        attempts = 0
        max_attempts = 1 + self.settings.max_retries
        last_result: Optional[ExecutionResult] = None

        while attempts < max_attempts and not self._shutdown_event.is_set():
            attempts += 1
            session: Optional[BrowserSession] = None
            try:
                logger.info(
                    "[%s] Iniciando tentativa %d/%d para e-mail '%s'",
                    user.profile_id,
                    attempts,
                    max_attempts,
                    user.masked_email,
                )

                # 1. Abre sessão no navegador (AdsPower ou Local Playwright)
                session = await self.browser_manager.open_session(user.profile_id)

                # 2. Executa a automação da página de onboarding
                result = await execute_onboarding(
                    page=session.page,
                    user_data=user,
                    settings=self.settings,
                )
                last_result = result

                # Se obteve sucesso ou erro funcional definitivo (ex: validação de form), não retenta
                if result.status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED):
                    return result

                # Se foi timeout e ainda há tentativas restantes, aguarda backoff
                if attempts < max_attempts and not self._shutdown_event.is_set():
                    wait_time = 1.5 * attempts
                    logger.warning(
                        "[%s] Tentativa %d falhou com %s. Aguardando %.1fs antes de retentar...",
                        user.profile_id,
                        attempts,
                        result.status.value,
                        wait_time,
                    )
                    await asyncio.sleep(wait_time)

            except AdsPowerConnectionError as exc:
                last_result = ExecutionResult(
                    profile_id=user.profile_id,
                    email=user.masked_email,
                    status=ExecutionStatus.CONNECTION_ERROR,
                    step="BROWSER_OPEN",
                    duration_ms=0.0,
                    error_message=str(exc),
                )
                logger.error("[%s] Erro de conexão com AdsPower: %s", user.profile_id, exc)
                if attempts < max_attempts:
                    await asyncio.sleep(2.0 * attempts)

            except AdsPowerProfileError as exc:
                last_result = ExecutionResult(
                    profile_id=user.profile_id,
                    email=user.masked_email,
                    status=ExecutionStatus.PROFILE_ERROR,
                    step="PROFILE_INITIALIZE",
                    duration_ms=0.0,
                    error_message=str(exc),
                )
                logger.error("[%s] Erro no perfil AdsPower: %s", user.profile_id, exc)
                # Erros de configuração de perfil não costumam resolver com retry imediato
                break

            except Exception as exc:
                last_result = ExecutionResult(
                    profile_id=user.profile_id,
                    email=user.masked_email,
                    status=ExecutionStatus.FAILED,
                    step="SESSION_LIFECYCLE",
                    duration_ms=0.0,
                    error_message=f"Falha na sessão: {exc}",
                )
                logger.exception("[%s] Exceção na sessão do navegador: %s", user.profile_id, exc)

            finally:
                if session:
                    await self.browser_manager.close_session(session)

        return last_result or ExecutionResult(
            profile_id=user.profile_id,
            email=user.masked_email,
            status=ExecutionStatus.FAILED,
            step="ABORTED",
            duration_ms=0.0,
            error_message="Execução cancelada ou esgotou tentativas.",
        )

    async def _worker(self, queue: asyncio.Queue[UserData]) -> None:
        """Worker assíncrono que consome usuários da fila respeitando o semáforo."""
        while not queue.empty() and not self._shutdown_event.is_set():
            try:
                user = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            # Proteção contra execução duplicada
            dedup_key = f"{user.profile_id}::{user.email.lower()}"
            if dedup_key in self._processed_records:
                logger.warning(
                    "Registro duplicado detectado para perfil '%s' e e-mail '%s'. Ignorando.",
                    user.profile_id,
                    user.masked_email,
                )
                queue.task_done()
                continue

            self._processed_records.add(dedup_key)

            async with self._semaphore:
                if self._shutdown_event.is_set():
                    queue.task_done()
                    break

                result = await self._execute_single_with_retry(user)
                self.reporter.record_result(result)
                self._completed_count += 1

                if self.on_progress:
                    try:
                        self.on_progress(self._completed_count, self._total_records, result)
                    except Exception as cb_exc:
                        logger.debug("Erro no callback de progresso: %s", cb_exc)

                # Pacing / Intervalo entre execuções para planejamento de carga
                if self.settings.rate_limit_delay > 0:
                    await asyncio.sleep(self.settings.rate_limit_delay)

            queue.task_done()

    async def run(self, users: List[UserData]) -> List[ExecutionResult]:
        """Inicia a execução orquestrada de todos os usuários fornecidos."""
        self._setup_signal_handlers()
        self._total_records = len(users)
        self._completed_count = 0
        self._processed_records.clear()

        queue: asyncio.Queue[UserData] = asyncio.Queue()
        for u in users:
            queue.put_nowait(u)

        # Inicia número de workers de acordo com a concorrência máxima configurada
        worker_count = min(self.settings.max_concurrency, max(1, len(users)))
        logger.info(
            "Iniciando pool com %d workers concorrentes para %d registros...",
            worker_count,
            len(users),
        )

        workers = [
            asyncio.create_task(self._worker(queue))
            for _ in range(worker_count)
        ]

        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            logger.warning("Execução cancelada externamente.")
        finally:
            # Garante liberação de todas as sessões e clientes
            await self.browser_manager.close_all()

        return self.reporter.results

