"""Configurações centrais do framework de QA.

Carrega configurações de variáveis de ambiente e arquivos .env, garantindo
que todas as variáveis sejam tipadas e validadas sem necessidade de
alteração no código de lógica principal.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

# Tenta carregar variáveis do arquivo .env
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class SelectorsConfig:
    """Seletores configuráveis para o formulário de onboarding."""

    email: str = "[data-testid='input-email'], input[type='email'], input[name='email']"
    password: str = "[data-testid='input-password'], input[type='password'], input[name='password']"
    name: str = "[data-testid='input-name'], input[name='name']"
    submit: str = "[data-testid='auth-submit-button'], [data-testid='btn-submit'], button:has-text('Create your account'), button:has-text('Sign up'), button:has-text('Continue'), button[type='submit']"
    success_message: str = "[data-testid='success-message'], .success-msg, .alert-success, div:has-text('Check your email'), h1:has-text('Check your email'), div:has-text('sent you a link'), div:has-text('Verifique seu e-mail'), h1:has-text('Welcome')"
    error_message: str = "[data-testid='error-message'], .error-msg, .alert-danger, [role='alert'], div:has-text('already in use'), div:has-text('Unable to verify')"
    activation_success: str = "[data-testid='activation-success'], .verified, h1:has-text('sucesso'), h1:has-text('confirmad'), div:has-text('confirmad'), div:has-text('ativad'), div:has-text('Welcome'), div:has-text('Dashboard')"


@dataclass
class Settings:
    """Configurações de execução e ambiente do framework."""

    # Integração AdsPower
    adspower_url: str = field(
        default_factory=lambda: os.getenv("ADSPOWER_URL", "http://127.0.0.1:50325").rstrip("/")
    )
    adspower_api_key: str = field(
        default_factory=lambda: os.getenv("ADSPOWER_API_KEY", "").strip()
    )
    use_adspower: bool = field(
        default_factory=lambda: os.getenv("USE_ADSPOWER", "false").lower() in ("true", "1", "yes")
    )

    # Aplicação de destino
    onboarding_url: str = field(
        default_factory=lambda: os.getenv("ONBOARDING_URL", "http://localhost:3000/register")
    )

    # Execução, concorrência e resiliência
    max_concurrency: int = field(
        default_factory=lambda: max(1, int(os.getenv("MAX_CONCURRENCY", "2")))
    )
    default_timeout: int = field(
        default_factory=lambda: max(1000, int(os.getenv("DEFAULT_TIMEOUT", "10000")))
    )
    max_retries: int = field(
        default_factory=lambda: max(0, int(os.getenv("MAX_RETRIES", "2")))
    )
    rate_limit_delay: float = field(
        default_factory=lambda: max(0.0, float(os.getenv("RATE_LIMIT_DELAY", "1.0")))
    )

    # Navegador Local (usado quando use_adspower=False)
    headless: bool = field(
        default_factory=lambda: os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
    )

    # Diretórios e caminhos
    csv_path: Path = field(
        default_factory=lambda: BASE_DIR / os.getenv("CSV_PATH", "data/usuarios.csv")
    )
    log_dir: Path = field(
        default_factory=lambda: BASE_DIR / os.getenv("LOG_DIR", "logs")
    )
    report_dir: Path = field(
        default_factory=lambda: BASE_DIR / os.getenv("REPORT_DIR", "reports")
    )

    # Notificações e Webhooks (Discord, Telegram e HTTP Genérico)
    discord_webhook_url: str = field(
        default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    )
    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    )
    telegram_chat_id: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "").strip()
    )
    webhook_url: str = field(
        default_factory=lambda: os.getenv("WEBHOOK_URL", "").strip()
    )

    # Verificação de E-mail (Ativação automática via IMAP / Catch-All)
    verify_email: bool = field(
        default_factory=lambda: os.getenv("VERIFY_EMAIL", "false").lower() in ("true", "1", "yes")
    )
    imap_host: str = field(
        default_factory=lambda: os.getenv("IMAP_HOST", "imap.gmail.com").strip()
    )
    imap_port: int = field(
        default_factory=lambda: int(os.getenv("IMAP_PORT", "993"))
    )
    imap_user: str = field(
        default_factory=lambda: os.getenv("IMAP_USER", "").strip()
    )
    imap_password: str = field(
        default_factory=lambda: os.getenv("IMAP_PASSWORD", "").strip()
    )
    email_wait_timeout: int = field(
        default_factory=lambda: int(os.getenv("EMAIL_WAIT_TIMEOUT", "60"))
    )
    email_poll_interval: float = field(
        default_factory=lambda: float(os.getenv("EMAIL_POLL_INTERVAL", "3.0"))
    )

    # Integração com SixtySix Gateway e Remix Automático (Árvore Auto-Alimentada)
    auto_remix: bool = field(
        default_factory=lambda: os.getenv("AUTO_REMIX", "true").lower() in ("true", "1", "yes")
    )
    six_gateway_url: str = field(
        default_factory=lambda: os.getenv("SIX_GATEWAY_URL", "http://127.0.0.1:17866").rstrip("/")
    )
    default_matrix_id: str = field(
        default_factory=lambda: os.getenv("DEFAULT_MATRIX_ID", "b9408f43-30ad-4673-a65c-a5e2f1be699b").strip()
    )

    # Seletores da UI
    selectors: SelectorsConfig = field(default_factory=SelectorsConfig)

    def __post_init__(self) -> None:
        """Garante que diretórios essenciais existam."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        (self.log_dir / "screenshots").mkdir(parents=True, exist_ok=True)


_settings_instance: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    """Retorna a instância singleton de configurações."""
    global _settings_instance
    if _settings_instance is None or reload:
        _settings_instance = Settings()
    return _settings_instance

