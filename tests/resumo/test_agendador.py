"""Resumo automático: horário, dias da semana, uma vez por dia, aviso e voz."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest

from nicx.acoes import lembretes
from nicx.nucleo.config import ResumoConfig
from nicx.resumo import agendador

SEXTA_18H = datetime(2026, 10, 30, 18, 0)
SABADO_18H = datetime(2026, 10, 31, 18, 0)


def _cfg(**mudancas) -> ResumoConfig:
    cfg = ResumoConfig(ativo=True)
    for chave, valor in mudancas.items():
        setattr(cfg, chave, valor)
    return cfg


def test_padrao_desligado():
    cfg = ResumoConfig()
    assert cfg.ativo is False and cfg.hora == "18:00"
    assert cfg.falar is True and cfg.notificar is True
    assert cfg.dias == ["seg", "ter", "qua", "qui", "sex"]
    assert not agendador.deve_enviar(cfg, SEXTA_18H, None)


@pytest.mark.parametrize(
    ("agora", "ultimo", "cfg", "esperado"),
    [
        (SEXTA_18H, None, {}, True),
        (SEXTA_18H - timedelta(minutes=1), None, {}, False),  # antes da hora
        (SABADO_18H, None, {}, False),  # sábado não está nos dias
        (SABADO_18H, None, {"dias": ["sab"]}, True),
        (SEXTA_18H, date(2026, 10, 30), {}, False),  # já saiu hoje
        (SEXTA_18H, date(2026, 10, 29), {}, True),
        (SEXTA_18H, None, {"hora": "25:00"}, False),  # hora inválida
        (SEXTA_18H, None, {"hora": "7:30"}, True),
        (SEXTA_18H, None, {"dias": []}, False),
    ],
)
def test_deve_enviar(agora, ultimo, cfg, esperado):
    assert agendador.deve_enviar(_cfg(**cfg), agora, ultimo) is esperado


@pytest.fixture
def enviados(monkeypatch):
    chamadas: list[datetime] = []
    monkeypatch.setattr(agendador, "enviar", lambda cfg, agora: chamadas.append(agora))
    return chamadas


def test_uma_vez_por_dia(nicx_home, enviados):
    cfg = _cfg()
    assert agendador.verificar(SEXTA_18H, cfg, em_thread=False)
    assert not agendador.verificar(
        SEXTA_18H + timedelta(seconds=10), cfg, em_thread=False
    )
    assert not agendador.verificar(SEXTA_18H + timedelta(hours=3), cfg, em_thread=False)
    assert enviados == [SEXTA_18H]
    assert agendador.ultimo_envio() == date(2026, 10, 30)
    estado = json.loads((nicx_home / "resumo_estado.json").read_text(encoding="utf-8"))
    assert estado == {"ultimo_envio": "2026-10-30"}
    # Segunda-feira seguinte, de novo.
    segunda = datetime(2026, 11, 2, 18, 5)
    assert agendador.verificar(segunda, cfg, em_thread=False)
    assert enviados == [SEXTA_18H, segunda]


def test_servidor_ligado_depois_do_horario(nicx_home, enviados):
    cfg = _cfg()
    tarde = datetime(2026, 10, 30, 21, 40)
    assert agendador.verificar(tarde, cfg, em_thread=False)
    # Madrugada do dia seguinte: antes do horário, nada.
    assert not agendador.verificar(datetime(2026, 11, 2, 0, 30), cfg, em_thread=False)
    assert enviados == [tarde]


def test_desligado_nao_toca_no_disco(nicx_home, enviados):
    assert not agendador.verificar(SEXTA_18H, ResumoConfig(), em_thread=False)
    assert enviados == []
    assert not (nicx_home / "resumo_estado.json").exists()


def test_estado_ilegivel_conta_como_nunca(nicx_home):
    (nicx_home / "resumo_estado.json").write_text("{lixo", encoding="utf-8")
    assert agendador.ultimo_envio() is None


def test_falha_no_envio_nao_derruba(nicx_home, monkeypatch):
    def quebra(cfg, agora):
        raise RuntimeError("sem voz")

    monkeypatch.setattr(agendador, "enviar", quebra)
    assert agendador.verificar(SEXTA_18H, _cfg(), em_thread=False)


def test_verificar_le_a_config_carregada(nicx_home, enviados, monkeypatch):
    monkeypatch.setattr(agendador, "config", lambda: _cfg(hora="17:00"))
    assert agendador.verificar(SEXTA_18H, em_thread=False)


# ---------------------------------------------------------------------------
# Envio: notificação e voz
# ---------------------------------------------------------------------------


@pytest.fixture
def avisos(monkeypatch):
    feito: dict[str, list] = {"notificacao": [], "fala": []}
    monkeypatch.setattr(
        lembretes, "show_notification", lambda texto: feito["notificacao"].append(texto)
    )
    monkeypatch.setattr(
        lembretes,
        "speak",
        lambda texto, voice_id="": feito["fala"].append((texto, voice_id)),
    )
    return feito


def test_envia_notificacao_e_voz(nicx_home, avisos):
    texto = agendador.enviar(_cfg(), SEXTA_18H, "pt-BR")
    assert texto.startswith("Resumo do seu dia.")
    assert avisos["notificacao"] == [texto]
    assert avisos["fala"] == [(texto, "")]  # português: a voz do usuário


def test_respeita_falar_e_notificar(nicx_home, avisos):
    agendador.enviar(_cfg(falar=False), SEXTA_18H, "pt-BR")
    assert len(avisos["notificacao"]) == 1 and avisos["fala"] == []
    agendador.enviar(_cfg(notificar=False), SEXTA_18H, "pt-BR")
    assert len(avisos["notificacao"]) == 1 and len(avisos["fala"]) == 1


def test_voz_do_idioma(nicx_home, avisos):
    texto = agendador.enviar(_cfg(), SEXTA_18H, "en")
    assert texto.startswith("Summary of your day.")
    assert avisos["fala"] == [(texto, "af_heart")]
    # Árabe: o Kokoro não fala; fica só a notificação.
    agendador.enviar(_cfg(), SEXTA_18H, "ar")
    assert len(avisos["fala"]) == 1 and len(avisos["notificacao"]) == 2


def test_em_thread(nicx_home, avisos, monkeypatch):
    monkeypatch.setattr(agendador, "idioma_padrao", lambda: "pt-BR")
    assert agendador.verificar(SEXTA_18H, _cfg())
    for thread in __import__("threading").enumerate():
        if thread.name == "resumo-do-dia":
            thread.join(timeout=10)
    assert len(avisos["notificacao"]) == 1


# ---------------------------------------------------------------------------
# Despertador dos lembretes
# ---------------------------------------------------------------------------


def test_ligar_registra_no_despertador():
    agendador.ligar()
    agendador.ligar()
    try:
        assert lembretes._TASKS.count(agendador.verificar) == 1
    finally:
        agendador.desligar()
    assert agendador.verificar not in lembretes._TASKS


def test_despertador_chama_as_tarefas(monkeypatch):
    voltas: list[int] = []

    def tarefa():
        voltas.append(1)
        lembretes._STOP.set()

    def quebrada():
        raise RuntimeError("x")

    lembretes._STOP.clear()
    lembretes.add_task(quebrada)
    lembretes.add_task(tarefa)
    try:
        lembretes._loop(0.001, lambda r: None)
    finally:
        lembretes.remove_task(quebrada)
        lembretes.remove_task(tarefa)
        lembretes._STOP.clear()
    assert voltas == [1]


def test_historico_dos_lembretes(nicx_home):
    lembretes.add("velho", datetime(2026, 10, 1, 9, 0))
    lembretes.pop_due(datetime(2026, 10, 1, 9, 1))
    lembretes.add("hoje", datetime(2026, 10, 30, 9, 0))
    lembretes.pop_due(datetime(2026, 10, 30, 9, 1))
    assert [r.text for r in lembretes.fired_on(date(2026, 10, 30))] == ["hoje"]
    # O de 29 dias atrás saiu do histórico (só 14 dias ficam).
    assert lembretes.fired_on(date(2026, 10, 1)) == []
