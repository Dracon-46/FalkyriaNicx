"""Textos fixos do Click em português ("Usage:", "Options", erros de uso).

O Click marca os próprios textos com ``gettext`` de cada módulo; trocar essas
funções por um dicionário deixa a ajuda inteira em PT-BR sem depender de
arquivos de tradução do sistema. Precisa ser importado antes de qualquer
decorador ``@click`` rodar (o ``help`` do ``--help`` é fixado na decoração).
"""

# ruff: noqa: E501  (tabela de mensagens: uma por linha fica mais legível)
from __future__ import annotations

import click.core
import click.decorators
import click.exceptions
import click.formatting
import click.parser
import click.termui
import click.types

_TEXTOS: dict[str, str] = {
    "%(prog)s, version %(version)s": "%(prog)s, versão %(version)s",
    "Aborted!": "Cancelado.",
    "Argument {name!r} takes {nargs} values.": "O argumento {name!r} recebe {nargs} valores.",
    "Choose from:\n\t{choices}": "Escolha entre:\n\t{choices}",
    "Commands": "Comandos",
    "Confirm the action without prompting.": "Confirma a ação sem perguntar.",
    "Could not open file {filename!r}: {message}": "Não consegui abrir o arquivo {filename!r}: {message}",
    "Do you want to continue?": "Quer continuar?",
    "Error: The two entered values do not match.": "Erro: os dois valores digitados não batem.",
    "Error: invalid input": "Erro: entrada inválida",
    "Error: {message}": "Erro: {message}",
    "Invalid value for {param_hint}: {message}": "Valor inválido para {param_hint}: {message}",
    "Invalid value: {message}": "Valor inválido: {message}",
    "Missing argument": "Falta o argumento",
    "Missing command.": "Falta o comando.",
    "Missing option": "Falta a opção",
    "Missing parameter": "Falta o parâmetro",
    "Missing parameter: {param_name}": "Falta o parâmetro: {param_name}",
    "No such command {name!r}.": "Não existe o comando {name!r}.",
    "No such option {name!r}.": "Não existe a opção {name!r}.",
    "Option {name!r} does not take a value.": "A opção {name!r} não recebe valor.",
    "Options": "Opções",
    "Positional arguments": "Argumentos",
    "Press any key to continue...": "Aperte qualquer tecla para continuar...",
    "Repeat for confirmation": "Repita para confirmar",
    "Show the version and exit.": "Mostra a versão e sai.",
    "Show this message and exit.": "Mostra esta ajuda e sai.",
    "Try '{command} {option}' for help.": "Use '{command} {option}' para ver a ajuda.",
    "Usage:": "Uso:",
    "Value must be an iterable.": "O valor precisa ser uma lista.",
    "default: {default}": "padrão: {default}",
    "deprecated": "obsoleto",
    "directory": "pasta",
    "env var: {var}": "variável de ambiente: {var}",
    "file": "arquivo",
    "path": "caminho",
    "unknown error": "erro desconhecido",
    "{name} {filename!r} does not exist.": "{name} {filename!r} não existe.",
    "{name} {filename!r} is a directory.": "{name} {filename!r} é uma pasta.",
    "{name} {filename!r} is a file.": "{name} {filename!r} é um arquivo.",
    "{name} {filename!r} is not executable.": "{name} {filename!r} não é executável.",
    "{name} {filename!r} is not readable.": "{name} {filename!r} não pode ser lido.",
    "{name} {filename!r} is not writable.": "{name} {filename!r} não pode ser gravado.",
    "{value!r} is not a valid UUID.": "{value!r} não é um UUID válido.",
    "{value!r} is not a valid {number_type}.": "{value!r} não é um {number_type} válido.",
    "{value} is not in the range {range}.": "{value} está fora do intervalo {range}.",
    "integer": "número inteiro",
    "float": "número",
}

# Singular e plural (ngettext): o português usa a mesma regra de "1 = singular".
_PLURAIS: dict[tuple[str, str], tuple[str, str]] = {
    (
        "Got unexpected extra argument ({args})",
        "Got unexpected extra arguments ({args})",
    ): (
        "Argumento a mais inesperado ({args})",
        "Argumentos a mais inesperados ({args})",
    ),
    (
        "Option {name!r} requires an argument.",
        "Option {name!r} requires {nargs} arguments.",
    ): (
        "A opção {name!r} precisa de um valor.",
        "A opção {name!r} precisa de {nargs} valores.",
    ),
    (
        "Did you mean {possibility}?",
        "(Did you mean one of: {possibilities}?)",
    ): (
        "Você quis dizer {possibility}?",
        "(Você quis dizer um destes: {possibilities}?)",
    ),
    (
        "{value!r} is not {choice}.",
        "{value!r} is not one of {choices}.",
    ): (
        "{value!r} não é {choice}.",
        "{value!r} não é um destes: {choices}.",
    ),
    (
        "Takes {nargs} values but 1 was given.",
        "Takes {nargs} values but {len} were given.",
    ): (
        "Recebe {nargs} valores, mas veio 1.",
        "Recebe {nargs} valores, mas vieram {len}.",
    ),
}


def _traduz(mensagem: str) -> str:
    return _TEXTOS.get(mensagem, mensagem)


def _traduz_plural(singular: str, plural: str, n: int) -> str:
    pt = _PLURAIS.get((singular, plural))
    if pt is None:
        return singular if n == 1 else plural
    return pt[0] if n == 1 else pt[1]


def instalar() -> None:
    """Troca o gettext dos módulos do Click pelos textos em português."""
    for modulo in (
        click.core,
        click.decorators,
        click.exceptions,
        click.formatting,
        click.parser,
        click.termui,
        click.types,
    ):
        if hasattr(modulo, "_"):
            modulo._ = _traduz
        if hasattr(modulo, "ngettext"):
            modulo.ngettext = _traduz_plural


instalar()
