from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from dqcheck.checks import TIPOS, Check
from dqcheck.suite import Suite


def ler_csv(caminho: str | Path) -> list[dict[str, Any]]:
    with open(caminho, newline="", encoding="utf-8-sig") as arquivo:
        return list(csv.DictReader(arquivo))


def suite_de_dict(config: dict[str, Any]) -> Suite:
    """Monta uma Suite a partir de ``{"verificacoes": [{"tipo": ..., "coluna": ..., ...}]}``."""
    itens = config.get("verificacoes")
    if not isinstance(itens, list) or not itens:
        raise ValueError("a configuração precisa de uma lista não vazia em 'verificacoes'")
    checks: list[Check] = []
    for posicao, item in enumerate(itens, start=1):
        item = dict(item)
        tipo = item.pop("tipo", None)
        if tipo not in TIPOS:
            raise ValueError(f"verificação {posicao}: tipo desconhecido {tipo!r} (use {', '.join(sorted(TIPOS))})")
        try:
            checks.append(TIPOS[tipo](**item))
        except TypeError as exc:
            raise ValueError(f"verificação {posicao} ({tipo}): parâmetros inválidos - {exc}") from exc
    return Suite(checks)


def carregar_suite(caminho: str | Path) -> Suite:
    with open(caminho, encoding="utf-8") as arquivo:
        return suite_de_dict(json.load(arquivo))
