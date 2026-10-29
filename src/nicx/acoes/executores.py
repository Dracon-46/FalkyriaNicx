"""Execução das rotinas: lembretes, anotações, estado do PC, pastas, print,
fechar apps e energia. Cada função devolve uma frase curta, boa para falar.

As frases vêm de ``textos`` e saem no idioma atual das ações.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from nicx.acoes import (
    agenda,
    arquivos,
    calendarios,
    confirmacao,
    lembretes,
    notas,
    textos,
    youtube,
)
from nicx.acoes.intencoes import Action
from nicx.acoes.rotinas import CLOSABLE, FOLDERS
from nicx.acoes.sistema import Outcome, _start, _windows_only
from nicx.acoes.tempo import parse_day, say_day, say_when
from nicx.acoes.textos import contar, texto

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Textos internos dos lembretes de timer e alarme (ver ``lembretes.kind_of``).
_TIMER_TEXT = "o tempo acabou"
_ALARM_TEXT = "alarme"


def _folder_label(key: str) -> str:
    """Nome da pasta conhecida no idioma das respostas."""
    if key not in FOLDERS:
        return key
    return textos.nome_pasta(key, FOLDERS[key][0])


# ---------------------------------------------------------------------------
# Lembretes e anotações
# ---------------------------------------------------------------------------


def remind(action: Action) -> Outcome:
    when = action.when or datetime.now()
    reminder = lembretes.add(action.target, when)
    spoken = say_when(reminder.due_at)
    if action.target == _TIMER_TEXT:
        return Outcome(True, texto("timer_marcado", quando=spoken))
    if action.target == _ALARM_TEXT:
        return Outcome(True, texto("alarme_marcado", quando=spoken))
    return Outcome(True, texto("lembrete_marcado", quando=spoken, o_que=action.target))


def remind_list() -> Outcome:
    items = lembretes.pending()
    if not items:
        return Outcome(True, texto("sem_lembretes"))
    names = {_TIMER_TEXT: texto("nome_timer"), _ALARM_TEXT: texto("nome_alarme")}
    parts = [f"{names.get(r.text, r.text)} {say_when(r.due_at)}" for r in items[:5]]
    more = texto("e_mais", n=len(items) - 5) if len(items) > 5 else ""
    return Outcome(
        True,
        texto(
            "lista_lembretes",
            qtd=contar("lembrete", len(items)),
            itens="; ".join(parts),
            mais=more,
        ),
    )


# tipo do lembrete -> (chave do nome contável, chave do nome com artigo)
_KIND_NAMES = {
    "": ("lembrete", "o_lembrete"),
    "timer": ("timer", "o_timer"),
    "alarme": ("alarme", "o_alarme"),
}


def remind_clear(action: Action) -> Outcome:
    noun, _the = _KIND_NAMES.get(action.target, _KIND_NAMES[""])
    n = lembretes.cancel_all(action.target)
    if n == 0:
        return Outcome(True, texto("nada_cancelar_varios", nomes=textos.nome(noun, 2)))
    return Outcome(True, texto("cancelei_qtd", qtd=contar(noun, n)))


def remind_cancel(action: Action) -> Outcome:
    noun, the = _KIND_NAMES.get(action.target, _KIND_NAMES[""])
    reminder = lembretes.cancel_next(action.target)
    if reminder is None:
        return Outcome(True, texto("nada_cancelar_um", nome=textos.nome(noun)))
    if lembretes.kind_of(reminder) == "lembrete":
        return Outcome(True, texto("cancelei_lembrete", o_que=reminder.text))
    return Outcome(
        True,
        texto("cancelei_tipo", o_nome=texto(the), quando=say_when(reminder.due_at)),
    )


def note_add(action: Action) -> Outcome:
    notas.add(action.target)
    return Outcome(True, texto("anotado"))


def notes_list() -> Outcome:
    items = notas.all_notes()
    if not items:
        return Outcome(True, texto("sem_anotacoes"))
    last = items[-5:]
    if len(items) == 1:
        return Outcome(True, texto("sua_anotacao", itens="; ".join(last)))
    return Outcome(True, texto("suas_anotacoes", n=len(last), itens="; ".join(last)))


def notes_clear() -> Outcome:
    n = notas.clear()
    return Outcome(True, texto("apaguei_qtd", qtd=contar("anotacao", n)))


# ---------------------------------------------------------------------------
# Estado do PC
# ---------------------------------------------------------------------------


def _gb(n: float) -> str:
    return textos.decimal(n / 1024**3)


def status() -> Outcome:
    import psutil

    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    parts = [
        texto("st_cpu", n=f"{cpu:.0f}"),
        texto("st_mem", n=f"{mem.percent:.0f}", gb=_gb(mem.available)),
    ]
    try:
        disk = psutil.disk_usage(Path.home().anchor or "/")
        parts.append(texto("st_disco", gb=_gb(disk.free)))
    except OSError:
        pass
    try:
        battery = psutil.sensors_battery()
    except Exception:  # noqa: BLE001 - sem sensor, sem bateria na frase
        battery = None
    if battery is not None:
        charging = texto("carregando") if battery.power_plugged else ""
        parts.append(texto("st_bateria", n=round(battery.percent), carregando=charging))

    # Quem mais pesa na memória, somando as várias janelas de cada programa.
    usage: dict[str, int] = {}
    for proc in psutil.process_iter(["name", "memory_info"]):
        try:
            name = (proc.info["name"] or "").removesuffix(".exe")
            usage[name] = usage.get(name, 0) + proc.info["memory_info"].rss
        except (psutil.Error, AttributeError, TypeError):
            continue
    heavy = sorted(usage.items(), key=lambda kv: kv[1], reverse=True)[:2]
    message = texto("st_agora", partes=texto("sep").join(parts))
    if heavy and mem.percent >= 70:
        top = texto("e").join(texto("st_item", nome=n, gb=_gb(b)) for n, b in heavy)
        message += texto("st_pesados", top=top)
    return Outcome(True, message)


# ---------------------------------------------------------------------------
# Pastas e print
# ---------------------------------------------------------------------------


def folder_path(key: str) -> Optional[Path]:
    home = Path.home()
    for candidate in FOLDERS[key][1]:
        path = home / candidate
        if path.is_dir():
            return path
    return None


def folder(action: Action) -> Outcome:
    label = _folder_label(action.target)
    path = folder_path(action.target)
    if path is None:
        return Outcome(False, texto("pasta_nao_achei", pasta=label))
    _start(str(path))
    return Outcome(True, texto("abrindo", alvo=label))


def screenshot() -> Outcome:
    try:
        from PIL import ImageGrab
    except ImportError:
        return Outcome(False, texto("sem_pillow"))
    base = folder_path("imagens") or Path.home()
    target_dir = base / "Nicx"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"print-{datetime.now():%Y%m%d-%H%M%S}.png"
    ImageGrab.grab(all_screens=True).save(target)
    return Outcome(True, texto("print_salvo", pasta=base.name))


# ---------------------------------------------------------------------------
# Fechar apps
# ---------------------------------------------------------------------------


def close(action: Action) -> Outcome:
    import psutil

    label, exes = CLOSABLE[action.target]
    label = textos.nome_app(label)
    wanted = {e.lower() for e in exes}
    running = {
        (p.info["name"] or "")
        for p in psutil.process_iter(["name"])
        if (p.info["name"] or "").lower() in wanted
    }
    if not running:
        return Outcome(True, texto("nao_esta_aberto", App=textos.maiuscula(label)))
    if sys.platform == "win32":
        # Sem /F: o programa recebe o pedido de fechar e pode perguntar se
        # quer salvar, como ao clicar no X.
        for exe in running:
            subprocess.run(  # noqa: S603, S607
                ["taskkill", "/IM", exe], capture_output=True, creationflags=_NO_WINDOW
            )
    else:
        for proc in psutil.process_iter(["name"]):
            if (proc.info["name"] or "") in running:
                proc.terminate()
    return Outcome(True, texto("fechando", app=label))


# ---------------------------------------------------------------------------
# Energia (sempre com confirmação)
# ---------------------------------------------------------------------------


def power(action: Action) -> Outcome:
    if action.op == "abort":
        if sys.platform != "win32":
            return _windows_only()
        subprocess.run(  # noqa: S603, S607
            ["shutdown", "/a"], capture_output=True, creationflags=_NO_WINDOW
        )
        return Outcome(True, texto("desligamento_cancelado"))
    confirmacao.ask(action)
    return Outcome(True, texto("pergunta_energia", acao=texto(f"acao_{action.op}")))


def confirm() -> Outcome:
    action = confirmacao.take()
    if action is None:
        return Outcome(False, texto("nada_confirmar"))
    if action.kind == "organize":
        return _organize_now(action)
    if sys.platform != "win32":
        return _windows_only()
    if action.op == "shutdown":
        subprocess.run(  # noqa: S603, S607
            ["shutdown", "/s", "/t", "30"],
            capture_output=True,
            creationflags=_NO_WINDOW,
        )
        return Outcome(True, texto("desligando"))
    if action.op == "restart":
        subprocess.run(  # noqa: S603, S607
            ["shutdown", "/r", "/t", "30"],
            capture_output=True,
            creationflags=_NO_WINDOW,
        )
        return Outcome(True, texto("reiniciando"))
    # Suspender corta tudo na hora: espera a resposta chegar antes.
    threading.Timer(
        3.0,
        lambda: subprocess.run(  # noqa: S603, S607
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Add-Type -AssemblyName System.Windows.Forms; "
                "[System.Windows.Forms.Application]::SetSuspendState("
                "'Suspend', $false, $false)",
            ],
            capture_output=True,
            creationflags=_NO_WINDOW,
        ),
    ).start()
    return Outcome(True, texto("suspendendo"))


def deny() -> Outcome:
    confirmacao.drop()
    return Outcome(True, texto("nada_feito"))


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------


def _event_line(event: "agenda.Event", now: datetime) -> str:
    if event.all_day:
        day = say_day(event.start_at, now, with_time=False)
        return texto("evento_dia_todo", titulo=event.title, dia=day)
    return texto("evento", titulo=event.title, quando=say_day(event.start_at, now))


def agenda_add(action: Action) -> Outcome:
    now = datetime.now()
    when = action.when or now
    all_day = action.op == "dia"
    if (when.date() < now.date()) if all_day else (when < now):
        return Outcome(False, texto("horario_passou", quando=say_day(when, now)))
    event = agenda.add(action.target, when, all_day=all_day, now=now)
    if all_day:
        day = say_day(event.start_at, now, with_time=False)
        aviso = texto("aviso_8h") if event.reminder_id else ""
        message = texto("marquei_dia_todo", titulo=event.title, dia=day, aviso=aviso)
    else:
        aviso = texto("aviso_15min") if event.reminder_id else ""
        message = texto(
            "marquei",
            titulo=event.title,
            quando=say_day(event.start_at, now),
            aviso=aviso,
        )
    # "marca dentista sexta às 10h no Google Agenda": marca e já manda.
    if action.site in calendarios.DESTINOS and action.site != "windows":
        sent = _send([event], action.site)
        message = f"{message} {sent.message}"
    return Outcome(True, message)


def _day_item(title: str, start: datetime, all_day: bool) -> str:
    if all_day:
        return texto("item_dia_todo", titulo=title)
    return texto(
        "item_hora",
        titulo=title,
        hora=textos.hora_curta(start),
        a_las="a la" if start.hour == 1 else "a las",
    )


def _day_items(day: date) -> list[str]:
    """Compromissos do dia: os da agenda local e os que os conectores já
    trouxeram do Google Agenda/Outlook (marcados com a origem)."""
    events = agenda.on_day(day)
    items = [
        (e.all_day, e.start_at, _day_item(e.title, e.start_at, e.all_day))
        for e in events
    ]
    sent = {e.google_id for e in events if e.google_id}
    sent |= {e.outlook_id for e in events if e.outlook_id}
    local = {(e.title.casefold(), e.start_at) for e in events}
    try:
        remote = calendarios.eventos_conectados(day)
    except Exception:  # noqa: BLE001 - a agenda local responde sozinha
        remote = []
    for r in remote:
        if (r.remote_id and r.remote_id in sent) or (
            r.title.casefold(),
            r.start,
        ) in local:
            continue  # o mesmo compromisso que o Nicx mandou
        origem = texto("cal_google" if r.origem == "google" else "cal_outlook")
        item = _day_item(r.title, r.start, r.all_day)
        items.append(
            (r.all_day, r.start, texto("item_origem", item=item, origem=origem))
        )
    # Dia todo primeiro, depois por hora.
    items.sort(key=lambda i: (not i[0], i[1]))
    return [text for _all_day, _start, text in items]


def agenda_list(action: Action) -> Outcome:
    now = datetime.now()
    if action.op == "dia" and action.when is not None:
        parts = _day_items(action.when.date())
        label = say_day(action.when, now, with_time=False)
        if not parts:
            return Outcome(True, texto("nada_no_dia", dia=label))
        return Outcome(
            True,
            texto(
                "voce_tem_no_dia", Dia=textos.maiuscula(label), itens="; ".join(parts)
            ),
        )
    events = agenda.upcoming(now, days=7)
    if not events:
        return Outcome(True, texto("nada_7_dias"))
    shown = [_event_line(e, now) for e in events[:6]]
    more = texto("e_mais", n=len(events) - 6) if len(events) > 6 else ""
    head = texto(
        "proximos_7_dias" if action.op == "semana" else "proximos_compromissos"
    )
    return Outcome(True, texto("lista", titulo=head, itens="; ".join(shown), mais=more))


def _split_day(query: str) -> tuple[str, Optional[date]]:
    """'reuniao sexta' -> ('reuniao', data da sexta)."""
    words = query.split()
    for i in range(len(words)):
        day = parse_day(" ".join(words[i:]))
        if day is not None:
            return " ".join(words[:i]), day
    return query, None


def agenda_cancel(action: Action) -> Outcome:
    now = datetime.now()
    query, day = _split_day(action.target)
    if query or day:
        event = agenda.find(query, now, day)
    else:
        upcoming = agenda.upcoming(now, days=366)
        event = upcoming[0] if upcoming else None
    if event is None:
        return Outcome(False, texto("compromisso_nao_achei"))
    agenda.cancel(event)
    return Outcome(True, texto("desmarquei", evento=_event_line(event, now)))


# Links abertos de uma vez (cada um é uma aba do navegador).
_MAX_LINKS = 5


def _pick_events(action: Action, destino: str) -> Optional[list["agenda.Event"]]:
    """Os compromissos a mandar; None se o citado não foi achado.

    ``action.site``: "todos" (a agenda inteira), "ultimo" ("isso", "o
    compromisso": o último marcado) ou vazio. ``action.target``: o
    compromisso citado ("reuniao sexta").
    """
    now = datetime.now()
    if action.target:
        query, day = _split_day(action.target)
        event = agenda.find(query, now, day)
        return [event] if event is not None else None
    whole = action.site == "todos" or (destino == "windows" and not action.site)
    if whole:
        return agenda.upcoming(now, days=366)
    last = agenda.last_added(now)
    return [last] if last is not None else []


def _send(events: list["agenda.Event"], destino: str) -> Outcome:
    """Manda para o Google/Outlook: direto pela API ou pelo link preenchido."""
    cal = texto("cal_google" if destino == "google" else "cal_outlook")
    results = [(e, calendarios.enviar(e, destino)) for e in events]
    links = [(e, r) for e, r in results if r.modo == "link"]
    for _event, result in links[:_MAX_LINKS]:
        _start(result.url)
    created = [e for e, r in results if r.modo == "api"]
    already = [e for e, r in results if r.modo == "ja_estava"]
    if len(results) == 1:
        event, result = results[0]
        key = {"api": "cal_criado", "ja_estava": "cal_ja_estava"}.get(
            result.modo, "cal_link"
        )
        parts = [texto(key, titulo=event.title, cal=cal)]
    else:
        parts = []
        if created:
            qtd = contar("compromisso", len(created))
            parts.append(texto("cal_criados", qtd=qtd, cal=cal))
        if links:
            qtd = contar("compromisso", min(len(links), _MAX_LINKS))
            parts.append(texto("cal_links", qtd=qtd, cal=cal))
        if not parts and already:
            parts.append(texto("cal_todos_ja_estavam", cal=cal))
    if any(r.reconectar for _e, r in results):
        key = (
            "cal_reconectar_google" if destino == "google" else "cal_reconectar_outlook"
        )
        parts.append(texto(key).strip())
    return Outcome(True, " ".join(parts))


def agenda_export(action: Optional[Action] = None) -> Outcome:
    """Manda compromissos para o calendário: o do Windows (.ics), o Google
    Agenda ou o Outlook. Sem destino no pedido, vale o padrão da config."""
    action = action or Action("agenda_export")
    destino = action.op if action.op in calendarios.DESTINOS else ""
    destino = destino or calendarios.calendario_padrao()
    events = _pick_events(action, destino)
    if events is None:
        return Outcome(False, texto("compromisso_nao_achei"))
    if not events:
        return Outcome(True, texto("nada_exportar"))
    if destino != "windows":
        return _send(events, destino)
    path = agenda.export_ics(events)
    n = contar("compromisso", len(events))
    if sys.platform != "win32":
        return Outcome(True, texto("ics_salvo", qtd=n, caminho=path))
    _start(str(path))
    return Outcome(True, texto("ics_aberto", qtd=n))


# ---------------------------------------------------------------------------
# Arquivos, fotos e YouTube
# ---------------------------------------------------------------------------

_KINDS = {
    "imagem",
    "print",
    "video",
    "musica",
    "pdf",
    "documento",
    "planilha",
    "apresentacao",
    "",
    "download",
}


def _kind_noun(kind: str) -> str:
    """Chave do nome contável do tipo de arquivo (ver ``textos.nome``)."""
    return f"k_{kind if kind in _KINDS else ''}"


def _open_path(path: Path) -> Outcome:
    _start(str(path))
    return Outcome(True, texto("abrindo", alvo=arquivos.describe(path)))


def _not_found(noun: str, query: str) -> Outcome:
    return Outcome(
        False,
        texto(
            "nao_achei_nome",
            nome=textos.nome(noun),
            nomes=textos.nome(noun, 2),
            q=query,
        ),
    )


def file_latest(action: Action) -> Outcome:
    kind = action.target
    noun = _kind_noun(kind)
    if kind == "print":
        path = arquivos.latest("imagem", arquivos.screenshots_folders() or None)
    elif kind == "download":
        downloads = folder_path("downloads")
        newest = None
        if downloads is not None:
            files = [p for p in downloads.iterdir() if p.is_file()]
            newest = max(files, key=lambda p: p.stat().st_mtime) if files else None
        path = newest
    else:
        path = arquivos.latest(kind)
    if path is None:
        return Outcome(
            False,
            texto("nenhum_arquivo", nome=textos.nome(noun), nomes=textos.nome(noun, 2)),
        )
    return _open_path(path)


def file_open(action: Action) -> Outcome:
    noun = _kind_noun(action.op)
    found = arquivos.search(action.target, kind=action.op or None, limit=5)
    if not found:
        return _not_found(noun, action.target)
    outcome = _open_path(found[0])
    if len(found) > 1:
        outcome = Outcome(
            True, texto("outros_parecidos", msg=outcome.message, n=len(found) - 1)
        )
    return outcome


def file_find(action: Action) -> Outcome:
    noun = _kind_noun(action.op)
    found = arquivos.search(action.target, kind=action.op or None, limit=5)
    if not found:
        return _not_found(noun, action.target)
    names = "; ".join(arquivos.describe(p) for p in found)
    return Outcome(True, texto("achei", qtd=contar(noun, len(found)), nomes=names))


def folder_list(action: Action) -> Outcome:
    path = folder_path(action.target)
    label = _folder_label(action.target)
    if path is None:
        return Outcome(False, texto("pasta_nao_achei", pasta=label))
    names, total = arquivos.list_folder(path, limit=10)
    if total == 0:
        return Outcome(True, texto("pasta_vazia", pasta=label))
    more = texto("e_mais", n=total - len(names)) if total > len(names) else ""
    return Outcome(
        True, texto("na_pasta", pasta=label, nomes="; ".join(names), mais=more)
    )


def organize(action: Action) -> Outcome:
    path = folder_path(action.target)
    label = _folder_label(action.target)
    if path is None:
        return Outcome(False, texto("pasta_nao_achei", pasta=label))
    groups = arquivos.plan(path)
    total = sum(len(files) for files in groups.values())
    if total == 0:
        return Outcome(True, texto("ja_organizada", pasta=label))
    resumo = ", ".join(f"{name} {len(files)}" for name, files in sorted(groups.items()))
    confirmacao.ask(action)
    return Outcome(
        True,
        texto(
            "vou_organizar", qtd=contar("arquivo", total), pasta=label, resumo=resumo
        ),
    )


def _organize_now(action: Action) -> Outcome:
    path = folder_path(action.target)
    if path is None:
        return Outcome(False, texto("pasta_sumiu"))
    moved, _log = arquivos.organize(path, arquivos.plan(path))
    label = _folder_label(action.target)
    return Outcome(
        True, texto("organizado", qtd=contar("arquivo_organizado", moved), pasta=label)
    )


def organize_undo() -> Outcome:
    result = arquivos.undo_last()
    if result is None:
        return Outcome(True, texto("nada_desfazer"))
    restored, folder_name = result
    return Outcome(
        True,
        texto("desfeito", qtd=contar("arquivo_voltou", restored), pasta=folder_name),
    )


def play_youtube(action: Action) -> Outcome:
    url = youtube.first_video(action.target)
    if url is None:
        _start(youtube.search_url(action.target))
        return Outcome(True, texto("youtube_busca", q=action.target))
    _start(url)
    return Outcome(True, texto("youtube_tocando", q=action.target))


def run(action: Action) -> Optional[Outcome]:
    """Executa uma rotina; None se a ação não for uma rotina."""
    simple = {
        "remind_list": remind_list,
        "notes_list": notes_list,
        "notes_clear": notes_clear,
        "status": status,
        "screenshot": screenshot,
        "organize_undo": organize_undo,
        "confirm": confirm,
        "deny": deny,
    }
    if action.kind in simple:
        return simple[action.kind]()
    with_action = {
        "remind": remind,
        "agenda_add": agenda_add,
        "agenda_list": agenda_list,
        "agenda_cancel": agenda_cancel,
        "agenda_export": agenda_export,
        "file_latest": file_latest,
        "file_open": file_open,
        "file_find": file_find,
        "folder_list": folder_list,
        "organize": organize,
        "youtube": play_youtube,
        "remind_clear": remind_clear,
        "remind_cancel": remind_cancel,
        "note_add": note_add,
        "folder": folder,
        "close": close,
        "power": power,
    }
    if action.kind in with_action:
        return with_action[action.kind](action)
    return None
