"""Utilitário para listar perfis do AdsPower e sincronizar com o usuarios.csv.

Conecta à Local API do AdsPower, lista todos os perfis cadastrados na conta
(com número de série, ID e nome) e permite gerar automaticamente o arquivo data/usuarios.csv.
"""

import argparse
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


def listar_perfis(sync_csv: bool = False, dominio: str = "sixtysix.online"):
    settings = get_settings()
    url = f"{settings.adspower_url}/api/v1/user/list"
    params = {"page": 1, "page_size": 100}

    print(f"[*] Consultando perfis na Local API do AdsPower ({settings.adspower_url})...")
    try:
        resp = httpx.get(url, params=params, timeout=5.0)
    except httpx.ConnectError:
        print(f"[!] ERRO: Não foi possível conectar ao AdsPower em {settings.adspower_url}.")
        print("[!] Verifique se o aplicativo do AdsPower está aberto e com a Local API ligada na porta 50325.")
        return

    if resp.status_code != 200:
        print(f"[!] Erro retornado pelo AdsPower: HTTP {resp.status_code} - {resp.text}")
        return

    data = resp.json()
    if data.get("code") != 0:
        print(f"[!] Erro na resposta da API: {data.get('msg')}")
        return

    perfis = data.get("data", {}).get("list", [])
    if not perfis:
        print("[*] Nenhum perfil encontrado na conta do AdsPower.")
        return

    print(f"[✓] {len(perfis)} perfil(is) encontrado(s) no AdsPower!\n")

    if HAS_RICH:
        t = Table(title="[bold cyan]PERFIS CADASTRADOS NO ADSPOWER[/bold cyan]")
        t.add_column("Nº (Serial)", style="bold yellow", justify="center")
        t.add_column("ID Único (user_id)", style="cyan")
        t.add_column("Nome do Perfil", style="white")
        t.add_column("Grupo", style="dim")

        for p in perfis:
            sn = str(p.get("serial_number", ""))
            uid = p.get("user_id", "")
            nome = p.get("name", "")
            grupo = p.get("group_name", "-")
            t.add_row(sn, uid, nome, grupo)
        console.print(t)
    else:
        for p in perfis:
            print(f"Nº: {p.get('serial_number')} | ID: {p.get('user_id')} | Nome: {p.get('name')}")

    if sync_csv:
        csv_path = settings.csv_path
        linhas = ["profile_id,email,password,name\n"]
        for p in perfis:
            sn = str(p.get("serial_number", p.get("user_id")))
            nome = p.get("name") or f"QA User {sn}"
            email = f"qa_perfil{sn}@{dominio}"
            senha = "SenhaTeste123!"
            linhas.append(f"{sn},{email},{senha},{nome}\n")

        with open(csv_path, "w", encoding="utf-8") as f:
            f.writelines(linhas)

        print(f"\n[✓] Arquivo '{csv_path}' sincronizado automaticamente com os {len(perfis)} perfis do AdsPower!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lista perfis do AdsPower e sincroniza com o CSV")
    parser.add_argument("--sync-csv", action="store_true", help="Atualiza automaticamente o data/usuarios.csv com os perfis encontrados")
    parser.add_argument("--dominio", type=str, default="sixtysix.online", help="Domínio para os e-mails sincronizados")
    args = parser.parse_args()

    listar_perfis(sync_csv=args.sync_csv, dominio=args.dominio)
