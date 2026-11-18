"""Testes unitários para o módulo de integração com a AdsPower Local API."""

import pytest
import httpx
from core.adspower import (
    AdsPowerClient,
    AdsPowerConnectionError,
    AdsPowerProfileError,
)


@pytest.mark.asyncio
async def test_check_health_success():
    """Valida retorno positivo do health check do AdsPower."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/status"
        return httpx.Response(200, json={"code": 0, "msg": "success"})

    transport = httpx.MockTransport(handler)
    client = AdsPowerClient(base_url="http://mock-adspower:50325")
    client._client = httpx.AsyncClient(base_url="http://mock-adspower:50325", transport=transport)

    is_online = await client.check_health()
    assert is_online is True


@pytest.mark.asyncio
async def test_check_health_offline():
    """Valida tratamento de conexão quando AdsPower está offline."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handler)
    client = AdsPowerClient(base_url="http://mock-adspower:50325")
    client._client = httpx.AsyncClient(base_url="http://mock-adspower:50325", transport=transport)

    is_online = await client.check_health()
    assert is_online is False


@pytest.mark.asyncio
async def test_start_browser_success():
    """Valida inicialização do navegador e extração do WebSocket CDP."""
    expected_ws = "ws://127.0.0.1:9222/devtools/browser/abc-123"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/browser/active":
            return httpx.Response(200, json={"code": 0, "data": {"status": "Inactive"}})
        if request.url.path == "/api/v1/browser/start":
            assert "user_id=perfil_01" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "ws": {"puppeteer": expected_ws},
                        "debug_port": "9222",
                    },
                    "msg": "success",
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = AdsPowerClient(base_url="http://mock-adspower:50325", api_key="secret-key")
    client._client = httpx.AsyncClient(base_url="http://mock-adspower:50325", transport=transport)

    ws_url = await client.start_browser("perfil_01")
    assert ws_url == expected_ws
    assert "perfil_01" in client._active_profiles


@pytest.mark.asyncio
async def test_start_browser_reuses_already_active():
    """Verifica reutilização de sessão se o perfil já se encontrar ativo."""
    active_ws = "ws://127.0.0.1:9222/devtools/browser/already-active"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/browser/active":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"status": "Active", "ws": {"puppeteer": active_ws}},
                },
            )
        return httpx.Response(500, text="Não deveria chamar start se já ativo")

    transport = httpx.MockTransport(handler)
    client = AdsPowerClient(base_url="http://mock-adspower:50325")
    client._client = httpx.AsyncClient(base_url="http://mock-adspower:50325", transport=transport)

    ws_url = await client.start_browser("perfil_ativo")
    assert ws_url == active_ws
    assert "perfil_ativo" in client._active_profiles


@pytest.mark.asyncio
async def test_start_browser_profile_error():
    """Verifica lançamento de AdsPowerProfileError quando a API retorna código de erro."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/browser/active":
            return httpx.Response(200, json={"code": 0, "data": {"status": "Inactive"}})
        if request.url.path == "/api/v1/browser/start":
            return httpx.Response(
                200,
                json={"code": -1, "msg": "Perfil não encontrado no sistema AdsPower."},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = AdsPowerClient(base_url="http://mock-adspower:50325")
    client._client = httpx.AsyncClient(base_url="http://mock-adspower:50325", transport=transport)

    with pytest.raises(AdsPowerProfileError, match="Perfil não encontrado"):
        await client.start_browser("perfil_inexistente")


@pytest.mark.asyncio
async def test_stop_browser_and_cleanup():
    """Valida o encerramento correto e a limpeza do conjunto de perfis ativos."""
    stopped_profiles = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/browser/stop":
            user_id = request.url.params.get("user_id")
            stopped_profiles.append(user_id)
            return httpx.Response(200, json={"code": 0, "msg": "success"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = AdsPowerClient(base_url="http://mock-adspower:50325")
    client._client = httpx.AsyncClient(base_url="http://mock-adspower:50325", transport=transport)

    # Simula dois perfis ativos
    client._active_profiles.add("p1")
    client._active_profiles.add("p2")

    await client.close_all_active()

    assert len(client._active_profiles) == 0
    assert "p1" in stopped_profiles
    assert "p2" in stopped_profiles

