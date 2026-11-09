from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dqcheck.checks import Check, Falha


@dataclass
class ResultadoCheck:
    nome: str
    severidade: str
    falhas: list[Falha] = field(default_factory=list)

    @property
    def passou(self) -> bool:
        return not self.falhas


@dataclass
class Relatorio:
    total_linhas: int
    resultados: list[ResultadoCheck]

    @property
    def erros(self) -> list[ResultadoCheck]:
        return [r for r in self.resultados if not r.passou and r.severidade == "erro"]

    @property
    def avisos(self) -> list[ResultadoCheck]:
        return [r for r in self.resultados if not r.passou and r.severidade == "aviso"]

    @property
    def ok(self) -> bool:
        """Só falhas de severidade 'erro' reprovam; 'aviso' é informativo."""
        return not self.erros

    def resumo(self, max_exemplos: int = 3) -> str:
        linhas = [f"{self.total_linhas} linhas, {len(self.resultados)} verificações"]
        for r in self.resultados:
            if r.passou:
                linhas.append(f"  [ok]    {r.nome}")
                continue
            etiqueta = "ERRO" if r.severidade == "erro" else "AVISO"
            linhas.append(f"  [{etiqueta}] {r.nome}: {len(r.falhas)} falha(s)")
            for f in r.falhas[:max_exemplos]:
                linhas.append(f"           linha {f.linha}: {f.valor!r} - {f.motivo}")
            if len(r.falhas) > max_exemplos:
                linhas.append(f"           ... e mais {len(r.falhas) - max_exemplos}")
        linhas.append("RESULTADO: " + ("APROVADO" if self.ok else "REPROVADO"))
        return "\n".join(linhas)

    def para_dict(self) -> dict[str, Any]:
        return {
            "total_linhas": self.total_linhas,
            "aprovado": self.ok,
            "verificacoes": [
                {
                    "nome": r.nome,
                    "severidade": r.severidade,
                    "passou": r.passou,
                    "falhas": [
                        {"linha": f.linha, "valor": f.valor, "motivo": f.motivo} for f in r.falhas
                    ],
                }
                for r in self.resultados
            ],
        }


class Suite:
    def __init__(self, checks: list[Check]) -> None:
        if not checks:
            raise ValueError("a suíte precisa de ao menos uma verificação")
        self.checks = checks

    def executar(self, linhas: list[dict[str, Any]]) -> Relatorio:
        resultados = [ResultadoCheck(c.nome, c.severidade, c.avaliar(linhas)) for c in self.checks]
        return Relatorio(len(linhas), resultados)
