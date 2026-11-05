"""``nicx atualizacao`` — novidades e o arquivo de versões das releases.

- ``nicx atualizacao procurar``: procura versão nova agora.
- ``nicx atualizacao assinar NicxSetup.exe --versao 0.2.1`` (Falkyria): gera o
  ``nicx-atualizacao.json`` assinado que vai na release, ao lado do instalador.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console


@click.group()
def atualizacao() -> None:
    """Procura atualizações e assina o arquivo de versões (Falkyria)."""


@atualizacao.command("procurar")
def procurar() -> None:
    """Procura versão nova do Nicx agora."""
    from nicx.atualizacao import servico

    console = Console()
    info = servico.verificar()
    ultima = info.get("ultima")
    if info.get("erro"):
        console.print(f"[yellow]Não deu para procurar: {info['erro']}[/yellow]")
    elif info["ha_nova"]:
        console.print(
            f"[green]Nicx {ultima['versao']} disponível[/green] "
            f"(você tem a {info['versao_atual']})."
        )
        if info["instalacao"] == "windows":
            console.print("Abra o Nicx e vá em Atualizações para instalar.")
        elif info["instalacao"] == "git":
            console.print("Para atualizar: [bold]nicx self-update[/bold]")
    else:
        console.print(f"Você já tem a versão mais nova ({info['versao_atual']}).")


@atualizacao.command("assinar")
@click.argument(
    "instalador", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option("--versao", required=True, help="versão da release, ex.: 0.2.1")
@click.option("--saida", type=click.Path(dir_okay=False, path_type=Path), default=None)
@click.option(
    "--sem-banco",
    is_flag=True,
    help="usa as novidades de src/nicx/atualizacao/novidades.py (sem internet)",
)
def assinar(instalador: Path, versao: str, saida: Path | None, sem_banco: bool) -> None:
    """Gera o nicx-atualizacao.json assinado para a release.

    As novidades vêm da tabela nicx_novidades (Painel Falkyria ou INSERT).
    """
    from nicx.atualizacao import banco, manifesto
    from nicx.atualizacao.novidades import NOVIDADES

    console = Console(stderr=True)
    if sem_banco:
        novidades = NOVIDADES
    else:
        try:
            novidades = banco.buscar()
        except banco.NovidadesIndisponiveis as exc:
            console.print(f"[red]{exc}. Use --sem-banco para assinar sem ele.[/red]")
            sys.exit(1)
    if not novidades or novidades[0]["versao"] != versao:
        onde = (
            "src/nicx/atualizacao/novidades.py"
            if sem_banco
            else "nicx_novidades (Painel Falkyria, seção Novidades, ou INSERT)"
        )
        console.print(
            f"[red]Cadastre e publique as novidades da {versao} em {onde} "
            "antes de assinar.[/red]"
        )
        sys.exit(1)
    try:
        conteudo = manifesto.montar(versao, instalador, novidades=novidades)
        assinado = manifesto.assinar(conteudo)
        manifesto.ler(assinado)  # confere com as chaves que o app aceita
    except FileNotFoundError:
        console.print("[red]Sem chave: rode `nicx loja chave` primeiro.[/red]")
        sys.exit(1)
    except manifesto.ManifestoInvalido as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)
    destino = saida or instalador.with_name(manifesto.NOME_ARQUIVO)
    destino.write_text(
        json.dumps(assinado, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    win = conteudo["windows"]
    console.print(
        f"[green]Assinado:[/green] {destino}\n"
        f"  Nicx {versao} · {win['arquivo']} · {win['tamanho'] / 1e6:.1f} MB · "
        f"sha256 {win['sha256'][:16]}…\n"
        f"  Suba os dois arquivos na release v{versao}."
    )


@atualizacao.command("novidades")
def listar_novidades() -> None:
    """Mostra as novidades publicadas no banco (as que vão na próxima assinatura)."""
    from nicx.atualizacao import banco

    console = Console()
    try:
        novidades = banco.buscar()
    except banco.NovidadesIndisponiveis as exc:
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)
    if not novidades:
        console.print("Nenhuma novidade publicada.")
    for n in novidades:
        console.print(f"[bold]{n['versao']}[/bold] · {n['data']} · {n['titulo']}")
        for item in n["itens"]:
            console.print(f"  • {item}")


__all__ = ["atualizacao"]
