"""Testes de ponta a ponta para a função execute_onboarding e relatórios de QA."""

import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from pathlib import Path
import pytest
from playwright.async_api import async_playwright

from config.settings import SelectorsConfig, Settings
from core.csv_loader import UserData
from core.onboarding import ExecutionResult, ExecutionStatus, execute_onboarding
from core.reporter import QAReporter, calculate_p95

HTML_PAGE = b"""<!DOCTYPE html>
<html>
<head><title>Homologacao Onboarding QA</title></head>
<body>
  <h1>Formulario de Cadastro</h1>
  <form id="form">
    <input data-testid="input-name" name="name" type="text" placeholder="Nome" />
    <input data-testid="input-email" name="email" type="email" placeholder="Email" />
    <input data-testid="input-password" name="password" type="password" placeholder="Senha" />
    <button data-testid="btn-submit" type="submit">Finalizar Cadastro</button>
  </form>
  <div id="output"></div>
  <script>
    document.getElementById('form').addEventListener('submit', function(e) {
      e.preventDefault();
      const email = document.querySelector('[data-testid="input-email"]').value;
      const out = document.getElementById('output');
      if (email.includes('falha')) {
        out.innerHTML = '<div data-testid="error-message">Este e-mail ja esta em uso.</div>';
      } else {
        out.innerHTML = '<div data-testid="success-message">Bem-vindo! Cadastro realizado com sucesso.</div>';
      }
    });
  </script>
</body>
</html>
"""


class MockServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML_PAGE)

    def log_message(self, format, *args):
        pass  # Silencia logs do servidor em testes


@pytest.fixture(scope="module")
def local_server():
    """Inicializa um servidor HTTP local em porta efêmera para testes E2E."""
    server = HTTPServer(("127.0.0.1", 0), MockServerHandler)
    host, port = server.server_address
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    yield f"http://{host}:{port}/register"
    server.shutdown()
    server.server_close()


def test_calculate_p95():
    """Valida o cálculo estatístico do percentil 95."""
    assert calculate_p95([]) == 0.0
    assert calculate_p95([100.0]) == 100.0

    # 10 valores de 10 a 100
    values = [float(i * 10) for i in range(1, 11)]
    p95 = calculate_p95(values)
    assert p95 >= 90.0 and p95 <= 100.0


def test_reporter_generation(tmp_path: Path):
    """Valida gravação e métricas dos relatórios CSV e JSON."""
    reporter = QAReporter(report_dir=tmp_path / "reports", log_dir=tmp_path / "logs")

    r1 = ExecutionResult(
        profile_id="p1",
        email="user1@test.com",
        status=ExecutionStatus.SUCCESS,
        step="COMPLETE",
        duration_ms=120.0,
    )
    r2 = ExecutionResult(
        profile_id="p2",
        email="user2@test.com",
        status=ExecutionStatus.FAILED,
        step="FORM_VALIDATION_ERROR",
        duration_ms=250.0,
        error_message="Erro na aplicação",
    )
    r3 = ExecutionResult(
        profile_id="p3",
        email="user3@test.com",
        status=ExecutionStatus.TIMEOUT,
        step="SUBMIT",
        duration_ms=1000.0,
        error_message="Timeout ao clicar",
    )

    reporter.record_result(r1)
    reporter.record_result(r2)
    reporter.record_result(r3)

    csv_path = reporter.generate_csv_report()
    assert csv_path.is_file()

    summary = reporter.generate_json_summary()
    assert summary["total_tests"] == 3
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 1
    assert summary["timeout_count"] == 1
    assert summary["success_rate_percent"] == 33.33
    assert summary["p95_duration_ms"] > 0
    assert "p1" in summary["per_profile_summary"]


@pytest.mark.asyncio
async def test_execute_onboarding_success_flow(local_server, tmp_path: Path):
    """Valida o fluxo completo de onboarding com sucesso em página web real."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        user = UserData(
            profile_id="test_prof_01",
            email="qa_sucesso@exemplo.com",
            password="SenhaValida123!",
            name="QA Tester",
        )

        settings = Settings(
            onboarding_url=local_server,
            default_timeout=5000,
            log_dir=tmp_path / "logs",
        )

        result = await execute_onboarding(page=page, user_data=user, settings=settings)

        assert result.status == ExecutionStatus.SUCCESS
        assert result.step == "COMPLETE"
        assert result.duration_ms > 0
        assert result.is_success is True

        await browser.close()


@pytest.mark.asyncio
async def test_execute_onboarding_form_error_flow(local_server, tmp_path: Path):
    """Valida detecção de mensagem de erro de validação do formulário."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        user = UserData(
            profile_id="test_prof_02",
            email="qa_falha@exemplo.com",  # Contém 'falha', ativando a resposta de erro na página mock
            password="SenhaValida123!",
            name="QA Tester Rejeitado",
        )

        settings = Settings(
            onboarding_url=local_server,
            default_timeout=5000,
            log_dir=tmp_path / "logs",
        )

        result = await execute_onboarding(page=page, user_data=user, settings=settings)

        assert result.status == ExecutionStatus.FAILED
        assert result.step == "FORM_VALIDATION_ERROR"
        assert "Este e-mail ja esta em uso" in (result.error_message or "")

        await browser.close()


@pytest.mark.asyncio
async def test_execute_onboarding_timeout_flow(tmp_path: Path):
    """Valida comportamento e captura de screenshot em caso de timeout."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        user = UserData(
            profile_id="test_prof_03",
            email="qa_timeout@exemplo.com",
            password="SenhaValida123!",
            name="QA Tester Timeout",
        )

        # URL inexistente com timeout agressivo de 100ms
        settings = Settings(
            onboarding_url="http://127.0.0.1:59999/unreachable",
            default_timeout=300,
            log_dir=tmp_path / "logs",
        )

        result = await execute_onboarding(page=page, user_data=user, settings=settings)

        assert result.status in (ExecutionStatus.TIMEOUT, ExecutionStatus.FAILED)
        assert result.duration_ms > 0

        await browser.close()

