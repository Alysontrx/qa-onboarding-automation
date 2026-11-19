"""Testes unitários para o módulo EmailVerifier."""

from email.message import EmailMessage
import pytest
from core.email_verifier import EmailVerifier, _extract_body, _find_activation_url


def test_find_activation_url_simple():
    body = "Por favor, ative sua conta clicando em https://sixtysix.online/auth/confirm?token=xyz123 para continuar."
    url = _find_activation_url(body)
    assert url == "https://sixtysix.online/auth/confirm?token=xyz123"


def test_find_activation_url_html_encoded():
    body = """
    <html>
        <body>
            <p>Clique no link abaixo:</p>
            <a href="https://sixtysix.online/auth/verify?token=abc&amp;type=signup">Confirmar Cadastro</a>
        </body>
    </html>
    """
    url = _find_activation_url(body)
    assert url == "https://sixtysix.online/auth/verify?token=abc&type=signup"


def test_extract_body_multipart():
    msg = EmailMessage()
    msg["Subject"] = "Confirmação de Cadastro"
    msg["To"] = "usuario1@sixtysix.online"
    msg.set_content("Texto simples de confirmação https://sixtysix.online/activate/123")
    msg.add_alternative(
        "<html><body><p>HTML: https://sixtysix.online/activate/123</p></body></html>",
        subtype="html",
    )

    extracted = _extract_body(msg)
    assert "https://sixtysix.online/activate/123" in extracted


def test_email_verifier_unconfigured():
    verifier = EmailVerifier(host="", user="", password="")
    assert not verifier.is_configured()
    assert verifier.fetch_activation_link_sync("alyson@sixtysix.online") is None


@pytest.mark.asyncio
async def test_wait_for_activation_link_timeout():
    verifier = EmailVerifier(host="imap.fake.com", user="test", password="123")
    # Substitui a chamada síncrona por um mock que retorna None
    verifier.fetch_activation_link_sync = lambda recipient: None  # type: ignore

    link = await verifier.wait_for_activation_link(
        recipient_email="test@sixtysix.online",
        timeout=0.1,
        poll_interval=0.05,
    )
    assert link is None
