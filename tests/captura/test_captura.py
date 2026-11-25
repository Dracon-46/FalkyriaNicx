"""Captura rápida: seleção ou texto copiado vão para as notas, com a origem."""

from __future__ import annotations

import threading

import pytest

from nicx.captura import servico
from nicx.contexto.janela import InfoJanela

CHROME = InfoJanela(
    hwnd=1, titulo="Receita de bolo - Google Chrome", processo="chrome.exe"
)
BANCO = InfoJanela(hwnd=2, titulo="Internet Banking - Itaú", processo="chrome.exe")


def _capturar(janela=CHROME, selecao="", copiado=""):
    guardado, avisos = [], []
    r = servico.capturar(
        janela=lambda: janela,
        selecao=lambda: selecao,
        copiado=lambda: copiado,
        esperar=lambda: None,
        guardar=guardado.append,
        avisar=avisos.append,
    )
    return r, guardado, avisos


def test_selecao_vira_nota_com_a_origem():
    r, guardado, avisos = _capturar(selecao="  200 g de farinha\n3 ovos  ")
    assert r.motivo == servico.OK
    assert guardado == [r.texto]
    assert r.texto.startswith("200 g de farinha 3 ovos (de ")
    assert "Guardado nas notas" in avisos[0]


def test_sem_selecao_usa_o_copiado_e_sem_nada_avisa():
    r, guardado, _ = _capturar(copiado="https://exemplo.com/artigo")
    assert r.motivo == servico.OK and guardado[0].startswith(
        "https://exemplo.com/artigo"
    )
    r, guardado, avisos = _capturar()
    assert r.motivo == servico.VAZIO and guardado == []
    assert "selecione ou copie" in avisos[0]


def test_janela_sensivel_nunca_e_capturada():
    chamou = []
    r = servico.capturar(
        janela=lambda: BANCO,
        selecao=lambda: chamou.append(1) or "senha",
        copiado=lambda: "x",
        esperar=lambda: None,
        guardar=chamou.append,
        avisar=lambda _t: None,
    )
    assert r.motivo == servico.SENSIVEL and chamou == []


def test_texto_longo_e_cortado_numa_linha():
    linha = servico.linha_da_nota("a\n" * 2000, "Word")
    assert "\n" not in linha and linha.endswith("… (de Word)")
    assert len(linha) <= servico.MAX_CARACTERES + len(" (de Word)")


def test_nota_de_verdade(tmp_path, monkeypatch):
    from nicx.acoes import notas

    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    r = servico.capturar(
        janela=lambda: None,
        selecao=lambda: "ideia: app de receitas",
        copiado=lambda: "",
        esperar=lambda: None,
        avisar=lambda _t: None,
    )
    assert r.motivo == servico.OK
    assert any("ideia: app de receitas" in n for n in notas.all_notes())


def test_acoes_rodam_fora_da_thread_e_uma_por_vez():
    comecou, solta = threading.Event(), threading.Event()
    vezes = []

    def lento():
        vezes.append(1)
        comecou.set()
        solta.wait(5)

    acoes = servico.AcoesCaptura(lento)
    acoes.executar()
    assert comecou.wait(5)
    acoes.executar()  # ainda ocupada: ignorada
    solta.set()
    for t in threading.enumerate():
        if t.name == "nicx-captura":
            t.join(5)
    assert vezes == [1]


@pytest.mark.parametrize(
    "teclas, esperado",
    [("ctrl+alt+n", "do Nicx"), ("ctrl+alt+d", "do ditado")],
)
def test_rota_recusa_atalho_repetido(teclas, esperado, monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.nucleo.config import NicxConfig
    from nicx.servidor.rotas.captura import router

    class Falso:
        def aplicar(self, cfg):
            self.cfg = cfg
            return {}

        def status(self):
            return {"estado": "desligado", "mensagem": "", "suportado": True}

    config = NicxConfig()
    config._config_path = tmp_path / "config.toml"
    app = FastAPI()
    app.include_router(router)
    app.state.config = config
    app.state.captura = Falso()
    http = TestClient(app)
    r = http.put("/v1/captura", json={"teclas": teclas})
    assert r.status_code == 400 and esperado in r.json()["detail"]
    r = http.put("/v1/captura", json={"ativo": True, "teclas": "ctrl+shift+k"})
    assert r.status_code == 200, r.text
    assert r.json()["ativo"] is True and r.json()["teclas"] == "ctrl+shift+k"
    assert "[captura]" in (tmp_path / "config.toml").read_text(encoding="utf-8")
