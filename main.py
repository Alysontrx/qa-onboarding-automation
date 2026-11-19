"""Ponto de entrada principal do Framework de QA - Automação de Onboarding.

Oferece interface de terminal profissional, suporte a parâmetros de linha de comando,
validação de pré-voo e exibição em tempo real do progresso da esteira de testes.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Garante que o diretório raiz esteja no sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from config.settings import Settings, get_settings
from core.browser_manager import BrowserManager
from core.csv_loader import load_users_from_csv
from core.executor import QAExecutor
from core.onboarding import ExecutionResult, ExecutionStatus
from core.reporter import QAReporter, setup_framework_logging


def print_banner(console: Optional[Console] = None) -> None:
    """Exibe o cabeçalho oficial do framework."""
    banner_text = (
        "[bold cyan]QA ONBOARDING AUTOMATION FRAMEWORK[/bold cyan]\n"
        "[dim]Playwright + AdsPower Local API | Concorrência e Métricas de Confiabilidade[/dim]"
    )
    if console and RICH_AVAILABLE:
        console.print(Panel(banner_text, box=box.DOUBLE, expand=False, border_style="cyan"))
    else:
        print("=" * 70)
        print("       QA ONBOARDING AUTOMATION FRAMEWORK - ADSPOWER + PLAYWRIGHT       ")
        print("=" * 70)


def parse_arguments() -> argparse.Namespace:
    """Analisa argumentos da linha de comando para sobrescrever configurações."""
    parser = argparse.ArgumentParser(
        description="Framework de QA para teste de escalabilidade do fluxo de onboarding.",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Caminho personalizado para o arquivo CSV de usuários.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Número máximo de perfis/navegadores executando em paralelo.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Timeout em milissegundos para operações no navegador.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="URL de homologação da tela de registro/onboarding.",
    )
    parser.add_argument(
        "--use-adspower",
        action="store_true",
        help="Habilita a integração com a Local API do AdsPower.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Força a execução via Chromium local do Playwright (ignora AdsPower).",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Abre os navegadores locais com interface visível (útil para debug).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas valida o CSV e configurações sem iniciar navegadores.",
    )
    return parser.parse_args()


async def run_framework(args: argparse.Namespace) -> int:
    """Fluxo de execução assíncrono do framework."""
    console = Console() if RICH_AVAILABLE else None
    print_banner(console)

    # 1. Carregamento e mesclagem de configurações
    settings = get_settings()

    if args.concurrency is not None:
        settings.max_concurrency = max(1, args.concurrency)
    if args.timeout is not None:
        settings.default_timeout = max(1000, args.timeout)
    if args.url:
        settings.onboarding_url = args.url
    if args.use_adspower:
        settings.use_adspower = True
    elif args.local:
        settings.use_adspower = False
    if args.no_headless:
        settings.headless = False
    if args.csv:
        settings.csv_path = Path(args.csv)

    # 2. Inicialização dos logs estruturados
    logger = setup_framework_logging(settings.log_dir)
    logger.info("Iniciando framework de QA com modo AdsPower=%s", settings.use_adspower)

    # 3. Leitura e Validação do CSV
    csv_file = settings.csv_path
    if console and RICH_AVAILABLE:
        console.print(f"[bold yellow]→ Carregando dados de teste:[/bold yellow] {csv_file}")
    else:
        print(f"-> Carregando dados de teste: {csv_file}")

    try:
        csv_result = load_users_from_csv(csv_file)
    except Exception as exc:
        if console and RICH_AVAILABLE:
            console.print(f"[bold red]ERRO CRÍTICO AO LER CSV:[/bold red] {exc}")
        else:
            print(f"ERRO CRÍTICO AO LER CSV: {exc}", file=sys.stderr)
        return 1

    # Exibição de avisos caso haja linhas inválidas no CSV
    if csv_result.has_errors:
        if console and RICH_AVAILABLE:
            err_table = Table(title="Inconsistências Encontradas no CSV", box=box.SIMPLE)
            err_table.add_column("Linha", style="cyan")
            err_table.add_column("Campo", style="yellow")
            err_table.add_column("Detalhe do Erro", style="red")
            for err in csv_result.errors:
                err_table.add_row(str(err.row_number), err.field, err.message)
            console.print(err_table)
        else:
            print(f"Avisos de validação no CSV ({len(csv_result.errors)} erros):")
            for err in csv_result.errors:
                print(f"  - {err}")

    if not csv_result.valid_records:
        if console and RICH_AVAILABLE:
            console.print("[bold red]Nenhum registro válido disponível para execução. Encerrando.[/bold red]")
        else:
            print("Nenhum registro válido disponível para execução. Encerrando.", file=sys.stderr)
        return 1

    unique_profiles = len(set(u.profile_id for u in csv_result.valid_records))

    # Exibição dos parâmetros de pré-voo
    if console and RICH_AVAILABLE:
        info_table = Table(box=box.ROUNDED, show_header=False)
        info_table.add_column("Parâmetro", style="bold green")
        info_table.add_column("Valor", style="white")
        info_table.add_row("Modo do Navegador", "AdsPower Local API" if settings.use_adspower else "Chromium Local (Playwright)")
        if settings.use_adspower:
            info_table.add_row("AdsPower URL", settings.adspower_url)
        info_table.add_row("URL Alvo (Homologação)", settings.onboarding_url)
        info_table.add_row("Perfis Únicos", str(unique_profiles))
        info_table.add_row("Cadastros Válidos", str(len(csv_result.valid_records)))
        info_table.add_row("Concorrência Máxima", str(settings.max_concurrency))
        info_table.add_row("Timeout por Etapa", f"{settings.default_timeout}ms")
        info_table.add_row("Máximo de Retentativas", str(settings.max_retries))
        console.print(info_table)
    else:
        print(f"Modo: {'AdsPower' if settings.use_adspower else 'Playwright Local'}")
        print(f"URL Alvo: {settings.onboarding_url}")
        print(f"Perfis: {unique_profiles} | Cadastros: {len(csv_result.valid_records)} | Concorrência: {settings.max_concurrency}")

    if args.dry_run:
        if console and RICH_AVAILABLE:
            console.print("[bold green]✓ Validação de pré-voo (Dry-Run) concluída com sucesso![/bold green]")
        else:
            print("✓ Validação de pré-voo (Dry-Run) concluída com sucesso!")
        return 0

    # 4. Inicialização dos componentes
    reporter = QAReporter(report_dir=settings.report_dir, log_dir=settings.log_dir)
    browser_manager = BrowserManager(settings)

    # 5. Execução orquestrada com barra de progresso
    start_wall_time = time.perf_counter()

    if console and RICH_AVAILABLE:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=console,
        )

        task_id = progress.add_task(
            "[cyan]Executando testes de onboarding...",
            total=len(csv_result.valid_records),
        )

        def on_progress(completed: int, total: int, result: ExecutionResult) -> None:
            color = "green" if result.is_success else "red"
            progress.update(
                task_id,
                completed=completed,
                description=f"[{color}][{result.status.value}][/{color}] {result.profile_id} ({completed}/{total})",
            )

        with progress:
            executor = QAExecutor(
                settings=settings,
                browser_manager=browser_manager,
                reporter=reporter,
                on_progress=on_progress,
            )
            await executor.run(csv_result.valid_records)

    else:
        def on_progress_simple(completed: int, total: int, result: ExecutionResult) -> None:
            print(f"[{completed}/{total}] {result.status.value}: {result.profile_id} ({result.duration_ms:.2f}ms)")

        executor = QAExecutor(
            settings=settings,
            browser_manager=browser_manager,
            reporter=reporter,
            on_progress=on_progress_simple,
        )
        await executor.run(csv_result.valid_records)

    total_wall_time = time.perf_counter() - start_wall_time

    # 6. Geração dos relatórios
    csv_report_path = reporter.generate_csv_report("resultados.csv")
    json_summary = reporter.generate_json_summary("resumo.json")

    # 7. Disparo automático de notificações e webhooks (Discord / Telegram / Outro Sistema)
    if settings.discord_webhook_url or (settings.telegram_bot_token and settings.telegram_chat_id) or settings.webhook_url:
        logger.info("Enviando notificações e relatórios para canais configurados...")
        notif_results = await reporter.send_notifications(
            summary_data=json_summary,
            discord_webhook_url=settings.discord_webhook_url,
            telegram_bot_token=settings.telegram_bot_token,
            telegram_chat_id=settings.telegram_chat_id,
            generic_webhook_url=settings.webhook_url,
            csv_file_path=csv_report_path,
        )
        if any(notif_results.values()):
            if console and RICH_AVAILABLE:
                console.print("[bold green]✓ Notificação enviada com sucesso para os canais configurados![/bold green]")
            else:
                print("✓ Notificação enviada com sucesso para os canais configurados!")

    # 8. Apresentação do Sumário Final
    if console and RICH_AVAILABLE:
        console.print("\n[bold cyan]═══ SUMÁRIO DE EXECUÇÃO DE QA ═══[/bold cyan]")

        summary_table = Table(box=box.HEAVY_EDGE)
        summary_table.add_column("Métrica", style="bold")
        summary_table.add_column("Resultado", justify="right")

        summary_table.add_row("Total de Testes Executados", str(json_summary["total_tests"]))
        summary_table.add_row("Sucessos [SUCCESS]", f"[green]{json_summary['success_count']}[/green]")
        summary_table.add_row("Falhas [FAILED]", f"[red]{json_summary['failure_count']}[/red]")
        summary_table.add_row("Timeouts [TIMEOUT]", f"[yellow]{json_summary['timeout_count']}[/yellow]")
        summary_table.add_row("Erros de Conexão", f"[magenta]{json_summary['connection_error_count']}[/magenta]")
        summary_table.add_row("Erros de Perfil", f"[magenta]{json_summary['profile_error_count']}[/magenta]")
        summary_table.add_row("Taxa de Sucesso", f"[bold]{json_summary['success_rate_percent']}%[/bold]")
        summary_table.add_row("Tempo Médio de Execução", f"{json_summary['avg_duration_ms']} ms")
        summary_table.add_row("Percentil 95 (p95)", f"[bold cyan]{json_summary['p95_duration_ms']} ms[/bold cyan]")
        summary_table.add_row("Tempo Total de Esteira", f"{total_wall_time:.2f} s")

        console.print(summary_table)

        # Se houver falhas, exibe tabela dedicada com o detalhamento dos erros
        failed_list = [r for r in reporter.results if r.status != ExecutionStatus.SUCCESS]
        if failed_list:
            fail_table = Table(title="[bold red]DETALHAMENTO DE ERROS E FALHAS ENCONTRADAS[/bold red]", box=box.ROUNDED)
            fail_table.add_column("Perfil", style="cyan")
            fail_table.add_column("E-mail", style="yellow")
            fail_table.add_column("Etapa", style="magenta")
            fail_table.add_column("Motivo da Falha", style="bold red")
            fail_table.add_column("Screenshot Salvo", style="dim")
            for f in failed_list:
                screen = Path(f.screenshot_path).name if f.screenshot_path else "-"
                err_clean = (f.error_message or "Erro não especificado").split("\n")[0][:100]
                fail_table.add_row(f.profile_id, f.email, f.step, err_clean, screen)
            console.print(fail_table)

        files_panel = (
            f"[bold]Relatório CSV:[/bold] {csv_report_path}\n"
            f"[bold]Resumo JSON:[/bold] {settings.report_dir / 'resumo.json'}\n"
            f"[bold]Log de Execução:[/bold] {settings.log_dir / 'qa_execution.log'}"
        )
        console.print(Panel(files_panel, title="Artefatos Gerados", border_style="blue"))

    else:
        print("\n" + "=" * 50)
        print("SUMÁRIO DE EXECUÇÃO DE QA")
        print("=" * 50)
        print(f"Total de Testes: {json_summary['total_tests']}")
        print(f"Sucessos: {json_summary['success_count']}")
        print(f"Falhas: {json_summary['failure_count']}")
        print(f"Timeouts: {json_summary['timeout_count']}")
        print(f"Taxa de Sucesso: {json_summary['success_rate_percent']}%")
        print(f"Média: {json_summary['avg_duration_ms']} ms | p95: {json_summary['p95_duration_ms']} ms")
        print(f"Tempo Total: {total_wall_time:.2f} s")
        print(f"Relatório CSV: {csv_report_path}")
        print(f"Resumo JSON: {settings.report_dir / 'resumo.json'}")

    # Retorna código 0 se não houver falhas críticas, 1 se houver erros
    return 0 if (json_summary["failure_count"] == 0 and json_summary["timeout_count"] == 0) else 1


def main() -> None:
    args = parse_arguments()
    try:
        exit_code = asyncio.run(run_framework(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[!] Execução interrompida pelo usuário.")
        sys.exit(130)


if __name__ == "__main__":
    main()

