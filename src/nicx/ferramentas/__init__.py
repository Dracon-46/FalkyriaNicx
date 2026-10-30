"""Tools primitive — tool system with ABC interface and built-in tools."""

from __future__ import annotations

from nicx.ferramentas._stubs import BaseTool, ToolExecutor, ToolSpec

# Subpacotes que não registram ferramentas: quem recarrega módulos para
# reregistrar ferramentas deve pular estes (recarregar o MCP cria cópias
# novas das classes do protocolo).
NOT_TOOL_MODULES = ("nicx.ferramentas.mcp", "nicx.ferramentas.sandbox")

# Import built-in tools to trigger @ToolRegistry.register() decorators.
# Each is wrapped in try/except so the package loads even before the
# individual tool modules are created.
try:
    import nicx.ferramentas.agentes.calculator  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.agentes.think  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.conhecimento.retrieval  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.agentes.llm_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.arquivos.file_read  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.web.web_search  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.web.weather  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.web.fx_macro  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.codigo.code_interpreter  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.codigo.code_interpreter_docker  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.codigo.repl  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.conhecimento.storage_tools  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.integracoes.mcp_adapter  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.integracoes.channel_tools  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.web.http_request  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.codigo.docker_shell_exec  # noqa: F401
    import nicx.ferramentas.codigo.shell_exec  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.pessoal.memory_manage  # noqa: F401
except ImportError:
    pass
try:
    import nicx.ferramentas.pessoal.user_profile_manage  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.pessoal.skill_manage  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.arquivos.file_write  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.arquivos.apply_patch  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.codigo.git_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.codigo.db_query  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.arquivos.pdf_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.conhecimento.knowledge_tools  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.integracoes.text_to_speech  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.agentes.digest_collect  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.conhecimento.scan_chunks  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.conhecimento.knowledge_sql  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.integracoes.apple_calendar  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.conhecimento.knowledge_search  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.web.browser  # noqa: F401
    import nicx.ferramentas.web.browser_axtree  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.agentes.proactive_tools  # noqa: F401
except ImportError:
    pass

# Controle do PC (volume, mídia, abrir apps): vive em nicx.acoes.
import nicx.acoes.ferramenta  # noqa: E402, F401

# Área de transferência e janela aberta: vive em nicx.contexto.
import nicx.contexto.ferramenta  # noqa: E402, F401

__all__ = ["NOT_TOOL_MODULES", "BaseTool", "ToolExecutor", "ToolSpec"]
