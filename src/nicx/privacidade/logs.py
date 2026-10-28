"""Avisos e erros do Nicx para o Painel Falkyria (só com consentimento).

Um handler de logging pega tudo de WARNING para cima, agrupa por tipo
(mesmo logger + mesmo modelo de mensagem) e manda, a cada minuto, uma
linha por tipo com quantas vezes aconteceu. A mensagem é limpa aqui, antes
de sair do PC:

- textos entre aspas viram "…" (é onde costuma aparecer o que a pessoa
  digitou ou o nome de um arquivo);
- caminhos, e-mails, links, IPs, tokens e números longos são trocados por
  marcadores;
- se ainda sobrar algo com cara de dado pessoal, vai só o modelo da
  mensagem, sem os valores.

Da exceção vai só o nome do tipo e o ponto do código do Nicx onde
estourou (módulo:função:linha), nunca variáveis nem caminhos.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any

import httpx

from nicx.privacidade.redaction import looks_like_pii

logger = logging.getLogger(__name__)

LOGS_TABLE = "nicx_logs"
MAX_MESSAGE = 300

_LEVELS = {
    logging.WARNING: "warning",
    logging.ERROR: "error",
    logging.CRITICAL: "critical",
}

# Loggers que não vão: o próprio envio (evita laço) e o cliente HTTP.
_IGNORED_PREFIXES = ("nicx.privacidade", "httpx", "httpcore", "hpack", "urllib3")

_SUBSTITUTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\"[^\"\n]*\"|'[^'\n]*'|“[^”\n]*”|‘[^’\n]*’"), "…"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>"),
    (re.compile(r"\b(?:https?|wss?|file)://\S+"), "<link>"),
    (re.compile(r"\b[A-Za-z]:[\\/][^\s:)\]}>,;]*"), "<caminho>"),
    (re.compile(r"(?<![\w.])/(?:[\w.~-]+/)+[\w.~-]*"), "<caminho>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ip>"),
    (
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
        "<id>",
    ),
    (re.compile(r"\b[A-Za-z0-9_\-+/=]{32,}\b"), "<token>"),
    (re.compile(r"\b\d{5,}\b"), "<n>"),
)


def sanitize(text: str) -> str:
    """Mensagem de log sem dados pessoais, em uma linha, até 300 caracteres."""
    out = " ".join(str(text).split())
    for pattern, replacement in _SUBSTITUTIONS:
        out = pattern.sub(replacement, out)
    if len(out) > MAX_MESSAGE:
        out = out[: MAX_MESSAGE - 1] + "…"
    return out


def fingerprint(logger_name: str, template: str) -> str:
    """Identifica o tipo do aviso: mesmo logger e mesmo modelo de mensagem."""
    return hashlib.sha256(f"{logger_name}\n{template}".encode("utf-8")).hexdigest()[:16]


def _message_of(record: logging.LogRecord) -> str:
    template = sanitize(str(record.msg))
    try:
        formatted = sanitize(record.getMessage())
    except Exception:
        return template
    # Sobrou algo com cara de dado pessoal: manda só o modelo da mensagem.
    return template if looks_like_pii(formatted) else formatted


def _location_of(record: logging.LogRecord) -> str | None:
    """Último ponto do código do Nicx na pilha da exceção: módulo:função:linha."""
    exc = record.exc_info[1] if record.exc_info else None
    tb = exc.__traceback__ if exc is not None else None
    found = None
    while tb is not None:
        module = tb.tb_frame.f_globals.get("__name__", "")
        if isinstance(module, str) and module.startswith("nicx"):
            found = f"{module}:{tb.tb_frame.f_code.co_name}:{tb.tb_lineno}"
        tb = tb.tb_next
    if found is None and record.name.startswith("nicx"):
        found = f"{record.name}:{record.funcName}:{record.lineno}"
    return found[:200] if found else None


def _is_noise(record: logging.LogRecord) -> bool:
    if record.name.startswith(_IGNORED_PREFIXES):
        return True
    # No Windows o asyncio reclama de toda conexão que o navegador fecha.
    exc = record.exc_info[1] if record.exc_info else None
    return record.name == "asyncio" and isinstance(
        exc, (ConnectionResetError, ConnectionAbortedError)
    )


class LogShipper(logging.Handler):
    """Agrupa avisos e erros e manda para o Supabase da Falkyria em lotes."""

    def __init__(
        self,
        url: str,
        key: str,
        anon_id: str,
        *,
        context: dict[str, str] | None = None,
        flush_interval: float = 60.0,
        max_groups: int = 50,
        timeout: float = 5.0,
    ) -> None:
        super().__init__(level=logging.WARNING)
        from nicx.privacidade.supabase_sink import _headers

        self._endpoint = f"{url.rstrip('/')}/rest/v1/{LOGS_TABLE}"
        self._headers = {**_headers(key), "Prefer": "return=minimal"}
        self._anon_id = anon_id
        self._context = context or {}
        self._flush_interval = flush_interval
        self._max_groups = max(1, max_groups)
        self._timeout = timeout
        self._groups: dict[str, dict[str, Any]] = {}
        self._send_lock = threading.Lock()
        self._stopped = threading.Event()
        self._thread = threading.Thread(target=self._run, name="nicx-logs", daemon=True)
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < logging.WARNING or _is_noise(record):
                return
            level = _LEVELS.get(
                record.levelno,
                "critical" if record.levelno > logging.CRITICAL else "warning",
            )
            fp = fingerprint(record.name, str(record.msg))
            now = datetime.now(timezone.utc).isoformat()
            group = self._groups.get(fp)
            if group is None:
                if len(self._groups) >= self._max_groups:
                    return
                exc = record.exc_info[1] if record.exc_info else None
                self._groups[fp] = {
                    "anon_id": self._anon_id,
                    "level": level,
                    "logger": record.name[:120],
                    "message": _message_of(record) or "(sem mensagem)",
                    "exc_type": type(exc).__name__[:120] if exc is not None else None,
                    "location": _location_of(record),
                    "fingerprint": fp,
                    "occurrences": 1,
                    "first_at": now,
                    "last_at": now,
                    "platform": "server",
                    **self._context,
                }
            else:
                group["occurrences"] = min(100_000, group["occurrences"] + 1)
                group["last_at"] = now
        except Exception:
            # Log de erro nunca pode derrubar o Nicx.
            pass

    def flush(self) -> None:
        with self._send_lock:
            self.acquire()
            try:
                batch = list(self._groups.values())
                self._groups = {}
            finally:
                self.release()
            if not batch:
                return
            try:
                response = httpx.post(
                    self._endpoint,
                    json=batch,
                    headers=self._headers,
                    timeout=self._timeout,
                )
                if response.status_code >= 400:
                    logger.debug(
                        "Logs recusados (%s): %s",
                        response.status_code,
                        response.text[:200],
                    )
            except httpx.HTTPError as exc:
                logger.debug("Logs não enviados: %s", exc)

    def close(self) -> None:
        self._stopped.set()
        try:
            self.flush()
        finally:
            super().close()

    def _run(self) -> None:
        while not self._stopped.wait(self._flush_interval):
            self.flush()


# Loggers que não repassam ao root (o uvicorn guarda os erros de requisição no seu).
_EXTRA_LOGGERS = ("uvicorn.error",)


def install(shipper: LogShipper) -> None:
    """Liga o envio no root e no uvicorn.error (que não repassa ao root)."""
    for name in ("", *_EXTRA_LOGGERS):
        logging.getLogger(name).addHandler(shipper)


def uninstall(shipper: LogShipper) -> None:
    for name in ("", *_EXTRA_LOGGERS):
        logging.getLogger(name).removeHandler(shipper)
    shipper.close()


__all__ = [
    "LOGS_TABLE",
    "LogShipper",
    "fingerprint",
    "install",
    "sanitize",
    "uninstall",
]
