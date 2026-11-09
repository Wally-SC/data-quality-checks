import json
from datetime import date
from pathlib import Path

import pytest

from dqcheck import Dominio, Faixa, Frescor, NaoNulo, Regex, Suite, Unico
from dqcheck.carga import ler_csv, suite_de_dict
from dqcheck.cli import main

RAIZ = Path(__file__).resolve().parent.parent


def linhas(coluna, *valores):
    return [{coluna: v} for v in valores]


def numeros_das_linhas(falhas):
    return [f.linha for f in falhas]


def test_nao_nulo_trata_vazio_e_espacos_como_nulo():
    falhas = NaoNulo("x").avaliar(linhas("x", "a", "", "  ", None, "b"))
    assert numeros_das_linhas(falhas) == [2, 3, 4]


def test_unico_aponta_todas_as_ocorrencias_e_ignora_nulos():
    falhas = Unico("x").avaliar(linhas("x", "1", "2", "1", "", "", "3"))
    assert numeros_das_linhas(falhas) == [1, 3]
    assert "2x" in falhas[0].motivo


def test_faixa():
    check = Faixa("x", minimo=0, maximo=10)
    falhas = check.avaliar(linhas("x", "5", "-1", "11", "abc", "", "2,5", 10))
    assert numeros_das_linhas(falhas) == [2, 3, 4]
    assert [f.motivo for f in falhas] == ["abaixo do mínimo 0", "acima do máximo 10", "não é numérico"]


def test_faixa_exige_algum_limite():
    with pytest.raises(ValueError):
        Faixa("x")


def test_regex_usa_correspondencia_completa():
    check = Regex("cpf", r"\d{3}\.\d{3}\.\d{3}-\d{2}")
    falhas = check.avaliar(linhas("cpf", "123.456.789-09", "123.456.789-09x", "abc", ""))
    assert numeros_das_linhas(falhas) == [2, 3]


def test_dominio():
    falhas = Dominio("s", ["a", "b"]).avaliar(linhas("s", "a", "c", "", "b "))
    assert numeros_das_linhas(falhas) == [2]


def test_frescor():
    hoje = date(2026, 11, 8)
    dados = linhas("d", "2026-11-01", "2026-11-05", "")
    assert Frescor("d", max_dias=3, hoje=hoje).avaliar(dados) == []
    falhas = Frescor("d", max_dias=2, hoje=hoje).avaliar(dados)
    assert len(falhas) == 1 and "3 dias" in falhas[0].motivo
    assert Frescor("d", max_dias=1, hoje=hoje).avaliar(linhas("d", "08/11/2026"))[0].motivo.startswith("data fora")
    assert "nenhuma data" in Frescor("d", max_dias=1, hoje=hoje).avaliar(linhas("d", ""))[0].motivo


def test_coluna_inexistente_gera_erro_claro():
    with pytest.raises(KeyError, match="nao_existe"):
        NaoNulo("nao_existe").avaliar(linhas("x", "1"))


def test_severidade_invalida():
    with pytest.raises(ValueError):
        NaoNulo("x", severidade="critico")


def test_aviso_nao_reprova_mas_erro_reprova():
    dados = [{"s": "z", "n": ""}]
    so_aviso = Suite([Dominio("s", ["a"], severidade="aviso")]).executar(dados)
    assert so_aviso.ok and len(so_aviso.avisos) == 1

    com_erro = Suite([Dominio("s", ["a"], severidade="aviso"), NaoNulo("n")]).executar(dados)
    assert not com_erro.ok and len(com_erro.erros) == 1


def test_suite_vazia_e_rejeitada():
    with pytest.raises(ValueError):
        Suite([])


def test_resumo_e_dict():
    rel = Suite([Unico("x"), NaoNulo("x")]).executar(linhas("x", "1", "1", ""))
    texto = rel.resumo()
    assert "[ERRO] unico(x): 2 falha(s)" in texto
    assert "[ERRO] nao_nulo(x): 1 falha(s)" in texto
    assert texto.endswith("RESULTADO: REPROVADO")
    dados = rel.para_dict()
    assert dados["aprovado"] is False
    assert [v["nome"] for v in dados["verificacoes"]] == ["unico(x)", "nao_nulo(x)"]
    json.dumps(dados)  # tem que ser serializável


def test_suite_a_partir_de_config():
    suite = suite_de_dict(
        {"verificacoes": [{"tipo": "nao_nulo", "coluna": "a"}, {"tipo": "faixa", "coluna": "b", "minimo": 1}]}
    )
    assert [c.nome for c in suite.checks] == ["nao_nulo(a)", "faixa(b)"]


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"verificacoes": []},
        {"verificacoes": [{"tipo": "inventado", "coluna": "a"}]},
        {"verificacoes": [{"tipo": "faixa", "coluna": "a", "limite": 3}]},
    ],
)
def test_config_invalida(config):
    with pytest.raises(ValueError):
        suite_de_dict(config)


def test_exemplo_do_repositorio_via_cli(tmp_path, capsys):
    saida = tmp_path / "relatorio.json"
    codigo = main([str(RAIZ / "exemplos/clientes.csv"), "--regras", str(RAIZ / "exemplos/regras.json"), "--saida", str(saida)])
    assert codigo == 1  # há erros

    relatorio = json.loads(saida.read_text(encoding="utf-8"))
    por_nome = {v["nome"]: v for v in relatorio["verificacoes"]}
    assert relatorio["total_linhas"] == 6 and relatorio["aprovado"] is False
    assert [f["linha"] for f in por_nome["unico(id)"]["falhas"]] == [4, 5]
    assert [f["linha"] for f in por_nome["nao_nulo(nome)"]["falhas"]] == [4]
    assert [f["linha"] for f in por_nome["regex(email)"]["falhas"]] == [3]
    assert [f["linha"] for f in por_nome["faixa(idade)"]["falhas"]] == [4, 5, 6]
    assert por_nome["dominio(status)"]["severidade"] == "aviso"
    assert por_nome["frescor(atualizado_em)"]["passou"] is True
    assert "REPROVADO" in capsys.readouterr().out


def test_cli_aprovado_retorna_zero(tmp_path):
    csv = tmp_path / "ok.csv"
    csv.write_text("id\n1\n2\n", encoding="utf-8")
    regras = tmp_path / "r.json"
    regras.write_text(json.dumps({"verificacoes": [{"tipo": "unico", "coluna": "id"}]}), encoding="utf-8")
    assert main([str(csv), "--regras", str(regras)]) == 0


def test_cli_erro_de_uso_retorna_dois(tmp_path, capsys):
    assert main([str(tmp_path / "nao_existe.csv"), "--regras", str(RAIZ / "exemplos/regras.json")]) == 2
    assert "erro:" in capsys.readouterr().err


def test_ler_csv_aceita_bom(tmp_path):
    arquivo = tmp_path / "bom.csv"
    arquivo.write_bytes("﻿id,nome\n1,Ana\n".encode("utf-8"))
    assert ler_csv(arquivo) == [{"id": "1", "nome": "Ana"}]
