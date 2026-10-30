"""Gravação do ditado: microfone até o usuário parar, o silêncio ou o limite.

Reaproveita as peças da escuta "Nicx, ligar" (:mod:`nicx.voz.escuta.detector`):
quadros de 32 ms a 16 kHz, portão de energia e Silero VAD. O áudio fica só na
memória (um array) e é descartado depois da transcrição.

Regras (modo "alternar"):

- para quando o usuário aperta o atalho de novo;
- para sozinho após ~1,5 s de silêncio depois de alguma fala;
- se ninguém falar nos primeiros segundos, desiste (nada é digitado);
- nunca passa de 60 s.

No modo "segurar" o silêncio não encerra: vale a tecla solta (ou o limite).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from nicx.voz.escuta.detector import FRAME_SECONDS, frame_rms

logger = logging.getLogger(__name__)

# Por que a gravação terminou.
PARADO = "parado"  # o usuário apertou (ou soltou) o atalho
SILENCIO = "silencio"
LIMITE = "limite"
SEM_FALA = "sem_fala"


@dataclass
class LimitesGravacao:
    silencio_fim_s: float = 1.5
    max_s: float = 60.0
    # Ninguém falou até aqui: desiste sem chamar o Whisper.
    espera_inicial_s: float = 8.0
    # O silêncio encerra a gravação? (falso no modo "segurar")
    parar_no_silencio: bool = True
    # Áudio guardado antes do início da fala e depois do fim.
    margem_inicio_s: float = 0.3
    margem_fim_s: float = 0.3
    # VAD (as mesmas faixas da escuta "Nicx, ligar").
    prob_inicio: float = 0.5
    prob_fim: float = 0.35
    min_rms: float = 0.004
    fator_ruido: float = 2.5
    # Fala de verdade: pelo menos isso de quadros com voz (~0,2 s).
    min_voz_s: float = 0.2


class DetectorFala:
    """Acompanha os quadros e diz quando a gravação deve terminar.

    *vad* recebe um quadro float32 e devolve a probabilidade de voz. Puro e
    testável sem microfone nem modelo.
    """

    def __init__(
        self,
        vad: Callable[[Any], float],
        limites: Optional[LimitesGravacao] = None,
        *,
        vad_reset: Optional[Callable[[], None]] = None,
    ) -> None:
        self.lim = limites or LimitesGravacao()
        self._vad = vad
        self._vad_reset = vad_reset
        self._quadros: list = []
        self._ruido = self.lim.min_rms
        self._calado = 0
        self._voz = 0
        self._primeiro_com_voz: Optional[int] = None
        self._ultimo_com_voz: Optional[int] = None
        self._silencio = 0
        self._fim_quadros = max(1, round(self.lim.silencio_fim_s / FRAME_SECONDS))
        self._max_quadros = max(1, round(self.lim.max_s / FRAME_SECONDS))
        self._espera_quadros = max(1, round(self.lim.espera_inicial_s / FRAME_SECONDS))
        self._min_voz = max(1, round(self.lim.min_voz_s / FRAME_SECONDS))

    @property
    def falou(self) -> bool:
        return self._voz >= self._min_voz

    @property
    def quadros(self) -> int:
        return len(self._quadros)

    def _probabilidade(self, quadro: Any) -> float:
        rms = frame_rms(quadro)
        portao = max(self.lim.min_rms, self._ruido * self.lim.fator_ruido)
        if rms < portao:
            # Silêncio: acompanha o ruído de fundo e nem roda o VAD.
            self._ruido = 0.95 * self._ruido + 0.05 * max(rms, 1e-5)
            self._calado += 1
            if self._calado == 30 and self._vad_reset:  # ~1 s calado
                self._vad_reset()
            return 0.0
        self._calado = 0
        return float(self._vad(quadro))

    def push(self, quadro: Any) -> Optional[str]:
        """Guarda o quadro; devolve o motivo para parar, ou None."""
        indice = len(self._quadros)
        self._quadros.append(quadro)
        prob = self._probabilidade(quadro)
        if prob >= self.lim.prob_inicio:
            self._voz += 1
            if self._primeiro_com_voz is None:
                self._primeiro_com_voz = indice
            self._ultimo_com_voz = indice
            self._silencio = 0
        elif prob >= self.lim.prob_fim and self._primeiro_com_voz is not None:
            self._ultimo_com_voz = indice  # fim de palavra, ainda fala
            self._silencio = 0
        else:
            self._silencio += 1

        if len(self._quadros) >= self._max_quadros:
            return LIMITE
        if not self.falou:
            if len(self._quadros) >= self._espera_quadros:
                return SEM_FALA
            return None
        if self.lim.parar_no_silencio and self._silencio >= self._fim_quadros:
            return SILENCIO
        return None

    def audio(self) -> Optional[Any]:
        """O trecho com fala (com margens), ou None se ninguém falou."""
        if not self.falou or self._primeiro_com_voz is None:
            return None
        import numpy as np

        inicio = max(
            0, self._primeiro_com_voz - round(self.lim.margem_inicio_s / FRAME_SECONDS)
        )
        ultimo = self._ultimo_com_voz if self._ultimo_com_voz is not None else inicio
        fim = min(
            len(self._quadros),
            ultimo + 1 + round(self.lim.margem_fim_s / FRAME_SECONDS),
        )
        return np.concatenate(self._quadros[inicio:fim]).astype("float32", copy=False)

    def descartar(self) -> None:
        """Solta o áudio da memória."""
        self._quadros = []


def gravar(
    fonte: Any,
    detector: DetectorFala,
    parar: Callable[[], bool],
    *,
    relogio: Callable[[], float] = time.monotonic,
) -> str:
    """Lê quadros de *fonte* (``read(timeout)``) até um motivo para parar.

    *parar* é consultado a cada quadro (atalho apertado de novo / tecla solta).
    Devolve o motivo; o áudio fica em ``detector.audio()``.
    """
    inicio = relogio()
    # Folga para o microfone que trava e não entrega quadro nenhum.
    prazo = detector.lim.max_s + 5.0
    while True:
        if parar():
            return PARADO
        quadro = fonte.read(0.1)
        if quadro is None:
            if relogio() - inicio > prazo:
                logger.warning("Ditado: o microfone parou de mandar áudio")
                return LIMITE
            continue
        motivo = detector.push(quadro)
        if motivo is not None:
            return motivo


__all__ = [
    "LIMITE",
    "PARADO",
    "SEM_FALA",
    "SILENCIO",
    "DetectorFala",
    "LimitesGravacao",
    "gravar",
]
