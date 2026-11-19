"""Módulo de logs estruturados e geração de relatórios de QA.

Responsável pela rotação de logs (RotatingFileHandler), registro seguro e estruturado
de cada execução (sem senhas) e geração automática de relatórios em CSV e JSON
contendo métricas estatísticas essenciais (taxa de sucesso, média, p95).
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
import math
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

from core.onboarding import ExecutionResult, ExecutionStatus

LOGGER_NAME = "qa_framework"


def setup_framework_logging(log_dir: Path, log_level: int = logging.INFO) -> logging.Logger:
    """Configura o sistema de logging com rotação de arquivos para o framework."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "qa_execution.log"

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(log_level)
    logger.propagate = False

    # Evita duplicação de handlers se a função for chamada mais de uma vez
    if not logger.handlers:
        # Handler de arquivo com rotação (5MB por arquivo, até 5 backups)
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def calculate_p95(values: List[float]) -> float:
    """Calcula o percentil 95 (p95) de uma lista de valores numéricos."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n == 1:
        return round(sorted_values[0], 2)
    # Índice p95 utilizando o método de posto mais próximo
    rank = 0.95 * (n - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    weight = rank - lower
    p95_value = sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight
    return round(p95_value, 2)


class QAReporter:
    """Gerencia a coleta de resultados e a emissão de relatórios de QA."""

    def __init__(self, report_dir: Path, log_dir: Optional[Path] = None) -> None:
        self.report_dir = Path(report_dir)
        self.log_dir = Path(log_dir) if log_dir else self.report_dir.parent / "logs"
        self.report_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(LOGGER_NAME)
        self._results: List[ExecutionResult] = []

    def record_result(self, result: ExecutionResult) -> None:
        """Registra em memória e grava no log estruturado."""
        self._results.append(result)

        # Log estruturado e seguro (sem senha)
        err_str = f" | Error='{result.error_message}'" if result.error_message else ""
        screenshot_str = f" | Screenshot='{result.screenshot_path}'" if result.screenshot_path else ""

        log_msg = (
            f"[{result.status.value}] Profile={result.profile_id} | "
            f"Email={result.email} | Step={result.step} | "
            f"Duration={result.duration_ms:.2f}ms{err_str}{screenshot_str}"
        )

        if result.status == ExecutionStatus.SUCCESS:
            self.logger.info(log_msg)
        elif result.status == ExecutionStatus.TIMEOUT:
            self.logger.warning(log_msg)
        else:
            self.logger.error(log_msg)

    @property
    def results(self) -> List[ExecutionResult]:
        return list(self._results)

    def generate_csv_report(self, filename: str = "resultados.csv") -> Path:
        """Exporta os resultados individuais para um arquivo CSV estruturado."""
        output_file = self.report_dir / filename
        fieldnames = [
            "timestamp",
            "profile_id",
            "email",
            "status",
            "step",
            "duration_ms",
            "error_message",
            "screenshot_path",
        ]

        with output_file.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in self._results:
                writer.writerow(r.to_dict())

        return output_file

    def generate_json_summary(self, filename: str = "resumo.json") -> Dict[str, Any]:
        """Gera o sumário estatístico consolidado e salva em JSON."""
        total = len(self._results)
        successes = sum(1 for r in self._results if r.status == ExecutionStatus.SUCCESS)
        failures = sum(1 for r in self._results if r.status == ExecutionStatus.FAILED)
        timeouts = sum(1 for r in self._results if r.status == ExecutionStatus.TIMEOUT)
        profile_errors = sum(1 for r in self._results if r.status == ExecutionStatus.PROFILE_ERROR)
        connection_errors = sum(1 for r in self._results if r.status == ExecutionStatus.CONNECTION_ERROR)

        durations = [r.duration_ms for r in self._results]
        avg_duration = round(sum(durations) / total, 2) if total > 0 else 0.0
        p95_duration = calculate_p95(durations)
        success_rate = round((successes / total) * 100.0, 2) if total > 0 else 0.0

        per_profile: Dict[str, Any] = {}
        for r in self._results:
            if r.profile_id not in per_profile:
                per_profile[r.profile_id] = []
            per_profile[r.profile_id].append(
                {
                    "email": r.email,
                    "status": r.status.value,
                    "step": r.step,
                    "duration_ms": round(r.duration_ms, 2),
                    "error_message": r.error_message or None,
                }
            )

        summary_data: Dict[str, Any] = {
            "total_tests": total,
            "success_count": successes,
            "failure_count": failures,
            "timeout_count": timeouts,
            "profile_error_count": profile_errors,
            "connection_error_count": connection_errors,
            "success_rate_percent": success_rate,
            "avg_duration_ms": avg_duration,
            "p95_duration_ms": p95_duration,
            "min_duration_ms": round(min(durations), 2) if durations else 0.0,
            "max_duration_ms": round(max(durations), 2) if durations else 0.0,
            "per_profile_summary": per_profile,
        }

        output_file = self.report_dir / filename
        with output_file.open("w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)

        return summary_data

    async def send_notifications(
        self,
        summary_data: Dict[str, Any],
        discord_webhook_url: str = "",
        telegram_bot_token: str = "",
        telegram_chat_id: str = "",
        generic_webhook_url: str = "",
        csv_file_path: Optional[Path] = None,
    ) -> Dict[str, bool]:
        """Dispara notificações para Discord, Telegram e Webhook HTTP após os testes."""
        results = {"discord": False, "telegram": False, "webhook": False}
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Notificação no Discord
            if discord_webhook_url:
                failed_results = [r for r in self._results if r.status != ExecutionStatus.SUCCESS]
                is_perfect = len(failed_results) == 0
                color = 3066993 if is_perfect else 15158332  # Verde se 100%, Vermelho se falhas
                
                embed_fields = [
                    {"name": "Total de Testes", "value": str(summary_data.get("total_tests", 0)), "inline": True},
                    {"name": "Sucessos", "value": f"✅ {summary_data.get('success_count', 0)}", "inline": True},
                    {"name": "Falhas / Timeouts", "value": f"❌ {summary_data.get('failure_count', 0)} / ⏱️ {summary_data.get('timeout_count', 0)}", "inline": True},
                    {"name": "Taxa de Sucesso", "value": f"**{summary_data.get('success_rate_percent', 0.0)}%**", "inline": True},
                    {"name": "Tempo Médio", "value": f"{summary_data.get('avg_duration_ms', 0.0)} ms", "inline": True},
                    {"name": "Percentil 95 (p95)", "value": f"**{summary_data.get('p95_duration_ms', 0.0)} ms**", "inline": True},
                ]

                # Se houver erros, adiciona a lista detalhada de falhas no card do Discord
                if failed_results:
                    error_lines = []
                    for f in failed_results[:6]:
                        err_msg = (f.error_message or "Falha não especificada").split("\n")[0][:120]
                        error_lines.append(f"• **Perfil `{f.profile_id}`** ({f.email})\n  ↳ Etapa: `{f.step}` | Erro: `{err_msg}`")
                    
                    if len(failed_results) > 6:
                        error_lines.append(f"... e mais {len(failed_results) - 6} erro(s) registrados no CSV.")

                    embed_fields.append({
                        "name": "🚨 Detalhes dos Erros Encontrados",
                        "value": "\n".join(error_lines),
                        "inline": False,
                    })

                embed_data = {
                    "title": "📊 Relatório de Execução de QA - Onboarding" if is_perfect else "🚨 ALERTA: Falhas Detectadas no Onboarding",
                    "color": color,
                    "fields": embed_fields,
                    "footer": {"text": "QA Framework • AdsPower + Playwright"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Anexos: Screenshot (se houver falha) e Planilha CSV de resultados
                screenshot_file = None
                for f in failed_results:
                    if f.screenshot_path and Path(f.screenshot_path).is_file():
                        screenshot_file = Path(f.screenshot_path)
                        break

                csv_target = csv_file_path or (self.report_dir / "resultados.csv")
                csv_exists = csv_target and Path(csv_target).is_file()

                try:
                    if screenshot_file or csv_exists:
                        if screenshot_file:
                            embed_data["image"] = {"url": f"attachment://{screenshot_file.name}"}

                        payload_json = json.dumps({"username": "QA Onboarding Bot", "embeds": [embed_data]})
                        files = {
                            "payload_json": (None, payload_json, "application/json"),
                        }

                        if screenshot_file:
                            files[screenshot_file.name] = (screenshot_file.name, screenshot_file.read_bytes(), "image/png")

                        if csv_exists:
                            files["resultados.csv"] = ("resultados.csv", Path(csv_target).read_bytes(), "text/csv")

                        resp = await client.post(discord_webhook_url, files=files)
                    else:
                        resp = await client.post(
                            discord_webhook_url,
                            json={"username": "QA Onboarding Bot", "embeds": [embed_data]},
                        )

                    results["discord"] = resp.status_code in (200, 204)
                    if results["discord"]:
                        self.logger.info("Notificação enviada com sucesso para o Discord com anexos.")
                    else:
                        self.logger.warning("Falha ao enviar para o Discord: HTTP %s", resp.status_code)
                except Exception as exc:
                    self.logger.warning("Erro ao conectar no Webhook do Discord: %s", exc)

            # 2. Notificação no Telegram
            if telegram_bot_token and telegram_chat_id:
                msg_text = (
                    "📊 *Relatório de QA - Onboarding*\n\n"
                    f"• *Total de Testes:* {summary_data.get('total_tests', 0)}\n"
                    f"• *Sucessos:* ✅ {summary_data.get('success_count', 0)}\n"
                    f"• *Falhas:* ❌ {summary_data.get('failure_count', 0)}\n"
                    f"• *Timeouts:* ⏱️ {summary_data.get('timeout_count', 0)}\n"
                    f"• *Taxa de Sucesso:* {summary_data.get('success_rate_percent', 0.0)}%\n"
                    f"• *Tempo Médio:* {summary_data.get('avg_duration_ms', 0.0)} ms\n"
                    f"• *Percentil 95 (p95):* {summary_data.get('p95_duration_ms', 0.0)} ms"
                )
                try:
                    tg_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
                    resp = await client.post(
                        tg_url,
                        json={"chat_id": telegram_chat_id, "text": msg_text, "parse_mode": "Markdown"},
                    )
                    results["telegram"] = resp.status_code == 200
                    if results["telegram"]:
                        self.logger.info("Notificação enviada com sucesso para o Telegram.")
                except Exception as exc:
                    self.logger.warning("Erro ao enviar notificação para o Telegram: %s", exc)

            # 3. Webhook HTTP Genérico (para o outro sistema)
            if generic_webhook_url:
                try:
                    resp = await client.post(generic_webhook_url, json=summary_data)
                    results["webhook"] = resp.is_success
                    if results["webhook"]:
                        self.logger.info("Payload JSON enviado com sucesso para o Webhook: %s", generic_webhook_url)
                except Exception as exc:
                    self.logger.warning("Erro ao enviar payload para o Webhook: %s", exc)

        return results

