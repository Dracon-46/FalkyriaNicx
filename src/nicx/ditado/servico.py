"""Liga/desliga o ditado conforme ``[ditado]`` e conduz cada ditado.

Uma instância por servidor (``app.state.ditado``). O atalho do ditado é
registrado no mesmo laço (thread) do atalho do Nicx, com outro id. Fluxo de
um ditado:

1. atalho apertado: guarda a janela em foco, toca um bipe (opcional) e abre o
   microfone; o estado vira ``ouvindo`` (a janela flutuante, se aberta, mostra);
2. para no segundo toque (modo "alternar"), após ~1,5 s de silêncio ou 60 s;
   no modo "segurar", quando a tecla é solta;
3. ``transcrevendo``: o Whisper local transcreve direto da memória;
4. aplica os comandos de voz simples e digita na janela guardada.

Privacidade: o áudio só existe na memória e é solto logo depois da
transcrição; o texto não vai para a memória do Nicx nem para os logs (só o
tamanho). Nunca levanta exceção para quem chama: problemas viram estado.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from dataclasses import replace
from typing import Any, Callable, Optional

from nicx.atalho.teclas import Combinacao, CombinacaoInvalida, ler_combinacao
from nicx.ditado.comandos import preparar_texto
from nicx.ditado.gravacao import DetectorFala, LimitesGravacao, gravar
from nicx.nucleo.idiomas import PADRAO, idioma

logger = logging.getLogger(__name__)

DESLIGADO = "desligado"
PRONTO = "pronto"
OUVINDO = "ouvindo"
TRANSCREVENDO = "transcrevendo"
EM_USO = "em_uso"
SEM_SUPORTE = "sem_suporte"
INVALIDO = "invalido"
ERRO = "erro"

ALTERNAR = "alternar"
SEGURAR = "segurar"
MODOS = (ALTERNAR, SEGURAR)

# A escuta "Nicx, ligar" fica quieta enquanto o ditado ouve (renovado).
_AVISO_OCUPADO_S = 4.0

FabricaEscuta = Callable[[Combinacao, Callable[[], None]], Any]


class TeclasEmConflito(CombinacaoInvalida):
    """A combinação do ditado é a mesma do atalho do Nicx."""


def _normal(teclas: str) -> str:
    try:
        return ler_combinacao(teclas).texto
    except CombinacaoInvalida:
        return str(teclas or "").strip().lower()


def validar_teclas(teclas: str, teclas_atalho: str = "") -> Combinacao:
    """Mesmas regras do atalho do Nicx e diferente dele."""
    combinacao = ler_combinacao(teclas)
    if teclas_atalho and combinacao.texto == _normal(teclas_atalho):
        raise TeclasEmConflito(
            f"{combinacao.rotulo} já é o atalho que chama o Nicx; escolha outra."
        )
    return combinacao


def idiomas_do_ditado(cfg: Any) -> tuple[str, Optional[str]]:
    """(código para os comandos, código do Whisper; None = detectar)."""
    escolhido = str(getattr(getattr(cfg, "ditado", None), "idioma", "") or "").strip()
    if escolhido:
        alvo = idioma(escolhido)
        return alvo.codigo, alvo.whisper
    fala = str(getattr(getattr(cfg, "speech", None), "language", "") or "").strip()
    if fala:
        return idioma(fala).codigo, fala.split("-")[0].lower()
    return PADRAO, None


# ---------------------------------------------------------------------------
# Peças de verdade (trocadas nos testes)
# ---------------------------------------------------------------------------


def _escuta_windows(combinacao: Combinacao, ao_apertar: Callable[[], None]) -> Any:
    from nicx.atalho.windows import HOTKEY_ID_DITADO, EscutaAtalho, laco_compartilhado

    return EscutaAtalho(
        combinacao, ao_apertar, ident=HOTKEY_ID_DITADO, laco=laco_compartilhado()
    )


def _microfone() -> Any:
    from nicx.voz.escuta.detector import MicrophoneSource

    return MicrophoneSource()


def _vad() -> tuple[Callable[[Any], float], Optional[Callable[[], None]]]:
    from nicx.voz.escuta.detector import StreamingSileroVad

    vad = StreamingSileroVad()
    return vad, vad.reset


def _bipe(tipo: str) -> None:
    try:
        import winsound

        # Curto e baixo: subindo ao começar, descendo ao terminar.
        winsound.Beep(1046 if tipo == "inicio" else 784, 60)
    except Exception:  # noqa: BLE001 - sem placa de som, sem bipe
        logger.debug("Ditado: bipe indisponível", exc_info=True)


def _tecla_apertada(vk: int) -> bool:
    from nicx.ditado.digitar import tecla_apertada

    return tecla_apertada(vk)


class TranscritorLocal:
    """Whisper local direto de um array: usa o modelo do servidor (o mesmo da
    conversa por voz, sem carregar outro) ou um próprio, de ``[speech]``."""

    def __init__(
        self,
        obter_config: Callable[[], Any],
        obter_backend: Callable[[], Any] = lambda: None,
    ) -> None:
        self._obter_config = obter_config
        self._obter_backend = obter_backend
        self._proprio: Any = None
        self._lock = threading.Lock()

    def _backend(self) -> Any:
        backend = self._obter_backend()
        if backend is not None and hasattr(backend, "transcrever_array"):
            return backend
        with self._lock:
            if self._proprio is None:
                from nicx.voz.faster_whisper import FasterWhisperBackend

                fala = self._obter_config().speech
                self._proprio = FasterWhisperBackend(
                    model_size=fala.model,
                    device=fala.device,
                    compute_type=fala.compute_type,
                    vad_filter=getattr(fala, "vad_filter", False),
                    hotwords=getattr(fala, "hotwords", ""),
                )
            return self._proprio

    def __call__(self, audio: Any, language: Optional[str]) -> str:
        return self._backend().transcrever_array(audio, language=language)


# ---------------------------------------------------------------------------
# Serviço
# ---------------------------------------------------------------------------


class ServicoDitado:
    def __init__(
        self,
        obter_config: Callable[[], Any],
        *,
        plataforma: str = sys.platform,
        fabrica_escuta: FabricaEscuta = _escuta_windows,
        fabrica_fonte: Callable[[], Any] = _microfone,
        fabrica_vad: Callable[[], tuple[Callable[[Any], float], Any]] = _vad,
        transcrever: Optional[Callable[[Any, Optional[str]], str]] = None,
        digitador: Any = None,
        som: Callable[[str], None] = _bipe,
        avisar_ocupado: Optional[Callable[[bool], None]] = None,
        tecla_apertada: Callable[[int], bool] = _tecla_apertada,
        limites: Optional[LimitesGravacao] = None,
    ) -> None:
        self._obter_config = obter_config
        self._plataforma = plataforma
        self._fabrica = fabrica_escuta
        self._fabrica_fonte = fabrica_fonte
        self._fabrica_vad = fabrica_vad
        self._transcrever = transcrever or TranscritorLocal(obter_config)
        self._digitador = digitador
        self._som = som
        self._avisar_ocupado = avisar_ocupado or (lambda _ocupado: None)
        self._tecla_apertada = tecla_apertada
        self._limites = limites
        self._lock = threading.RLock()
        self._escuta: Any = None
        self._combinacao: Optional[Combinacao] = None
        self._estado = DESLIGADO
        self._mensagem = ""
        self._em_sessao = False
        self._parar_evt = threading.Event()

    @property
    def suportado(self) -> bool:
        return self._plataforma == "win32"

    @property
    def estado(self) -> str:
        return self._estado

    # -- ciclo de vida -----------------------------------------------------
    def aplicar(self) -> dict:
        """Lê ``[ditado]`` do config e (re)registra o atalho se ativo."""
        with self._lock:
            self._parar_escuta()
            self._combinacao = None
            cfg = self._obter_config()
            dit = getattr(cfg, "ditado", None)
            if dit is None or not bool(getattr(dit, "ativo", False)):
                return self._definir(DESLIGADO, "")
            if not self.suportado:
                logger.info(
                    "Ditado: sem suporte neste sistema (só no Windows); nada foi "
                    "registrado."
                )
                return self._definir(SEM_SUPORTE, "O ditado só funciona no Windows.")
            modo = str(getattr(dit, "modo", ALTERNAR) or ALTERNAR)
            if modo not in MODOS:
                logger.warning("Ditado desligado: modo desconhecido %r", modo)
                return self._definir(
                    INVALIDO, "Modo desconhecido: use 'alternar' ou 'segurar'."
                )
            atalho = getattr(cfg, "atalho", None)
            try:
                combinacao = validar_teclas(
                    str(getattr(dit, "teclas", "") or ""),
                    str(getattr(atalho, "teclas", "") or ""),
                )
            except CombinacaoInvalida as exc:
                logger.warning("Ditado desligado: %s", exc)
                return self._definir(INVALIDO, str(exc))

            try:
                escuta = self._fabrica(combinacao, self._ao_apertar)
                resultado = escuta.iniciar()
            except Exception as exc:  # noqa: BLE001 - não derruba o servidor
                logger.exception("Falha ao registrar o atalho do ditado")
                return self._definir(ERRO, str(exc))
            if not resultado.ok:
                if resultado.em_uso:
                    logger.warning(
                        "O atalho do ditado %s já está em uso por outro programa; "
                        "escolha outra combinação nas Configurações do Nicx.",
                        combinacao.rotulo,
                    )
                    return self._definir(EM_USO, resultado.mensagem)
                logger.warning(
                    "Não foi possível registrar o atalho do ditado %s: %s",
                    combinacao.rotulo,
                    resultado.mensagem,
                )
                return self._definir(ERRO, resultado.mensagem)

            self._escuta = escuta
            self._combinacao = combinacao
            logger.info("Ditado ativo no atalho %s (modo %s)", combinacao.rotulo, modo)
            if self._em_sessao:
                return self.status()
            return self._definir(PRONTO, "")

    def parar(self) -> None:
        with self._lock:
            self._parar_evt.set()
            self._parar_escuta()
            self._combinacao = None
            if not self._em_sessao:
                self._definir(DESLIGADO, "")

    def _parar_escuta(self) -> None:
        escuta, self._escuta = self._escuta, None
        if escuta is not None:
            try:
                escuta.parar()
            except Exception:  # noqa: BLE001
                logger.debug("Falha ao parar o atalho do ditado", exc_info=True)

    def _definir(self, estado: str, mensagem: str) -> dict:
        self._estado = estado
        self._mensagem = mensagem
        return self.status()

    def status(self) -> dict:
        return {
            "estado": self._estado,
            "mensagem": self._mensagem,
            "suportado": self.suportado,
        }

    # -- um ditado -----------------------------------------------------------
    def _digitador_atual(self) -> Any:
        if self._digitador is None:
            from nicx.ditado.digitar import DigitadorWindows

            self._digitador = DigitadorWindows()
        return self._digitador

    def _ao_apertar(self) -> None:
        """Chamado numa thread própria a cada toque no atalho."""
        with self._lock:
            if self._em_sessao:
                if self._estado == OUVINDO:
                    self._parar_evt.set()  # segundo toque: para de ouvir
                return
            if self._combinacao is None:
                return
            combinacao = self._combinacao
            # A janela onde o texto vai entrar: a da frente agora, antes de
            # qualquer coisa nossa aparecer.
            hwnd = self._digitador_atual().janela_em_foco()
            self._parar_evt = threading.Event()
            self._em_sessao = True
            self._definir(OUVINDO, "")
        try:
            self._sessao(hwnd, combinacao, self._parar_evt)
        finally:
            with self._lock:
                self._em_sessao = False
                if self._estado in (OUVINDO, TRANSCREVENDO):
                    self._definir(PRONTO if self._combinacao else DESLIGADO, "")

    def _sessao(
        self, hwnd: int, combinacao: Combinacao, parar_evt: threading.Event
    ) -> None:
        cfg = self._obter_config()
        dit = getattr(cfg, "ditado", None)
        modo = str(getattr(dit, "modo", ALTERNAR) or ALTERNAR)
        com_som = bool(getattr(dit, "som", True))
        codigo, lingua_whisper = idiomas_do_ditado(cfg)

        limites = self._limites or LimitesGravacao()
        if modo == SEGURAR:
            limites = replace(limites, parar_no_silencio=False)

        ultimo_aviso = [0.0]

        def avisar() -> None:
            agora = time.monotonic()
            if agora - ultimo_aviso[0] >= _AVISO_OCUPADO_S:
                ultimo_aviso[0] = agora
                try:
                    self._avisar_ocupado(True)
                except Exception:  # noqa: BLE001
                    logger.debug("Ditado: aviso de ocupado falhou", exc_info=True)

        def parar() -> bool:
            avisar()
            if parar_evt.is_set():
                return True
            return modo == SEGURAR and not self._tecla_apertada(
                combinacao.codigo_virtual
            )

        detector: Optional[DetectorFala] = None
        try:
            avisar()
            if com_som:
                self._som("inicio")
            vad, vad_reset = self._fabrica_vad()
            detector = DetectorFala(vad, limites, vad_reset=vad_reset)
            fonte = self._fabrica_fonte()
            fonte.start()
            try:
                motivo = gravar(fonte, detector, parar)
            finally:
                fonte.stop()
            if com_som:
                self._som("fim")
            audio = detector.audio()
            detector.descartar()
            if audio is None:
                logger.info("Ditado: nenhuma fala ouvida (%s); nada digitado", motivo)
                return
            segundos = len(audio) / 16000
            with self._lock:
                self._definir(TRANSCREVENDO, "")
            inicio = time.monotonic()
            bruto = self._transcrever(audio, lingua_whisper)
            del audio
            texto = preparar_texto(bruto, codigo)
            if not texto:
                logger.info("Ditado: %.1f s sem texto útil; nada digitado", segundos)
                return
            ok = self._digitador_atual().digitar(texto, hwnd)
            if not ok:
                with self._lock:
                    self._definir(
                        ERRO,
                        "Não foi possível digitar na janela de origem (ela fechou, "
                        "mudou ou é de administrador).",
                    )
                return
            logger.info(
                "Ditado: %d caracteres digitados (%.1f s de fala, %.1f s até digitar)",
                len(texto),
                segundos,
                time.monotonic() - inicio,
            )
        except Exception as exc:  # noqa: BLE001 - nunca derruba o servidor
            # Só o tipo do erro: a mensagem de alguns erros poderia trazer texto.
            logger.exception("Ditado: falha (%s)", type(exc).__name__)
            with self._lock:
                self._definir(ERRO, "O ditado falhou; veja o log do Nicx.")
        finally:
            if detector is not None:
                detector.descartar()
            try:
                self._avisar_ocupado(False)
            except Exception:  # noqa: BLE001
                pass


__all__ = [
    "ALTERNAR",
    "DESLIGADO",
    "EM_USO",
    "ERRO",
    "INVALIDO",
    "MODOS",
    "OUVINDO",
    "PRONTO",
    "SEGURAR",
    "SEM_SUPORTE",
    "TRANSCREVENDO",
    "ServicoDitado",
    "TeclasEmConflito",
    "TranscritorLocal",
    "idiomas_do_ditado",
    "validar_teclas",
]
