"""Atende os pedidos de projeto que chegam pelo chat.

``preparar`` recebe a mensagem e devolve:

- ``None`` quando não é pedido de projeto (a mensagem segue para o modelo;
  se ela citar um projeto, a atividade dele é marcada, no máximo de tempos
  em tempos);
- ``Preparo(resposta=...)`` para o que sai na hora, sem modelo: criar,
  listar, ver, o que falta, anotar decisão, pendências, arquivar;
- ``Preparo(resumo=...)`` para "continue de onde parei": o bloco com o
  resumo do projeto, que quem chama anexa no fim da mensagem do usuário.

Nada do conteúdo vai para logs.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nicx.projetos import busca, continuar, deteccao, pedidos
from nicx.projetos.armazenamento import (
    ProjetoErro,
    ProjetoJaExiste,
    Projetos,
    achar_pendencia,
)
from nicx.projetos.modelo import Projeto
from nicx.projetos.textos import pendencias as frase_pendencias
from nicx.projetos.textos import quando, texto

logger = logging.getLogger(__name__)

# Nome não achado e comprido demais: provavelmente não era pedido de projeto.
_MAX_PALAVRAS_NOME = 6


@dataclass(frozen=True)
class Preparo:
    tipo: str
    resposta: Optional[str] = None
    resumo: Optional[str] = None  # bloco para o fim da mensagem
    projeto_id: str = ""


def _lista(projetos: list[Projeto], idioma: Optional[str]) -> str:
    return ", ".join(p.nome for p in projetos[:8])


def _nao_achei(nome: str, projetos: list[Projeto], idioma: Optional[str]) -> str:
    if not projetos:
        return texto("sem_projetos", idioma)
    return texto("nao_achei", idioma, nome=nome, lista=_lista(projetos, idioma))


def _resolver(
    nome: str,
    projetos: list[Projeto],
    sinal: Optional[deteccao.SinalJanela] = None,
) -> Optional[Projeto]:
    """Pelo nome; sem nome, o da janela em uso ou o mais recente."""
    if nome:
        return busca.melhor(nome, projetos)
    if not projetos:
        return None
    return deteccao.projeto_da_janela(projetos, sinal) or projetos[0]


def _resolver_pasta(pasta: str) -> Optional[str]:
    """Caminho completo, nome de pasta aberta no VS Code ou nas do usuário."""
    pasta = pasta.strip().strip("\"'")
    if not pasta:
        return None
    caminho = Path(os.path.expanduser(pasta))
    if caminho.is_absolute():
        return str(caminho) if caminho.is_dir() else None
    achada = deteccao.pasta_do_vscode(pasta)
    if achada:
        return achada
    try:
        from nicx.contexto.arquivo_aberto import pastas_do_usuario

        raizes = [Path.home(), *pastas_do_usuario()]
    except Exception:  # noqa: BLE001
        raizes = [Path.home()]
    for raiz in raizes:
        candidata = raiz / pasta
        if candidata.is_dir():
            return str(candidata)
    return None


def _ver(projeto: Projeto, idioma: Optional[str]) -> str:
    partes = [texto("ver_cabeca", idioma, nome=projeto.nome)]
    if projeto.objetivo:
        partes.append(texto("ver_objetivo", idioma, texto=projeto.objetivo))
    if projeto.estado:
        partes.append(texto("ver_estado", idioma, texto=projeto.estado))
    else:
        partes.append(texto("ver_sem_estado", idioma))
    if projeto.decisoes:
        partes.append(texto("ver_decisao", idioma, texto=projeto.decisoes[-1].texto))
    abertas = projeto.abertas
    if abertas:
        lista = "; ".join(p.texto for p in abertas[:5])
        if len(abertas) > 5:
            lista += f" (+{len(abertas) - 5})"
        partes.append(texto("ver_abertas", idioma, lista=lista))
    else:
        partes.append(texto("ver_sem_abertas", idioma))
    momento = quando(projeto.ultima_atividade, idioma)
    if momento:
        partes.append(texto("ver_atividade", idioma, quando=momento))
    return " ".join(partes)


def _falta(projeto: Projeto, idioma: Optional[str]) -> str:
    abertas = projeto.abertas
    if not abertas:
        return texto("falta_nada", idioma, nome=projeto.nome)
    lista = "; ".join(p.texto for p in abertas[:10])
    if len(abertas) > 10:
        lista += f" (+{len(abertas) - 10})"
    return texto("falta", idioma, nome=projeto.nome, lista=lista)


def _listar(projetos: list[Projeto], idioma: Optional[str]) -> str:
    if not projetos:
        return texto("sem_projetos", idioma)
    itens = [
        texto(
            "item",
            idioma,
            nome=p.nome,
            pendencias=frase_pendencias(len(p.abertas), idioma),
        )
        for p in projetos[:12]
    ]
    return texto("lista", idioma, lista="; ".join(itens))


def _criar(
    pedido: pedidos.Pedido,
    loja: Projetos,
    idioma: Optional[str],
    sinal: Optional[deteccao.SinalJanela],
) -> str:
    pastas: list[str] = []
    aviso = ""
    if pedido.pasta:
        achada = _resolver_pasta(pedido.pasta)
        if achada:
            pastas.append(achada)
        else:
            aviso = texto("pasta_nao_achada", idioma, pasta=pedido.pasta)
    else:
        # Sem pasta dita: a pasta aberta no VS Code, se tiver o mesmo nome.
        sinal = sinal if sinal is not None else deteccao.sinal_da_janela()
        if sinal is not None and sinal.pasta_aberta:
            mesmo = busca.normalizar(sinal.pasta_aberta).replace(" ", "")
            if mesmo == busca.normalizar(pedido.nome).replace(" ", ""):
                achada = deteccao.pasta_do_vscode(sinal.pasta_aberta)
                if achada:
                    pastas.append(achada)
    try:
        projeto = loja.criar(pedido.nome, pastas=pastas, idioma=idioma or "")
    except ProjetoJaExiste as existe:
        return texto("ja_existe", idioma, nome=existe.projeto.nome)
    resposta = texto("criado", idioma, nome=projeto.nome)
    if projeto.pastas:
        resposta += texto("criado_pasta", idioma, pasta=projeto.pastas[0])
    return resposta + aviso


def _separar_junto(
    junto: str, projetos: list[Projeto]
) -> tuple[Optional[Projeto], str]:
    """ "Lumen comprar o domínio" -> (Lumen, "comprar o domínio")."""
    projeto = busca.nome_no_comeco(junto, projetos)
    if projeto is None:
        return None, ""
    alvo = busca.normalizar(projeto.nome).replace(" ", "")
    palavras = junto.split()
    corpo = ""
    for i in range(1, len(palavras) + 1):
        if busca.normalizar(" ".join(palavras[:i])).replace(" ", "") == alvo:
            corpo = " ".join(palavras[i:])
            break
    corpo = re.sub(r"^(?:que|de|:|-|that|to)\s+", "", corpo.strip(), flags=re.I)
    return projeto, corpo.strip()


def preparar(
    mensagem: str,
    *,
    idioma: Optional[str] = None,
    primeira: bool = True,
    loja: Optional[Projetos] = None,
    sinal: Optional[deteccao.SinalJanela] = None,
    max_resumo: int = continuar.MAX_PADRAO,
) -> Optional[Preparo]:
    """O que fazer com *mensagem* (ver o docstring do módulo)."""
    loja = loja or Projetos()
    pedido = pedidos.detectar(mensagem, primeira=primeira)
    if pedido is None:
        _marcar_mencao(mensagem, loja)
        return None
    tipo = pedido.tipo
    if tipo == pedidos.CRIAR:
        return Preparo(tipo, resposta=_criar(pedido, loja, idioma, sinal))

    projetos = loja.listar()
    if tipo == pedidos.LISTAR:
        return Preparo(tipo, resposta=_listar(projetos, idioma))

    if tipo == pedidos.CONTINUAR:
        if not projetos:
            return Preparo(tipo, resposta=texto("continuar_sem_projetos", idioma))
        projeto = _resolver(pedido.nome, projetos, sinal)
        if projeto is None:
            if len(pedido.nome.split()) > _MAX_PALAVRAS_NOME:
                return None
            return Preparo(tipo, resposta=_nao_achei(pedido.nome, projetos, idioma))
        resumo = continuar.montar(
            projeto, continuar.coletar(projeto), max_caracteres=max_resumo
        )
        deteccao.registrar_atividade(projeto, loja=loja)
        logger.debug("Continuar: resumo de %d caracteres", len(resumo))
        return Preparo(
            tipo, resumo=continuar.bloco(projeto, resumo), projeto_id=projeto.id
        )

    if tipo == pedidos.PENDENCIA and pedido.junto:
        projeto, corpo = _separar_junto(pedido.nome, projetos)
        if projeto is None:
            return Preparo(tipo, resposta=_nao_achei(pedido.nome, projetos, idioma))
        pedido = pedidos.Pedido(tipo, nome=projeto.nome, texto=corpo)
    elif tipo == pedidos.CONCLUIR and not pedido.nome:
        # Sem projeto dito: a pendência aberta que combinar, em qualquer um.
        # Nenhuma combina: "marca a tarefa X como feita" era sobre outra coisa.
        for candidato in projetos:
            if achar_pendencia(pedido.texto, candidato.abertas) is not None:
                pedido = pedidos.Pedido(tipo, nome=candidato.nome, texto=pedido.texto)
                break
        else:
            return None

    projeto = _resolver(pedido.nome, projetos, sinal)
    if projeto is None:
        # "Como está o projeto de lei X?" é pergunta para o modelo (que tem a
        # ferramenta ``projetos`` se for mesmo um projeto do usuário).
        if tipo == pedidos.VER or len(pedido.nome.split()) > _MAX_PALAVRAS_NOME:
            return None
        return Preparo(tipo, resposta=_nao_achei(pedido.nome, projetos, idioma))
    try:
        resposta = _executar(pedido, projeto, loja, idioma)
    except ProjetoErro:
        resposta = texto("falta_texto", idioma, nome=projeto.nome)
    return Preparo(tipo, resposta=resposta, projeto_id=projeto.id)


def _executar(
    pedido: pedidos.Pedido, projeto: Projeto, loja: Projetos, idioma: Optional[str]
) -> str:
    tipo = pedido.tipo
    if tipo in (pedidos.VER, pedidos.FALTA):
        deteccao.registrar_atividade(projeto, loja=loja)
        return _ver(projeto, idioma) if tipo == pedidos.VER else _falta(projeto, idioma)
    if tipo in (pedidos.DECISAO, pedidos.PENDENCIA, pedidos.ESTADO, pedidos.CONCLUIR):
        if not pedido.texto.strip():
            return texto("falta_texto", idioma, nome=projeto.nome)
    if tipo == pedidos.DECISAO:
        decisao = loja.registrar_decisao(projeto.id, pedido.texto)
        return texto("decisao_ok", idioma, nome=projeto.nome, texto=decisao.texto)
    if tipo == pedidos.PENDENCIA:
        pendencia = loja.adicionar_pendencia(projeto.id, pedido.texto)
        return texto("pendencia_ok", idioma, nome=projeto.nome, texto=pendencia.texto)
    if tipo == pedidos.ESTADO:
        atualizado = loja.atualizar_estado(projeto.id, pedido.texto)
        return texto("estado_ok", idioma, nome=projeto.nome, texto=atualizado.estado)
    if tipo == pedidos.CONCLUIR:
        feita = loja.concluir_pendencia(projeto.id, pedido.texto)
        if feita is None:
            lista = "; ".join(p.texto for p in projeto.abertas[:6]) or "-"
            return texto("pendencia_nao_achada", idioma, nome=projeto.nome, lista=lista)
        return texto("concluida_ok", idioma, nome=projeto.nome, texto=feita.texto)
    if tipo == pedidos.ARQUIVAR:
        loja.arquivar(projeto.id)
        return texto("arquivado", idioma, nome=projeto.nome)
    if tipo == pedidos.RENOMEAR:
        try:
            novo = loja.renomear(projeto.id, pedido.novo_nome)
        except ProjetoJaExiste as existe:
            return texto("ja_existe", idioma, nome=existe.projeto.nome)
        return texto("renomeado", idioma, nome=novo.nome)
    return _ver(projeto, idioma)


def _marcar_mencao(mensagem: str, loja: Projetos) -> None:
    """Conversa que cita "o projeto X" marca atividade em X (sem gravar sempre)."""
    if not pedidos.menciona_projeto(mensagem):
        return
    try:
        if not loja.caminho.exists():
            return
        t = f" {busca.normalizar(mensagem)} "
        for projeto in loja.listar():
            nome = busca.normalizar(projeto.nome)
            if nome and f" {nome} " in t:
                deteccao.registrar_atividade(projeto, loja=loja)
                return
    except Exception:  # noqa: BLE001 — nunca atrapalha a conversa
        logger.debug("Não deu para marcar a menção ao projeto", exc_info=True)


__all__ = ["Preparo", "preparar"]
