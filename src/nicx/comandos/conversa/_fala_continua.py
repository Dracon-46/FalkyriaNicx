"""Fala frase a frase no ``nicx chat --voice``.

Enquanto a resposta chega do modelo, cada frase pronta vai para uma fila:
uma thread sintetiza (uma por vez, até duas prontas à frente) e outra toca,
na ordem e sem sobreposição. Assim o Nicx começa a falar na primeira frase,
sem esperar o texto inteiro nem o áudio inteiro.
"""

from __future__ import annotations

import queue
import re
import threading
from typing import Any, Callable, Optional

# Frases curtas demais soam picotadas: juntam com a próxima.
MIN_CARACTERES = 20
# Sem pontuação por muito tempo: corta na última vírgula.
MAX_CARACTERES = 220

_ABREVIACOES = {
    "sr", "sra", "srta", "dr", "dra", "prof", "profa", "ex", "etc", "vs",
    "p.ex", "obs", "pág", "pag", "nº", "no", "av", "mr", "mrs", "ms", "st",
}  # fmt: skip

_FIM_FRASE = re.compile(r"[.!?…:]+[\"'”»)]*(?=\s)|\n+")
_BLOCO_CODIGO = re.compile(r"```.*?```", re.DOTALL)
_PENSANDO = re.compile(r"<think>.*?</think>", re.DOTALL)


def texto_falavel(texto: str) -> str:
    """Tira o que não se lê em voz alta: código, markdown, links."""
    texto = _BLOCO_CODIGO.sub(" ", texto)
    texto = re.sub(r"`([^`]*)`", r"\1", texto)
    texto = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", texto)
    texto = re.sub(r"^\s{0,3}(#{1,6}|[-*+]|\d+[.)])\s+", "", texto, flags=re.M)
    texto = re.sub(r"[*_~#>|]+", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


class DivisorFrases:
    """Recebe o texto em pedaços e devolve as frases que já fecharam."""

    def __init__(self) -> None:
        self._buffer = ""
        self._pendente = ""

    def adicionar(self, pedaco: str) -> list[str]:
        self._buffer += pedaco
        return self._extrair(final=False)

    def terminar(self) -> list[str]:
        frases = self._extrair(final=True)
        resto = texto_falavel(_PENSANDO.sub(" ", self._pendente + " " + self._buffer))
        self._buffer = self._pendente = ""
        if resto:
            frases.append(resto)
        return frases

    def _extrair(self, *, final: bool) -> list[str]:
        frases: list[str] = []
        while True:
            # Pensamento fechado some do texto; aberto, espera fechar.
            self._buffer = _PENSANDO.sub(" ", self._buffer)
            texto = self._buffer
            if "<think>" in texto and not final:
                texto = texto[: texto.index("<think>")]
            # Bloco de código ainda aberto: espera fechar.
            if texto.count("```") % 2 == 1 and not final:
                break
            corte = self._achar_corte(texto)
            if corte is None:
                break
            frase, self._buffer = texto[:corte], texto[corte:].lstrip()
            frase = self._pendente + " " + frase if self._pendente else frase
            limpa = texto_falavel(_PENSANDO.sub(" ", frase))
            if len(limpa) < MIN_CARACTERES:
                self._pendente = frase
                continue
            self._pendente = ""
            frases.append(limpa)
        return frases

    def _achar_corte(self, texto: str) -> Optional[int]:
        sem_codigo = _BLOCO_CODIGO.sub(lambda m: " " * len(m.group()), texto)
        for m in _FIM_FRASE.finditer(sem_codigo):
            antes = sem_codigo[: m.start()].rsplit(None, 1)
            palavra = antes[-1].lower().rstrip(".") if antes else ""
            if m.group().startswith(".") and (
                palavra in _ABREVIACOES or len(palavra) == 1
            ):
                continue  # "Sr. João", "J. Silva"
            return m.end()
        if len(texto) > MAX_CARACTERES:
            virgula = texto.rfind(", ", 0, MAX_CARACTERES)
            if virgula > MIN_CARACTERES:
                return virgula + 1
        return None


_FIM = object()


class FalaContinua:
    """Fila de fala: sintetiza e toca as frases na ordem, sem sobrepor."""

    def __init__(
        self,
        sintetizar: Callable[[str], Optional[tuple[bytes, int]]],
        tocar: Callable[[bytes, int], None],
        *,
        a_frente: int = 2,
    ) -> None:
        self._sintetizar = sintetizar
        self._tocar = tocar
        self._frases: queue.Queue[Any] = queue.Queue()
        self._audios: queue.Queue[Any] = queue.Queue(maxsize=a_frente)
        self._cancelado = threading.Event()
        self._divisor = DivisorFrases()
        self.erro: Optional[BaseException] = None
        self._threads = [
            threading.Thread(target=self._sintetizador, daemon=True),
            threading.Thread(target=self._tocador, daemon=True),
        ]
        for t in self._threads:
            t.start()

    def adicionar(self, pedaco: str) -> None:
        for frase in self._divisor.adicionar(pedaco):
            self._frases.put(frase)

    def terminar(self, timeout: Optional[float] = None) -> None:
        """Fala o que sobrou e espera a última frase acabar."""
        for frase in self._divisor.terminar():
            self._frases.put(frase)
        self._frases.put(_FIM)
        for t in self._threads:
            t.join(timeout)

    def cancelar(self) -> None:
        self._cancelado.set()
        self._frases.put(_FIM)

    def _sintetizador(self) -> None:
        try:
            while not self._cancelado.is_set():
                frase = self._frases.get()
                if frase is _FIM:
                    break
                audio = self._sintetizar(frase)
                if audio:
                    self._entregar(audio)
        except BaseException as exc:  # noqa: BLE001 - relatado pelo chamador
            self.erro = exc
            self._cancelado.set()
        finally:
            self._entregar(_FIM)

    def _entregar(self, item: Any) -> None:
        # Fila cheia e fala cancelada: desiste em vez de travar a thread.
        while True:
            try:
                self._audios.put(item, timeout=0.2)
                return
            except queue.Full:
                if self._cancelado.is_set():
                    return

    def _tocador(self) -> None:
        while True:
            try:
                item = self._audios.get(timeout=0.2)
            except queue.Empty:
                if self._cancelado.is_set():
                    break
                continue
            if item is _FIM or self._cancelado.is_set():
                break
            audio, taxa = item
            self._tocar(audio, taxa)


__all__ = ["DivisorFrases", "FalaContinua", "texto_falavel"]
