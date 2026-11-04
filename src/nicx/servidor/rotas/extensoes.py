"""Rotas das extensões (leva F): servidores MCP, habilidades e pacotes.

Servidores MCP:

- ``GET /v1/extensoes/mcp``: os servidores (token e ambiente escondidos), a
  situação de cada um, o catálogo e se o ``npx`` existe no PC.
- ``POST /v1/extensoes/mcp`` / ``PUT /v1/extensoes/mcp/{id}`` /
  ``DELETE /v1/extensoes/mcp/{id}``.
- ``POST /v1/extensoes/mcp/testar``: liga, lista as ferramentas e desliga (com
  ``id``, usa o token guardado no lugar da máscara).
- ``POST /v1/extensoes/mcp/recarregar``: liga as mudanças no chat sem reiniciar.

Habilidades (``SKILL.md``):

- ``GET /v1/extensoes/habilidades``; ``POST`` cria (título, descrição, instruções);
  ``PUT /{nome}`` reescreve uma criada no Nicx; ``PUT /{nome}/ativa``;
  ``DELETE /{nome}``.
- ``POST /v1/extensoes/habilidades/importar`` (.zip) e ``/github`` (repositório):
  ``scripts/`` nunca vem; habilidade que pede permissão perigosa só entra com
  ``confirmar``.
- ``POST /v1/extensoes/habilidades/recarregar``: liga as mudanças no chat.

Pacotes:

- ``GET /v1/extensoes/pacotes?idioma=``: os prontos (com a prévia) e os instalados.
- ``POST /v1/extensoes/pacotes/previa`` (``{"conteudo": "<json>"}``): o que entra
  e o que o pacote pode fazer, sem instalar.
- ``POST /v1/extensoes/pacotes/instalar`` (``{"pronto": "professor"}`` ou
  ``{"conteudo": "<json>", "com_mcp": false}``); ``DELETE /v1/extensoes/pacotes/{id}``.
- ``POST /v1/extensoes/pacotes/exportar``: monta um pacote com os itens escolhidos.

Loja da Falkyria (Supabase; o app só lê e confere a assinatura):

- ``GET /v1/extensoes/loja``: o catálogo publicado, com o instalado e atualizações.
- ``GET /v1/extensoes/loja/{id}``: a prévia do pacote, já conferido.
- ``POST /v1/extensoes/loja/{id}/instalar`` (``{"com_mcp": false}``).
"""

from __future__ import annotations

import asyncio
import shutil
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/extensoes", tags=["extensoes"])
_SERVIDOR_NAO_ACHADO = "servidor não encontrado"


class ServidorPedido(BaseModel):
    nome: str = Field(min_length=1, max_length=40)
    tipo: str = "stdio"
    comando: str = Field(default="", max_length=500)
    args: list[str] = []
    env: dict[str, str] = {}
    url: str = Field(default="", max_length=500)
    token: str = Field(default="", max_length=4000)
    incluir: list[str] = []
    excluir: list[str] = []
    ativo: bool = True
    confianca: str = "perguntar"
    descricao: str = Field(default="", max_length=200)


class Teste(ServidorPedido):
    id: Optional[str] = None


def _servidor(pedido: BaseModel):
    from nicx.extensoes.mcp import Servidor

    dados = pedido.model_dump()
    dados.pop("id", None)
    return Servidor.de_dict(dados)


@router.get("/mcp")
async def listar_mcp():
    from nicx.extensoes import catalogo_mcp, mcp

    def _ler() -> dict[str, Any]:
        situacao = mcp.situacao()
        return {
            "servidores": [
                {**mcp.publico(s), "situacao": situacao.get(s.id)} for s in mcp.listar()
            ],
            "catalogo": [m.para_dict() for m in catalogo_mcp.CATALOGO],
            "npx": shutil.which("npx") is not None,
        }

    return await asyncio.to_thread(_ler)


@router.post("/mcp")
async def criar_mcp(pedido: ServidorPedido):
    from nicx.extensoes import mcp

    try:
        servidor = await asyncio.to_thread(mcp.criar, _servidor(pedido))
    except mcp.ServidorInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return mcp.publico(servidor)


@router.post("/mcp/testar")
async def testar_mcp(pedido: Teste):
    from nicx.extensoes import mcp

    servidor = _servidor(pedido)
    if pedido.id:
        servidor = mcp.com_segredos_antigos(servidor, mcp.obter(pedido.id))
    try:
        mcp.validar(servidor)
    except mcp.ServidorInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await asyncio.to_thread(mcp.testar, servidor)


@router.post("/mcp/recarregar")
async def recarregar_mcp(request: Request):
    from nicx.extensoes import mcp

    situacao = await asyncio.to_thread(mcp.recarregar, request.app.state)
    return {"situacao": situacao}


@router.put("/mcp/{servidor_id}")
async def atualizar_mcp(servidor_id: str, pedido: ServidorPedido):
    from nicx.extensoes import mcp

    try:
        servidor = await asyncio.to_thread(
            mcp.atualizar, servidor_id, _servidor(pedido)
        )
    except mcp.ServidorInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=_SERVIDOR_NAO_ACHADO) from exc
    return mcp.publico(servidor)


@router.delete("/mcp/{servidor_id}")
async def apagar_mcp(servidor_id: str):
    from nicx.extensoes import mcp

    if not await asyncio.to_thread(mcp.apagar, servidor_id):
        raise HTTPException(status_code=404, detail=_SERVIDOR_NAO_ACHADO)
    return {"ok": True}


# --------------------------------------------------------------- habilidades
_HABILIDADE_NAO_ACHADA = "habilidade não encontrada"


class HabilidadePedido(BaseModel):
    titulo: str = Field(min_length=1, max_length=60)
    descricao: str = Field(min_length=1, max_length=1024)
    instrucoes: str = Field(min_length=1, max_length=20_000)


class Ativa(BaseModel):
    ativa: bool


class Github(BaseModel):
    url: str = Field(min_length=10, max_length=300)
    nomes: list[str] = []
    confirmar: bool = False


@router.get("/habilidades")
async def listar_habilidades():
    from nicx.extensoes import habilidades

    def _ler() -> dict[str, Any]:
        return {
            "habilidades": [h.para_dict() for h in habilidades.listar()],
            "pasta": str(habilidades.pasta()),
        }

    return await asyncio.to_thread(_ler)


@router.post("/habilidades")
async def criar_habilidade(pedido: HabilidadePedido):
    from nicx.extensoes import habilidades

    try:
        h = await asyncio.to_thread(
            habilidades.salvar, pedido.titulo, pedido.descricao, pedido.instrucoes
        )
    except habilidades.HabilidadeInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return h.para_dict()


@router.post("/habilidades/importar")
async def importar_habilidades(
    arquivo: UploadFile = File(...), confirmar: bool = Form(False)
):
    from nicx.extensoes import habilidades

    dados = await arquivo.read(habilidades.MAX_ZIP + 1)
    try:
        resultados = await asyncio.to_thread(habilidades.importar_zip, dados, confirmar)
    except habilidades.HabilidadeInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"resultados": resultados}


@router.post("/habilidades/github")
async def instalar_do_github(pedido: Github):
    from nicx.extensoes import habilidades

    try:
        resultados = await asyncio.to_thread(
            habilidades.importar_github, pedido.url, pedido.nomes, pedido.confirmar
        )
    except habilidades.HabilidadeInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"resultados": resultados}


@router.post("/habilidades/recarregar")
async def recarregar_habilidades(request: Request):
    from nicx.extensoes import habilidades

    agente = getattr(request.app.state, "agent", None)
    total = await asyncio.to_thread(
        habilidades.ligar_no_agente, agente, getattr(request.app.state, "bus", None)
    )
    return {"ligadas": total}


@router.put("/habilidades/{nome}")
async def atualizar_habilidade(nome: str, pedido: HabilidadePedido):
    from nicx.extensoes import habilidades

    atual = await asyncio.to_thread(habilidades.obter, nome)
    if atual is None:
        raise HTTPException(status_code=404, detail=_HABILIDADE_NAO_ACHADA)
    if not atual.editavel:
        raise HTTPException(
            status_code=400, detail="só dá para editar as criadas no Nicx"
        )
    try:
        h = await asyncio.to_thread(
            lambda: habilidades.salvar(
                pedido.titulo,
                pedido.descricao,
                pedido.instrucoes,
                nome,
                substituir=True,
            )
        )
    except habilidades.HabilidadeInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return h.para_dict()


@router.put("/habilidades/{nome}/ativa")
async def ligar_habilidade(nome: str, pedido: Ativa):
    from nicx.extensoes import habilidades

    try:
        await asyncio.to_thread(habilidades.ligar, nome, pedido.ativa)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=_HABILIDADE_NAO_ACHADA) from exc
    return {"nome": nome, "ativa": pedido.ativa}


@router.delete("/habilidades/{nome}")
async def apagar_habilidade(nome: str):
    from nicx.extensoes import habilidades

    try:
        apagou = await asyncio.to_thread(habilidades.apagar, nome)
    except habilidades.HabilidadeInvalida as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not apagou:
        raise HTTPException(status_code=404, detail=_HABILIDADE_NAO_ACHADA)
    return {"ok": True}


# ------------------------------------------------------------------ pacotes
class Conteudo(BaseModel):
    conteudo: str = Field(min_length=2, max_length=1024 * 1024)


class Instalacao(BaseModel):
    pronto: Optional[str] = None
    conteudo: Optional[str] = Field(default=None, max_length=1024 * 1024)
    com_mcp: bool = False
    idioma: Optional[str] = None


class Exportacao(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    nome: str = Field(min_length=1, max_length=60)
    descricao: str = Field(default="", max_length=300)
    autor: str = Field(default="", max_length=60)
    versao: str = Field(default="1.0.0", max_length=20)
    assistentes: list[str] = []
    rotinas: list[str] = []
    habilidades: list[str] = []
    mcp: list[str] = []


def _religar(app_state: Any) -> None:
    """MCP e habilidades novos (ou removidos) valem no chat sem reiniciar."""
    from nicx.extensoes import habilidades, mcp

    mcp.recarregar(app_state)
    habilidades.ligar_no_agente(
        getattr(app_state, "agent", None), getattr(app_state, "bus", None)
    )


@router.get("/pacotes")
async def listar_pacotes(idioma: Optional[str] = None):
    from nicx.extensoes import pacotes, pacotes_prontos

    def _ler() -> dict[str, Any]:
        return {
            "prontos": [pacotes.previa(p) for p in pacotes_prontos.prontos(idioma)],
            "instalados": pacotes.instalados(),
        }

    return await asyncio.to_thread(_ler)


@router.post("/pacotes/previa")
async def previa_pacote(pedido: Conteudo):
    from nicx.extensoes import pacotes

    try:
        pacote = pacotes.ler(pedido.conteudo)
    except pacotes.PacoteInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await asyncio.to_thread(pacotes.previa, pacote)


@router.post("/pacotes/instalar")
async def instalar_pacote(request: Request, pedido: Instalacao):
    from nicx.extensoes import pacotes, pacotes_prontos

    if pedido.pronto:
        pacote = pacotes_prontos.pronto(pedido.pronto, pedido.idioma)
        if pacote is None:
            raise HTTPException(status_code=404, detail="pacote não encontrado")
    elif pedido.conteudo:
        try:
            pacote = pacotes.ler(pedido.conteudo)
        except pacotes.PacoteInvalido as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=400, detail="falta o pacote")
    resultado = await asyncio.to_thread(
        lambda: pacotes.instalar(pacote, com_mcp=pedido.com_mcp)
    )
    await asyncio.to_thread(_religar, request.app.state)
    return resultado


@router.post("/pacotes/exportar")
async def exportar_pacote(pedido: Exportacao):
    from nicx.extensoes import pacotes

    try:
        return await asyncio.to_thread(
            lambda: pacotes.exportar(
                pedido.id,
                pedido.nome,
                pedido.descricao,
                pedido.autor,
                pedido.versao,
                assistentes_ids=pedido.assistentes,
                rotinas_ids=pedido.rotinas,
                habilidades_nomes=pedido.habilidades,
                mcp_ids=pedido.mcp,
            )
        )
    except pacotes.PacoteInvalido as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/pacotes/{pacote_id}")
async def desinstalar_pacote(request: Request, pacote_id: str):
    from nicx.extensoes import pacotes

    if not await asyncio.to_thread(pacotes.desinstalar, pacote_id):
        raise HTTPException(status_code=404, detail="pacote não instalado")
    await asyncio.to_thread(_religar, request.app.state)
    return {"ok": True}


# --------------------------------------------------------------------- loja
class InstalacaoLoja(BaseModel):
    com_mcp: bool = False


def _erro_loja(exc: Exception) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/loja")
async def catalogo_loja():
    from nicx.extensoes import loja

    try:
        return {"pacotes": await asyncio.to_thread(loja.catalogo)}
    except loja.LojaErro as exc:
        raise _erro_loja(exc) from exc


@router.get("/loja/{pacote_id}")
async def previa_loja(pacote_id: str):
    from nicx.extensoes import loja

    try:
        return await asyncio.to_thread(loja.previa, pacote_id)
    except loja.LojaErro as exc:
        raise _erro_loja(exc) from exc


@router.post("/loja/{pacote_id}/instalar")
async def instalar_da_loja(request: Request, pacote_id: str, pedido: InstalacaoLoja):
    from nicx.extensoes import loja

    try:
        resultado = await asyncio.to_thread(
            lambda: loja.instalar(pacote_id, com_mcp=pedido.com_mcp)
        )
    except loja.LojaErro as exc:
        raise _erro_loja(exc) from exc
    await asyncio.to_thread(_religar, request.app.state)
    return resultado


__all__ = ["router"]
