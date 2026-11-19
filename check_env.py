"""Diagnóstico de pré-voo do Framework de QA.

Verifica em menos de 3 segundos se o ambiente está 100% pronto para execução:
- Versão do Python
- Dependências instaladas
- Navegador Playwright
- Conectividade com a Local API do AdsPower
- Integridade do arquivo de usuários CSV
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from rich.console import Console
    from rich.table import Table
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

import httpx
from config.settings import get_settings
from core.csv_loader import load_users_from_csv


def check_system():
    settings = get_settings()
    results = []

    # 1. Versão do Python
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)
    results.append(("Python 3.11+", f"v{py_ver}", "OK" if py_ok else "ERRO"))

    # 2. Playwright instalado
    try:
        import playwright
        pw_ok = True
        pw_msg = "Instalado"
    except ImportError:
        pw_ok = False
        pw_msg = "Não instalado (pip install -r requirements.txt)"
    results.append(("Playwright Library", pw_msg, "OK" if pw_ok else "ERRO"))

    # 3. CSV de Usuários
    try:
        csv_res = load_users_from_csv(settings.csv_path)
        csv_ok = len(csv_res.valid_records) > 0
        csv_msg = f"{len(csv_res.valid_records)} contas válidas"
    except Exception as e:
        csv_ok = False
        csv_msg = f"Falha ao ler CSV: {e}"
    results.append(("Arquivo de Usuários (CSV)", csv_msg, "OK" if csv_ok else "ERRO"))

    # 4. Conectividade com AdsPower Local API
    try:
        resp = httpx.get(f"{settings.adspower_url}/status", timeout=2.0)
        if resp.status_code == 200 and resp.json().get("code") == 0:
            ads_ok = True
            ads_msg = f"Online em {settings.adspower_url}"
        else:
            ads_ok = False
            ads_msg = f"HTTP {resp.status_code} - Código de erro retornado"
    except Exception:
        ads_ok = False
        ads_msg = f"Desconectado em {settings.adspower_url} (AdsPower fechado ou API inativa)"
    results.append(("AdsPower Local API", ads_msg, "OK" if ads_ok else "ALERTA (Modo Local Disponível)"))

    # Apresentação
    if HAS_RICH:
        table = Table(title="[bold cyan]DIAGNÓSTICO DE AMBIENTE - QA FRAMEWORK[/bold cyan]")
        table.add_column("Componente", style="bold")
        table.add_column("Status / Detalhes", style="white")
        table.add_column("Resultado", justify="center")

        for comp, msg, status in results:
            color = "green" if status == "OK" else ("yellow" if "ALERTA" in status else "red")
            table.add_row(comp, msg, f"[{color}]{status}[/{color}]")
        console.print(table)
    else:
        print("=== DIAGNÓSTICO DE AMBIENTE ===")
        for comp, msg, status in results:
            print(f"[{status}] {comp}: {msg}")

    print("\n[✓] O framework está pronto para rodar com Chromium Local ou AdsPower assim que for ligado!")


if __name__ == "__main__":
    check_system()

