"""Fala frase a frase no ``nicx chat --voice``."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rich.console import Console

from nicx.comandos.conversa._fala_continua import (
    DivisorFrases,
    FalaContinua,
    texto_falavel,
)
from nicx.comandos.conversa.chat import _stream_and_speak


def _frases(*pedacos: str) -> list[str]:
    divisor = DivisorFrases()
    saida: list[str] = []
    for p in pedacos:
        saida += divisor.adicionar(p)
    return saida + divisor.terminar()


def test_corta_quando_a_frase_fecha_mesmo_em_pedacos():
    divisor = DivisorFrases()
    assert divisor.adicionar("O tempo hoje em Sorocaba está ") == []
    assert divisor.adicionar("bom e seco. Amanhã ") == [
        "O tempo hoje em Sorocaba está bom e seco."
    ]
    assert divisor.terminar() == ["Amanhã"]


def test_nao_corta_abreviacao_inicial_numero_nem_hora():
    texto = (
        "O Sr. João Silva marcou às 15:30 e pagou R$ 3.500,00 ontem. "
        "Fim da conversa aqui."
    )
    assert _frases(texto) == [
        "O Sr. João Silva marcou às 15:30 e pagou R$ 3.500,00 ontem.",
        "Fim da conversa aqui.",
    ]


def test_frase_curta_junta_com_a_proxima():
    assert _frases("Sim. Pode deixar que eu cuido disso agora.") == [
        "Sim. Pode deixar que eu cuido disso agora."
    ]


def test_codigo_e_pensamento_nao_sao_falados():
    texto = (
        "<think>vou pensar bastante aqui. muito.</think>"
        "Use este comando no terminal agora:\n"
        "```bash\nnicx doctor. --tudo\n```\nDepois me conte o que apareceu na tela."
    )
    falado = " ".join(_frases(texto))
    assert "pensar" not in falado
    assert "nicx doctor" not in falado
    assert "Use este comando no terminal agora" in falado
    assert "Depois me conte o que apareceu na tela." in falado


def test_texto_falavel_tira_markdown():
    assert texto_falavel("**Dica:** veja [o site](https://x.y) e `nicx`") == (
        "Dica: veja o site e nicx"
    )


def test_fala_em_ordem_sem_sobrepor_e_comeca_antes_do_fim():
    tocando = threading.Lock()
    ordem: list[str] = []
    primeira_tocou = threading.Event()

    def sintetizar(frase):
        time.sleep(0.02)
        return (frase.encode(), 24000)

    def tocar(audio, taxa):
        assert tocando.acquire(blocking=False), "duas frases ao mesmo tempo"
        ordem.append(audio.decode())
        primeira_tocou.set()
        time.sleep(0.02)
        tocando.release()

    fala = FalaContinua(sintetizar, tocar)
    fala.adicionar("Primeira frase completa aqui. ")
    assert primeira_tocou.wait(2), "não começou a falar antes do fim do texto"
    fala.adicionar("Segunda frase completa aqui. Terceira frase completa")
    fala.terminar(timeout=5)
    assert ordem == [
        "Primeira frase completa aqui.",
        "Segunda frase completa aqui.",
        "Terceira frase completa",
    ]
    assert fala.erro is None


def test_cancelar_para_sem_travar():
    tocou: list[str] = []
    fala = FalaContinua(lambda f: (f.encode(), 24000), lambda a, t: tocou.append(a))
    fala.cancelar()
    fala.adicionar("Uma frase longa que não deve tocar. Outra frase longa também. ")
    fala.terminar(timeout=2)
    assert tocou == []


def test_erro_na_sintese_fica_registrado():
    def falha(frase):
        raise RuntimeError("sem voz")

    fala = FalaContinua(falha, lambda a, t: None)
    fala.adicionar("Uma frase que vai falhar na voz. ")
    fala.terminar(timeout=2)
    assert isinstance(fala.erro, RuntimeError)


class _MotorComStream:
    def __init__(self, pedacos):
        self._pedacos = pedacos

    async def stream(self, messages, *, model, **kwargs):
        for p in self._pedacos:
            yield p


def test_chat_com_voz_fala_frase_a_frase_e_devolve_o_texto():
    console = Console(record=True, width=120)
    falado: list[str] = []
    backend = MagicMock()
    backend.synthesize.side_effect = lambda frase, **kw: SimpleNamespace(
        audio=frase.encode(), sample_rate=24000
    )
    sessao = MagicMock()
    sessao.get_tts_backend.return_value = backend
    sessao.voice_for_backend.return_value = ("pf_dora", 1.0)
    motor = _MotorComStream(["Olá! Tudo certo por aqui ", "hoje. Até mais tarde, viu."])

    with patch(
        "nicx.voz.voice_io.play_wav",
        side_effect=lambda a, sample_rate: falado.append(a.decode()),
    ):
        texto = _stream_and_speak(motor, [], "m", {}, console, sessao)

    assert texto == "Olá! Tudo certo por aqui hoje. Até mais tarde, viu."
    assert falado == ["Olá! Tudo certo por aqui hoje.", "Até mais tarde, viu."]


def test_chat_sem_stream_utilizavel_cai_no_jeito_antigo():
    sessao = MagicMock()
    motor = MagicMock()  # stream() devolve um MagicMock, não um iterador assíncrono
    assert _stream_and_speak(motor, [], "m", {}, Console(), sessao) is None
    sessao.get_tts_backend.assert_not_called()
