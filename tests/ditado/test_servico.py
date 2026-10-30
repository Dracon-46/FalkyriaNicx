"""Fluxo do ditado com atalho, microfone, Whisper e digitação simulados."""

from __future__ import annotations

import logging
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from nicx.atalho.windows import ERROR_HOTKEY_ALREADY_REGISTERED, ResultadoRegistro
from nicx.ditado import servico
from nicx.ditado.gravacao import LimitesGravacao
from nicx.voz.escuta.detector import FRAME_SAMPLES, FRAME_SECONDS

FALA = np.full(FRAME_SAMPLES, 0.1, dtype="float32")
SILENCIO = np.zeros(FRAME_SAMPLES, dtype="float32")
SEGREDO = "minha senha do banco"


def vad(quadro) -> float:
    return 0.9 if float(quadro[0]) > 0.05 else 0.0


def quadros(segundos: float, quadro) -> list:
    return [quadro] * round(segundos / FRAME_SECONDS)


class FakeEscuta:
    resultado = ResultadoRegistro(True)

    def __init__(self, combinacao, ao_apertar) -> None:
        self.combinacao = combinacao
        self.ao_apertar = ao_apertar
        self.parada = False

    def iniciar(self) -> ResultadoRegistro:
        return type(self).resultado

    def parar(self) -> None:
        self.parada = True


class FakeFonte:
    """Entrega a lista; depois, *infinita* repete fala (com uma pausa curta)."""

    def __init__(self, lista: list, *, infinita: bool = False) -> None:
        self.lista = list(lista)
        self.infinita = infinita
        self.aberta = False

    def start(self) -> None:
        self.aberta = True

    def stop(self) -> None:
        self.aberta = False

    def read(self, timeout: float = 0.5):
        if self.lista:
            return self.lista.pop(0)
        if self.infinita:
            time.sleep(0.005)
            return FALA
        return None


class FakeDigitador:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok
        self.digitados: list[tuple[str, int]] = []

    def janela_em_foco(self) -> int:
        return 4242

    def digitar(self, texto: str, hwnd: int) -> bool:
        self.digitados.append((texto, hwnd))
        return self.ok


def _cfg(**ditado):
    base = dict(ativo=True, teclas="ctrl+alt+d", modo="alternar", idioma="", som=True)
    base.update(ditado)
    return SimpleNamespace(
        ditado=SimpleNamespace(**base),
        atalho=SimpleNamespace(ativo=True, teclas="ctrl+alt+n"),
        speech=SimpleNamespace(language="pt"),
    )


def _servico(
    cfg=None,
    *,
    fonte=None,
    texto="Olá, mundo vírgula tudo bem",
    digitador=None,
    plataforma="win32",
    tecla=lambda _vk: True,
):
    cfg = cfg or _cfg()
    criadas: list[FakeEscuta] = []
    registro = SimpleNamespace(
        transcricoes=[], sons=[], ocupado=[], criadas=criadas, fontes=[]
    )

    def fabrica(combinacao, ao_apertar):
        escuta = FakeEscuta(combinacao, ao_apertar)
        criadas.append(escuta)
        return escuta

    def fabrica_fonte():
        f = (
            fonte()
            if callable(fonte)
            else (
                fonte
                or FakeFonte(
                    quadros(0.5, SILENCIO) + quadros(1.0, FALA) + quadros(3.0, SILENCIO)
                )
            )
        )
        registro.fontes.append(f)
        return f

    def transcrever(audio, lingua):
        registro.transcricoes.append((len(audio), lingua))
        return texto

    registro.digitador = digitador or FakeDigitador()
    svc = servico.ServicoDitado(
        lambda: cfg,
        plataforma=plataforma,
        fabrica_escuta=fabrica,
        fabrica_fonte=fabrica_fonte,
        fabrica_vad=lambda: (vad, None),
        transcrever=transcrever,
        digitador=registro.digitador,
        som=registro.sons.append,
        avisar_ocupado=registro.ocupado.append,
        tecla_apertada=tecla,
        limites=LimitesGravacao(espera_inicial_s=2.0, max_s=10.0),
    )
    return svc, registro


def test_ditado_completo_digita_na_janela_guardada(caplog) -> None:
    svc, reg = _servico(texto=f"{SEGREDO} vírgula tudo bem ponto final")
    assert svc.aplicar()["estado"] == servico.PRONTO
    assert reg.criadas[0].combinacao.texto == "ctrl+alt+d"

    with caplog.at_level(logging.DEBUG):
        reg.criadas[0].ao_apertar()  # para sozinho no silêncio

    assert reg.digitador.digitados == [(f"{SEGREDO}, tudo bem.", 4242)]
    assert reg.transcricoes[0][1] == "pt"  # [speech] language
    assert reg.sons == ["inicio", "fim"]
    assert reg.ocupado[0] is True and reg.ocupado[-1] is False
    assert not reg.fontes[0].aberta  # microfone fechado
    assert svc.status()["estado"] == servico.PRONTO
    # Privacidade: o texto ditado não aparece no log, só o tamanho.
    assert SEGREDO not in caplog.text
    assert "caracteres digitados" in caplog.text


def test_segundo_toque_para_de_ouvir() -> None:
    svc, reg = _servico(fonte=lambda: FakeFonte(quadros(0.5, FALA), infinita=True))
    svc.aplicar()
    apertar = reg.criadas[0].ao_apertar
    sessao = threading.Thread(target=apertar)
    sessao.start()
    for _ in range(200):
        if svc.estado == servico.OUVINDO:
            break
        time.sleep(0.01)
    assert svc.estado == servico.OUVINDO
    time.sleep(0.05)
    apertar()  # segundo toque
    sessao.join(3)
    assert not sessao.is_alive()
    assert len(reg.digitador.digitados) == 1
    assert svc.estado == servico.PRONTO


def test_modo_segurar_para_ao_soltar_a_tecla() -> None:
    soltou = {"n": 0}

    def tecla(vk: int) -> bool:
        assert vk == ord("D")
        soltou["n"] += 1
        return soltou["n"] < 40  # ~40 quadros com a tecla apertada

    svc, reg = _servico(
        _cfg(modo="segurar"),
        fonte=lambda: FakeFonte(quadros(1.0, FALA) + quadros(5.0, SILENCIO)),
        tecla=tecla,
    )
    svc.aplicar()
    reg.criadas[0].ao_apertar()
    assert len(reg.digitador.digitados) == 1
    # Parou pela tecla, antes do fim da fala gravada.
    assert reg.transcricoes[0][0] < 1.6 * 16000


def test_silencio_nao_chama_o_whisper() -> None:
    svc, reg = _servico(fonte=lambda: FakeFonte(quadros(5.0, SILENCIO)))
    svc.aplicar()
    reg.criadas[0].ao_apertar()
    assert reg.transcricoes == []
    assert reg.digitador.digitados == []
    assert svc.estado == servico.PRONTO


@pytest.mark.parametrize(
    "texto", ["", "  ", "...", "Legendas pela comunidade Amara.org"]
)
def test_texto_vazio_ou_ruido_nao_digita(texto: str) -> None:
    svc, reg = _servico(texto=texto)
    svc.aplicar()
    reg.criadas[0].ao_apertar()
    assert len(reg.transcricoes) == 1
    assert reg.digitador.digitados == []


def test_sem_som_quando_desligado() -> None:
    svc, reg = _servico(_cfg(som=False))
    svc.aplicar()
    reg.criadas[0].ao_apertar()
    assert reg.sons == []
    assert len(reg.digitador.digitados) == 1


def test_idioma_escolhido_vai_para_o_whisper_e_os_comandos() -> None:
    svc, reg = _servico(_cfg(idioma="en"), texto="hello comma world")
    svc.aplicar()
    reg.criadas[0].ao_apertar()
    assert reg.transcricoes[0][1] == "en"
    assert reg.digitador.digitados[0][0] == "hello, world"


def test_idiomas_do_ditado() -> None:
    assert servico.idiomas_do_ditado(_cfg(idioma="fr")) == ("fr", "fr")
    assert servico.idiomas_do_ditado(_cfg()) == ("pt-BR", "pt")
    cfg = _cfg()
    cfg.speech.language = ""
    assert servico.idiomas_do_ditado(cfg) == ("pt-BR", None)  # Whisper detecta


def test_falha_ao_digitar_vira_erro_e_o_proximo_funciona() -> None:
    digitador = FakeDigitador(ok=False)
    svc, reg = _servico(digitador=digitador)
    svc.aplicar()
    reg.criadas[0].ao_apertar()
    assert svc.status()["estado"] == servico.ERRO
    assert "janela de origem" in svc.status()["mensagem"]

    digitador.ok = True
    reg.criadas[0].ao_apertar()
    assert svc.estado == servico.PRONTO
    assert len(digitador.digitados) == 2


def test_falha_no_whisper_vira_erro_e_fecha_o_microfone(caplog) -> None:
    svc, reg = _servico()

    def quebra(_audio, _lingua):
        raise RuntimeError("modelo indisponível")

    svc._transcrever = quebra
    svc.aplicar()
    with caplog.at_level(logging.ERROR, logger="nicx.ditado.servico"):
        reg.criadas[0].ao_apertar()
    assert svc.estado == servico.ERRO
    assert reg.ocupado[-1] is False
    assert not reg.fontes[0].aberta


# ---------------------------------------------------------------------------
# Registro do atalho
# ---------------------------------------------------------------------------


def test_desligado_por_padrao_nao_registra() -> None:
    svc, reg = _servico(_cfg(ativo=False))
    assert svc.aplicar()["estado"] == servico.DESLIGADO
    assert reg.criadas == []


def test_igual_ao_atalho_do_nicx_e_recusado() -> None:
    svc, reg = _servico(_cfg(teclas="Alt + Ctrl + N"))
    status = svc.aplicar()
    assert status["estado"] == servico.INVALIDO
    assert "atalho que chama o Nicx" in status["mensagem"]
    assert reg.criadas == []


def test_combinacao_invalida_ou_modo_desconhecido() -> None:
    svc, _ = _servico(_cfg(teclas="win+l"))
    assert svc.aplicar()["estado"] == servico.INVALIDO
    svc, _ = _servico(_cfg(modo="sussurrar"))
    assert svc.aplicar()["estado"] == servico.INVALIDO


def test_em_uso_por_outro_programa(caplog) -> None:
    FakeEscuta.resultado = ResultadoRegistro(
        False, ERROR_HOTKEY_ALREADY_REGISTERED, "A combinação já está em uso."
    )
    try:
        svc, _ = _servico()
        with caplog.at_level(logging.WARNING, logger="nicx.ditado.servico"):
            assert svc.aplicar()["estado"] == servico.EM_USO
        assert "em uso por outro programa" in caplog.text
    finally:
        FakeEscuta.resultado = ResultadoRegistro(True)


def test_sem_suporte_fora_do_windows(caplog) -> None:
    svc, reg = _servico(plataforma="linux")
    with caplog.at_level(logging.INFO, logger="nicx.ditado.servico"):
        status = svc.aplicar()
    assert status["estado"] == servico.SEM_SUPORTE
    assert status["suportado"] is False
    assert reg.criadas == []
    assert "sem suporte neste sistema" in caplog.text


def test_reaplicar_troca_o_registro_e_parar_desliga() -> None:
    cfg = _cfg()
    svc, reg = _servico(cfg)
    svc.aplicar()
    cfg.ditado.teclas = "ctrl+shift+f9"
    assert svc.aplicar()["estado"] == servico.PRONTO
    assert reg.criadas[0].parada
    assert reg.criadas[1].combinacao.texto == "ctrl+shift+f9"
    svc.parar()
    assert reg.criadas[1].parada
    assert svc.estado == servico.DESLIGADO
    # Depois de parar, um toque atrasado não faz nada.
    reg.criadas[1].ao_apertar()
    assert reg.fontes == []


def test_validar_teclas() -> None:
    assert servico.validar_teclas("Ctrl + Alt + D", "ctrl+alt+n").texto == "ctrl+alt+d"
    with pytest.raises(servico.TeclasEmConflito):
        servico.validar_teclas("ctrl+alt+n", "Ctrl + Alt + N")
