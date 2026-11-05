"""Conta Falkyria: o que a tela e as rotas usam.

LGPD na prática:

- cadastro só com o aceite dos Termos e da Política (as versões vão junto e o
  banco marca a hora); conta antiga sem aceite precisa aceitar antes de usar;
- só o necessário: e-mail, senha (no Supabase Auth), nome opcional e backups
  ilegíveis no servidor;
- a pessoa vê os dados (:func:`estado`, :func:`listar_backups`), corrige o
  nome, exporta tudo (:func:`exportar`) e apaga a conta (:func:`apagar_conta`).
"""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime
from typing import Any, Optional

from nicx.conta import cliente, cofre, cripto
from nicx.conta.cliente import ContaErro

logger = logging.getLogger(__name__)
_LOCK = threading.RLock()
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
MIN_SENHA = 10


def versoes() -> dict[str, str]:
    from nicx.privacidade import POLICY_VERSION, TERMS_VERSION

    return {"termos_versao": TERMS_VERSION, "politica_versao": POLICY_VERSION}


def _validar_email(email: str) -> str:
    email = email.strip().lower()
    if not _EMAIL.match(email):
        raise ContaErro("e-mail inválido")
    return email


def _validar_senha(senha: str) -> None:
    if (
        len(senha) < MIN_SENHA
        or not re.search(r"[A-Za-z]", senha)
        or not re.search(r"\d", senha)
    ):
        raise ContaErro(
            "senha fraca: use pelo menos 10 caracteres, com letras e números"
        )


def _guardar(resposta: dict[str, Any]) -> dict[str, Any]:
    usuario = resposta.get("user") or {}
    sessao = {
        "access_token": resposta["access_token"],
        "refresh_token": resposta["refresh_token"],
        "expires_at": int(
            resposta.get("expires_at")
            or time.time() + int(resposta.get("expires_in", 3600))
        ),
        "email": usuario.get("email", ""),
        "user_id": usuario.get("id", ""),
    }
    cofre.gravar(sessao)
    return sessao


def _sessao() -> dict[str, Any]:
    """A sessão válida (renova o token se estiver vencendo) ou ``ContaErro``."""
    with _LOCK:
        sessao = cofre.ler()
        if sessao is None:
            raise ContaErro("entre na Conta Falkyria primeiro", sessao_acabou=True)
        if int(sessao.get("expires_at", 0)) - 60 > time.time():
            return sessao
        try:
            return _guardar(cliente.renovar(sessao["refresh_token"]))
        except ContaErro as exc:
            if exc.sessao_acabou:
                cofre.apagar()
            raise


def _token() -> str:
    return _sessao()["access_token"]


def _anotar(titulo: str) -> None:
    from nicx.historico.registro import anotar

    anotar("extensao", titulo, detalhe={"tipo": "conta"})


# ------------------------------------------------------------- entrar e sair
def cadastrar(email: str, senha: str, nome: str, aceitou: bool) -> dict[str, Any]:
    if not aceitou:
        raise ContaErro(
            "para criar a conta, aceite os Termos de Uso e a Política de Privacidade"
        )
    email = _validar_email(email)
    _validar_senha(senha)
    resposta = cliente.cadastrar(
        email, senha, {"nome": " ".join(nome.split())[:60], **versoes()}
    )
    # Com confirmação de e-mail ligada, não vem sessão: falta o código.
    if resposta and resposta.get("access_token"):
        _guardar(resposta)
        return {"confirmar": False}
    return {"confirmar": True}


def confirmar(email: str, codigo: str) -> dict[str, Any]:
    _guardar(cliente.verificar(_validar_email(email), codigo.strip(), "signup"))
    _anotar("Conta Falkyria criada")
    return estado()


def reenviar(email: str) -> None:
    cliente.reenviar(_validar_email(email))


def entrar(email: str, senha: str) -> dict[str, Any]:
    _guardar(cliente.entrar(_validar_email(email), senha))
    return estado()


def esqueci(email: str) -> None:
    cliente.recuperar(_validar_email(email))


def redefinir(email: str, codigo: str, nova: str) -> dict[str, Any]:
    _validar_senha(nova)
    _guardar(cliente.verificar(_validar_email(email), codigo.strip(), "recovery"))
    cliente.trocar_senha(_token(), nova)
    return estado()


_ADMIN_CACHE: dict[str, Any] = {"uid": None, "ate": 0.0, "admin": False}
_ADMIN_TTL_S = 600.0


def e_admin() -> bool:
    """A conta logada é de administrador da Falkyria? Na dúvida, não.

    Quem decide é o banco (``nicx_admin_status``: lista de administradores e
    e-mail confirmado); sem conta, sem internet ou com erro, as opções de
    administrador ficam escondidas. Guardado por 10 minutos.
    """
    if cofre.ler() is None:
        return False
    try:
        sessao = _sessao()
    except ContaErro:
        return False
    uid = sessao.get("user_id")
    with _LOCK:
        if _ADMIN_CACHE["uid"] == uid and _ADMIN_CACHE["ate"] > time.time():
            return bool(_ADMIN_CACHE["admin"])
    try:
        status = cliente.rpc("nicx_admin_status", sessao["access_token"])
        admin = isinstance(status, dict) and status.get("admin") is True
    except Exception:  # noqa: BLE001 - na dúvida, escondido
        logger.debug("Não deu para saber se a conta é de administrador", exc_info=True)
        return False
    with _LOCK:
        _ADMIN_CACHE.update(uid=uid, ate=time.time() + _ADMIN_TTL_S, admin=admin)
    return admin


def sair() -> None:
    with _LOCK:
        _ADMIN_CACHE.update(uid=None, ate=0.0, admin=False)
    sessao = cofre.ler()
    cofre.apagar()
    if sessao:
        try:
            cliente.sair(sessao["access_token"])
        except ContaErro:
            logger.debug("Logout no servidor falhou; a sessão local já saiu")


# ------------------------------------------------------------------- perfil
def _perfil(token: str, user_id: str) -> Optional[dict[str, Any]]:
    linhas = cliente.rest(
        "GET",
        "nicx_contas",
        token,
        params={
            "select": "nome,termos_versao,politica_versao,aceitou_em,criado_em",
            "id": f"eq.{user_id}",
        },
    )
    return linhas[0] if linhas else None


def estado() -> dict[str, Any]:
    """Quem está logado, o perfil e se falta aceitar uma versão nova dos termos."""
    base = {"conectado": False, "protegido": cofre.protegido(), **versoes()}
    if cofre.ler() is None:
        return base
    try:
        sessao = _sessao()
        perfil = _perfil(sessao["access_token"], sessao["user_id"]) or {}
    except ContaErro as exc:
        if exc.sessao_acabou:
            return base
        return {**base, "conectado": True, "erro": str(exc)}
    atuais = versoes()
    return {
        **base,
        "conectado": True,
        "email": sessao.get("email", ""),
        "nome": perfil.get("nome", ""),
        "aceitou_em": perfil.get("aceitou_em"),
        "criado_em": perfil.get("criado_em"),
        "precisa_aceitar": (perfil.get("termos_versao"), perfil.get("politica_versao"))
        != (atuais["termos_versao"], atuais["politica_versao"]),
    }


def aceitar() -> dict[str, Any]:
    """Aceite das versões atuais (conta antiga ou termos novos)."""
    sessao = _sessao()
    token, uid = sessao["access_token"], sessao["user_id"]
    if _perfil(token, uid) is None:
        cliente.rest("POST", "nicx_contas", token, json={"id": uid, **versoes()})
    else:
        cliente.rest(
            "PATCH", "nicx_contas", token, params={"id": f"eq.{uid}"}, json=versoes()
        )
    return estado()


def mudar_nome(nome: str) -> dict[str, Any]:
    sessao = _sessao()
    _exigir_aceite()
    cliente.rest(
        "PATCH",
        "nicx_contas",
        sessao["access_token"],
        params={"id": f"eq.{sessao['user_id']}"},
        json={"nome": " ".join(nome.split())[:60]},
    )
    return estado()


def _exigir_aceite() -> None:
    if estado().get("precisa_aceitar"):
        raise ContaErro(
            "aceite os Termos de Uso e a Política de Privacidade atuais primeiro"
        )


# ------------------------------------------------------------------- backup
def fazer_backup(senha_backup: str, rotulo: str = "") -> dict[str, Any]:
    import json

    from nicx import __version__
    from nicx.conta import backup

    _exigir_aceite()
    pacote = backup.montar()
    envelope = cripto.cifrar(json.dumps(pacote, ensure_ascii=False), senha_backup)
    rotulo = " ".join(rotulo.split())[:60] or datetime.now().strftime(
        "Backup de %d/%m/%Y %H:%M"
    )
    (linha,) = cliente.rest(
        "POST",
        "nicx_backups",
        _token(),
        json={
            "rotulo": rotulo,
            "versao_nicx": str(__version__)[:32],
            "conteudo": envelope,
        },
        devolver=True,
    )
    _anotar(f"Backup na Conta Falkyria: {rotulo}")
    return {
        "id": linha["id"],
        "rotulo": linha["rotulo"],
        "criado_em": linha["criado_em"],
        "tamanho": linha["tamanho"],
        "resumo": backup.resumo(pacote),
    }


def listar_backups() -> list[dict[str, Any]]:
    return (
        cliente.rest(
            "GET",
            "nicx_backups",
            _token(),
            params={
                "select": "id,rotulo,versao_nicx,tamanho,criado_em",
                "order": "criado_em.desc",
            },
        )
        or []
    )


def _abrir(backup_id: str, senha_backup: str) -> str:
    linhas = cliente.rest(
        "GET",
        "nicx_backups",
        _token(),
        params={"select": "conteudo", "id": f"eq.{backup_id}"},
    )
    if not linhas:
        raise ContaErro("backup não encontrado")
    try:
        return cripto.decifrar(linhas[0]["conteudo"], senha_backup)
    except cripto.SenhaErrada as exc:
        raise ContaErro(str(exc)) from exc


def previa_backup(backup_id: str, senha_backup: str) -> dict[str, Any]:
    import json

    from nicx.conta import backup

    return backup.resumo(json.loads(_abrir(backup_id, senha_backup)))


def restaurar(backup_id: str, senha_backup: str) -> dict[str, Any]:
    from nicx.conta import backup

    resultado = backup.aplicar(_abrir(backup_id, senha_backup))
    _anotar("Backup da Conta Falkyria restaurado")
    return resultado


def apagar_backup(backup_id: str) -> None:
    cliente.rest("DELETE", "nicx_backups", _token(), params={"id": f"eq.{backup_id}"})


# --------------------------------------------------------------------- LGPD
def exportar() -> dict[str, Any]:
    """Tudo o que a Falkyria guarda desta conta (backups cifrados, como estão)."""
    sessao = _sessao()
    token = sessao["access_token"]
    backups = (
        cliente.rest(
            "GET",
            "nicx_backups",
            token,
            params={
                "select": "id,rotulo,versao_nicx,tamanho,criado_em,conteudo",
                "order": "criado_em.desc",
            },
        )
        or []
    )
    usuario = cliente.chamar("GET", "/auth/v1/user", token=token) or {}
    return {
        "exportado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "conta": {
            "email": usuario.get("email", sessao.get("email", "")),
            "criada_em": usuario.get("created_at"),
            "email_confirmado_em": usuario.get("email_confirmed_at"),
            "ultimo_login_em": usuario.get("last_sign_in_at"),
        },
        "perfil": _perfil(token, sessao["user_id"]),
        "backups": backups,
        "observacao": (
            "Os backups estão cifrados com a sua senha de backup; a Falkyria não "
            "consegue abri-los. Estatísticas anônimas (se você permitiu) não têm "
            "ligação com a conta: apague-as em Configurações > Privacidade."
        ),
    }


def apagar_conta(senha: str) -> None:
    """Confere a senha e apaga login, perfil e backups de uma vez."""
    sessao = _sessao()
    cliente.entrar(sessao["email"], senha)  # confirma que é a pessoa
    cliente.rpc("nicx_apagar_conta", sessao["access_token"])
    cofre.apagar()
    _anotar("Conta Falkyria apagada")


__all__ = [
    "ContaErro",
    "aceitar",
    "apagar_backup",
    "apagar_conta",
    "cadastrar",
    "confirmar",
    "entrar",
    "esqueci",
    "estado",
    "exportar",
    "fazer_backup",
    "listar_backups",
    "mudar_nome",
    "previa_backup",
    "redefinir",
    "reenviar",
    "restaurar",
    "sair",
]
