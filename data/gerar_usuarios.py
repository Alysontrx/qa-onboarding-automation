"""Gerador automático de massa de dados de teste para o domínio da aplicação.

Gera registros únicos no formato exigido pelo framework: profile_id,email,password,name
"""

import argparse
from datetime import datetime
from pathlib import Path

DEFAULT_CSV = Path(__file__).resolve().parent / "usuarios.csv"


def gerar_usuarios(dominio: str, quantidade: int, senha: str, prefixo_perfil: str = ""):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    linhas = ["profile_id,email,password,name\n"]

    for i in range(1, quantidade + 1):
        perfil_id = f"{prefixo_perfil}{i}" if prefixo_perfil else str(i)
        email = f"qa_{timestamp}_{i:03d}@{dominio}"
        nome = f"Usuario QA {i:03d}"
        linhas.append(f"{perfil_id},{email},{senha},{nome}\n")

    # Grava no CSV
    with open(DEFAULT_CSV, "w", encoding="utf-8") as f:
        f.writelines(linhas)

    print(f"[✓] {quantidade} contas geradas com sucesso para o domínio '@{dominio}'!")
    print(f"[✓] Salvo em: {DEFAULT_CSV}")
    print("\nExemplo das primeiras contas geradas:")
    for l in linhas[1:4]:
        print("  -", l.strip())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gerador de massa de teste CSV para o QA Framework")
    parser.add_argument("--dominio", type=str, default="sixtysix.online", help="Domínio dos e-mails (ex: sixtysix.online)")
    parser.add_argument("--quantidade", type=int, default=5, help="Quantidade de contas a gerar")
    parser.add_argument("--senha", type=str, default="SenhaTeste123!", help="Senha padrão para os cadastros")
    parser.add_argument("--prefixo-perfil", type=str, default="", help="Prefixo para ID do perfil (ex: se vazio usa 1, 2, 3; se 'p' usa p1, p2)")

    args = parser.parse_args()
    gerar_usuarios(args.dominio, args.quantidade, args.senha, args.prefixo_perfil)

