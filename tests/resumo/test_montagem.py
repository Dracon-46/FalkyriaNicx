"""Montagem do resumo do dia: fontes vazias e cheias, idiomas, fuso, projetos."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from types import ModuleType

import pytest

from nicx.acoes import agenda, calendarios, lembretes, notas
from nicx.resumo import montagem, montar
from nicx.resumo.textos import FRASES

NOW = datetime(2026, 10, 30, 18, 30)  # sexta-feira
HOJE = NOW.date()
LONGE = datetime(2026, 10, 1, 8, 0)  # "agora" de quando os itens foram marcados


def _notas(home, linhas):
    (home / "notas.md").write_text(
        "# Anotações do Nicx\n\n" + "".join(f"- [{s}] {t}\n" for s, t in linhas),
        encoding="utf-8",
    )


def _organizacao(home, nome, pasta, n, sufixo=".json"):
    folder = home / "organizacao"
    folder.mkdir(exist_ok=True)
    moves = [{"source": f"a{i}", "target": f"b{i}"} for i in range(n)]
    (folder / f"{nome}{sufixo}").write_text(
        json.dumps({"folder": pasta, "moves": moves}), encoding="utf-8"
    )


def _projetos(monkeypatch, funcao):
    fake = ModuleType("nicx.projetos")
    fake.resumo_do_dia = funcao
    monkeypatch.setitem(sys.modules, "nicx.projetos", fake)


# ---------------------------------------------------------------------------
# Fontes vazias
# ---------------------------------------------------------------------------


def test_tudo_vazio():
    r = montar(HOJE, "pt-BR", agora=NOW)
    assert r.texto == (
        "Resumo do seu dia. Não encontrei nada registrado nesse dia."
        " Amanhã a agenda está livre."
    )
    assert r.texto_pendente == "Nada ficou pendente hoje. Amanhã a agenda está livre."
    secoes = r.como_dict()["secoes"]
    assert secoes["notas_total"] == 0 and secoes["compromissos_feitos"] == []


def test_padrao_e_hoje_em_portugues(monkeypatch):
    monkeypatch.setattr(montagem, "agora_local", lambda: NOW)
    r = montar()
    assert r.dia == HOJE and r.idioma == "pt-BR"


def test_arquivos_ruins_nao_derrubam(nicx_home):
    (nicx_home / "notas.md").write_bytes(b"\xff\xfe lixo")
    (nicx_home / "organizacao").mkdir()
    (nicx_home / "organizacao" / "20261030-100000.json").write_text(
        "{", encoding="utf-8"
    )
    (nicx_home / "lembretes_disparados.json").write_text("nada", encoding="utf-8")
    r = montar(HOJE, "pt-BR", agora=NOW)
    assert "Não encontrei nada" in r.texto


# ---------------------------------------------------------------------------
# Fontes cheias
# ---------------------------------------------------------------------------


@pytest.fixture
def dia_cheio(nicx_home):
    # Compromissos: um que já passou, um que ainda vem, um amanhã (com avisos).
    agenda.add("reunião com o João", datetime(2026, 10, 30, 15, 0), now=LONGE)
    agenda.add("academia", datetime(2026, 10, 30, 20, 0), now=LONGE)
    agenda.add("feriado", datetime(2026, 10, 30), all_day=True, now=LONGE)
    agenda.add("dentista", datetime(2026, 10, 31, 9, 30), now=LONGE)
    # Lembretes: dois tocaram hoje (um timer, que não conta), um ainda vem.
    lembretes.add("tomar remédio", datetime(2026, 10, 30, 9, 0))
    lembretes.add(lembretes._KIND_TEXT["timer"], datetime(2026, 10, 30, 10, 0))
    lembretes.add("ligar pra mãe", datetime(2026, 10, 30, 21, 0))
    lembretes.add("pagar boleto", datetime(2026, 10, 31, 10, 0))
    lembretes.pop_due(datetime(2026, 10, 30, 16, 0))  # inclui o aviso das 14h45
    _notas(
        nicx_home,
        [
            ("29/10 22:00", "de ontem"),
            ("30/10 08:00", "primeira"),
            ("30/10 09:00", "comprar pão"),
            ("30/10 10:00", "x" * 80),
            ("30/10 11:00", "ligar para o contador"),
        ],
    )
    _organizacao(nicx_home, "20261030-101500", "C:\\Users\\a\\Downloads", 12)
    _organizacao(nicx_home, "20261030-111500", "/home/a/Documentos", 1)
    _organizacao(nicx_home, "20261030-121500", "C:\\Users\\a\\Downloads", 3)
    _organizacao(nicx_home, "20261030-131500", "/home/a/Imagens", 5, ".desfeito")
    _organizacao(nicx_home, "20261029-101500", "/home/a/Músicas", 7)
    return nicx_home


def test_dia_cheio(dia_cheio):
    r = montar(HOJE, "pt-BR", agora=NOW)
    assert r.texto == (
        "Resumo do seu dia."
        " Compromissos que você teve: reunião com o João às 15h."
        " Ainda na agenda de hoje: feriado (dia todo); academia às 20h."
        " Lembretes que tocaram: tomar remédio."
        " Lembretes que ainda vêm hoje: ligar pra mãe às 21h."
        " Você fez 4 anotações; as últimas: comprar pão; "
        + "x"
        * 49
        + "…; ligar para o contador."
        " Organizei a pasta Downloads (15 arquivos); a pasta Documentos (1 arquivo)."
        " Amanhã você tem: dentista às 9h30."
    )
    assert r.texto_pendente == (
        "Ainda pendente hoje."
        " Lembretes que ainda vêm hoje: ligar pra mãe às 21h."
        " Ainda na agenda de hoje: feriado (dia todo); academia às 20h."
        " Amanhã você tem: dentista às 9h30."
    )
    secoes = r.como_dict()["secoes"]
    assert secoes["compromissos_restantes"][1] == {
        "titulo": "academia",
        "hora": "20:00",
    }
    assert secoes["compromissos_restantes"][0]["hora"] is None
    assert secoes["organizacoes"] == [
        {"pasta": "Downloads", "arquivos": 15},
        {"pasta": "Documentos", "arquivos": 1},
    ]


def test_resumo_de_ontem_fala_de_hoje(dia_cheio):
    r = montar(HOJE - timedelta(days=1), "pt-BR", agora=NOW)
    assert r.texto.startswith("Resumo de ontem. Você fez 1 anotação: de ontem.")
    assert "Organizei a pasta Músicas (7 arquivos)." in r.texto
    assert r.texto.endswith(
        "Hoje você tem: feriado (dia todo); reunião com o João às 15h; academia às 20h."
    )


def test_outro_dia_sem_frase_final(dia_cheio):
    r = montar(date(2026, 10, 20), "pt-BR", agora=NOW)
    assert r.texto == "Resumo de 20/10. Não encontrei nada registrado nesse dia."
    assert r.texto_pendente == "Nada ficou pendente em 20/10."


def test_muitos_itens_viram_e_mais(nicx_home):
    for i in range(8):
        lembretes.add(f"item {i}", datetime(2026, 10, 30, 19, i))
    r = montar(HOJE, "pt-BR", agora=NOW)
    assert "item 4 às 19h04 e mais 3." in r.texto


def test_eventos_sincronizados_sem_repetir(nicx_home, monkeypatch):
    enviado = agenda.add("call", datetime(2026, 10, 30, 10, 0), now=LONGE)
    agenda.update(enviado, google_id="g1")
    remotos = [
        calendarios.EventoConectado(
            "call", datetime(2026, 10, 30, 10, 0), False, "google", "g1"
        ),
        calendarios.EventoConectado(
            "aniversário da Ana", datetime(2026, 10, 30), True, "google", "g2"
        ),
        calendarios.EventoConectado(
            "planejamento", datetime(2026, 10, 30, 19, 0), False, "outlook", "o1"
        ),
    ]
    monkeypatch.setattr(
        calendarios,
        "eventos_conectados",
        lambda day: remotos if day == HOJE else [],
    )
    r = montar(HOJE, "pt-BR", agora=NOW)
    assert "Compromissos que você teve: call às 10h." in r.texto
    assert (
        "Ainda na agenda de hoje: aniversário da Ana (dia todo); planejamento às 19h."
        in r.texto
    )


# ---------------------------------------------------------------------------
# Anotações: o ano sai da ordem do arquivo
# ---------------------------------------------------------------------------


def test_notas_do_ano_passado_no_mesmo_dia_nao_contam(nicx_home):
    _notas(
        nicx_home,
        [
            ("30/10 09:00", "do ano passado"),
            ("15/12 09:00", "dezembro"),
            ("02/01 09:00", "janeiro"),
            ("30/10 07:00", "de hoje"),
        ],
    )
    r = montar(HOJE, "pt-BR", agora=NOW)
    assert r.notas_total == 1 and r.notas_ultimas == ["de hoje"]


def test_notas_com_o_modulo_de_notas(nicx_home, monkeypatch):
    class _Agora(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 30, 12, 0)

    monkeypatch.setattr(notas, "datetime", _Agora)
    notas.add("primeira")
    notas.add("segunda")
    r = montar(HOJE, "pt-BR", agora=NOW)
    assert "Você fez 2 anotações; as últimas: primeira; segunda." in r.texto


# ---------------------------------------------------------------------------
# Projetos (contrato de nicx.projetos.resumo_do_dia)
# ---------------------------------------------------------------------------


def test_projetos_com_modulo_falso(nicx_home, monkeypatch):
    pedidos: list[date] = []

    def resumo_do_dia(dia):
        pedidos.append(dia)
        return {
            "atualizados": ["Nicx", "Lumen"],
            "concluidas": [("Nicx", "corrigir login")],
            "pendentes": [("Nicx", f"tarefa {i}") for i in range(12)],
        }

    _projetos(monkeypatch, resumo_do_dia)
    r = montar(HOJE, "pt-BR", agora=NOW)
    assert pedidos == [HOJE]
    assert "Projetos em que você mexeu: Nicx; Lumen." in r.texto
    assert "Pendências concluídas: corrigir login (Nicx)." in r.texto
    assert "Ficou pendente: tarefa 0 (Nicx); tarefa 1 (Nicx)" in r.texto
    assert "tarefa 4 (Nicx) e mais 5." in r.texto  # só 10 vêm, 5 são faladas
    assert len(r.pendencias_abertas) == 10
    assert "Ficou pendente: tarefa 0 (Nicx)" in r.texto_pendente
    secoes = r.como_dict()["secoes"]
    assert secoes["pendencias_concluidas"] == [
        {"projeto": "Nicx", "pendencia": "corrigir login"}
    ]


def test_projetos_ausente_ou_com_erro(nicx_home, monkeypatch):
    assert montar(HOJE, "pt-BR", agora=NOW).projetos_atualizados == []

    def quebra(dia):
        raise RuntimeError("banco travado")

    _projetos(monkeypatch, quebra)
    r = montar(HOJE, "pt-BR", agora=NOW)
    assert "Não encontrei nada" in r.texto

    _projetos(monkeypatch, lambda dia: {"pendentes": [("só um",), None, ("P", "ok")]})
    r = montar(HOJE, "pt-BR", agora=NOW)
    assert r.pendencias_abertas == [("P", "ok")]

    _projetos(monkeypatch, lambda dia: ["não é dict"])
    assert montar(HOJE, "pt-BR", agora=NOW).pendencias_abertas == []


def test_modulo_de_projetos_sem_a_funcao(nicx_home, monkeypatch):
    monkeypatch.setitem(sys.modules, "nicx.projetos", ModuleType("nicx.projetos"))
    assert "Não encontrei nada" in montar(HOJE, "pt-BR", agora=NOW).texto


# ---------------------------------------------------------------------------
# Fuso
# ---------------------------------------------------------------------------


def test_hoje_no_fuso_de_sao_paulo(monkeypatch):
    # 01h30 em UTC do dia 31 ainda é 22h30 do dia 30 em São Paulo.
    monkeypatch.setattr(
        montagem,
        "_agora_utc",
        lambda: datetime(2026, 10, 31, 1, 30, tzinfo=timezone.utc),
    )
    assert montagem.agora_local() == datetime(2026, 10, 30, 22, 30)
    assert montagem.hoje() == date(2026, 10, 30)
    assert montar().dia == date(2026, 10, 30)


def test_fuso_vem_da_config(monkeypatch):
    monkeypatch.setattr(
        montagem,
        "_agora_utc",
        lambda: datetime(2026, 10, 31, 1, 30, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(calendarios, "fuso", lambda: "Asia/Tokyo")
    assert montagem.agora_local() == datetime(2026, 10, 31, 10, 30)
    monkeypatch.setattr(calendarios, "fuso", lambda: "Fuso/Inexistente")
    assert isinstance(montagem.agora_local(), datetime)  # cai no relógio do PC


# ---------------------------------------------------------------------------
# Idiomas
# ---------------------------------------------------------------------------


def test_todos_os_idiomas_tem_as_mesmas_chaves():
    base = set(FRASES["pt-BR"]) - {"refinar"}
    for codigo, frases in FRASES.items():
        assert set(frases) - {"refinar"} == base, codigo


@pytest.mark.parametrize(
    ("idioma", "cabecalho", "trecho"),
    [
        ("pt-BR", "Resumo do seu dia.", "Ainda na agenda de hoje: academia às 20h."),
        ("en", "Summary of your day.", "Still on today's calendar: academia at 8 PM."),
        ("es", "Resumen de tu día.", "Aún en la agenda de hoy: academia a las 20:00."),
        (
            "fr",
            "Résumé de ta journée.",
            "Encore à l'agenda aujourd'hui : academia à 20 h.",
        ),
        ("zh", "今天的总结。", "今天还有的日程：20:00 academia。"),
        ("hi", "आज का सारांश।", "आज अभी बाकी कार्यक्रम: academia (20:00)।"),
        ("ar", "ملخص يومك.", "ما زال في جدول اليوم: academia الساعة 20:00."),
    ],
)
def test_idiomas(nicx_home, idioma, cabecalho, trecho):
    agenda.add("academia", datetime(2026, 10, 30, 20, 0), now=LONGE)
    r = montar(HOJE, idioma, agora=NOW)
    assert r.texto.startswith(cabecalho)
    assert trecho in r.texto


def test_idioma_desconhecido_vira_portugues():
    assert montar(HOJE, "xx", agora=NOW).idioma == "pt-BR"
    assert montar(HOJE, "en-US", agora=NOW).texto.startswith("Summary of your day.")


def test_espanhol_a_la_una(nicx_home):
    agenda.add("almuerzo", datetime(2026, 10, 31, 1, 0), now=LONGE)
    r = montar(HOJE, "es", agora=NOW)
    assert r.texto.endswith("Mañana tienes: almuerzo a la 1:00.")
