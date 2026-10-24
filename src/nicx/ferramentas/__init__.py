"""Tools primitive — tool system with ABC interface and built-in tools."""

from __future__ import annotations

from nicx.ferramentas._stubs import BaseTool, ToolExecutor, ToolSpec

# Import built-in tools to trigger @ToolRegistry.register() decorators.
# Each is wrapped in try/except so the package loads even before the
# individual tool modules are created.
try:
    import nicx.ferramentas.calculator  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.think  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.retrieval  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.llm_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.file_read  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.web_search  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.weather  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.fx_macro  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.code_interpreter  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.code_interpreter_docker  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.repl  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.storage_tools  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.mcp_adapter  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.channel_tools  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.http_request  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.docker_shell_exec  # noqa: F401
    import nicx.ferramentas.shell_exec  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.memory_manage  # noqa: F401
except ImportError:
    pass
try:
    import nicx.ferramentas.user_profile_manage  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.skill_manage  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.file_write  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.apply_patch  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.git_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.db_query  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.pdf_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.image_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.audio_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.knowledge_tools  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.text_to_speech  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.digest_collect  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.scan_chunks  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.knowledge_sql  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.apple_calendar  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.knowledge_search  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.browser  # noqa: F401
    import nicx.ferramentas.browser_axtree  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.proactive_tools  # noqa: F401
except ImportError:
    pass

# Controle do PC (volume, mídia, abrir apps): vive em nicx.acoes.
import nicx.acoes.ferramenta  # noqa: E402, F401

__all__ = ["BaseTool", "ToolExecutor", "ToolSpec"]
