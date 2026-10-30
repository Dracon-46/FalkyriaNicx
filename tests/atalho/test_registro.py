"""Registro do atalho com o user32 simulado (nenhum atalho de verdade) e o
gerenciador que liga/desliga conforme o config."""

from __future__ import annotations

import logging
import queue
import threading
from types import SimpleNamespace

from nicx.atalho import servico
from nicx.atalho.teclas import ler_combinacao
from nicx.atalho.windows import (
    ERROR_HOTKEY_ALREADY_REGISTERED,
    HOTKEY_ID,
    MOD_NOREPEAT,
    WM_HOTKEY,
    WM_QUIT,
    EscutaAtalho,
    ResultadoRegistro,
)


class FakeUser32:
    """Imita o pedaço do user32 usado pela escuta: uma fila por thread."""

    def __init__(self, *, recusar_com: int = 0) -> None:
        self.recusar_com = recusar_com
        self.registros: list[tuple] = []
        self.removidos: list[int] = []
        self.fila: "queue.Queue[tuple[int, int]]" = queue.Queue()
        self.ultimo_erro = 0
        self.thread_registro: int | None = None
        self.thread_remocao: int | None = None

    def PeekMessageW(self, *_args) -> int:  # noqa: N802
        return 0

    def RegisterHotKey(self, hwnd, ident, mods, vk) -> int:  # noqa: N802
        self.thread_registro = threading.get_ident()
        if self.recusar_com:
            self.ultimo_erro = self.recusar_com
            return 0
        self.registros.append((hwnd, ident, mods, vk))
        return 1

    def UnregisterHotKey(self, _hwnd, ident) -> int:  # noqa: N802
        self.thread_remocao = threading.get_ident()
        self.removidos.append(ident)
        return 1

    def GetMessageW(self, ref, *_args) -> int:  # noqa: N802
        mensagem, wparam = self.fila.get(timeout=5)
        ref._obj.message = mensagem
        ref._obj.wParam = wparam
        return 0 if mensagem == WM_QUIT else 1

    def PostThreadMessageW(self, _thread_id, mensagem, wparam, _lparam) -> int:  # noqa: N802
        self.fila.put((mensagem, wparam))
        return 1

    def apertar(self) -> None:
        self.fila.put((WM_HOTKEY, HOTKEY_ID))


def _win32(user32: FakeUser32):
    kernel32 = SimpleNamespace(GetCurrentThreadId=lambda: 777)
    return user32, kernel32, lambda: user32.ultimo_erro


def test_registra_dispara_e_remove_na_mesma_thread() -> None:
    user32 = FakeUser32()
    tocou = threading.Event()
    relogio = SimpleNamespace(agora=0.0)
    escuta = EscutaAtalho(
        ler_combinacao("ctrl+alt+n"),
        tocou.set,
        win32=_win32(user32),
        relogio=lambda: relogio.agora,
    )

    resultado = escuta.iniciar()
    assert resultado.ok
    assert user32.registros == [(None, HOTKEY_ID, 0x0003 | MOD_NOREPEAT, ord("N"))]

    user32.apertar()
    assert tocou.wait(2)

    escuta.parar()
    assert not escuta.rodando
    assert user32.removidos == [HOTKEY_ID]
    # O Windows exige registrar e remover na thread do laço de mensagens.
    assert user32.thread_registro == user32.thread_remocao


def test_toques_seguidos_contam_uma_vez() -> None:
    user32 = FakeUser32()
    toques: list[int] = []
    feito = threading.Event()
    relogio = SimpleNamespace(agora=10.0)

    def ao_apertar() -> None:
        toques.append(1)
        feito.set()

    escuta = EscutaAtalho(
        ler_combinacao("ctrl+alt+n"),
        ao_apertar,
        win32=_win32(user32),
        relogio=lambda: relogio.agora,
    )
    assert escuta.iniciar().ok
    user32.apertar()
    user32.apertar()  # mesmo instante: ignorado
    assert feito.wait(2)
    escuta.parar()
    assert toques == [1]


def test_combinacao_em_uso_por_outro_programa() -> None:
    user32 = FakeUser32(recusar_com=ERROR_HOTKEY_ALREADY_REGISTERED)
    escuta = EscutaAtalho(
        ler_combinacao("ctrl+alt+n"), lambda: None, win32=_win32(user32)
    )
    resultado = escuta.iniciar()
    assert not resultado.ok
    assert resultado.em_uso
    assert "em uso" in resultado.mensagem
    escuta.parar()  # nada para parar, sem erro
    assert user32.removidos == []


# ---------------------------------------------------------------------------
# Gerenciador
# ---------------------------------------------------------------------------


class FakeEscuta:
    def __init__(self, combinacao, ao_apertar, resultado: ResultadoRegistro) -> None:
        self.combinacao = combinacao
        self.ao_apertar = ao_apertar
        self.resultado = resultado
        self.parada = False

    def iniciar(self) -> ResultadoRegistro:
        return self.resultado

    def parar(self) -> None:
        self.parada = True


class FakeAcoes:
    def __init__(self) -> None:
        self.executadas: list[str] = []

    def executar(self, acao: str) -> None:
        self.executadas.append(acao)


def _gerenciador(resultado=ResultadoRegistro(True), plataforma="win32"):
    criadas: list[FakeEscuta] = []
    acoes = FakeAcoes()

    def fabrica(combinacao, ao_apertar):
        escuta = FakeEscuta(combinacao, ao_apertar, resultado)
        criadas.append(escuta)
        return escuta

    gerente = servico.GerenciadorAtalho(
        acoes, plataforma=plataforma, fabrica_escuta=fabrica
    )
    return gerente, criadas, acoes


def _cfg(ativo=True, teclas="ctrl+alt+n", acao="flutuante"):
    return SimpleNamespace(ativo=ativo, teclas=teclas, acao=acao)


def test_gerenciador_liga_reinicia_e_desliga() -> None:
    gerente, criadas, acoes = _gerenciador()

    assert gerente.aplicar(_cfg(ativo=False))["estado"] == servico.DESLIGADO
    assert criadas == []

    assert gerente.aplicar(_cfg())["estado"] == servico.REGISTRADO
    criadas[0].ao_apertar()
    assert acoes.executadas == ["flutuante"]

    # Config mudou: o registro anterior sai antes do novo entrar.
    assert gerente.aplicar(_cfg(teclas="ctrl+shift+space", acao="app"))["estado"] == (
        servico.REGISTRADO
    )
    assert criadas[0].parada
    assert criadas[1].combinacao.texto == "ctrl+shift+space"
    criadas[1].ao_apertar()
    assert acoes.executadas == ["flutuante", "app"]

    gerente.parar()
    assert criadas[1].parada
    assert gerente.status()["estado"] == servico.DESLIGADO


def test_gerenciador_avisa_combinacao_em_uso(caplog) -> None:
    gerente, _criadas, _acoes = _gerenciador(
        ResultadoRegistro(False, ERROR_HOTKEY_ALREADY_REGISTERED, "em uso")
    )
    with caplog.at_level(logging.WARNING, logger="nicx.atalho.servico"):
        status = gerente.aplicar(_cfg())
    assert status["estado"] == servico.EM_USO
    assert "em uso por outro programa" in caplog.text


def test_gerenciador_combinacao_invalida_nao_registra() -> None:
    gerente, criadas, _acoes = _gerenciador()
    status = gerente.aplicar(_cfg(teclas="win+l"))
    assert status["estado"] == servico.INVALIDO
    assert criadas == []


def test_gerenciador_erro_inesperado_nao_quebra() -> None:
    def fabrica(_combinacao, _ao_apertar):
        raise OSError("user32 indisponível")

    gerente = servico.GerenciadorAtalho(
        FakeAcoes(), plataforma="win32", fabrica_escuta=fabrica
    )
    status = gerente.aplicar(_cfg())
    assert status["estado"] == servico.ERRO
    assert "user32" in status["mensagem"]


def test_sem_suporte_fora_do_windows(caplog) -> None:
    gerente, criadas, _acoes = _gerenciador(plataforma="linux")
    with caplog.at_level(logging.INFO, logger="nicx.atalho.servico"):
        status = gerente.aplicar(_cfg())
    assert status["estado"] == servico.SEM_SUPORTE
    assert status["suportado"] is False
    assert criadas == []
    assert "sem suporte neste sistema" in caplog.text


# ---------------------------------------------------------------------------
# Um laço só para os dois atalhos (Nicx e ditado)
# ---------------------------------------------------------------------------


def test_dois_atalhos_no_mesmo_laco() -> None:
    from nicx.atalho.windows import HOTKEY_ID_DITADO, LacoAtalhos

    user32 = FakeUser32()
    laco = LacoAtalhos(win32=_win32(user32), relogio=lambda: 0.0)
    nicx = threading.Event()
    ditado = threading.Event()

    assert laco.registrar(HOTKEY_ID, ler_combinacao("ctrl+alt+n"), nicx.set).ok
    assert laco.registrar(HOTKEY_ID_DITADO, ler_combinacao("ctrl+alt+d"), ditado.set).ok
    assert [r[1] for r in user32.registros] == [HOTKEY_ID, HOTKEY_ID_DITADO]

    user32.fila.put((WM_HOTKEY, HOTKEY_ID_DITADO))
    assert ditado.wait(2)
    assert not nicx.is_set()

    # Tirar um não derruba o outro.
    laco.remover(HOTKEY_ID_DITADO)
    assert laco.rodando
    user32.apertar()
    assert nicx.wait(2)

    # Sem atalho nenhum, a thread sai sozinha.
    laco.remover(HOTKEY_ID)
    laco._thread.join(2)
    assert not laco.rodando
    assert user32.removidos == [HOTKEY_ID_DITADO, HOTKEY_ID]
    assert user32.thread_registro == user32.thread_remocao

    # E volta na próxima vez.
    assert laco.registrar(HOTKEY_ID, ler_combinacao("ctrl+alt+n"), nicx.set).ok
    laco.parar()
    assert not laco.rodando


def test_mesma_combinacao_duas_vezes_fica_em_uso() -> None:
    from nicx.atalho.windows import HOTKEY_ID_DITADO, LacoAtalhos

    class User32Unico(FakeUser32):
        def RegisterHotKey(self, hwnd, ident, mods, vk) -> int:  # noqa: N802
            if any(r[2:] == (mods, vk) for r in self.registros):
                self.ultimo_erro = ERROR_HOTKEY_ALREADY_REGISTERED
                return 0
            return super().RegisterHotKey(hwnd, ident, mods, vk)

    user32 = User32Unico()
    laco = LacoAtalhos(win32=_win32(user32))
    assert laco.registrar(HOTKEY_ID, ler_combinacao("ctrl+alt+n"), lambda: None).ok
    resultado = laco.registrar(
        HOTKEY_ID_DITADO, ler_combinacao("ctrl+alt+n"), lambda: None
    )
    assert resultado.em_uso
    laco.parar()
