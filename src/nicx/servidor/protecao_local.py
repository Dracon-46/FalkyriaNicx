"""Proteção da API local contra sites abertos no navegador.

O servidor do Nicx escuta em 127.0.0.1 sem senha (é o próprio PC). Dois ataques
de um site qualquer que a pessoa abre:

- **DNS rebinding**: o site aponta o próprio domínio para 127.0.0.1 e vira
  "mesma origem" da API. Barrado pelo ``Host``: só nomes do próprio PC.
- **CSRF**: um formulário ou ``fetch(..., {mode: "no-cors"})`` manda um pedido
  "simples" (sem preflight) que muda algo. Barrado pelo ``Origin``/
  ``Sec-Fetch-Site``: os navegadores sempre mandam em POST/PUT/DELETE e em
  WebSocket; a CLI, o lançador e os testes não mandam e continuam passando.

``/webhooks`` fica de fora: recebe chamadas de serviços externos pelo túnel e
confere a assinatura de cada um.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Iterable
from urllib.parse import urlsplit

# "testserver" é o Host do TestClient (testes); não é um domínio que um site use.
HOSTS_DO_PC = frozenset(
    {"127.0.0.1", "localhost", "::1", "tauri.localhost", "testserver"}
)
_SEGUROS = frozenset({"GET", "HEAD", "OPTIONS"})
_LIVRES = ("/webhooks",)

Receber = Callable[[], Awaitable[dict[str, Any]]]
Enviar = Callable[[dict[str, Any]], Awaitable[None]]


def _nome_e_porta(host: str) -> tuple[str, str]:
    """``"127.0.0.1:8765"`` -> ``("127.0.0.1", "8765")``; aceita ``[::1]:80``."""
    host = (host or "").strip().lower()
    if host.startswith("["):
        nome, _, resto = host[1:].partition("]")
        return nome, resto.lstrip(":")
    nome, _, porta = host.partition(":")
    return nome, porta


class ProtecaoLocal:
    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        origens: Iterable[str] = (),
        checar_host: bool = True,
    ) -> None:
        self.app = app
        self.origens = {o.rstrip("/").lower() for o in origens if o and o != "*"}
        self.checar_host = checar_host

    def _origem_ok(self, origem: str, host: str) -> bool:
        origem = origem.rstrip("/").lower()
        if origem in self.origens:
            return True
        partes = urlsplit(origem)
        if partes.scheme not in {"http", "https"} or not partes.hostname:
            return False  # "null" (arquivo, iframe isolado) e esquemas estranhos
        nome_host, porta_host = _nome_e_porta(host)
        mesma_porta = str(partes.port or "") == porta_host
        # A própria tela do Nicx, servida por este servidor.
        return (
            partes.hostname in HOSTS_DO_PC and nome_host in HOSTS_DO_PC and mesma_porta
        )

    async def _recusar(self, scope: dict[str, Any], send: Enviar, motivo: str) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        corpo = json.dumps({"detail": motivo}, ensure_ascii=False).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(corpo)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": corpo})

    async def __call__(
        self, scope: dict[str, Any], receive: Receber, send: Enviar
    ) -> None:
        if scope["type"] not in {"http", "websocket"} or scope.get(
            "path", ""
        ).startswith(_LIVRES):
            await self.app(scope, receive, send)
            return
        cabecalhos = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers") or []
        }
        host = cabecalhos.get("host", "")
        if self.checar_host and _nome_e_porta(host)[0] not in HOSTS_DO_PC:
            await self._recusar(
                scope, send, "endereço não permitido para a API do Nicx"
            )
            return
        muda_algo = (
            scope["type"] == "websocket" or scope.get("method", "GET") not in _SEGUROS
        )
        if muda_algo:
            origem = cabecalhos.get("origin")
            if origem is not None and not self._origem_ok(origem, host):
                await self._recusar(scope, send, "pedido de outro site recusado")
                return
            if cabecalhos.get("sec-fetch-site") == "cross-site" and origem is None:
                await self._recusar(scope, send, "pedido de outro site recusado")
                return
        await self.app(scope, receive, send)


__all__ = ["HOSTS_DO_PC", "ProtecaoLocal"]
