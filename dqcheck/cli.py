from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dqcheck.carga import carregar_suite, ler_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dqcheck",
        description="Valida um CSV com regras de qualidade. Código de saída 1 se alguma regra de severidade 'erro' falhar.",
    )
    parser.add_argument("csv", type=Path, help="arquivo CSV a validar")
    parser.add_argument("--regras", type=Path, required=True, help="arquivo JSON com as verificações")
    parser.add_argument("--saida", type=Path, help="grava o relatório completo em JSON")
    args = parser.parse_args(argv)

    try:
        linhas = ler_csv(args.csv)
        relatorio = carregar_suite(args.regras).executar(linhas)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    print(relatorio.resumo())
    if args.saida:
        args.saida.write_text(json.dumps(relatorio.para_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if relatorio.ok else 1
