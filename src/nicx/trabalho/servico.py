"""O modo Trabalho em segundo plano: uma tarefa por vez.

Uma tarefa por vez porque o modelo roda na CPU: duas ao mesmo tempo só
deixariam as duas lentas. Ao terminar, avisa com uma notificação do Windows.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from nicx.nucleo import cancelamento
from nicx.trabalho import executor, ferramentas, modelo
from nicx.trabalho.modelo import Tarefa
from nicx.trabalho.pasta import validar_pasta

logger = logging.getLogger(__name__)

MAX_PEDIDO = 2000
ESPERA_CONFIRMACAO_S = 30 * 60


class TrabalhoErro(RuntimeError):
    """Algo que impede a ação agora; a mensagem diz por quê."""


class _Rodando:
    def __init__(self, tarefa: Tarefa) -> None:
        self.tarefa = tarefa
        self.parar = cancelamento.Cancelamento()
        self.pausa = executor.Pausa()
        self.resposta = threading.Event()
        self.confirmado = False
        self.thread: Optional[threading.Thread] = None


_LOCK = threading.RLock()
_ATUAL: Optional[_Rodando] = None


def _em_curso() -> Optional[_Rodando]:
    with _LOCK:
        if _ATUAL and _ATUAL.thread and _ATUAL.thread.is_alive():
            return _ATUAL
        return None


def _ocupado() -> bool:
    """Há tarefa trabalhando? Uma que só está terminando é esperada."""
    r = _em_curso()
    if r and r.tarefa.estado not in modelo.ATIVOS and r.thread:
        r.thread.join(timeout=10)
        r = _em_curso()
    return r is not None


def _confirmar_com(r: _Rodando):
    def confirmar(texto: str) -> bool:
        r.resposta.clear()
        r.confirmado = False
        anterior = r.tarefa.estado
        r.tarefa.pergunta = {"texto": texto}
        r.tarefa.estado = modelo.AGUARDANDO_CONFIRMACAO
        r.tarefa.anotar("pergunta", texto)
        modelo.salvar(r.tarefa)
        _avisar(f"O Nicx precisa da sua confirmação: {texto}")
        respondeu = False
        for _ in range(ESPERA_CONFIRMACAO_S * 2):
            if r.resposta.wait(0.5) or r.parar.cancelado:
                respondeu = r.resposta.is_set()
                break
        r.tarefa.pergunta = None
        r.tarefa.estado = anterior
        r.tarefa.anotar(
            "resposta", "confirmado" if respondeu and r.confirmado else "não confirmado"
        )
        modelo.salvar(r.tarefa)
        cancelamento.verificar()
        return respondeu and r.confirmado

    return confirmar


def _avisar(texto: str) -> None:
    try:
        from nicx.acoes.lembretes import show_notification

        show_notification(texto)
    except Exception:  # noqa: BLE001
        logger.debug("Aviso do modo Trabalho não mostrado", exc_info=True)


def _iniciar(r: _Rodando, engine: Any, modelo_nome: str, *, so_planejar: bool) -> None:
    global _ATUAL

    def trabalho() -> None:
        executor.rodar(
            r.tarefa,
            engine,
            modelo_nome,
            r.parar,
            r.pausa,
            _confirmar_com(r),
            so_planejar=so_planejar,
        )
        if not so_planejar and r.tarefa.estado == modelo.CONCLUIDA:
            _avisar(
                "O Nicx terminou a tarefa na pasta. Veja o resumo na página Trabalho."
            )
            _anotar_historico(r.tarefa)

    with _LOCK:
        _ATUAL = r
        r.thread = threading.Thread(
            target=trabalho, name=f"nicx-trabalho-{r.tarefa.id}", daemon=True
        )
        r.thread.start()


def _anotar_historico(tarefa: Tarefa) -> None:
    try:
        from nicx.historico.registro import anotar

        anotar(
            "organizacao",
            f"Trabalho na pasta: {tarefa.pedido[:120]}",
            detalhe={"tarefa": tarefa.id, "arquivos": tarefa.arquivos_mudados()[:50]},
        )
    except Exception:  # noqa: BLE001
        logger.debug("Histórico do modo Trabalho não gravado", exc_info=True)


# ------------------------------------------------------------------ ações


def criar(pasta: str, pedido: str, engine: Any, modelo_nome: str) -> dict:
    """Valida a pasta e começa o plano (a execução espera a aprovação)."""
    if _ocupado():
        raise TrabalhoErro("já há uma tarefa em andamento: espere ou pare a atual")
    pedido = " ".join((pedido or "").split())
    if len(pedido) < 5:
        raise TrabalhoErro("descreva a tarefa")
    if len(pedido) > MAX_PEDIDO:
        raise TrabalhoErro(f"descreva a tarefa em até {MAX_PEDIDO} caracteres")
    if engine is None or not modelo_nome:
        raise TrabalhoErro("o motor do Nicx não está pronto")
    raiz = validar_pasta(pasta)
    tarefa = Tarefa(id=modelo.novo_id(), pasta=str(raiz), pedido=pedido)
    modelo.salvar(tarefa)
    _iniciar(_Rodando(tarefa), engine, modelo_nome, so_planejar=True)
    return tarefa.para_dict()


def _carregar(tarefa_id: str) -> Tarefa:
    r = _em_curso()
    if r and r.tarefa.id == tarefa_id:
        return r.tarefa
    tarefa = modelo.carregar(tarefa_id)
    if tarefa is None:
        raise TrabalhoErro("tarefa não encontrada")
    return tarefa


def ver(tarefa_id: str) -> dict:
    return _carregar(tarefa_id).para_dict()


def listar() -> list[dict]:
    r = _em_curso()
    lista = []
    for t in modelo.listar():
        if r and r.tarefa.id == t.id:
            t = r.tarefa
        elif t.estado in modelo.ATIVOS:
            t.estado = modelo.INTERROMPIDA  # o Nicx fechou no meio
        d = t.para_dict()
        d.pop("registro", None)
        d.pop("diario", None)
        lista.append(d)
    return lista


def aprovar(
    tarefa_id: str, passos: Optional[list[str]], engine: Any, modelo_nome: str
) -> dict:
    """Começa (ou retoma) a execução, com o plano que a pessoa aprovou."""
    if _ocupado():
        raise TrabalhoErro("já há uma tarefa em andamento")
    tarefa = _carregar(tarefa_id)
    if tarefa.estado not in (
        modelo.AGUARDANDO_APROVACAO,
        modelo.PARADA,
        modelo.INTERROMPIDA,
        modelo.ERRO,
    ):
        raise TrabalhoErro("esta tarefa não está esperando aprovação")
    validar_pasta(tarefa.pasta)  # a pasta ainda existe e continua permitida
    if passos is not None and tarefa.estado == modelo.AGUARDANDO_APROVACAO:
        limpos = [" ".join(p.split())[:300] for p in passos if p and p.strip()][
            : executor.MAX_PASSOS
        ]
        if not limpos:
            raise TrabalhoErro("o plano ficou vazio")
        tarefa.plano = [modelo.Passo(descricao=p) for p in limpos]
    tarefa.erro = ""
    tarefa.estado = modelo.EXECUTANDO
    modelo.salvar(tarefa)
    _iniciar(_Rodando(tarefa), engine, modelo_nome, so_planejar=False)
    return tarefa.para_dict()


def pausar(tarefa_id: str) -> dict:
    r = _em_curso()
    if not r or r.tarefa.id != tarefa_id:
        raise TrabalhoErro("esta tarefa não está rodando")
    r.pausa.pausar()
    r.tarefa.estado = modelo.PAUSADA
    r.tarefa.anotar("info", "pausada")
    modelo.salvar(r.tarefa)
    return r.tarefa.para_dict()


def continuar(tarefa_id: str) -> dict:
    r = _em_curso()
    if not r or r.tarefa.id != tarefa_id:
        raise TrabalhoErro("esta tarefa não está rodando")
    r.pausa.continuar()
    r.tarefa.estado = modelo.EXECUTANDO
    r.tarefa.anotar("info", "continuando")
    modelo.salvar(r.tarefa)
    return r.tarefa.para_dict()


def parar(tarefa_id: str) -> dict:
    r = _em_curso()
    if not r or r.tarefa.id != tarefa_id:
        tarefa = _carregar(tarefa_id)
        if tarefa.estado == modelo.AGUARDANDO_APROVACAO:
            tarefa.estado = modelo.PARADA
            modelo.salvar(tarefa)
        return tarefa.para_dict()
    r.parar.cancelar()
    r.pausa.continuar()
    r.resposta.set()
    if r.thread:
        r.thread.join(timeout=10)
    return r.tarefa.para_dict()


def responder(tarefa_id: str, confirmado: bool) -> dict:
    r = _em_curso()
    if not r or r.tarefa.id != tarefa_id or not r.tarefa.pergunta:
        raise TrabalhoErro("não há pergunta esperando resposta")
    r.confirmado = bool(confirmado)
    r.resposta.set()
    return r.tarefa.para_dict()


def desfazer(tarefa_id: str) -> dict:
    """Volta a pasta para como estava antes da tarefa."""
    if (r := _em_curso()) and r.tarefa.id == tarefa_id:
        if r.tarefa.estado in modelo.ATIVOS:
            raise TrabalhoErro("pare a tarefa antes de desfazer")
        if r.thread:  # terminou e só falta avisar/gravar o histórico
            r.thread.join(timeout=10)
    tarefa = _carregar(tarefa_id)
    if not tarefa.diario:
        raise TrabalhoErro("esta tarefa não mudou nada na pasta")
    problemas = ferramentas.desfazer(tarefa)
    tarefa.estado = modelo.DESFEITA
    tarefa.anotar(
        "info",
        "desfeita" + (f" (com problemas: {'; '.join(problemas)})" if problemas else ""),
    )
    tarefa.diario = []
    modelo.salvar(tarefa)
    d = tarefa.para_dict()
    d["problemas"] = problemas
    return d


__all__ = [
    "TrabalhoErro",
    "aprovar",
    "continuar",
    "criar",
    "desfazer",
    "listar",
    "parar",
    "pausar",
    "responder",
    "ver",
]
