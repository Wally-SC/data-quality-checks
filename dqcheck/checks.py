"""Verificações de qualidade de dados sobre linhas (lista de dicionários).

Valores vindos de CSV chegam como texto: ``None`` e ``""`` (ou só espaços) contam como nulo.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

SEVERIDADES = ("erro", "aviso")


@dataclass(frozen=True)
class Falha:
    check: str
    coluna: str
    linha: int  # 1 = primeira linha de dados
    valor: Any
    motivo: str


def e_nulo(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


class Check:
    """Base de todas as verificações. Subclasses implementam ``avaliar``."""

    tipo = "check"

    def __init__(self, coluna: str, severidade: str = "erro") -> None:
        if severidade not in SEVERIDADES:
            raise ValueError(f"severidade inválida: {severidade!r} (use {' ou '.join(SEVERIDADES)})")
        self.coluna = coluna
        self.severidade = severidade

    @property
    def nome(self) -> str:
        return f"{self.tipo}({self.coluna})"

    def avaliar(self, linhas: list[dict[str, Any]]) -> list[Falha]:
        raise NotImplementedError

    def _falha(self, linha: int, valor: Any, motivo: str) -> Falha:
        return Falha(self.nome, self.coluna, linha, valor, motivo)

    def _valores(self, linhas: list[dict[str, Any]]) -> Iterable[tuple[int, Any]]:
        for numero, registro in enumerate(linhas, start=1):
            if self.coluna not in registro:
                raise KeyError(f"coluna {self.coluna!r} não existe nos dados")
            yield numero, registro[self.coluna]


class NaoNulo(Check):
    tipo = "nao_nulo"

    def avaliar(self, linhas):
        return [self._falha(n, v, "valor ausente") for n, v in self._valores(linhas) if e_nulo(v)]


class Unico(Check):
    tipo = "unico"

    def avaliar(self, linhas):
        pares = [(n, v) for n, v in self._valores(linhas) if not e_nulo(v)]
        contagem = Counter(v for _, v in pares)
        return [self._falha(n, v, f"valor repetido {contagem[v]}x") for n, v in pares if contagem[v] > 1]


class Faixa(Check):
    tipo = "faixa"

    def __init__(self, coluna, minimo=None, maximo=None, severidade="erro"):
        super().__init__(coluna, severidade)
        if minimo is None and maximo is None:
            raise ValueError("informe minimo e/ou maximo")
        self.minimo, self.maximo = minimo, maximo

    def avaliar(self, linhas):
        falhas = []
        for n, v in self._valores(linhas):
            if e_nulo(v):
                continue  # ausência é assunto do NaoNulo
            try:
                numero = float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
            except ValueError:
                falhas.append(self._falha(n, v, "não é numérico"))
                continue
            if self.minimo is not None and numero < self.minimo:
                falhas.append(self._falha(n, v, f"abaixo do mínimo {self.minimo}"))
            elif self.maximo is not None and numero > self.maximo:
                falhas.append(self._falha(n, v, f"acima do máximo {self.maximo}"))
        return falhas


class Regex(Check):
    tipo = "regex"

    def __init__(self, coluna, padrao, severidade="erro"):
        super().__init__(coluna, severidade)
        self.padrao = re.compile(padrao)

    def avaliar(self, linhas):
        return [
            self._falha(n, v, f"não casa com /{self.padrao.pattern}/")
            for n, v in self._valores(linhas)
            if not e_nulo(v) and not self.padrao.fullmatch(str(v).strip())
        ]


class Dominio(Check):
    tipo = "dominio"

    def __init__(self, coluna, valores, severidade="erro"):
        super().__init__(coluna, severidade)
        self.valores = {str(v) for v in valores}

    def avaliar(self, linhas):
        return [
            self._falha(n, v, "fora dos valores permitidos")
            for n, v in self._valores(linhas)
            if not e_nulo(v) and str(v).strip() not in self.valores
        ]


class Frescor(Check):
    """A data mais recente da coluna não pode ser mais velha que ``max_dias`` (dados desatualizados)."""

    tipo = "frescor"

    def __init__(self, coluna, max_dias, hoje: date | None = None, severidade="erro"):
        super().__init__(coluna, severidade)
        self.max_dias = max_dias
        self._hoje = hoje

    def avaliar(self, linhas):
        datas = []
        for n, v in self._valores(linhas):
            if e_nulo(v):
                continue
            try:
                datas.append((date.fromisoformat(str(v).strip()), n))
            except ValueError:
                return [self._falha(n, v, "data fora do formato AAAA-MM-DD")]
        if not datas:
            return [self._falha(0, None, "nenhuma data para avaliar")]
        mais_recente, n = max(datas)
        idade = ((self._hoje or date.today()) - mais_recente).days
        if idade > self.max_dias:
            return [self._falha(n, mais_recente.isoformat(), f"dados com {idade} dias (limite {self.max_dias})")]
        return []


TIPOS: dict[str, type[Check]] = {c.tipo: c for c in (NaoNulo, Unico, Faixa, Regex, Dominio, Frescor)}
