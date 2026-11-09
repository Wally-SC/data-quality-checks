# data-quality-checks

Mini-framework de **qualidade de dados**: você descreve regras em JSON, ele valida um
CSV e gera um relatório. Pensado para ser usado como etapa de um pipeline: o código de
saída é `1` quando alguma regra de severidade `erro` falha, o que interrompe a execução
em CI ou em um orquestrador.

## Verificações disponíveis

| Tipo | Valida | Parâmetros |
|---|---|---|
| `nao_nulo` | valor presente (vazio e só espaços contam como nulo) | `coluna` |
| `unico` | sem repetição (aponta todas as linhas repetidas) | `coluna` |
| `faixa` | valor numérico dentro de limites | `coluna`, `minimo` e/ou `maximo` |
| `regex` | texto casa **por inteiro** com o padrão | `coluna`, `padrao` |
| `dominio` | valor está numa lista permitida | `coluna`, `valores` |
| `frescor` | o dado mais recente não é mais velho que N dias | `coluna`, `max_dias` |

Toda verificação aceita `"severidade": "erro"` (padrão, reprova) ou `"aviso"` (só informa).
Valores nulos são ignorados pelas regras de conteúdo (`faixa`, `regex`, `dominio`);
ausência é responsabilidade do `nao_nulo`, assim cada regra tem uma única função.

## Uso pela linha de comando

```bash
python -m dqcheck exemplos/clientes.csv --regras exemplos/regras.json --saida relatorio.json
echo $?   # 0 aprovado | 1 reprovado | 2 erro de uso (arquivo ou regra inválida)
```

```
6 linhas, 6 verificações
  [ERRO] unico(id): 2 falha(s)
           linha 4: '4' - valor repetido 2x
           linha 5: '4' - valor repetido 2x
  [ERRO] nao_nulo(nome): 1 falha(s)
           linha 4: '' - valor ausente
  [ERRO] regex(email): 1 falha(s)
           linha 3: 'carla.exemplo.com' - não casa com /[^@\s]+@[^@\s]+\.[a-z]{2,}/
  [ERRO] faixa(idade): 3 falha(s)
           linha 4: '17' - abaixo do mínimo 18
           linha 5: '230' - acima do máximo 120
           linha 6: 'abc' - não é numérico
  [AVISO] dominio(status): 1 falha(s)
           linha 5: 'suspenso' - fora dos valores permitidos
  [ok]    frescor(atualizado_em)
RESULTADO: REPROVADO
```

## Uso como biblioteca

```python
from dqcheck import Suite, NaoNulo, Unico, Faixa

suite = Suite([NaoNulo("id"), Unico("id"), Faixa("valor", minimo=0)])
relatorio = suite.executar([{"id": "1", "valor": "10"}, {"id": "1", "valor": "-5"}])

print(relatorio.resumo())
if not relatorio.ok:
    raise SystemExit(1)
```

## Como estender

Uma nova regra é uma subclasse de `Check` com o método `avaliar(linhas)`, devolvendo uma
lista de `Falha`. Para usá-la no JSON, registre-a no dicionário `TIPOS` em `dqcheck/checks.py`.

## Testes

```bash
pip install pytest
pytest
```
