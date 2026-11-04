"""Supabase Auth (GoTrue) e banco (PostgREST) da Falkyria, por HTTP.

Mesmo projeto e chave pública das estatísticas (``[analytics] host/key``), mas
sem ligação com elas: aqui vai o token da sessão da pessoa, lá o id anônimo.
Os erros do Auth viram frases em português (:class:`ContaErro`).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

PRAZO_S = 20.0
# Página do site que abre os links dos e-mails (confirmar a conta, senha nova)
# enquanto a Falkyria não tem um serviço de e-mail próprio para mandar códigos.
SITE_CONTA = "https://dracon-46.github.io/nicx/conta/"

# código do Supabase Auth -> frase para a pessoa
_ERROS = {
    "invalid_credentials": "e-mail ou senha errados",
    "email_not_confirmed": "confirme o e-mail com o código que enviamos",
    "user_already_exists": "já existe uma conta com esse e-mail",
    "email_exists": "já existe uma conta com esse e-mail",
    "weak_password": "senha fraca: use pelo menos 10 caracteres, com letras e números",
    "over_email_send_rate_limit": "muitos e-mails em pouco tempo; espere um pouco e tente de novo",  # noqa: E501
    "over_request_rate_limit": "muitas tentativas; espere um pouco e tente de novo",
    "otp_expired": "código errado ou vencido",
    "signup_disabled": "o cadastro de contas está fechado no momento",
    "email_address_invalid": "e-mail inválido",
    "email_address_not_authorized": "o envio de e-mails da Falkyria ainda não está liberado para esse endereço",  # noqa: E501
    "same_password": "a senha nova precisa ser diferente da atual",
    "session_not_found": "a sessão acabou; entre de novo",
    "refresh_token_not_found": "a sessão acabou; entre de novo",
    "refresh_token_already_used": "a sessão acabou; entre de novo",
}


class ContaErro(RuntimeError):
    """Falha da conta com a frase para mostrar."""

    def __init__(self, mensagem: str, *, sessao_acabou: bool = False) -> None:
        super().__init__(mensagem)
        self.sessao_acabou = sessao_acabou


def destino() -> tuple[str, str]:
    from nicx.nucleo.config import AnalyticsConfig

    padrao = AnalyticsConfig()
    try:
        from nicx.nucleo.config import load_config

        cfg = load_config().analytics
        return (cfg.host or padrao.host).rstrip("/"), cfg.key or padrao.key
    except Exception:  # noqa: BLE001
        return padrao.host.rstrip("/"), padrao.key


def _cabecalhos(token: Optional[str] = None) -> dict[str, str]:
    _, chave = destino()
    cab = {"apikey": chave, "Content-Type": "application/json"}
    if token:
        cab["Authorization"] = f"Bearer {token}"
    elif chave.startswith("eyJ"):
        cab["Authorization"] = f"Bearer {chave}"
    return cab


def _erro(resposta: Any) -> ContaErro:
    try:
        corpo = resposta.json()
    except ValueError:
        corpo = {}
    codigo = str(
        corpo.get("error_code") or corpo.get("code") or corpo.get("error") or ""
    )
    mensagem = _ERROS.get(codigo)
    if mensagem is None:
        texto = str(
            corpo.get("msg")
            or corpo.get("message")
            or corpo.get("error_description")
            or ""
        )
        if "limite de backups" in texto:
            mensagem = "limite de backups por dia atingido"
        else:
            logger.info(
                "Conta: resposta %s (%s)", resposta.status_code, codigo or texto[:80]
            )
            mensagem = f"o servidor da Falkyria respondeu {resposta.status_code}"
    acabou = resposta.status_code == 401 or codigo in {
        "session_not_found",
        "refresh_token_not_found",
        "refresh_token_already_used",
        "bad_jwt",
    }
    return ContaErro(mensagem, sessao_acabou=acabou)


def chamar(
    metodo: str,
    caminho: str,
    *,
    token: Optional[str] = None,
    json: Any = None,
    params: Optional[dict[str, str]] = None,
    extra: Optional[dict[str, str]] = None,
) -> Any:
    import httpx

    host, _ = destino()
    try:
        resposta = httpx.request(
            metodo,
            f"{host}{caminho}",
            json=json,
            params=params,
            headers={**_cabecalhos(token), **(extra or {})},
            timeout=PRAZO_S,
        )
    except httpx.HTTPError as exc:
        raise ContaErro("sem conexão com o servidor da Falkyria") from exc
    if resposta.status_code >= 400:
        raise _erro(resposta)
    if resposta.status_code == 204 or not resposta.content:
        return None
    return resposta.json()


# ------------------------------------------------------------------- Auth
def cadastrar(email: str, senha: str, metadados: dict[str, str]) -> dict[str, Any]:
    return chamar(
        "POST",
        "/auth/v1/signup",
        params={"redirect_to": SITE_CONTA},
        json={"email": email, "password": senha, "data": metadados},
    )


def verificar(email: str, codigo: str, tipo: str) -> dict[str, Any]:
    return chamar(
        "POST", "/auth/v1/verify", json={"type": tipo, "email": email, "token": codigo}
    )


def reenviar(email: str) -> None:
    chamar(
        "POST",
        "/auth/v1/resend",
        params={"redirect_to": SITE_CONTA},
        json={"type": "signup", "email": email},
    )


def entrar(email: str, senha: str) -> dict[str, Any]:
    return chamar(
        "POST",
        "/auth/v1/token",
        params={"grant_type": "password"},
        json={"email": email, "password": senha},
    )


def renovar(refresh_token: str) -> dict[str, Any]:
    return chamar(
        "POST",
        "/auth/v1/token",
        params={"grant_type": "refresh_token"},
        json={"refresh_token": refresh_token},
    )


def recuperar(email: str) -> None:
    chamar(
        "POST",
        "/auth/v1/recover",
        params={"redirect_to": SITE_CONTA},
        json={"email": email},
    )


def trocar_senha(token: str, nova: str) -> None:
    chamar("PUT", "/auth/v1/user", token=token, json={"password": nova})


def sair(token: str) -> None:
    chamar("POST", "/auth/v1/logout", token=token)


# ------------------------------------------------------------------- banco
def rest(
    metodo: str,
    tabela: str,
    token: str,
    *,
    params: Optional[dict[str, str]] = None,
    json: Any = None,
    devolver: bool = False,
) -> Any:
    extra = {"Prefer": "return=representation"} if devolver else None
    return chamar(
        metodo, f"/rest/v1/{tabela}", token=token, params=params, json=json, extra=extra
    )


def rpc(funcao: str, token: str, argumentos: Optional[dict[str, Any]] = None) -> Any:
    return chamar("POST", f"/rest/v1/rpc/{funcao}", token=token, json=argumentos or {})


__all__ = [
    "ContaErro",
    "cadastrar",
    "chamar",
    "destino",
    "entrar",
    "recuperar",
    "reenviar",
    "renovar",
    "rest",
    "rpc",
    "sair",
    "trocar_senha",
    "verificar",
]
