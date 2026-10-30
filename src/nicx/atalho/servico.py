"""Liga, desliga e reinicia o atalho global conforme ``[atalho]`` do config.

Uma instância por servidor (``app.state.atalho``). Nunca levanta exceção para
quem chama: qualquer problema vira um estado (``em_uso``, ``erro``...) que a
API mostra e o log registra em português.
"""

from __future__ import annotations

import logging
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from nicx.atalho.acao import ACOES, AcoesAtalho
from nicx.atalho.teclas import Combinacao, CombinacaoInvalida, ler_combinacao

logger = logging.getLogger(__name__)

DESLIGADO = "desligado"
REGISTRADO = "registrado"
EM_USO = "em_uso"
SEM_SUPORTE = "sem_suporte"
INVALIDO = "invalido"
ERRO = "erro"

# fabrica(combinacao, ao_apertar) -> objeto com iniciar() e parar()
FabricaEscuta = Callable[[Combinacao, Callable[[], None]], Any]


def _escuta_windows(combinacao: Combinacao, ao_apertar: Callable[[], None]) -> Any:
    from nicx.atalho.windows import HOTKEY_ID, EscutaAtalho, laco_compartilhado

    # Mesmo laço (thread) do atalho do ditado, com outro id.
    return EscutaAtalho(
        combinacao, ao_apertar, ident=HOTKEY_ID, laco=laco_compartilhado()
    )


def rotulo_de(teclas: str) -> str:
    try:
        return ler_combinacao(teclas).rotulo
    except CombinacaoInvalida:
        return str(teclas or "")


class GerenciadorAtalho:
    def __init__(
        self,
        acoes: Optional[Any] = None,
        *,
        plataforma: str = sys.platform,
        fabrica_escuta: FabricaEscuta = _escuta_windows,
    ) -> None:
        self._acoes = acoes if acoes is not None else AcoesAtalho()
        self._plataforma = plataforma
        self._fabrica = fabrica_escuta
        self._lock = threading.RLock()
        self._escuta: Any = None
        self._acao = "flutuante"
        self._teclas = ""
        self._estado = DESLIGADO
        self._mensagem = ""

    @property
    def suportado(self) -> bool:
        return self._plataforma == "win32"

    # -- ciclo de vida -----------------------------------------------------
    def aplicar(self, cfg: Any) -> dict:
        """Aplica ``[atalho]`` (*cfg* com ``ativo``, ``teclas``, ``acao``):
        para o registro anterior e, se ativo, registra de novo."""
        with self._lock:
            self._parar_escuta()
            ativo = bool(getattr(cfg, "ativo", False))
            self._teclas = str(getattr(cfg, "teclas", "") or "")
            acao = str(getattr(cfg, "acao", "flutuante") or "flutuante")
            self._acao = acao if acao in ACOES else "flutuante"
            if not ativo:
                return self._definir(DESLIGADO, "")
            if not self.suportado:
                logger.info(
                    "Atalho global de teclado: sem suporte neste sistema "
                    "(só no Windows); nada foi registrado."
                )
                return self._definir(
                    SEM_SUPORTE, "O atalho global só funciona no Windows."
                )
            try:
                combinacao = ler_combinacao(self._teclas)
            except CombinacaoInvalida as exc:
                logger.warning("Atalho de teclado desligado: %s", exc)
                return self._definir(INVALIDO, str(exc))
            self._teclas = combinacao.texto

            try:
                escuta = self._fabrica(combinacao, self._ao_apertar)
                resultado = escuta.iniciar()
            except Exception as exc:  # noqa: BLE001 - não derruba o servidor
                logger.exception("Falha ao registrar o atalho de teclado")
                return self._definir(ERRO, str(exc))

            if not resultado.ok:
                if resultado.em_uso:
                    logger.warning(
                        "O atalho %s já está em uso por outro programa; escolha "
                        "outra combinação nas Configurações do Nicx.",
                        combinacao.rotulo,
                    )
                    return self._definir(EM_USO, resultado.mensagem)
                logger.warning(
                    "Não foi possível registrar o atalho %s: %s",
                    combinacao.rotulo,
                    resultado.mensagem,
                )
                return self._definir(ERRO, resultado.mensagem)

            self._escuta = escuta
            logger.info(
                "Atalho de teclado %s ativo (ação: %s)", combinacao.rotulo, self._acao
            )
            return self._definir(REGISTRADO, "")

    def parar(self) -> None:
        with self._lock:
            self._parar_escuta()
            if self._estado == REGISTRADO:
                self._definir(DESLIGADO, "")

    def _parar_escuta(self) -> None:
        escuta, self._escuta = self._escuta, None
        if escuta is not None:
            try:
                escuta.parar()
            except Exception:  # noqa: BLE001
                logger.debug("Falha ao parar o atalho de teclado", exc_info=True)

    def _definir(self, estado: str, mensagem: str) -> dict:
        self._estado = estado
        self._mensagem = mensagem
        return self.status()

    def _ao_apertar(self) -> None:
        self._acoes.executar(self._acao)

    # -- leitura -----------------------------------------------------------
    def status(self) -> dict:
        return {
            "estado": self._estado,
            "mensagem": self._mensagem,
            "suportado": self.suportado,
        }


def salvar_secao(path: Path, nome: str, valores: dict[str, Any]) -> None:
    """Grava as chaves *valores* (as ``None`` ficam como estão) na seção
    ``[nome]`` do config.toml sem apagar o resto (escrita atômica)."""
    import tomlkit

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = (
        tomlkit.parse(path.read_text(encoding="utf-8"))
        if path.exists()
        else tomlkit.document()
    )
    if nome not in doc:
        doc.add(nome, tomlkit.table())
    secao = doc[nome]
    for chave, valor in valores.items():
        if valor is not None:
            secao[chave] = valor
    temporario: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as handle:
            temporario = Path(handle.name)
            handle.write(tomlkit.dumps(doc))
        temporario.replace(path)
        temporario = None
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)


def salvar_config(
    path: Path,
    *,
    ativo: Optional[bool] = None,
    teclas: Optional[str] = None,
    acao: Optional[str] = None,
) -> None:
    """Grava ``[atalho]`` no config.toml sem apagar o resto (escrita atômica)."""
    salvar_secao(
        path,
        "atalho",
        {
            "ativo": None if ativo is None else bool(ativo),
            "teclas": teclas,
            "acao": acao,
        },
    )


__all__ = [
    "DESLIGADO",
    "EM_USO",
    "ERRO",
    "INVALIDO",
    "REGISTRADO",
    "SEM_SUPORTE",
    "GerenciadorAtalho",
    "rotulo_de",
    "salvar_config",
    "salvar_secao",
]
