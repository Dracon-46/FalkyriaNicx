"""Habilidades (skills) do usuário: criar sem programar, importar, ligar e desligar.

Uma habilidade é uma pasta com ``SKILL.md`` (cabeçalho YAML com ``name`` e
``description`` e, embaixo, as instruções) em ``~/.nicx/skills``. No chat ela
vira a ferramenta ``skill_<nome>``: quando o pedido combina com a descrição, o
modelo chama a ferramenta e recebe as instruções para seguir.

- criadas pela tela: ``skills/nicx/<nome>/SKILL.md``;
- importadas de um ``.zip`` ou do GitHub: ``skills/<fonte>/<nome>/`` pelo
  importador de sempre (``scripts/`` nunca é copiado por aqui: nada de código);
- desligadas ficam no disco, listadas em ``~/.nicx/habilidades_desligadas.json``.
"""

from __future__ import annotations

import io
import json
import logging
import re
import shutil
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

PASTA_CRIADAS = "nicx"
MAX_INSTRUCOES = 20_000
MAX_ZIP = 5 * 1024 * 1024
MAX_ARQUIVOS_ZIP = 200
_LOCK = threading.RLock()
_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9]|-(?!-)){0,62}[a-z0-9]$|^[a-z0-9]$")


class HabilidadeInvalida(ValueError):
    """Pedido que não dá para atender; a mensagem diz por quê."""


@dataclass
class Habilidade:
    nome: str  # slug: "resumo-de-reuniao"
    titulo: str
    descricao: str
    instrucoes: str
    pasta: Path
    origem: str  # "nicx" (criada aqui), "github", "importadas", "pacote:<id>"...
    ativa: bool = True
    versao: str = ""
    autor: str = ""
    perigosas: tuple[str, ...] = ()  # capacidades perigosas que pede

    @property
    def editavel(self) -> bool:
        return self.origem == PASTA_CRIADAS

    def para_dict(self) -> dict[str, Any]:
        return {
            "nome": self.nome,
            "titulo": self.titulo,
            "descricao": self.descricao,
            "instrucoes": self.instrucoes,
            "origem": self.origem,
            "ativa": self.ativa,
            "editavel": self.editavel,
            "versao": self.versao,
            "autor": self.autor,
            "perigosas": list(self.perigosas),
        }


def slug(texto: str) -> str:
    from nicx.rotinas.armazenamento import normalizar

    return "-".join(normalizar(texto).split())[:64].strip("-")


# ------------------------------------------------------------------ pastas
def pasta() -> Path:
    from nicx.nucleo.paths import get_config_dir

    try:
        from nicx.nucleo.config import load_config

        configurada = str(load_config().skills.skills_dir or "")
    except Exception:  # noqa: BLE001
        configurada = ""
    if configurada and configurada not in {"~/.nicx/skills", "~/.nicx/skills/"}:
        return Path(configurada).expanduser()
    return get_config_dir() / "skills"


def _arquivo_desligadas() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir() / "habilidades_desligadas.json"


def desligadas() -> set[str]:
    try:
        dados = json.loads(_arquivo_desligadas().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(n) for n in dados} if isinstance(dados, list) else set()


def _gravar_desligadas(nomes: set[str]) -> None:
    arquivo = _arquivo_desligadas()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(sorted(nomes), ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------ leitura
def _ler(diretorio: Path, raiz: Path, fora: set[str]) -> Optional[Habilidade]:
    from nicx.cerebro.habilidades.loader import load_skill_directory
    from nicx.cerebro.habilidades.security import DANGEROUS_CAPABILITIES

    try:
        m = load_skill_directory(diretorio)
    except Exception as exc:  # noqa: BLE001 - uma pasta quebrada não derruba a lista
        logger.info("Habilidade ilegível em %s: %s", diretorio, exc)
        return None
    relativo = diretorio.relative_to(raiz).parts
    origem = relativo[0] if len(relativo) > 1 else "pasta"
    meta = (m.metadata or {}).get("nicx", {}) if isinstance(m.metadata, dict) else {}
    titulo = str(meta.get("titulo") or m.name)
    return Habilidade(
        nome=m.name,
        titulo=titulo,
        descricao=m.description or "",
        instrucoes=m.markdown_content or "",
        pasta=diretorio,
        origem=str(meta.get("pacote") and f"pacote:{meta['pacote']}" or origem),
        ativa=m.name not in fora,
        versao=m.version or "",
        autor=m.author or "",
        perigosas=tuple(
            c for c in (m.required_capabilities or []) if c in DANGEROUS_CAPABILITIES
        ),
    )


def listar() -> list[Habilidade]:
    raiz = pasta()
    if not raiz.exists():
        return []
    fora = desligadas()
    vistas: dict[str, Habilidade] = {}
    for marcador in sorted([*raiz.rglob("SKILL.md"), *raiz.rglob("skill.toml")]):
        diretorio = marcador.parent
        if (
            len(diretorio.relative_to(raiz).parts) > 3
            or "discovered" in diretorio.parts
        ):
            continue
        h = _ler(diretorio, raiz, fora)
        if h is not None and h.nome not in vistas:
            vistas[h.nome] = h
    return sorted(vistas.values(), key=lambda h: h.titulo.lower())


def obter(nome: str) -> Optional[Habilidade]:
    return next((h for h in listar() if h.nome == nome), None)


def nomes_ativos() -> list[str]:
    return [h.nome for h in listar() if h.ativa]


# ------------------------------------------------------------- criar e editar
def _anotar(titulo: str) -> None:
    from nicx.historico.registro import anotar

    anotar("extensao", titulo, detalhe={"tipo": "habilidade"})


def _markdown(
    nome: str, titulo: str, descricao: str, instrucoes: str, pacote: str = ""
) -> str:
    meta: dict[str, Any] = {"titulo": titulo}
    if pacote:
        meta["pacote"] = pacote
    cabecalho = yaml.safe_dump(
        {"name": nome, "description": descricao, "metadata": {"nicx": meta}},
        allow_unicode=True,
        sort_keys=False,
    )
    return f"---\n{cabecalho}---\n\n{instrucoes.strip()}\n"


def salvar(
    titulo: str,
    descricao: str,
    instrucoes: str,
    nome: str = "",
    *,
    pacote: str = "",
    substituir: bool = False,
) -> Habilidade:
    """Cria (ou, com *substituir*, reescreve) uma habilidade feita no Nicx."""
    titulo = " ".join(titulo.split())[:60]
    descricao = " ".join(descricao.split())
    nome = nome or slug(titulo)
    if not titulo or not _SLUG.match(nome):
        raise HabilidadeInvalida("dê um nome com letras ou números")
    if not descricao or len(descricao) > 1024:
        raise HabilidadeInvalida("a descrição diz quando usar (até 1024 caracteres)")
    if not instrucoes.strip() or len(instrucoes) > MAX_INSTRUCOES:
        raise HabilidadeInvalida(f"instruções: de 1 a {MAX_INSTRUCOES} caracteres")
    with _LOCK:
        existente = obter(nome)
        if existente is not None and not (substituir and existente.editavel):
            raise HabilidadeInvalida(f"já existe uma habilidade chamada {nome}")
        destino = pasta() / PASTA_CRIADAS / nome
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "SKILL.md").write_text(
            _markdown(nome, titulo, descricao, instrucoes, pacote), encoding="utf-8"
        )
    _anotar(f"Habilidade {'alterada' if existente else 'criada'}: {titulo}")
    h = obter(nome)
    assert h is not None
    return h


def ligar(nome: str, ativa: bool) -> None:
    with _LOCK:
        if obter(nome) is None:
            raise KeyError(nome)
        fora = desligadas()
        fora.discard(nome) if ativa else fora.add(nome)
        _gravar_desligadas(fora)


def apagar(nome: str) -> bool:
    with _LOCK:
        h = obter(nome)
        if h is None:
            return False
        raiz = pasta().resolve()
        alvo = h.pasta.resolve()
        if alvo == raiz or raiz not in alvo.parents:
            raise HabilidadeInvalida(
                "essa habilidade está fora da pasta de habilidades"
            )
        shutil.rmtree(alvo)
        fora = desligadas()
        if nome in fora:
            fora.discard(nome)
            _gravar_desligadas(fora)
    _anotar(f"Habilidade removida: {h.titulo}")
    return True


# ------------------------------------------------------------------ importar
def _importar_resolvida(item: Any, confirmar_perigosas: bool) -> dict[str, Any]:
    from nicx.cerebro.habilidades.importer import SkillImporter
    from nicx.cerebro.habilidades.parser import SkillParser
    from nicx.cerebro.habilidades.tool_translator import ToolTranslator

    importer = SkillImporter(
        parser=SkillParser(), tool_translator=ToolTranslator(), target_root=pasta()
    )
    resultado = importer.import_skill(
        item, with_scripts=False, force=True, confirm_dangerous=confirmar_perigosas
    )
    return {
        "nome": item.name,
        "ok": bool(resultado.success and not resultado.skipped),
        "pede_confirmacao": bool(
            resultado.requires_confirmation and not resultado.success
        ),
        "perigosas": list(resultado.dangerous_capabilities),
        "avisos": list(resultado.warnings),
    }


def _extrair_zip(dados: bytes, destino: Path) -> None:
    if len(dados) > MAX_ZIP:
        raise HabilidadeInvalida("o arquivo passa de 5 MB")
    try:
        arquivo = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile as exc:
        raise HabilidadeInvalida("não é um .zip válido") from exc
    with arquivo:
        membros = arquivo.infolist()
        if len(membros) > MAX_ARQUIVOS_ZIP:
            raise HabilidadeInvalida("arquivos demais no .zip")
        if sum(m.file_size for m in membros) > 4 * MAX_ZIP:
            raise HabilidadeInvalida("o .zip descompactado fica grande demais")
        base = destino.resolve()
        for m in membros:
            alvo = (destino / m.filename).resolve()
            if base not in alvo.parents and alvo != base:
                raise HabilidadeInvalida("o .zip tenta escrever fora da pasta")
        arquivo.extractall(destino)


def importar_zip(
    dados: bytes, confirmar_perigosas: bool = False
) -> list[dict[str, Any]]:
    """Instala as habilidades (pastas com SKILL.md) de um .zip."""
    from nicx.cerebro.habilidades.loader import load_skill_directory
    from nicx.cerebro.habilidades.sources.base import ResolvedSkill

    with tempfile.TemporaryDirectory(prefix="nicx-hab-") as tmp:
        raiz = Path(tmp)
        _extrair_zip(dados, raiz)
        pastas = sorted({p.parent for p in raiz.rglob("SKILL.md")})
        if not pastas:
            raise HabilidadeInvalida("nenhum SKILL.md no .zip")
        resultados = []
        for diretorio in pastas[:20]:
            try:
                m = load_skill_directory(diretorio)
            except Exception as exc:  # noqa: BLE001
                resultados.append(
                    {"nome": diretorio.name, "ok": False, "avisos": [str(exc)]}
                )
                continue
            item = ResolvedSkill(
                name=m.name,
                source="importadas",
                path=diretorio,
                category="",
                description=m.description or "",
                commit="",
            )
            resultados.append(_importar_resolvida(item, confirmar_perigosas))
    if any(r["ok"] for r in resultados):
        _anotar(
            "Habilidades importadas: "
            + ", ".join(r["nome"] for r in resultados if r["ok"])
        )
    return resultados


def importar_github(
    url: str, nomes: Optional[list[str]] = None, confirmar_perigosas: bool = False
) -> list[dict[str, Any]]:
    """Instala habilidades de um repositório (todas, ou só *nomes*)."""
    if not re.match(r"^https://github\.com/[\w.-]+/[\w.-]+/?$", url.strip()):
        raise HabilidadeInvalida(
            "use o endereço do repositório: https://github.com/dono/nome"
        )
    from nicx.cerebro.habilidades.sources.github import GitHubResolver
    from nicx.nucleo.paths import get_config_dir

    url = url.strip().rstrip("/")
    cache = get_config_dir() / "skill-cache" / "github" / url.rsplit("/", 1)[-1]
    resolver = GitHubResolver(cache_root=cache, repo_url=url)
    try:
        resolver.sync()
    except Exception as exc:  # noqa: BLE001
        raise HabilidadeInvalida(f"não consegui baixar o repositório: {exc}") from exc
    itens = resolver.list_skills()
    if nomes:
        itens = [i for i in itens if i.name in set(nomes)]
    if not itens:
        raise HabilidadeInvalida("nenhuma habilidade encontrada no repositório")
    resultados = [_importar_resolvida(i, confirmar_perigosas) for i in itens[:50]]
    if any(r["ok"] for r in resultados):
        _anotar(
            "Habilidades instaladas do GitHub: " + "/".join(url.rsplit("/", 2)[-2:])
        )
    return resultados


# ------------------------------------------------------------------ no chat
def _ferramentas(bus: Any, executor: Any) -> list[Any]:
    from nicx.cerebro.habilidades.manager import SkillManager

    manager = SkillManager(bus)
    manager.discover(paths=[pasta()])
    fora = desligadas()
    manager._skills = {k: v for k, v in manager._skills.items() if k not in fora}
    if executor is not None:
        manager.set_tool_executor(executor)
    tools = manager.get_skill_tools(tool_executor=executor)
    for t in tools:
        t._nicx_habilidade = True
    return tools


def ligar_no_agente(agent: Any, bus: Any = None) -> int:
    """Troca as habilidades do agente do chat pelas ativas agora. Devolve quantas."""
    if agent is None or not hasattr(agent, "_tools"):
        return 0
    executor = getattr(agent, "_executor", None)
    novas = _ferramentas(bus or getattr(agent, "_bus", None), executor)
    from nicx.servidor.rotas.chat import _get_agent_model_lock

    with _get_agent_model_lock(agent):
        atuais = [
            t for t in agent._tools if getattr(t, "_nicx_habilidade", False) is not True
        ]
        existentes = {t.spec.name for t in atuais}
        atuais.extend(t for t in novas if t.spec.name not in existentes)
        agent._tools[:] = atuais
        if executor is not None and isinstance(getattr(executor, "_tools", None), dict):
            executor._tools = {t.spec.name: t for t in atuais}
    return len(novas)


__all__ = [
    "Habilidade",
    "HabilidadeInvalida",
    "apagar",
    "desligadas",
    "importar_github",
    "importar_zip",
    "ligar",
    "ligar_no_agente",
    "listar",
    "nomes_ativos",
    "obter",
    "pasta",
    "salvar",
    "slug",
]
