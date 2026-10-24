"""Tools primitive — tool system with ABC interface and built-in tools."""

from __future__ import annotations

from nicx.tools._stubs import BaseTool, ToolExecutor, ToolSpec

# Import built-in tools to trigger @ToolRegistry.register() decorators.
# Each is wrapped in try/except so the package loads even before the
# individual tool modules are created.
try:
    import nicx.tools.calculator  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.think  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.retrieval  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.llm_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.file_read  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.web_search  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.weather  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.fx_macro  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.code_interpreter  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.code_interpreter_docker  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.repl  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.storage_tools  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.mcp_adapter  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.channel_tools  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.http_request  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.docker_shell_exec  # noqa: F401
    import nicx.tools.shell_exec  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.memory_manage  # noqa: F401
except ImportError:
    pass
try:
    import nicx.tools.user_profile_manage  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.skill_manage  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.file_write  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.apply_patch  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.git_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.db_query  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.pdf_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.image_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.audio_tool  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.knowledge_tools  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.text_to_speech  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.digest_collect  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.scan_chunks  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.knowledge_sql  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.apple_calendar  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.knowledge_search  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.browser  # noqa: F401
    import nicx.tools.browser_axtree  # noqa: F401
except ImportError:
    pass

try:
    import nicx.tools.proactive_tools  # noqa: F401
except ImportError:
    pass

# Controle do PC (volume, mídia, abrir apps): vive em nicx.acoes.
import nicx.acoes.ferramenta  # noqa: E402, F401

__all__ = ["BaseTool", "ToolExecutor", "ToolSpec"]
