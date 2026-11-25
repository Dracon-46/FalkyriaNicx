"""Planejar e executar uma tarefa do modo Trabalho com o modelo local.

1. **Plano**: o modelo vê a tarefa e o que há na pasta e devolve até
   :data:`MAX_PASSOS` passos curtos (JSON). A pessoa aprova antes de qualquer
   mudança.
2. **Execução**: um passo por vez. Para cada passo o modelo recebe a tarefa, o
   plano, o que já foi feito e as ferramentas; chama ferramentas até terminar
   e responde em uma ou duas frases o que fez. Entre uma chamada e outra o
   executor confere Parar (:mod:`nicx.nucleo.cancelamento`, que também corta
   a geração do Ollama) e Pausar.
3. **Resumo**: o que foi feito, montado dos resultados dos passos.

Um modelo de 4B erra: por isso o plano é curto, cada passo tem limite de
chamadas e um passo que falha não derruba os outros.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import Any, Callable, Optional

from nicx.nucleo import cancelamento
from nicx.nucleo.types import Message, Role, ToolCall
from nicx.trabalho import modelo
from nicx.trabalho.ferramentas import DEFINICOES, Ferramentas
from nicx.trabalho.modelo import Passo, Tarefa

logger = logging.getLogger(__name__)

MAX_PASSOS = 7
MAX_CHAMADAS_POR_PASSO = 8
MAX_RESULTADO = 4000
#: Até quanto (em caracteres) os passos continuam a mesma conversa. Continuar
#: deixa o Ollama reaproveitar o prompt já lido (~1,5 s em vez de ~40 s por
#: passo neste PC, medido no 0.40.18) e o modelo ainda vê o que leu antes;
#: passou disso, o passo recomeça com o plano e o resumo, para caber em 8k tokens.
LIMITE_CONVERSA = 14000

SISTEMA = (
    "Você é o Nicx, a IA da Falkyria, fazendo uma tarefa numa pasta do computador da "
    "pessoa. "
    "Use só as ferramentas; os caminhos são relativos à pasta de trabalho. "
    "Antes de mexer em um arquivo, liste a pasta ou leia o arquivo: nunca invente o "
    "conteúdo. "
    "Faça só o passo pedido. Quando o passo terminar, responda sem ferramenta, em uma "
    "ou duas "
    "frases, o que você fez. Não apague nada que a tarefa não peça."
)


class Pausa:
    """Pausar e continuar entre uma chamada e outra (conferido pelo executor)."""

    def __init__(self) -> None:
        self._livre = threading.Event()
        self._livre.set()

    def pausar(self) -> None:
        self._livre.clear()

    def continuar(self) -> None:
        self._livre.set()

    @property
    def pausada(self) -> bool:
        return not self._livre.is_set()

    def esperar(self, parar: cancelamento.Cancelamento) -> None:
        while not self._livre.wait(0.5):
            if parar.cancelado:
                return


def _gerar(engine: Any, modelo_nome: str, mensagens: list[Message], **kw: Any) -> dict:
    return engine.generate(
        mensagens, model=modelo_nome, temperature=0.2, max_tokens=1500, **kw
    )


def _resumo_da_pasta(ferramentas: Ferramentas) -> str:
    ok, texto = ferramentas.executar("listar_arquivos", {"caminho": "."})
    linhas = texto.splitlines()
    if len(linhas) > 60:
        texto = "\n".join(linhas[:60]) + f"\n… (+{len(linhas) - 60} itens)"
    return texto if ok else "(não deu para listar a pasta)"


def extrair_passos(texto: str) -> list[str]:
    """Passos do JSON que o modelo devolveu (aceita lista solta ou objeto)."""
    texto = (texto or "").strip()
    m = re.search(r"\{.*\}|\[.*\]", texto, re.DOTALL)
    if not m:
        return []
    try:
        dados = json.loads(m.group(0))
    except ValueError:
        return []
    if isinstance(dados, dict):
        dados = (
            dados.get("passos")
            or dados.get("steps")
            or next((v for v in dados.values() if isinstance(v, list)), [])
        )
    passos = []
    for item in dados if isinstance(dados, list) else []:
        if isinstance(item, dict):
            item = (
                item.get("descricao")
                or item.get("passo")
                or item.get("description")
                or ""
            )
        item = " ".join(str(item).split())
        if item:
            passos.append(item[:300])
    return passos[:MAX_PASSOS]


def planejar(
    tarefa: Tarefa, engine: Any, modelo_nome: str, ferramentas: Ferramentas
) -> list[Passo]:
    conteudo = (
        f"Tarefa: {tarefa.pedido}\n\n"
        f"O que há na pasta de trabalho:\n{_resumo_da_pasta(ferramentas)}\n\n"
        f"Divida a tarefa em no máximo {MAX_PASSOS} passos curtos e concretos, na "
        "ordem certa, "
        "cada um feito com as ferramentas (listar, ler, escrever, criar planilha ou "
        "documento, "
        "criar pasta, mover, apagar, pesquisar na web). O primeiro passo costuma ser "
        "olhar os "
        'arquivos. Responda só com JSON: {"passos": ["...", "..."]}'
    )
    resposta = _gerar(
        engine,
        modelo_nome,
        [
            Message(role=Role.SYSTEM, content=SISTEMA),
            Message(role=Role.USER, content=conteudo),
        ],
        response_format={"type": "json_object"},
    )
    passos = extrair_passos(resposta.get("content", ""))
    if not passos:
        passos = [tarefa.pedido]  # sem plano legível: um passo só, a tarefa inteira
    return [Passo(descricao=p) for p in passos]


def executar_passo(
    tarefa: Tarefa,
    indice: int,
    engine: Any,
    modelo_nome: str,
    ferramentas: Ferramentas,
    parar: cancelamento.Cancelamento,
    pausa: Pausa,
    salvar: Callable[[], None],
    conversa: Optional[list[Message]] = None,
) -> str:
    """Faz um passo com as ferramentas e devolve a frase do que foi feito.

    ``conversa`` (opcional) é a conversa dos passos anteriores: o passo a
    continua enquanto ela for pequena e a deixa pronta para o próximo.
    """
    passo = tarefa.plano[indice]
    if conversa and _tamanho(conversa) <= LIMITE_CONVERSA:
        conversa.append(
            Message(
                role=Role.USER,
                content=f"Agora faça só o passo {indice + 1}: {passo.descricao}",
            )
        )
        mensagens = conversa
    else:
        mensagens = _inicio_do_passo(tarefa, indice)
        if conversa is not None:
            conversa[:] = mensagens
            mensagens = conversa
    return _laco_do_passo(
        tarefa, mensagens, engine, modelo_nome, ferramentas, parar, pausa, salvar
    )


def _tamanho(mensagens: list[Message]) -> int:
    total = 0
    for m in mensagens:
        total += len(m.content or "")
        for c in m.tool_calls or []:
            total += len(c.arguments or "") + len(c.name or "")
    return total


def _inicio_do_passo(tarefa: Tarefa, indice: int) -> list[Message]:
    passo = tarefa.plano[indice]
    plano = "\n".join(f"{i + 1}. {p.descricao}" for i, p in enumerate(tarefa.plano))
    feitos = "\n".join(
        f"{i + 1}. {p.resultado}"
        for i, p in enumerate(tarefa.plano[:indice])
        if p.resultado
    )
    return [
        Message(role=Role.SYSTEM, content=SISTEMA),
        Message(
            role=Role.USER,
            content=(
                f"Tarefa: {tarefa.pedido}\n\nPlano:\n{plano}\n\n"
                + (f"Já feito:\n{feitos}\n\n" if feitos else "")
                + f"Agora faça só o passo {indice + 1}: {passo.descricao}"
            ),
        ),
    ]


def _laco_do_passo(
    tarefa: Tarefa,
    mensagens: list[Message],
    engine: Any,
    modelo_nome: str,
    ferramentas: Ferramentas,
    parar: cancelamento.Cancelamento,
    pausa: Pausa,
    salvar: Callable[[], None],
) -> str:
    for chamada in range(MAX_CHAMADAS_POR_PASSO + 1):
        cancelamento.verificar()
        pausa.esperar(parar)
        cancelamento.verificar()
        ultima = chamada == MAX_CHAMADAS_POR_PASSO
        if ultima:
            mensagens.append(
                Message(
                    role=Role.USER,
                    content="Termine o passo agora: diga em uma frase o que foi feito.",
                )
            )
        resposta = _gerar(
            engine, modelo_nome, mensagens, **({} if ultima else {"tools": DEFINICOES})
        )
        brutas = resposta.get("tool_calls") or []
        texto = (resposta.get("content") or "").strip()
        if not brutas or ultima:
            final = (
                re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()
                or "passo concluído"
            )
            mensagens.append(Message(role=Role.ASSISTANT, content=final))
            return final
        chamadas = [
            ToolCall(
                id=c.get("id") or f"c{chamada}_{i}",
                name=c.get("name", ""),
                arguments=c.get("arguments") or "{}",
            )
            for i, c in enumerate(brutas)
        ]
        mensagens.append(
            Message(role=Role.ASSISTANT, content=texto, tool_calls=chamadas)
        )
        for c in chamadas:
            cancelamento.verificar()
            ok, saida = ferramentas.executar(c.name, c.arguments)
            tarefa.ferramentas_usadas += 1
            tarefa.anotar(
                "ferramenta" if ok else "aviso",
                f"{c.name}: {saida.splitlines()[0][:300] if saida else ''}",
            )
            salvar()
            mensagens.append(
                Message(
                    role=Role.TOOL,
                    content=saida[:MAX_RESULTADO],
                    tool_call_id=c.id,
                    name=c.name,
                )
            )
    return "passo concluído"


def resumir(tarefa: Tarefa) -> str:
    feitos = [p.resultado for p in tarefa.plano if p.estado == "feito" and p.resultado]
    falhas = [p.descricao for p in tarefa.plano if p.estado == "falhou"]
    partes = []
    if feitos:
        partes.append(" ".join(feitos))
    mudados = tarefa.arquivos_mudados()
    if mudados:
        partes.append(
            f"Arquivos mexidos: {', '.join(mudados[:15])}"
            + ("…" if len(mudados) > 15 else "")
            + "."
        )
    if falhas:
        partes.append(f"Não deu certo: {'; '.join(falhas)}.")
    return "\n\n".join(partes) or "Nada foi mudado na pasta."


def rodar(
    tarefa: Tarefa,
    engine: Any,
    modelo_nome: str,
    parar: cancelamento.Cancelamento,
    pausa: Pausa,
    confirmar: Callable[[str], bool],
    *,
    so_planejar: bool = False,
) -> None:
    """Planeja (se precisar) e, aprovado, executa os passos pendentes."""
    salvar = lambda: modelo.salvar(tarefa)  # noqa: E731
    ferramentas = Ferramentas(tarefa, confirmar, salvar)
    marca = cancelamento.ATUAL.set(parar)
    try:
        if not tarefa.plano:
            tarefa.estado = modelo.PLANEJANDO
            tarefa.anotar("info", "montando o plano")
            salvar()
            tarefa.plano = planejar(tarefa, engine, modelo_nome, ferramentas)
            tarefa.estado = modelo.AGUARDANDO_APROVACAO
            tarefa.anotar("info", f"plano com {len(tarefa.plano)} passo(s)")
            salvar()
            if so_planejar:
                return
        tarefa.estado = modelo.EXECUTANDO
        salvar()
        conversa: list[Message] = []
        for i, passo in enumerate(tarefa.plano):
            if passo.estado in ("feito", "pulado"):
                continue
            passo.estado = "fazendo"
            tarefa.anotar("passo", f"passo {i + 1}: {passo.descricao}")
            salvar()
            try:
                passo.resultado = executar_passo(
                    tarefa,
                    i,
                    engine,
                    modelo_nome,
                    ferramentas,
                    parar,
                    pausa,
                    salvar,
                    conversa,
                )
                passo.estado = "feito"
            except cancelamento.Cancelado:
                passo.estado = "pendente"
                raise
            except Exception as exc:  # noqa: BLE001 - um passo errado não derruba os outros
                logger.warning(
                    "Passo %d da tarefa falhou: %s", i + 1, type(exc).__name__
                )
                passo.estado = "falhou"
                passo.resultado = f"falhou: {exc}"[:500]
                conversa.clear()  # o próximo passo recomeça do plano e do resumo
                tarefa.anotar("erro", f"passo {i + 1} falhou: {exc}"[:500])
            salvar()
        tarefa.resumo = resumir(tarefa)
        tarefa.estado = modelo.CONCLUIDA
        tarefa.anotar("info", "tarefa concluída")
    except cancelamento.Cancelado:
        tarefa.estado = modelo.PARADA
        tarefa.resumo = resumir(tarefa)
        tarefa.anotar("info", "parada pela pessoa")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Tarefa do modo Trabalho falhou: %s", type(exc).__name__, exc_info=True
        )
        tarefa.estado = modelo.ERRO
        tarefa.erro = str(exc)[:500]
        tarefa.anotar("erro", tarefa.erro)
    finally:
        cancelamento.ATUAL.reset(marca)
        tarefa.pergunta = None
        salvar()


__all__ = ["MAX_PASSOS", "Pausa", "extrair_passos", "planejar", "resumir", "rodar"]
