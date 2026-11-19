"""Utilitário para conectar e registrar pontes no SixtySix Gateway.

Permite:
- Ver o status do SixtySix Gateway
- Consultar a matriz ativa para remix
- Registrar manualmente ou automaticamente uma URL de projeto Lovable no pool
"""

import argparse
import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.gateway_sync import SixtySixGatewaySync


async def main():
    parser = argparse.ArgumentParser(description="Registrador de Pontes no SixtySix Gateway")
    parser.add_argument("--url", type=str, help="URL do projeto Lovable (ex: https://meu-projeto.lovable.app)")
    parser.add_argument("--label", type=str, default="Manual QA", help="Rótulo ou identificador do perfil")
    parser.add_argument("--gateway", type=str, default="http://127.0.0.1:17866", help="URL do SixtySix Gateway Local")
    parser.add_argument("--status", action="store_true", help="Apenas consultar o status do Gateway")
    args = parser.parse_args()

    sync = SixtySixGatewaySync(gateway_url=args.gateway)

    print("═══════════════════════════════════════════════════════════")
    print("      CONECTOR QA AUTOMATION ➔ SIXTYSIX GATEWAY             ")
    print("═══════════════════════════════════════════════════════════\n")

    # 1. Checa status do Gateway
    print(f"[*] Verificando SixtySix Gateway em {args.gateway}...")
    status = await sync.check_gateway_status()
    if not status.get("ok"):
        print(f"[!] Erro ao conectar ao SixtySix Gateway: {status.get('error')}")
        print("[!] Certifique-se de que o SixtySix Desktop Server está rodando na porta 17866.")
        return

    print(f"[✓] SixtySix Gateway ONLINE!")
    print(f"    • Pontes Ativas no Pool: {status.get('active_bridge_pool', 0)}")
    print(f"    • Matrizes de Remix Disponíveis: {status.get('matrices', 0)}")

    # 2. Próxima matriz
    matrix_info = await sync.get_next_matrix()
    if matrix_info and matrix_info.get("ok"):
        print(f"\n[🎯] Próxima Matriz para Remix: {matrix_info.get('matrix_id')}")
        print(f"    Link: {matrix_info.get('remix_url')}")

    if args.status and not args.url:
        return

    # 3. Registro de projeto
    target_url = args.url
    if not target_url:
        print("\n" + "-" * 59)
        target_url = input("Cole a URL do projeto Lovable para adicionar ao SixtySix: ").strip()

    if not target_url:
        print("[*] Nenhuma URL informada. Saindo.")
        return

    label = args.label
    print(f"\n[*] Enviando auto-registro para o SixtySix Gateway...")
    reg = await sync.register_worker(project_origin=target_url, workspace_label=label)
    if reg.get("registered"):
        print(f"[✓] SUCESSO! Projeto registrado no SixtySix Gateway!")
        print(f"    • Worker ID gerado: {reg.get('worker_id')}")
        print(f"    • A nova ponte já está atendendo requisições Claude Opus no SixtySix!")
    else:
        print(f"[!] Falha no registro: {reg.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
