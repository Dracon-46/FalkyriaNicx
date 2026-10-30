"""Onde os projetos ficam: ``~/.nicx/projetos.json``.

Cada mudança relê o arquivo, muda e grava de novo, segurando uma trava entre
processos (o servidor, o terminal e a janela flutuante podem mexer ao mesmo
tempo). A gravação é atômica (arquivo temporário + ``os.replace``, com nova
tentativa no Windows) e guarda a versão anterior em ``projetos.json.bak``.

Arquivo estragado não apaga nada: um projeto ilegível é pulado (os outros
seguem); o arquivo inteiro ilegível vai para ``projetos.json.corrompido`` e
os projetos voltam do ``.bak``.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, TypeVar

from nicx.memoria.store import _cross_process_lock, _replace_with_retry
from nicx.projetos import busca
from nicx.projetos.modelo import (
    MAX_CAMINHOS,
    MAX_DECISOES,
    MAX_NOME,
    MAX_PASSOS,
    MAX_PENDENCIAS,
    Decisao,
    Pendencia,
    Projeto,
    agora,
    limpar_texto,
)

logger = logging.getLogger(__name__)

VERSAO = 1
_T = TypeVar("_T")
_THREAD_LOCK = threading.Lock()


class ProjetoErro(ValueError):
    """Pedido inválido (nome vazio, projeto que já existe, não achado)."""


class ProjetoJaExiste(ProjetoErro):
    def __init__(self, projeto: Projeto) -> None:
        super().__init__(f"Já existe o projeto {projeto.nome}")
        self.projeto = projeto


class ProjetoNaoEncontrado(ProjetoErro):
    pass


def caminho_padrao() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "projetos.json"


def _ler_lista(texto: str) -> list[Any]:
    dados = json.loads(texto)
    if isinstance(dados, dict):
        dados = dados.get("projetos")
    if not isinstance(dados, list):
        raise ValueError("sem lista de projetos")
    return dados


def _projetos_de(itens: Iterable[Any]) -> list[Projeto]:
    projetos: list[Projeto] = []
    vistos: set[str] = set()
    for item in itens:
        try:
            projeto = Projeto.de_dict(item)
        except (ValueError, TypeError):
            logger.warning("Projeto ilegível ignorado em projetos.json")
            continue
        if projeto.id in vistos:
            continue
        vistos.add(projeto.id)
        projetos.append(projeto)
    return projetos


class Projetos:
    """Os projetos do usuário num arquivo JSON local."""

    def __init__(self, caminho: str | Path | None = None) -> None:
        self.caminho = Path(caminho) if caminho is not None else caminho_padrao()

    # -- arquivo --------------------------------------------------------------

    @property
    def _bak(self) -> Path:
        return self.caminho.with_name(self.caminho.name + ".bak")

    @property
    def _trava(self) -> Path:
        return self.caminho.with_name(self.caminho.name + ".lock")

    def _carregar(self, *, salvar_estragado: bool = False) -> list[Projeto]:
        if not self.caminho.exists():
            return []
        try:
            texto = self.caminho.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Não deu para ler projetos.json")
            return []
        if not texto.strip():
            return []
        try:
            return _projetos_de(_ler_lista(texto))
        except (ValueError, TypeError):
            pass
        logger.warning("projetos.json ilegível; usando a cópia anterior (.bak)")
        if salvar_estragado:
            # Guarda o arquivo ruim antes da próxima gravação cobrir.
            destino = self.caminho.with_name(self.caminho.name + ".corrompido")
            try:
                shutil.copyfile(self.caminho, destino)
            except OSError:
                logger.warning("Não deu para guardar o projetos.json ilegível")
        try:
            return _projetos_de(_ler_lista(self._bak.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return []

    def _gravar(self, projetos: list[Projeto]) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        conteudo = json.dumps(
            {"versao": VERSAO, "projetos": [p.para_dict() for p in projetos]},
            ensure_ascii=False,
            indent=1,
        )
        if self.caminho.exists():
            try:
                atual = self.caminho.read_text(encoding="utf-8")
                _ler_lista(atual)  # só copia para o .bak se estiver bom
                self._escrever(self._bak, atual)
            except (OSError, ValueError, TypeError):
                pass
        self._escrever(self.caminho, conteudo)

    @staticmethod
    def _escrever(destino: Path, conteudo: str) -> None:
        fd, temporario = tempfile.mkstemp(
            dir=str(destino.parent), prefix=destino.name + ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
                arquivo.write(conteudo)
            _replace_with_retry(temporario, destino)
        except BaseException:
            try:
                os.unlink(temporario)
            except OSError:
                pass
            raise

    def _mudar(self, funcao: Callable[[list[Projeto]], _T]) -> _T:
        """Lê, aplica *funcao* (que muda a lista) e grava, tudo sob a trava."""
        with _THREAD_LOCK, _cross_process_lock(self._trava):
            projetos = self._carregar(salvar_estragado=True)
            resultado = funcao(projetos)
            self._gravar(projetos)
            return resultado

    def _mudar_um(self, projeto_id: str, funcao: Callable[[Projeto], _T]) -> _T:
        def aplicar(projetos: list[Projeto]) -> _T:
            projeto = _por_id(projetos, projeto_id)
            resultado = funcao(projeto)
            projeto.marcar_atividade()
            return resultado

        return self._mudar(aplicar)

    # -- leitura --------------------------------------------------------------

    def listar(self, *, arquivados: bool = False) -> list[Projeto]:
        """Do mais recente para o mais antigo."""
        with _THREAD_LOCK:
            projetos = self._carregar()
        if not arquivados:
            projetos = [p for p in projetos if not p.arquivado]
        return sorted(projetos, key=lambda p: p.ultima_atividade, reverse=True)

    def obter(self, projeto_id: str) -> Optional[Projeto]:
        return next(
            (p for p in self.listar(arquivados=True) if p.id == projeto_id), None
        )

    def buscar(self, nome: str, *, arquivados: bool = False) -> Optional[Projeto]:
        return busca.melhor(nome, self.listar(arquivados=arquivados))

    def mais_recente(self) -> Optional[Projeto]:
        projetos = self.listar()
        return projetos[0] if projetos else None

    # -- mudanças -------------------------------------------------------------

    def criar(
        self,
        nome: str,
        *,
        objetivo: str = "",
        pastas: Iterable[str] = (),
        idioma: str = "",
    ) -> Projeto:
        nome = limpar_texto(nome, MAX_NOME).strip(" .,;:!?-\"'")
        if not nome:
            raise ProjetoErro("Nome vazio")

        def aplicar(projetos: list[Projeto]) -> Projeto:
            alvo = busca.normalizar(nome)
            for existente in projetos:
                if not existente.arquivado and busca.normalizar(existente.nome) == alvo:
                    raise ProjetoJaExiste(existente)
            projeto = Projeto(
                nome=nome,
                objetivo=limpar_texto(objetivo, 1000),
                pastas=_caminhos(pastas),
                idioma=idioma or "",
            )
            projeto.marcar_atividade(projeto.criado_em)
            projetos.append(projeto)
            return projeto

        return self._mudar(aplicar)

    def renomear(self, projeto_id: str, novo_nome: str) -> Projeto:
        novo_nome = limpar_texto(novo_nome, MAX_NOME).strip(" .,;:!?-\"'")
        if not novo_nome:
            raise ProjetoErro("Nome vazio")

        def aplicar(projetos: list[Projeto]) -> Projeto:
            projeto = _por_id(projetos, projeto_id)
            alvo = busca.normalizar(novo_nome)
            for outro in projetos:
                if (
                    outro.id != projeto_id
                    and not outro.arquivado
                    and busca.normalizar(outro.nome) == alvo
                ):
                    raise ProjetoJaExiste(outro)
            projeto.nome = novo_nome
            projeto.marcar_atividade()
            return projeto

        return self._mudar(aplicar)

    def arquivar(self, projeto_id: str, arquivado: bool = True) -> Projeto:
        def aplicar(projeto: Projeto) -> Projeto:
            projeto.arquivado = arquivado
            return projeto

        return self._mudar_um(projeto_id, aplicar)

    def apagar(self, projeto_id: str) -> bool:
        def aplicar(projetos: list[Projeto]) -> bool:
            antes = len(projetos)
            projetos[:] = [p for p in projetos if p.id != projeto_id]
            return len(projetos) != antes

        return self._mudar(aplicar)

    def atualizar(self, projeto_id: str, **campos: Any) -> Projeto:
        """Muda objetivo, estado, próximos passos, pastas ou arquivos."""

        def aplicar(projeto: Projeto) -> Projeto:
            if "objetivo" in campos:
                projeto.objetivo = limpar_texto(campos["objetivo"], 1000)
            if "estado" in campos:
                projeto.estado = limpar_texto(campos["estado"], 1000)
            if "proximos_passos" in campos:
                projeto.proximos_passos = [
                    t
                    for t in (limpar_texto(v) for v in campos["proximos_passos"] or [])
                    if t
                ][:MAX_PASSOS]
            if "pastas" in campos:
                projeto.pastas = _caminhos(campos["pastas"] or [])
            if "arquivos" in campos:
                projeto.arquivos = _caminhos(campos["arquivos"] or [])
            return projeto

        return self._mudar_um(projeto_id, aplicar)

    def atualizar_estado(self, projeto_id: str, estado: str) -> Projeto:
        return self.atualizar(projeto_id, estado=estado)

    def registrar_decisao(
        self, projeto_id: str, texto: str, *, origem: str = ""
    ) -> Decisao:
        texto = limpar_texto(texto)
        if not texto:
            raise ProjetoErro("Decisão vazia")

        def aplicar(projeto: Projeto) -> Decisao:
            decisao = Decisao(texto=texto, origem=origem)
            projeto.decisoes.append(decisao)
            del projeto.decisoes[:-MAX_DECISOES]
            return decisao

        return self._mudar_um(projeto_id, aplicar)

    def adicionar_pendencia(
        self, projeto_id: str, texto: str, *, origem: str = ""
    ) -> Pendencia:
        texto = limpar_texto(texto)
        if not texto:
            raise ProjetoErro("Pendência vazia")

        def aplicar(projeto: Projeto) -> Pendencia:
            alvo = busca.normalizar(texto)
            for existente in projeto.abertas:
                if busca.normalizar(existente.texto) == alvo:
                    return existente
            pendencia = Pendencia(texto=texto, origem=origem)
            projeto.pendencias.append(pendencia)
            _podar_pendencias(projeto)
            return pendencia

        return self._mudar_um(projeto_id, aplicar)

    def concluir_pendencia(
        self, projeto_id: str, qual: str, *, feita: bool = True
    ) -> Optional[Pendencia]:
        """Marca a pendência (pelo id ou pelo texto, com tolerância)."""

        def aplicar(projeto: Projeto) -> Optional[Pendencia]:
            candidatas = projeto.abertas if feita else projeto.pendencias
            pendencia = achar_pendencia(qual, candidatas)
            if pendencia is None:
                return None
            pendencia.feita = feita
            pendencia.feita_em = agora() if feita else ""
            return pendencia

        return self._mudar_um(projeto_id, aplicar)

    def editar_pendencia(
        self, projeto_id: str, pendencia_id: str, texto: str
    ) -> Pendencia:
        texto = limpar_texto(texto)
        if not texto:
            raise ProjetoErro("Pendência vazia")

        def aplicar(projeto: Projeto) -> Pendencia:
            for pendencia in projeto.pendencias:
                if pendencia.id == pendencia_id:
                    pendencia.texto = texto
                    return pendencia
            raise ProjetoNaoEncontrado("Pendência não encontrada")

        return self._mudar_um(projeto_id, aplicar)

    def apagar_pendencia(self, projeto_id: str, pendencia_id: str) -> bool:
        def aplicar(projeto: Projeto) -> bool:
            antes = len(projeto.pendencias)
            projeto.pendencias = [p for p in projeto.pendencias if p.id != pendencia_id]
            return len(projeto.pendencias) != antes

        return self._mudar_um(projeto_id, aplicar)

    def anexar_pasta(self, projeto_id: str, caminho: str) -> Projeto:
        return self._anexar(projeto_id, "pastas", caminho)

    def anexar_arquivo(self, projeto_id: str, caminho: str) -> Projeto:
        return self._anexar(projeto_id, "arquivos", caminho)

    def _anexar(self, projeto_id: str, campo: str, caminho: str) -> Projeto:
        caminho = str(caminho or "").strip().strip('"')
        if not caminho:
            raise ProjetoErro("Caminho vazio")

        def aplicar(projeto: Projeto) -> Projeto:
            lista = getattr(projeto, campo)
            setattr(projeto, campo, _caminhos([*lista, caminho]))
            return projeto

        return self._mudar_um(projeto_id, aplicar)

    def tocar(self, projeto_id: str, quando: Optional[str] = None) -> Optional[Projeto]:
        """Marca atividade no projeto (sem mudar mais nada)."""

        def aplicar(projetos: list[Projeto]) -> Optional[Projeto]:
            projeto = next((p for p in projetos if p.id == projeto_id), None)
            if projeto is not None:
                projeto.marcar_atividade(quando)
            return projeto

        return self._mudar(aplicar)


def _por_id(projetos: list[Projeto], projeto_id: str) -> Projeto:
    for projeto in projetos:
        if projeto.id == projeto_id:
            return projeto
    raise ProjetoNaoEncontrado(f"Projeto não encontrado: {projeto_id}")


def _caminhos(caminhos: Iterable[str]) -> list[str]:
    vistos: set[str] = set()
    saida: list[str] = []
    for caminho in caminhos:
        caminho = str(caminho or "").strip().strip('"').rstrip("\\/") or ""
        chave = os.path.normcase(caminho)
        if caminho and chave not in vistos:
            vistos.add(chave)
            saida.append(caminho)
    return saida[:MAX_CAMINHOS]


def _podar_pendencias(projeto: Projeto) -> None:
    """Acima do limite, saem as feitas mais antigas (as abertas ficam)."""
    excesso = len(projeto.pendencias) - MAX_PENDENCIAS
    if excesso <= 0:
        return
    feitas = sorted(
        (p for p in projeto.pendencias if p.feita), key=lambda p: p.feita_em
    )[:excesso]
    fora = {p.id for p in feitas}
    projeto.pendencias = [p for p in projeto.pendencias if p.id not in fora]


def achar_pendencia(qual: str, pendencias: Iterable[Pendencia]) -> Optional[Pendencia]:
    """A pendência pelo id ou pelo texto (igual, começo, palavras ou trecho)."""
    lista = list(pendencias)
    qual = str(qual or "").strip()
    if not qual:
        return None
    for pendencia in lista:
        if pendencia.id == qual:
            return pendencia
    melhor: tuple[int, Optional[Pendencia]] = (0, None)
    for pendencia in lista:
        nota = busca.pontuar(qual, pendencia.texto)
        if nota > melhor[0]:
            melhor = (nota, pendencia)
    return melhor[1] if melhor[0] >= 60 else None


__all__ = [
    "ProjetoErro",
    "ProjetoJaExiste",
    "ProjetoNaoEncontrado",
    "Projetos",
    "achar_pendencia",
    "caminho_padrao",
]
