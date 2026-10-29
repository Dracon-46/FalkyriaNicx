"""Mandar compromissos da agenda para o Google Agenda e o Outlook.

Dois caminhos, nesta ordem:

1. **Direto pela API**, quando a conta já está conectada com permissão de
   escrita: Google Calendar ``events.insert`` (token do conector Google,
   renovado por ``call_with_refresh``) ou Microsoft Graph ``POST /me/events``
   (token com ``Calendars.ReadWrite``, se algum conector o tiver guardado).
   O id devolvido fica no compromisso local, e o mesmo compromisso nunca é
   criado duas vezes.
2. **Link pré-preenchido**: sem conta, sem permissão ou com erro, o Nicx
   abre o navegador com o evento já preenchido; o usuário só clica em Salvar.

Nada aqui registra app nem inventa client ID: só usa o que os conectores já
guardaram em ``~/.nicx/connectors``.

Também lê (só leitura) os eventos que os conectores já sincronizaram, para
"o que eu tenho amanhã" mostrar o Google Agenda junto com a agenda local.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode

from nicx.acoes import agenda

logger = logging.getLogger(__name__)

DESTINOS = ("windows", "google", "outlook", "outlook_trabalho")
PADRAO = "windows"
FUSO_PADRAO = "America/Sao_Paulo"

GOOGLE_RENDER = "https://calendar.google.com/calendar/render"
OUTLOOK_PESSOAL = "https://outlook.live.com/calendar/0/deeplink/compose"
OUTLOOK_TRABALHO = "https://outlook.office.com/calendar/0/deeplink/compose"

# Escopos do Google que deixam criar eventos.
GOOGLE_ESCRITA = frozenset(
    {
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
    }
)
# Arquivos de credenciais onde um token do Microsoft Graph pode estar.
_OUTLOOK_TOKENS = ("outlook_calendar.json", "microsoft.json", "outlook.json")
_MS_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------


def _config_agenda() -> Any:
    from nicx.nucleo.config import load_config

    return load_config().agenda


def calendario_padrao() -> str:
    """O destino de "manda pro calendário" (``[agenda] calendario_padrao``)."""
    try:
        valor = str(_config_agenda().calendario_padrao or PADRAO)
    except Exception:  # noqa: BLE001 - sem config, o comportamento de sempre
        return PADRAO
    return valor if valor in DESTINOS else PADRAO


def fuso() -> str:
    try:
        return str(_config_agenda().fuso or FUSO_PADRAO)
    except Exception:  # noqa: BLE001
        return FUSO_PADRAO


def _config_path() -> Path:
    import os

    from nicx.nucleo.paths import get_config_path

    custom = os.environ.get("NICX_CONFIG")
    return Path(custom).expanduser() if custom else get_config_path()


def salvar_padrao(valor: str) -> str:
    """Grava ``[agenda] calendario_padrao`` no config.toml, preservando o resto,
    e já vale para o processo atual."""
    import tomlkit

    if valor not in DESTINOS:
        raise ValueError(f"calendário desconhecido: {valor!r}")
    path = _config_path()
    if path.exists():
        doc = tomlkit.parse(path.read_text(encoding="utf-8"))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = tomlkit.document()
    if "agenda" not in doc:
        doc.add("agenda", tomlkit.table())
    doc["agenda"]["calendario_padrao"] = valor
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    try:
        _config_agenda().calendario_padrao = valor
    except Exception:  # noqa: BLE001 - o arquivo já está gravado
        logger.debug("Config em memória não atualizada", exc_info=True)
    return valor


# ---------------------------------------------------------------------------
# Links pré-preenchidos
# ---------------------------------------------------------------------------


def _query(params: Dict[str, str]) -> str:
    # %20 em vez de "+" (o Outlook mostra o "+"); "/" e ":" são válidos na query.
    return urlencode(params, quote_via=quote, safe="/:")


def _com_fuso(moment: datetime, nome_fuso: str) -> datetime:
    """Hora local da agenda com o fuso configurado (ou o do PC)."""
    try:
        from zoneinfo import ZoneInfo

        return moment.replace(tzinfo=ZoneInfo(nome_fuso))
    except Exception:  # noqa: BLE001 - sem tzdata: o fuso do PC
        return moment.astimezone()


def link_google(event: agenda.Event, nome_fuso: Optional[str] = None) -> str:
    """Google Agenda com o evento preenchido (dia todo: datas sem hora, fim
    exclusivo; com hora: hora local em ``ctz``)."""
    start, end = event.start_at, event.end_at
    if event.all_day:
        dates = f"{start:%Y%m%d}/{end:%Y%m%d}"
    else:
        dates = f"{start:%Y%m%dT%H%M%S}/{end:%Y%m%dT%H%M%S}"
    params = {"action": "TEMPLATE", "text": event.title, "dates": dates}
    if event.details:
        params["details"] = event.details
    if event.location:
        params["location"] = event.location
    params["ctz"] = nome_fuso or fuso()
    return f"{GOOGLE_RENDER}?{_query(params)}"


def link_outlook(
    event: agenda.Event, trabalho: bool = False, nome_fuso: Optional[str] = None
) -> str:
    """Outlook na web com o evento preenchido: pessoal (outlook.live.com) ou de
    trabalho/escola (outlook.office.com)."""
    start, end = event.start_at, event.end_at
    if event.all_day:
        startdt, enddt = f"{start:%Y-%m-%d}", f"{end:%Y-%m-%d}"
    else:
        tz = nome_fuso or fuso()
        startdt = _com_fuso(start, tz).isoformat(timespec="seconds")
        enddt = _com_fuso(end, tz).isoformat(timespec="seconds")
    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": event.title,
        "startdt": startdt,
        "enddt": enddt,
        "allday": "true" if event.all_day else "false",
    }
    if event.details:
        params["body"] = event.details
    if event.location:
        params["location"] = event.location
    base = OUTLOOK_TRABALHO if trabalho else OUTLOOK_PESSOAL
    return f"{base}?{_query(params)}"


def link_para(event: agenda.Event, destino: str) -> str:
    if destino == "google":
        return link_google(event)
    return link_outlook(event, trabalho=destino == "outlook_trabalho")


# ---------------------------------------------------------------------------
# Criar direto pela API
# ---------------------------------------------------------------------------


@dataclass
class Envio:
    """Como um compromisso foi mandado.

    ``modo``: ``"api"`` (criado direto), ``"ja_estava"`` (já tinha sido
    criado antes) ou ``"link"`` (abrir ``url`` no navegador). ``reconectar``
    diz que a conta está conectada, mas sem permissão de escrita.
    """

    modo: str
    url: str = ""
    reconectar: bool = False


def _connectors_dir() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "connectors"


def _read_tokens(path: Path) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _escopos(tokens: Dict[str, Any]) -> Optional[set[str]]:
    """Escopos concedidos, se o arquivo guardou (conexões antigas não têm)."""
    scope = tokens.get("scope")
    if isinstance(scope, list):
        return {str(s) for s in scope}
    if isinstance(scope, str) and scope.strip():
        return set(scope.split())
    return None


def _google_credentials() -> Optional[Path]:
    folder = _connectors_dir()
    for name in ("gcalendar.json", "google.json"):
        path = folder / name
        tokens = _read_tokens(path) if path.exists() else None
        if tokens and (
            tokens.get("access_token")
            or tokens.get("token")
            or tokens.get("refresh_token")
        ):
            return path
    return None


def _google_event_id(event: agenda.Event) -> str:
    # Id escolhido pelo cliente (base32hex: 0-9 e a-v): se a resposta se perder
    # e o pedido for repetido, o Google recusa com 409 em vez de duplicar.
    return "nc" + event.id.lower() + re.sub(r"\D", "", event.created)


def corpo_google(
    event: agenda.Event, nome_fuso: Optional[str] = None
) -> Dict[str, Any]:
    tz = nome_fuso or fuso()
    if event.all_day:
        start = {"date": f"{event.start_at:%Y-%m-%d}"}
        end = {"date": f"{event.end_at:%Y-%m-%d}"}
    else:
        start = {
            "dateTime": event.start_at.isoformat(timespec="seconds"),
            "timeZone": tz,
        }
        end = {"dateTime": event.end_at.isoformat(timespec="seconds"), "timeZone": tz}
    body: Dict[str, Any] = {
        "id": _google_event_id(event),
        "summary": event.title,
        "start": start,
        "end": end,
        "reminders": {"useDefault": True},
    }
    if event.details:
        body["description"] = event.details
    if event.location:
        body["location"] = event.location
    return body


def _status(exc: Exception) -> Optional[int]:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _criar_google(event: agenda.Event) -> Envio:
    import httpx

    from nicx.conectores import gcalendar
    from nicx.conectores.google_auth import GoogleAuthError, call_with_refresh

    link = Envio("link", url=link_google(event))
    path = _google_credentials()
    if path is None:
        return link  # sem conta conectada: só o link
    tokens = _read_tokens(path) or {}
    escopos = _escopos(tokens)
    if escopos is not None and not (escopos & GOOGLE_ESCRITA):
        link.reconectar = True  # conectado só para leitura
        return link
    body = corpo_google(event)
    try:
        created = call_with_refresh(
            gcalendar._gcal_api_event_insert, str(path), "primary", body
        )
        remote_id = str(created.get("id") or body["id"])
    except httpx.HTTPStatusError as exc:
        status = _status(exc)
        if status == 409:  # já criado num pedido anterior que perdeu a resposta
            remote_id = body["id"]
        else:
            link.reconectar = status in (401, 403)
            logger.info("Google Agenda recusou o evento (%s); usando o link", status)
            return link
    except GoogleAuthError as exc:
        logger.info("Google Agenda sem autorização (%s); usando o link", exc)
        link.reconectar = True
        return link
    except Exception as exc:  # noqa: BLE001 - rede fora: o link resolve
        logger.warning("Falha ao criar no Google Agenda: %s", exc)
        return link
    agenda.update(event, google_id=remote_id)
    event.google_id = remote_id
    return Envio("api")


def _outlook_tokens() -> Optional[tuple[Path, Dict[str, Any]]]:
    folder = _connectors_dir()
    for name in _OUTLOOK_TOKENS:
        path = folder / name
        tokens = _read_tokens(path) if path.exists() else None
        if tokens and tokens.get("access_token"):
            return path, tokens
    return None


def corpo_outlook(
    event: agenda.Event, nome_fuso: Optional[str] = None
) -> Dict[str, Any]:
    tz = nome_fuso or fuso()
    if event.all_day:
        # Dia todo: meia-noite a meia-noite do dia seguinte.
        start = {"dateTime": f"{event.start_at:%Y-%m-%d}T00:00:00", "timeZone": "UTC"}
        end = {"dateTime": f"{event.end_at:%Y-%m-%d}T00:00:00", "timeZone": "UTC"}
    else:
        # Em UTC: o Graph aceita sempre, sem depender do nome do fuso.
        def utc(moment: datetime) -> str:
            value = _com_fuso(moment, tz).astimezone(timezone.utc)
            return value.replace(tzinfo=None).isoformat(timespec="seconds")

        start = {"dateTime": utc(event.start_at), "timeZone": "UTC"}
        end = {"dateTime": utc(event.end_at), "timeZone": "UTC"}
    body: Dict[str, Any] = {
        "subject": event.title,
        "start": start,
        "end": end,
        "isAllDay": event.all_day,
        # O Graph ignora um POST repetido com o mesmo transactionId.
        "transactionId": f"nicx-{event.id}-{re.sub(r'[^0-9]', '', event.created)}",
    }
    if event.details:
        body["body"] = {"contentType": "text", "content": event.details}
    if event.location:
        body["location"] = {"displayName": event.location}
    return body


def _refresh_microsoft(path: Path, tokens: Dict[str, Any]) -> Optional[str]:
    """Renova o token do Graph com o refresh_token e o client_id já guardados."""
    import httpx

    refresh, client_id = tokens.get("refresh_token"), tokens.get("client_id")
    if not (refresh and client_id):
        return None
    data = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "scope": tokens.get("scope") or "Calendars.ReadWrite offline_access",
    }
    if tokens.get("client_secret"):
        data["client_secret"] = tokens["client_secret"]
    url = _MS_TOKEN_URL.format(tenant=tokens.get("tenant") or "common")
    try:
        resp = httpx.post(url, data=data, timeout=30.0)
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        return None
    tokens["access_token"] = token
    if payload.get("refresh_token"):
        tokens["refresh_token"] = payload["refresh_token"]
    if payload.get("scope"):
        tokens["scope"] = payload["scope"]
    from nicx.conectores.oauth import save_tokens

    save_tokens(str(path), tokens)
    return token


def _criar_outlook(event: agenda.Event, trabalho: bool) -> Envio:
    import httpx

    from nicx.conectores import outlook

    link = Envio("link", url=link_outlook(event, trabalho=trabalho))
    found = _outlook_tokens()
    if found is None:
        return link  # o conector do Outlook (IMAP) não cria eventos
    path, tokens = found
    escopos = _escopos(tokens)
    if escopos is not None and "calendars.readwrite" not in {
        s.rsplit("/", 1)[-1].lower() for s in escopos
    }:
        link.reconectar = True
        return link
    body = corpo_outlook(event)
    try:
        try:
            created = outlook._graph_api_event_create(tokens["access_token"], body)
        except httpx.HTTPStatusError as exc:
            if _status(exc) != 401:
                raise
            token = _refresh_microsoft(path, tokens)
            if token is None:
                raise
            created = outlook._graph_api_event_create(token, body)
    except httpx.HTTPStatusError as exc:
        status = _status(exc)
        link.reconectar = status in (401, 403)
        logger.info("Outlook recusou o evento (%s); usando o link", status)
        return link
    except Exception as exc:  # noqa: BLE001 - rede fora: o link resolve
        logger.warning("Falha ao criar no Outlook: %s", exc)
        return link
    remote_id = str(created.get("id") or body["transactionId"])
    agenda.update(event, outlook_id=remote_id)
    event.outlook_id = remote_id
    return Envio("api")


def enviar(event: agenda.Event, destino: str) -> Envio:
    """Manda o compromisso para ``destino`` ("google", "outlook" ou
    "outlook_trabalho"): direto pela API se der, senão pelo link."""
    # Relê do disco: outro pedido pode já ter criado o evento remoto.
    event = agenda.get(event.id) or event
    if destino == "google":
        if event.google_id:
            return Envio("ja_estava")
        return _criar_google(event)
    if destino in ("outlook", "outlook_trabalho"):
        if event.outlook_id:
            return Envio("ja_estava")
        return _criar_outlook(event, trabalho=destino == "outlook_trabalho")
    raise ValueError(f"destino desconhecido: {destino!r}")


def estado_contas() -> Dict[str, Optional[bool]]:
    """Para a tela de Configurações: contas conectadas e se dá para escrever
    (None = não sabemos até tentar)."""
    google = _google_credentials()
    google_escrita: Optional[bool] = None
    if google is not None:
        escopos = _escopos(_read_tokens(google) or {})
        google_escrita = None if escopos is None else bool(escopos & GOOGLE_ESCRITA)
    outlook_found = _outlook_tokens()
    outlook_escrita: Optional[bool] = None
    if outlook_found is not None:
        escopos = _escopos(outlook_found[1])
        outlook_escrita = (
            None
            if escopos is None
            else "calendars.readwrite"
            in {s.rsplit("/", 1)[-1].lower() for s in escopos}
        )
    return {
        "google_conectado": google is not None,
        "google_escrita": google_escrita if google is not None else False,
        "outlook_conectado": outlook_found is not None,
        "outlook_escrita": outlook_escrita if outlook_found is not None else False,
    }


# ---------------------------------------------------------------------------
# Leitura: eventos já sincronizados pelos conectores
# ---------------------------------------------------------------------------


@dataclass
class EventoConectado:
    title: str
    start: datetime  # hora local
    all_day: bool
    origem: str  # "google" ou "outlook"
    remote_id: str = ""


_ORIGENS = {"gcalendar": "google", "outlook": "outlook", "outlook_calendar": "outlook"}
_WHEN = re.compile(r"^When: (\S+)", re.MULTILINE)


def eventos_conectados(day: date) -> List[EventoConectado]:
    """Eventos de ``day`` que os conectores já trouxeram para ``knowledge.db``.

    Só leitura e sem rede; sem banco ou sem eventos, lista vazia.
    """
    from nicx.nucleo.paths import get_config_dir

    db = get_config_dir() / "knowledge.db"
    if not db.exists():
        return []
    # Fusos diferentes: busca um dia a mais para cada lado e filtra depois.
    lo = (day - timedelta(days=1)).isoformat()
    hi = (day + timedelta(days=2)).isoformat()
    marks = ",".join("?" for _ in _ORIGENS)
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT title, timestamp, content, source, metadata"
                " FROM knowledge_chunks"
                f" WHERE source IN ({marks}) AND doc_type = 'event'"
                " AND chunk_index = 0 AND deleted_at IS NULL"
                " AND timestamp >= ? AND timestamp < ?",
                (*_ORIGENS, lo, hi),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.debug("Eventos sincronizados indisponíveis: %s", exc)
        return []
    found: List[EventoConectado] = []
    seen: set[tuple[str, str]] = set()
    for title, stamp, content, source, metadata in rows:
        when = _WHEN.search(content or "")
        raw = when.group(1) if when else str(stamp)
        try:
            if "T" not in raw:
                start = datetime.combine(
                    date.fromisoformat(raw[:10]), datetime.min.time()
                )
                all_day = True
            else:
                start = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if start.tzinfo is not None:
                    start = start.astimezone().replace(tzinfo=None)
                all_day = False
        except ValueError:
            continue
        if start.date() != day:
            continue
        try:
            remote_id = str(json.loads(metadata or "{}").get("event_id", ""))
        except ValueError:
            remote_id = ""
        key = (title or "", start.isoformat())
        if key in seen:
            continue
        seen.add(key)
        found.append(
            EventoConectado(
                title=title or "",
                start=start,
                all_day=all_day,
                origem=_ORIGENS[source],
                remote_id=remote_id,
            )
        )
    return sorted(found, key=lambda e: (not e.all_day, e.start))


__all__ = [
    "DESTINOS",
    "Envio",
    "EventoConectado",
    "calendario_padrao",
    "corpo_google",
    "corpo_outlook",
    "enviar",
    "estado_contas",
    "eventos_conectados",
    "link_google",
    "link_outlook",
    "link_para",
    "salvar_padrao",
]
