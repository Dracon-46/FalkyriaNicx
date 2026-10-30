"""Digitação com o user32 simulado: nenhuma tecla de verdade é enviada."""

from __future__ import annotations

import ctypes
import sys
from types import SimpleNamespace

import pytest

from nicx.ditado import digitar
from nicx.ditado.digitar import (
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    VK_RETURN,
    VK_SHIFT,
    DigitadorWindows,
    eventos_para,
)


def test_eventos_unicode_e_quebra_de_linha() -> None:
    assert eventos_para("ç") == [
        (0, ord("ç"), KEYEVENTF_UNICODE),
        (0, ord("ç"), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
    ]
    # Shift+Enter: pula linha sem enviar mensagem em programas de chat.
    assert eventos_para("\n") == [
        (VK_SHIFT, 0, 0),
        (VK_RETURN, 0, 0),
        (VK_RETURN, 0, KEYEVENTF_KEYUP),
        (VK_SHIFT, 0, KEYEVENTF_KEYUP),
    ]
    # Emoji: par de surrogates UTF-16, cada um apertado e solto.
    emoji = eventos_para("😀")
    assert [e[1] for e in emoji] == [0xD83D, 0xD83D, 0xDE00, 0xDE00]
    assert eventos_para("a\r\nb") == eventos_para("a\nb")


@pytest.mark.skipif(sys.platform != "win32", reason="estrutura INPUT do Windows")
def test_estrutura_input_tem_o_tamanho_do_windows() -> None:
    input_t, _ = digitar._estruturas()
    assert ctypes.sizeof(input_t) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)


class FakeUser32:
    def __init__(self, *, frente: int = 1, aceita_foco: bool = True) -> None:
        self.frente = frente
        self.aceita_foco = aceita_foco
        self.apertadas: set[int] = set()
        self.ligacoes: list[tuple] = []

    def GetForegroundWindow(self) -> int:  # noqa: N802
        return self.frente

    def IsWindow(self, hwnd) -> bool:  # noqa: N802
        return hwnd in (1, 2)

    def IsIconic(self, _hwnd) -> bool:  # noqa: N802
        return False

    def ShowWindow(self, *_a) -> int:  # noqa: N802
        return 1

    def BringWindowToTop(self, *_a) -> int:  # noqa: N802
        return 1

    def SetForegroundWindow(self, hwnd) -> int:  # noqa: N802
        if self.aceita_foco:
            self.frente = hwnd
            return 1
        return 0

    def GetWindowThreadProcessId(self, *_a) -> int:  # noqa: N802
        return 99

    def AttachThreadInput(self, *args) -> int:  # noqa: N802
        self.ligacoes.append(args)
        return 1

    def GetAsyncKeyState(self, vk) -> int:  # noqa: N802
        return -32768 if vk in self.apertadas else 0


def _digitador(user32: FakeUser32, enviados: list, *, recusar: bool = False):
    def enviar(eventos):
        enviados.append(list(eventos))
        return 0 if recusar else len(eventos)

    kernel32 = SimpleNamespace(GetCurrentThreadId=lambda: 7)
    return DigitadorWindows(
        win32=(user32, kernel32), enviar=enviar, dormir=lambda _s: None
    )


def test_volta_para_a_janela_e_digita_em_lotes() -> None:
    user32 = FakeUser32(frente=2)
    enviados: list = []
    digitador = _digitador(user32, enviados)
    texto = "x" * 100  # 200 eventos
    assert digitador.digitar(texto, 1)
    assert user32.frente == 1
    assert [len(lote) for lote in enviados] == [64, 64, 64, 8]
    assert sum(enviados, []) == eventos_para(texto)


def test_foco_negado_tenta_pela_fila_da_janela_e_nao_digita() -> None:
    user32 = FakeUser32(frente=2, aceita_foco=False)
    enviados: list = []
    assert not _digitador(user32, enviados).digitar("oi", 1)
    assert enviados == []  # nada vai para a janela errada
    assert user32.ligacoes == [(7, 99, True), (7, 99, False)]


def test_janela_que_fechou_nao_recebe_nada() -> None:
    enviados: list = []
    assert not _digitador(FakeUser32(), enviados).digitar("oi", 555)
    assert enviados == []


def test_espera_soltar_os_modificadores() -> None:
    user32 = FakeUser32()
    user32.apertadas = {0x12}  # Alt ainda apertado
    relogio = {"t": 0.0}

    def dormir(s: float) -> None:
        relogio["t"] += s
        if relogio["t"] > 0.1:
            user32.apertadas.clear()

    digitador = DigitadorWindows(
        win32=(user32, SimpleNamespace(GetCurrentThreadId=lambda: 7)),
        enviar=lambda e: len(e),
        dormir=dormir,
        relogio=lambda: relogio["t"],
    )
    assert digitador.esperar_modificadores()
    assert relogio["t"] > 0.1


def test_windows_recusou_as_teclas() -> None:
    enviados: list = []
    assert not _digitador(FakeUser32(), enviados, recusar=True).digitar("oi", 1)
    assert len(enviados) == 1
