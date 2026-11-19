"""Volume do Windows pelo Core Audio (IAudioEndpointVolume), sem bibliotecas.

As teclas de volume (o jeito antigo) mudam ~2% por toque e não dizem em quanto
ficou: "põe em 80" precisava zerar e subir, e "aumenta" não sabia o nível. Aqui
o Nicx lê e define o nível exato do alto-falante padrão. Se algo falhar (sem
dispositivo de áudio, COM indisponível), quem chama volta para as teclas.
"""

from __future__ import annotations

import ctypes
import sys
import uuid
from ctypes import (
    POINTER,
    byref,
    c_float,
    c_int,
    c_ubyte,
    c_uint,
    c_ulong,
    c_ushort,
    c_void_p,
)
from typing import Optional


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", c_ulong),
        ("Data2", c_ushort),
        ("Data3", c_ushort),
        ("Data4", c_ubyte * 8),
    ]

    @classmethod
    def de(cls, texto: str) -> "_GUID":
        u = uuid.UUID(texto)
        return cls(
            u.time_low, u.time_mid, u.time_hi_version, (c_ubyte * 8)(*u.bytes[8:])
        )


_CLSID_ENUMERADOR = _GUID.de("BCDE0395-E52F-467C-8E3D-C4579291692E")
_IID_ENUMERADOR = _GUID.de("A95664D2-9614-4F35-A746-DE8DB63617E6")
_IID_VOLUME = _GUID.de("5CDF2C82-841E-4546-9722-0CF74078229A")
_CLSCTX_ALL = 23
_E_RENDER, _E_MULTIMIDIA = 0, 1


def _metodo(ponteiro: c_void_p, indice: int, *tipos):
    """Função da vtable COM de *ponteiro* (HRESULT: erro vira OSError)."""
    tabela = ctypes.cast(ponteiro, POINTER(POINTER(c_void_p))).contents
    prototipo = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *tipos)
    return lambda *args: prototipo(tabela[indice])(ponteiro, *args)


class _Volume:
    """Abre o controle de volume do alto-falante padrão (use com ``with``)."""

    def __enter__(self) -> "_Volume":
        ole32 = ctypes.OleDLL("ole32")
        self._ole32 = ole32
        self._iniciou = ole32.CoInitializeEx(None, 0x2) in (0, 1)  # apartment
        self._enumerador = c_void_p()
        self._dispositivo = c_void_p()
        self._volume = c_void_p()
        ole32.CoCreateInstance(
            byref(_CLSID_ENUMERADOR),
            None,
            _CLSCTX_ALL,
            byref(_IID_ENUMERADOR),
            byref(self._enumerador),
        )
        _metodo(self._enumerador, 4, c_int, c_int, POINTER(c_void_p))(
            _E_RENDER, _E_MULTIMIDIA, byref(self._dispositivo)
        )
        _metodo(
            self._dispositivo, 3, POINTER(_GUID), c_uint, c_void_p, POINTER(c_void_p)
        )(byref(_IID_VOLUME), _CLSCTX_ALL, None, byref(self._volume))
        return self

    def nivel(self) -> int:
        valor = c_float()
        _metodo(self._volume, 9, POINTER(c_float))(byref(valor))
        return round(valor.value * 100)

    def definir(self, nivel: int) -> int:
        nivel = max(0, min(100, int(nivel)))
        _metodo(self._volume, 7, c_float, c_void_p)(c_float(nivel / 100), None)
        if nivel > 0 and self.mudo():
            self.mudar(False)  # pedir volume é querer ouvir
        return self.nivel()

    def mudo(self) -> bool:
        valor = c_int()
        _metodo(self._volume, 15, POINTER(c_int))(byref(valor))
        return bool(valor.value)

    def mudar(self, mudo: bool) -> None:
        _metodo(self._volume, 14, c_int, c_void_p)(int(mudo), None)

    def __exit__(self, *_exc) -> None:
        for p in (self._volume, self._dispositivo, self._enumerador):
            if p:
                _metodo(p, 2)()  # Release
        if self._iniciou:
            self._ole32.CoUninitialize()


def nivel() -> Optional[int]:
    """O volume atual (0-100), ou ``None`` se não deu para ler."""
    if sys.platform != "win32":
        return None
    try:
        with _Volume() as v:
            return v.nivel()
    except OSError:
        return None


def definir(nivel: int) -> Optional[int]:
    """Põe o volume em *nivel* e devolve em quanto ficou (``None`` = falhou)."""
    if sys.platform != "win32":
        return None
    try:
        with _Volume() as v:
            return v.definir(nivel)
    except OSError:
        return None


def alternar_mudo() -> Optional[bool]:
    """Liga/desliga o mudo; devolve se ficou mudo (``None`` = falhou)."""
    if sys.platform != "win32":
        return None
    try:
        with _Volume() as v:
            novo = not v.mudo()
            v.mudar(novo)
            return novo
    except OSError:
        return None


__all__ = ["alternar_mudo", "definir", "nivel"]
