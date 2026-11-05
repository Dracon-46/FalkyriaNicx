"""Rotas da Conta Falkyria (opcional).

- ``GET /v1/conta``: quem está logado, o perfil e se falta aceitar os termos.
- ``POST /v1/conta/cadastrar`` / ``confirmar`` / ``reenviar`` / ``entrar`` /
  ``esqueci`` / ``redefinir`` / ``sair`` / ``aceitar``; ``PUT /v1/conta/nome``.
- ``GET /v1/conta/backups``; ``POST /v1/conta/backups`` (``{"senha", "rotulo"}``);
  ``POST /v1/conta/backups/{id}/previa`` e ``/restaurar`` (``{"senha"}``);
  ``DELETE /v1/conta/backups/{id}``.
- ``GET /v1/conta/exportar``: tudo o que a Falkyria guarda desta conta (LGPD).
- ``POST /v1/conta/apagar`` (``{"senha"}``): apaga login, perfil e backups.

As senhas passam só por aqui, no PC, a caminho do Supabase Auth (a da conta)
ou da cifra local (a do backup); nada é guardado nem vai para o log.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/conta", tags=["conta"])


class Email(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class Entrada(Email):
    senha: str = Field(min_length=1, max_length=200)


class Cadastro(Entrada):
    nome: str = Field(default="", max_length=60)
    aceitou: bool = False


class Codigo(Email):
    codigo: str = Field(min_length=4, max_length=12)


class Redefinicao(Codigo):
    senha: str = Field(min_length=1, max_length=200)


class Nome(BaseModel):
    nome: str = Field(default="", max_length=60)


class Senha(BaseModel):
    senha: str = Field(min_length=1, max_length=200)


class Aceite(BaseModel):
    """As versões que a pessoa leu: só grava se ainda forem as atuais."""

    termos_versao: str = Field(min_length=1, max_length=20)
    politica_versao: str = Field(min_length=1, max_length=20)


class NovoBackup(Senha):
    rotulo: str = Field(default="", max_length=60)


async def _rodar(funcao: Callable[[], Any]) -> Any:
    from nicx.conta.cliente import ContaErro

    try:
        return await asyncio.to_thread(funcao)
    except ContaErro as exc:
        status = 401 if exc.sessao_acabou else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except ValueError as exc:  # backup vazio, senha do backup curta, pacote inválido
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("")
async def estado():
    from nicx.conta import servico

    return await _rodar(servico.estado)


@router.get("/admin")
async def admin():
    """Mostrar as opções de administrador? Só com conta de administrador."""
    from nicx.conta import servico

    return {"admin": await asyncio.to_thread(servico.e_admin)}


@router.post("/cadastrar")
async def cadastrar(pedido: Cadastro):
    from nicx.conta import servico

    return await _rodar(
        lambda: servico.cadastrar(
            pedido.email, pedido.senha, pedido.nome, pedido.aceitou
        )
    )


@router.post("/confirmar")
async def confirmar(pedido: Codigo):
    from nicx.conta import servico

    return await _rodar(lambda: servico.confirmar(pedido.email, pedido.codigo))


@router.post("/reenviar")
async def reenviar(pedido: Email):
    from nicx.conta import servico

    await _rodar(lambda: servico.reenviar(pedido.email))
    return {"ok": True}


@router.post("/entrar")
async def entrar(pedido: Entrada):
    from nicx.conta import servico

    return await _rodar(lambda: servico.entrar(pedido.email, pedido.senha))


@router.post("/esqueci")
async def esqueci(pedido: Email):
    from nicx.conta import servico

    await _rodar(lambda: servico.esqueci(pedido.email))
    return {"ok": True}


@router.post("/redefinir")
async def redefinir(pedido: Redefinicao):
    from nicx.conta import servico

    return await _rodar(
        lambda: servico.redefinir(pedido.email, pedido.codigo, pedido.senha)
    )


@router.post("/sair")
async def sair():
    from nicx.conta import servico

    await _rodar(servico.sair)
    return {"ok": True}


@router.post("/aceitar")
async def aceitar(pedido: Aceite):
    from nicx.conta import servico

    atuais = servico.versoes()
    lidas = (pedido.termos_versao, pedido.politica_versao)
    if lidas != (atuais["termos_versao"], atuais["politica_versao"]):
        # A tela mostrava textos de outra versão: não dá para registrar um
        # aceite do que a pessoa não leu.
        raise HTTPException(
            status_code=409,
            detail=(
                "Os Termos ou a Política mudaram. Leia a versão nova e aceite de novo."
            ),
        )
    return await _rodar(servico.aceitar)


@router.put("/nome")
async def mudar_nome(pedido: Nome):
    from nicx.conta import servico

    return await _rodar(lambda: servico.mudar_nome(pedido.nome))


@router.get("/backups")
async def listar_backups():
    from nicx.conta import servico

    return {"backups": await _rodar(servico.listar_backups)}


@router.post("/backups")
async def fazer_backup(pedido: NovoBackup):
    from nicx.conta import servico

    return await _rodar(lambda: servico.fazer_backup(pedido.senha, pedido.rotulo))


@router.post("/backups/{backup_id}/previa")
async def previa_backup(backup_id: str, pedido: Senha):
    from nicx.conta import servico

    return await _rodar(lambda: servico.previa_backup(backup_id, pedido.senha))


@router.post("/backups/{backup_id}/restaurar")
async def restaurar(request: Request, backup_id: str, pedido: Senha):
    from nicx.conta import servico
    from nicx.servidor.rotas.extensoes import _religar

    resultado = await _rodar(lambda: servico.restaurar(backup_id, pedido.senha))
    await asyncio.to_thread(_religar, request.app.state)
    return resultado


@router.delete("/backups/{backup_id}")
async def apagar_backup(backup_id: str):
    from nicx.conta import servico

    await _rodar(lambda: servico.apagar_backup(backup_id))
    return {"ok": True}


@router.get("/exportar")
async def exportar():
    from nicx.conta import servico

    return await _rodar(servico.exportar)


@router.post("/apagar")
async def apagar_conta(pedido: Senha):
    from nicx.conta import servico

    await _rodar(lambda: servico.apagar_conta(pedido.senha))
    return {"ok": True}


__all__ = ["router"]
