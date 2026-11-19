"""Módulo de verificação e captura de links de ativação de e-mail via IMAP.

Suporta Catch-All (Pega-Tudo) via Cloudflare Email Routing, Gmail, Zoho, cPanel
e qualquer servidor IMAP padrão, permitindo que a automação capture o link de
confirmação em tempo real e ative a conta no mesmo navegador Playwright.
"""

from __future__ import annotations

import asyncio
import email
from email.header import decode_header
import html
import imaplib
import logging
import re
import time
from typing import List, Optional

logger = logging.getLogger("qa_framework.email_verifier")

# Padrões de links de ativação comumente usados por sistemas de autenticação
ACTIVATION_PATTERNS = [
    r"https?://[^\s<>\"']*(?:confirm|verify|activate|token|validat|signup|auth)[^\s<>\"']*",
    r"https?://[^\s<>\"']+",
]


def _decode_str(val: str | bytes | None) -> str:
    """Decodifica cabeçalhos de e-mail codificados em RFC 2047."""
    if not val:
        return ""
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="ignore")
    decoded_fragments = decode_header(val)
    parts = []
    for fragment, enc in decoded_fragments:
        if isinstance(fragment, bytes):
            parts.append(fragment.decode(enc or "utf-8", errors="ignore"))
        else:
            parts.append(str(fragment))
    return "".join(parts)


def _extract_body(msg: email.message.Message) -> str:
    """Extrai o corpo textual (texto puro ou HTML) de uma mensagem de e-mail."""
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = str(part.get("Content-Disposition", ""))
            if "attachment" in cdisp:
                continue
            if ctype in ("text/plain", "text/html"):
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body_parts.append(payload.decode(charset, errors="ignore"))
                except Exception:
                    pass
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body_parts.append(payload.decode(charset, errors="ignore"))
        except Exception:
            pass

    return "\n".join(body_parts)


def _find_activation_url(body: str, target_domain: Optional[str] = None) -> Optional[str]:
    """Localiza e desescapa a URL de ativação a partir do corpo do e-mail."""
    if not body:
        return None

    # 1. Procura primeiro por links com palavras-chave de ativação/verificação
    for pattern in ACTIVATION_PATTERNS:
        matches = re.findall(pattern, body, re.IGNORECASE)
        for url in matches:
            # Limpa entidades HTML (&amp; -> &) e pontuação final residual
            clean_url = html.unescape(url).rstrip(").,;'\"")
            if target_domain and target_domain.lower() not in clean_url.lower():
                continue
            return clean_url

    return None


class EmailVerifier:
    """Cliente IMAP síncrono/assíncrono para captura automática de links de ativação."""

    def __init__(
        self,
        host: str,
        port: int = 993,
        user: str = "",
        password: str = "",
        use_ssl: bool = True,
        target_domain: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_ssl = use_ssl
        self.target_domain = target_domain

    def is_configured(self) -> bool:
        """Verifica se as credenciais mínimas de IMAP foram fornecidas."""
        return bool(self.host and self.user and self.password)

    def fetch_activation_link_sync(
        self,
        recipient_email: str,
        max_messages_to_check: int = 15,
    ) -> Optional[str]:
        """Conecta via IMAP e busca o link de ativação para o e-mail informado."""
        if not self.is_configured():
            logger.warning("Credenciais de IMAP não configuradas no .env (IMAP_USER/IMAP_PASSWORD).")
            return None

        clean_recipient = recipient_email.strip().lower()
        client = None

        try:
            if self.use_ssl:
                client = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                client = imaplib.IMAP4(self.host, self.port)

            client.login(self.user, self.password)

            # Tenta selecionar a caixa de entrada (INBOX)
            status, _ = client.select("INBOX")
            if status != "OK":
                logger.error("Falha ao selecionar caixa INBOX no servidor IMAP: %s", status)
                return None

            # Busca os e-mails mais recentes
            status, data = client.search(None, "ALL")
            if status != "OK" or not data or not data[0]:
                return None

            msg_ids = data[0].split()
            # Ordena do mais recente para o mais antigo e limita a quantidade
            recent_ids = msg_ids[-max_messages_to_check:][::-1]

            for msg_id in recent_ids:
                status, msg_data = client.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue

                for response_part in msg_data:
                    if not isinstance(response_part, tuple):
                        continue

                    raw_email = response_part[1]
                    msg = email.message_from_bytes(raw_email)

                    # Verifica cabeçalhos de destino (To, Delivered-To, X-Forwarded-To)
                    headers_to_check = [
                        _decode_str(msg.get("To", "")),
                        _decode_str(msg.get("Delivered-To", "")),
                        _decode_str(msg.get("X-Forwarded-To", "")),
                        _decode_str(msg.get("X-Original-To", "")),
                    ]
                    all_headers_str = " ".join(headers_to_check).lower()

                    body = _extract_body(msg)

                    # O e-mail pertence ao usuário se o endereço estiver nos headers ou no corpo
                    if clean_recipient in all_headers_str or clean_recipient in body.lower():
                        logger.debug("E-mail para '%s' localizado na caixa postal.", clean_recipient)
                        link = _find_activation_url(body, self.target_domain)
                        if link:
                            logger.info("Link de ativação capturado para '%s': %s", clean_recipient, link)
                            return link

            return None

        except Exception as exc:
            logger.error("Erro durante leitura da caixa postal IMAP: %s", exc)
            return None
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass
                try:
                    client.logout()
                except Exception:
                    pass

    async def wait_for_activation_link(
        self,
        recipient_email: str,
        timeout: float = 60.0,
        poll_interval: float = 3.0,
    ) -> Optional[str]:
        """Aguarda de forma assíncrona até que o link de ativação chegue na caixa postal.

        Args:
            recipient_email: O e-mail (@sixtysix.online) cadastrado no formulário.
            timeout: Tempo limite total em segundos para aguardar o e-mail.
            poll_interval: Intervalo em segundos entre cada checagem no IMAP.

        Returns:
            URL completa de ativação ou None se esgotar o tempo.
        """
        start_time = time.monotonic()
        logger.info(
            "Aguardando e-mail de ativação para '%s' (Timeout: %.0fs, Intervalo: %.1fs)...",
            recipient_email,
            timeout,
            poll_interval,
        )

        while (time.monotonic() - start_time) < timeout:
            link = await asyncio.to_thread(self.fetch_activation_link_sync, recipient_email)
            if link:
                return link

            await asyncio.sleep(poll_interval)

        logger.warning("Tempo esgotado aguardando e-mail de ativação para '%s'.", recipient_email)
        return None
