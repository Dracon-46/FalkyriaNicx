"""Gravação do ditado com quadros sintéticos e VAD simulado (sem microfone)."""

from __future__ import annotations

import numpy as np

from nicx.ditado.gravacao import (
    LIMITE,
    PARADO,
    SEM_FALA,
    SILENCIO,
    DetectorFala,
    LimitesGravacao,
    gravar,
)
from nicx.voz.escuta.detector import FRAME_SAMPLES, FRAME_SECONDS

FALA = np.full(FRAME_SAMPLES, 0.1, dtype="float32")
SILENCIO_Q = np.zeros(FRAME_SAMPLES, dtype="float32")


def vad(quadro) -> float:
    return 0.9 if float(quadro[0]) > 0.05 else 0.0


def quadros(segundos: float, quadro) -> list:
    return [quadro] * round(segundos / FRAME_SECONDS)


def alimentar(detector: DetectorFala, lista: list) -> tuple[str | None, int]:
    for i, quadro in enumerate(lista):
        motivo = detector.push(quadro)
        if motivo:
            return motivo, i + 1
    return None, len(lista)


def test_para_depois_de_um_segundo_e_meio_de_silencio() -> None:
    detector = DetectorFala(vad)
    lista = quadros(1.0, SILENCIO_Q) + quadros(2.0, FALA) + quadros(5.0, SILENCIO_Q)
    motivo, usados = alimentar(detector, lista)
    assert motivo == SILENCIO
    # 1 s de espera + 2 s de fala + ~1,5 s de silêncio.
    assert abs(usados * FRAME_SECONDS - 4.5) < 0.1
    audio = detector.audio()
    # A fala com ~0,3 s de margem de cada lado, sem o silêncio do começo.
    assert abs(len(audio) / 16000 - 2.6) < 0.1
    assert audio.dtype == np.float32
    detector.descartar()
    assert detector.quadros == 0


def test_ninguem_falou_desiste_sem_audio() -> None:
    detector = DetectorFala(vad, LimitesGravacao(espera_inicial_s=2.0))
    motivo, usados = alimentar(detector, quadros(10.0, SILENCIO_Q))
    assert motivo == SEM_FALA
    assert abs(usados * FRAME_SECONDS - 2.0) < 0.1
    assert detector.audio() is None


def test_estalo_curto_nao_conta_como_fala() -> None:
    detector = DetectorFala(vad, LimitesGravacao(espera_inicial_s=1.0))
    lista = quadros(0.064, FALA) + quadros(3.0, SILENCIO_Q)
    motivo, _ = alimentar(detector, lista)
    assert motivo == SEM_FALA
    assert detector.audio() is None


def test_limite_de_tempo() -> None:
    detector = DetectorFala(vad, LimitesGravacao(max_s=3.0))
    motivo, usados = alimentar(detector, quadros(10.0, FALA))
    assert motivo == LIMITE
    assert abs(usados * FRAME_SECONDS - 3.0) < 0.1
    assert detector.audio() is not None


def test_modo_segurar_ignora_o_silencio() -> None:
    detector = DetectorFala(vad, LimitesGravacao(parar_no_silencio=False, max_s=8.0))
    motivo, _ = alimentar(detector, quadros(1.0, FALA) + quadros(4.0, SILENCIO_Q))
    assert motivo is None


class FonteLista:
    def __init__(self, lista: list) -> None:
        self.lista = list(lista)

    def read(self, timeout: float = 0.5):
        return self.lista.pop(0) if self.lista else None


def test_gravar_para_quando_pedem() -> None:
    detector = DetectorFala(vad)
    chamadas = {"n": 0}

    def parar() -> bool:
        chamadas["n"] += 1
        return chamadas["n"] > 40

    assert gravar(FonteLista(quadros(10.0, FALA)), detector, parar) == PARADO
    assert detector.quadros == 40


def test_gravar_microfone_mudo_tem_prazo() -> None:
    relogio = {"t": 0.0}

    def agora() -> float:
        relogio["t"] += 1.0
        return relogio["t"]

    detector = DetectorFala(vad, LimitesGravacao(max_s=3.0))
    motivo = gravar(FonteLista([]), detector, lambda: False, relogio=agora)
    assert motivo == LIMITE
