"""Desfazer unificado: "desfaz" volta a última coisa que o Nicx mudou.

Cada linha do histórico que dá para desfazer guarda como fazê-lo:
- ``colecao``: lembretes, agenda e projetos (com o que mudou junto);
- ``nota`` / ``notas``: uma anotação nova ou a limpeza das anotações;
- ``organizacao``: uma organização de pasta (o registro dos movimentos);
- ``arquivo``: um arquivo escrito por ferramenta (cópia de antes, ou "era novo").

Cópias ficam em ``~/.nicx/desfazer/`` e somem depois de :data:`DIAS_COPIAS`.
"""

from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from nicx.historico import mudancas, textos
from nicx.historico.registro import anotar, registro

logger = logging.getLogger(__name__)

DIAS_COPIAS = 30
LIMITE_COPIA = (
    5 * 1024 * 1024
)  # arquivos maiores não ganham cópia (e não dão para desfazer)


def pasta_copias() -> Path:
    from nicx.nucleo.paths import get_config_dir

    pasta = get_config_dir() / "desfazer"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def guardar_copia(origem: Path, prefixo: str = "") -> Optional[Path]:
    """Copia o arquivo para a pasta do desfazer; None se grande demais ou ilegível."""
    try:
        if not origem.is_file() or origem.stat().st_size > LIMITE_COPIA:
            return None
        destino = (
            pasta_copias() / f"{datetime.now():%Y%m%d-%H%M%S-%f}-{prefixo}{origem.name}"
        )
        shutil.copy2(origem, destino)
        return destino
    except OSError:
        logger.debug("Sem cópia de %s", origem, exc_info=True)
        return None


def limpar_copias(dias: int = DIAS_COPIAS) -> int:
    limite = time.time() - dias * 86400
    apagadas = 0
    for f in pasta_copias().iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < limite:
                f.unlink()
                apagadas += 1
        except OSError:
            continue
    return apagadas


# --------------------------------------------------------------- coleções
def _lembretes() -> tuple[Callable[[], list[dict]], Callable[[list[dict]], None]]:
    from dataclasses import asdict

    from nicx.acoes import lembretes

    def ler() -> list[dict]:
        return [asdict(r) for r in lembretes._load()]

    def gravar(itens: list[dict]) -> None:
        lembretes._save([lembretes.Reminder(**d) for d in itens], registrar=False)

    return ler, gravar


def _agenda() -> tuple[Callable[[], list[dict]], Callable[[list[dict]], None]]:
    from dataclasses import asdict

    from nicx.acoes import agenda

    def ler() -> list[dict]:
        return [asdict(e) for e in agenda._load()]

    def gravar(itens: list[dict]) -> None:
        agenda._save([agenda.Event(**d) for d in itens], registrar=False)

    return ler, gravar


def _aplicar_colecao(mudanca: dict[str, Any]) -> None:
    colecao = mudanca["colecao"]
    if colecao == "projetos":
        from nicx.projetos.armazenamento import Projetos
        from nicx.projetos.modelo import Projeto

        def trocar(projetos: list) -> None:
            atuais = [p.para_dict() for p in projetos]
            projetos[:] = [
                Projeto.de_dict(d) for d in mudancas.inverter(mudanca, atuais)
            ]

        Projetos()._mudar(trocar)
    else:
        from nicx.acoes import agenda, lembretes

        trava = lembretes._LOCK if colecao == "lembretes" else agenda._LOCK
        ler, gravar = _lembretes() if colecao == "lembretes" else _agenda()
        with trava:
            gravar(mudancas.inverter(mudanca, ler()))
    for filha in mudanca.get("junto", []):
        _aplicar_colecao(filha)


# --------------------------------------------------------------- anotações
def _aplicar_nota(dados: dict[str, Any]) -> None:
    from nicx.acoes import notas

    arquivo = notas.path()
    linhas = (
        arquivo.read_text(encoding="utf-8").splitlines() if arquivo.exists() else []
    )
    alvo = dados["linha"]
    for i in range(len(linhas) - 1, -1, -1):
        if linhas[i].strip() == alvo.strip():
            del linhas[i]
            arquivo.write_text("\n".join(linhas).rstrip() + "\n", encoding="utf-8")
            return
    raise ValueError("a anotação já não está no arquivo")


def _aplicar_notas(dados: dict[str, Any]) -> None:
    from nicx.acoes import notas

    copia = Path(dados["copia"])
    if not copia.exists():
        raise FileNotFoundError("a cópia das anotações sumiu")
    antigas = [
        linha
        for linha in copia.read_text(encoding="utf-8").splitlines()
        if linha.startswith("- [")
    ]
    arquivo = notas.path()
    atuais = (
        arquivo.read_text(encoding="utf-8").splitlines()
        if arquivo.exists()
        else ["# Anotações do Nicx", ""]
    )
    cabeca = [linha for linha in atuais if not linha.startswith("- [")]
    novas = [
        linha for linha in atuais if linha.startswith("- [") and linha not in antigas
    ]
    while cabeca and not cabeca[-1].strip():
        cabeca.pop()
    arquivo.write_text(
        "\n".join(cabeca + [""] + antigas + novas).rstrip() + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------- arquivos
def _aplicar_arquivo(dados: dict[str, Any]) -> None:
    caminho = Path(dados["caminho"])
    if dados.get("copia"):
        copia = Path(dados["copia"])
        if not copia.exists():
            raise FileNotFoundError("a cópia de antes sumiu")
        caminho.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(copia, caminho)
    elif dados.get("novo"):
        if caminho.exists():
            # o arquivo novo não é apagado: vai para a pasta do desfazer
            shutil.move(
                str(caminho),
                str(
                    pasta_copias()
                    / f"{datetime.now():%Y%m%d-%H%M%S}-removido-{caminho.name}"
                ),
            )
    else:
        raise ValueError("sem cópia de antes")


def _aplicar_organizacao(dados: dict[str, Any]) -> None:
    from nicx.acoes import arquivos

    if arquivos.undo_log(Path(dados["log"])) is None:
        raise FileNotFoundError("o registro da organização sumiu")


_APLICAR: dict[str, Callable[[dict[str, Any]], None]] = {
    "colecao": _aplicar_colecao,
    "nota": _aplicar_nota,
    "notas": _aplicar_notas,
    "arquivo": _aplicar_arquivo,
    "organizacao": _aplicar_organizacao,
}


def desfazer(
    atividade_id: Optional[int] = None,
    *,
    tipos: Optional[list[str]] = None,
    idioma: Optional[str] = None,
) -> tuple[bool, str]:
    """Desfaz uma atividade (a última que dá, se ``atividade_id`` faltar).

    Devolve (deu certo, frase para o usuário).
    """
    reg = registro()
    atividade = (
        reg.obter(atividade_id) if atividade_id else reg.ultima_desfazivel(tipos)
    )
    if atividade is None:
        return False, textos.texto("nada_desfazer", idioma)
    if atividade.desfeito_em:
        return False, textos.texto("ja_desfeito", idioma)
    if not atividade.desfazer or atividade.resultado != "ok":
        return False, textos.texto("nao_desfazivel", idioma)
    aplicar = _APLICAR.get(str(atividade.desfazer.get("tipo")))
    if aplicar is None:
        return False, textos.texto("nao_desfazivel", idioma)
    try:
        with mudancas.sem_registro():
            aplicar(atividade.desfazer)
    except Exception as exc:  # noqa: BLE001 - a frase explica
        logger.warning("Desfazer %s falhou: %s", atividade.id, exc)
        return False, textos.texto("nao_deu_desfazer", idioma, motivo=str(exc))
    reg.marcar_desfeito(atividade.id)
    anotar(
        "desfazer",
        textos.texto("desfeito_titulo", idioma, texto=atividade.titulo),
        detalhe={"atividade": atividade.id},
    )
    return True, textos.texto("desfeito", idioma, texto=atividade.titulo)


__all__ = ["desfazer", "guardar_copia", "limpar_copias", "pasta_copias"]
