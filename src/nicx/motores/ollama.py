"""Ollama inference engine backend."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator, Sequence
from typing import Any, Dict, List, NoReturn

import httpx

from nicx.motores._base import (
    EngineConnectionError,
    EngineOutOfMemoryError,
    EngineRequestError,
    InferenceEngine,
    estimate_prompt_tokens,
    messages_to_dicts,
)
from nicx.motores._http_async import (
    STREAM_TRANSPORT_ERRORS,
    AsyncHTTPEngineMixin,
)
from nicx.motores._stubs import StreamChunk
from nicx.nucleo.registry import EngineRegistry
from nicx.nucleo.types import Message

logger = logging.getLogger(__name__)

# Qwen3 treats ``/think`` and ``/no_think`` as soft-switch control tokens that
# toggle reasoning mode. Small models (e.g. qwen3:14b) fed a multi-line prompt
# sometimes emit one of these as the sole tool argument, e.g.
# ``{"command": "/no_think"}`` instead of the real command. Ollama parses that
# into a fully-formed tool_call via the model's chat template, so we have to
# drop it on our side before the agent executes garbage.
_QWEN_CONTROL_TOKENS = frozenset({"/think", "/no_think"})


def _is_control_token_only_args(raw_args: Any) -> bool:
    """Return True if tool-call arguments contain nothing but a Qwen3 token.

    ``raw_args`` may be a dict (Ollama's native shape) or a JSON / bare string.
    A call is considered degenerate only when it carries at least one control
    token and no other usable content, so legitimate calls such as
    ``{"command": "date"}`` or ``{"command": "echo /no_think"}`` are kept.
    """
    parsed: Any = raw_args
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
        except (json.JSONDecodeError, TypeError):
            parsed = raw_args

    if isinstance(parsed, str):
        return parsed.strip().lower() in _QWEN_CONTROL_TOKENS

    if not isinstance(parsed, dict) or not parsed:
        return False

    saw_token = False
    for value in parsed.values():
        if not isinstance(value, str):
            return False  # a non-string value is real content
        stripped = value.strip()
        if not stripped:
            continue
        if stripped.lower() in _QWEN_CONTROL_TOKENS:
            saw_token = True
        else:
            return False  # real string content
    return saw_token


# Used when neither NICX_NUM_CTX nor ``[engine.ollama] num_ctx`` is usable.
# Above Ollama's 4k default so an image plus a real conversation fit, and
# small enough that a 4B model still loads on a CPU-only 16 GB machine.
_FALLBACK_NUM_CTX = 8192


def _configured_num_ctx() -> int | None:
    """Return ``[engine.ollama] num_ctx`` from the user's config, if valid."""
    try:
        from nicx.nucleo.config import load_config

        value = int(load_config().engine.ollama.num_ctx)
    except Exception:  # noqa: BLE001 - a broken config must not block inference
        return None
    return value if value > 0 else None


def _default_num_ctx() -> int:
    """Default context window (tokens) sent to Ollama.

    Priority: ``NICX_NUM_CTX`` env var > ``[engine.ollama] num_ctx`` in
    ``config.toml`` > 8192. A bigger window costs RAM even when unused, and on
    small machines that is the difference between loading and Ollama's
    out-of-memory error.
    """
    raw = os.environ.get("NICX_NUM_CTX", "").strip()
    if raw:
        try:
            value = int(raw)
        except ValueError:
            value = 0
        if value > 0:
            return value
    return _configured_num_ctx() or _FALLBACK_NUM_CTX


_FALLBACK_KEEP_ALIVE = "20m"


def _keep_alive() -> str:
    """How long Ollama keeps the model loaded after a request.

    Priority: ``NICX_KEEP_ALIVE`` > ``[engine.ollama] keep_alive`` > 20m.
    """
    raw = os.environ.get("NICX_KEEP_ALIVE", "").strip()
    if raw:
        return raw
    try:
        from nicx.nucleo.config import load_config

        value = str(load_config().engine.ollama.keep_alive).strip()
    except Exception:  # noqa: BLE001 - a broken config must not block inference
        value = ""
    return value or _FALLBACK_KEEP_ALIVE


_OOM_MARKERS = (
    "out of memory",
    "out-of-memory",
    "failed to allocate",
    "unable to allocate",
    "requires more system memory",
    "insufficient memory",
    "not enough memory",
)


def _looks_like_out_of_memory(detail: str) -> bool:
    low = (detail or "").lower()
    return any(marker in low for marker in _OOM_MARKERS)


def _out_of_memory_error(detail: str, status: int) -> EngineOutOfMemoryError:
    num_ctx = _default_num_ctx()
    smaller = max(2048, num_ctx // 2)
    return EngineOutOfMemoryError(
        "O Ollama não tem memória suficiente para carregar o modelo. "
        "Feche programas que consomem muita RAM (navegador, editores) e tente "
        "de novo, ou reduza a janela de contexto em ~/.nicx/config.toml "
        f"([engine.ollama] num_ctx, hoje {num_ctx}; experimente {smaller}) "
        "ou use um modelo menor.",
        status=status,
        detail=detail,
    )


def _ollama_request_options(
    *,
    temperature: float,
    max_tokens: int,
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """Build Ollama ``options`` dict from generate/stream kwargs."""
    options: Dict[str, Any] = {
        "temperature": temperature,
        "num_predict": max_tokens,
    }
    if kwargs.get("num_ctx") is not None:
        options["num_ctx"] = int(kwargs["num_ctx"])
    else:
        options["num_ctx"] = _default_num_ctx()
    if kwargs.get("num_gpu") is not None:
        options["num_gpu"] = int(kwargs["num_gpu"])
    return options


# O Ollama que o Nicx ligou neste processo: desliga junto quando o Nicx sai.
_started: Any = None


def started_by_nicx() -> bool:
    """Se o Nicx precisou ligar o Ollama neste processo."""
    return _started is not None


def stop_started_server() -> None:
    """Desliga o Ollama que o Nicx ligou (com os processos filhos dele, que
    seguram o modelo na RAM). Um Ollama que a pessoa abriu nunca é tocado."""
    global _started
    process, _started = _started, None
    if process is None or process.poll() is not None:
        return
    import subprocess
    import sys

    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
        else:
            process.terminate()
        process.wait(timeout=5)
    except Exception as exc:
        logger.debug("Ollama ligado pelo Nicx não desligou: %s", exc)


def _normalize_host(host: str) -> str:
    """'0.0.0.0', '127.0.0.1:11434' (formato do OLLAMA_HOST) -> URL completa.

    Endereço sem esquema é do jeito do Ollama: porta padrão 11434, e 0.0.0.0
    (escuta em tudo) vira 127.0.0.1 para conectar. URL completa (ex.: um
    Ollama remoto atrás de proxy HTTPS) fica como veio.
    """
    host = host.strip().rstrip("/")
    if "://" in host:
        return host
    if host.count(":") > 1 and not host.startswith("["):
        host = f"[{host}]"  # IPv6 sem colchetes ("::1")
    url = httpx.URL(f"http://{host}")
    hostname = url.host or "localhost"
    if hostname in ("0.0.0.0", "::"):
        hostname = "127.0.0.1"
    netloc = f"[{hostname}]" if ":" in hostname else hostname
    return f"http://{netloc}:{url.port or 11434}"


def _find_ollama() -> str | None:
    """Caminho do executável do Ollama: PATH ou a instalação padrão do Windows."""
    import shutil
    from pathlib import Path

    found = shutil.which("ollama")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    if local:
        exe = Path(local) / "Programs" / "Ollama" / "ollama.exe"
        if exe.is_file():
            return str(exe)
    return None


@EngineRegistry.register("ollama")
class OllamaEngine(AsyncHTTPEngineMixin, InferenceEngine):
    """Ollama backend via its native HTTP API."""

    engine_id = "ollama"

    # Ollama has no context-length overflow signal in its 400 bodies, so the
    # shared ``_raise_stream_http_error`` keeps its default (no
    # ``EngineContextLengthError`` branch, unlike the OpenAI-compat engines).
    # Out-of-memory 500s are recognized first, see below.

    _DEFAULT_HOST = "http://localhost:11434"

    def __init__(
        self,
        host: str | None = None,
        *,
        timeout: float = 1800.0,
    ) -> None:
        # Priority: explicit host (from config.toml) > OLLAMA_HOST env var > default
        if host is None:
            env_host = os.environ.get("OLLAMA_HOST")
            host = env_host or self._DEFAULT_HOST
        self._host = _normalize_host(host)
        # Used by the shared async streaming plumbing (AsyncHTTPEngineMixin) so a
        # wedged token read is bounded by ``timeout`` instead of hanging the
        # single event loop for the httpx default.
        self._timeout = timeout
        # Injection seam for tests: an ``httpx.MockTransport`` swapped in here drives
        # the async stream path with no real Ollama server. ``None`` in production so
        # httpx uses its default networking.
        self._async_transport: httpx.AsyncBaseTransport | None = None
        self._client = httpx.Client(base_url=self._host, timeout=timeout)
        # Last stream usage — captured from Ollama's final chunk
        self._last_stream_usage: Dict[str, int] = {}

    def _raise_stream_http_error(self, status: int, detail: str) -> NoReturn:
        """Report Ollama's out-of-memory failures as such, not as unreachable."""
        if _looks_like_out_of_memory(detail):
            raise _out_of_memory_error((detail or "").strip()[:500], status)
        super()._raise_stream_http_error(status, detail)

    def generate(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        msg_dicts = messages_to_dicts(messages)
        # Ollama expects tool_call arguments as dicts, not JSON strings
        for md in msg_dicts:
            for tc in md.get("tool_calls", []):
                fn = tc.get("function", {})
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        fn["arguments"] = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        pass
        payload: Dict[str, Any] = {
            "model": model,
            "messages": msg_dicts,
            "stream": False,
            "keep_alive": _keep_alive(),
            "options": _ollama_request_options(
                temperature=temperature,
                max_tokens=max_tokens,
                kwargs=kwargs,
            ),
        }
        # Disable extended thinking by default (Qwen3.5 etc.).
        # When enabled, thinking tokens consume the entire budget and
        # the visible content comes back empty.
        if "think" not in kwargs:
            payload["think"] = False
        elif kwargs["think"] is not None:
            payload["think"] = kwargs["think"]
        # Pass tools if provided
        tools = kwargs.get("tools")
        if tools:
            payload["tools"] = tools

        # Apply structured output / JSON mode
        response_format = kwargs.get("response_format")
        if response_format is not None:
            from nicx.motores._stubs import ResponseFormat

            if isinstance(response_format, ResponseFormat):
                payload["format"] = "json"
            elif isinstance(response_format, dict):
                payload["format"] = "json"
        try:
            resp = self._client.post("/api/chat", json=payload)
            if resp.status_code == 400 and tools:
                # Model may not support function calling -- retry without tools
                payload.pop("tools", None)
                resp = self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise EngineConnectionError(
                f"Ollama not reachable at {self._host}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response else ""
            status = exc.response.status_code
            if _looks_like_out_of_memory(body):
                raise _out_of_memory_error(body, status) from exc
            raise EngineRequestError(
                f"Ollama returned {status}: {body}", status=status, detail=body
            ) from exc
        data = resp.json()
        # prompt_eval_count = tokens actually evaluated (KV-cache-aware).
        # estimate_prompt_tokens = full prompt size (for cost comparison).
        # We report both so downstream can use the right one:
        #   prompt_tokens        → full size (what cloud would charge)
        #   prompt_tokens_evaluated → actual compute (with KV cache)
        reported_prompt = data.get("prompt_eval_count", 0)
        estimated_prompt = estimate_prompt_tokens(messages)
        prompt_tokens = max(reported_prompt, estimated_prompt)
        prompt_tokens_evaluated = (
            reported_prompt if reported_prompt > 0 else prompt_tokens
        )
        completion_tokens = data.get("eval_count", 0)
        content = data.get("message", {}).get("content", "")
        result: Dict[str, Any] = {
            "content": content,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "prompt_tokens_evaluated": prompt_tokens_evaluated,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            "model": data.get("model", model),
            "finish_reason": "stop",
        }
        # Extract timing from Ollama response (nanoseconds → seconds)
        result["ttft"] = data.get("prompt_eval_duration", 0) / 1e9
        result["engine_timing"] = {
            k: data[k]
            for k in (
                "total_duration",
                "load_duration",
                "prompt_eval_duration",
                "eval_duration",
            )
            if k in data
        }
        # Extract tool calls if present
        raw_tool_calls = data.get("message", {}).get("tool_calls", [])
        if raw_tool_calls:
            tool_calls = []
            for i, tc in enumerate(raw_tool_calls):
                fn = tc.get("function", {})
                raw_args = fn.get("arguments", "{}")
                if _is_control_token_only_args(raw_args):
                    logger.warning(
                        "Dropping Qwen3 control-token tool call %s(%r)",
                        fn.get("name", ""),
                        raw_args,
                    )
                    continue
                tool_calls.append(
                    {
                        "id": tc.get("id", f"call_{i}"),
                        "name": fn.get("name", ""),
                        "arguments": (
                            json.dumps(raw_args)
                            if isinstance(raw_args, dict)
                            else raw_args
                        ),
                    }
                )
            if tool_calls:
                result["tool_calls"] = tool_calls
        return result

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages_to_dicts(messages),
            "stream": True,
            "keep_alive": _keep_alive(),
            "options": _ollama_request_options(
                temperature=temperature,
                max_tokens=max_tokens,
                kwargs=kwargs,
            ),
        }
        # Mirror generate()'s default: disable extended thinking unless the
        # caller opted in. Qwen3/etc. with thinking on can stall the visible
        # stream for 60+ seconds before any tokens reach the client, which
        # frontends interpret as a "Load failed" timeout.
        if "think" not in kwargs:
            payload["think"] = False
        elif kwargs["think"] is not None:
            payload["think"] = kwargs["think"]
        try:
            # ASYNC streaming: ``httpx.AsyncClient`` + ``aiter_lines`` never
            # blocks the event loop between tokens (the previous SYNC
            # ``self._client`` + ``iter_lines`` inside this ``async def`` blocked
            # the single uvicorn worker on every inter-token wait, serializing all
            # concurrent chats and letting one wedged read freeze the whole API).
            # The shared client keeps pooled connections across turns.
            client = self._get_async_client()
            async with client.stream("POST", "/api/chat", json=payload) as resp:
                # ``not is_success`` covers 3xx as well as 4xx/5xx and maps
                # to ``EngineConnectionError`` (matching the OpenAI-compat
                # path) instead of leaking a raw ``httpx.HTTPStatusError``.
                # With redirects off (the default) an unexpected 3xx would
                # otherwise fall through to ``aiter_lines`` and surface as a
                # silent EMPTY stream rather than a clean engine error.
                if not resp.is_success:
                    # Read the (short) error body before touching ``.text``:
                    # a streaming response is otherwise unread.
                    await resp.aread()
                    self._raise_stream_http_error(resp.status_code, resp.text)
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done", False):
                        reported_prompt = chunk.get("prompt_eval_count", 0)
                        est_prompt = estimate_prompt_tokens(messages)
                        full_prompt = max(reported_prompt, est_prompt)
                        evaluated = (
                            reported_prompt if reported_prompt > 0 else full_prompt
                        )
                        comp = chunk.get("eval_count", 0)
                        self._last_stream_usage = {
                            "prompt_tokens": full_prompt,
                            "prompt_tokens_evaluated": evaluated,
                            "completion_tokens": comp,
                            "total_tokens": full_prompt + comp,
                        }
                        break
        except STREAM_TRANSPORT_ERRORS as exc:
            # Transport failures (incl. a mid-stream server disconnect) map to a
            # clean error; the set is kept narrow (see STREAM_TRANSPORT_ERRORS)
            # so cancellation still propagates.
            raise EngineConnectionError(
                f"Ollama not reachable at {self._host}"
            ) from exc

    async def stream_full(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Yield ``StreamChunk``s including tool_calls.

        Unlike the default ``stream_full`` in the base class (which wraps
        ``stream()`` and drops tools), this posts to ``/api/chat`` with
        ``tools`` from kwargs and parses tool_calls out of the streamed
        response. Falls back to a tools-less retry on 400 (mirrors
        ``generate()``'s behaviour for models that don't support tools).
        """
        msg_dicts = messages_to_dicts(messages)
        for md in msg_dicts:
            for tc in md.get("tool_calls", []):
                fn = tc.get("function", {})
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        fn["arguments"] = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        pass

        payload: Dict[str, Any] = {
            "model": model,
            "messages": msg_dicts,
            "stream": True,
            "keep_alive": _keep_alive(),
            "options": _ollama_request_options(
                temperature=temperature,
                max_tokens=max_tokens,
                kwargs=kwargs,
            ),
        }
        if "think" not in kwargs:
            payload["think"] = False
        elif kwargs["think"] is not None:
            payload["think"] = kwargs["think"]

        tools = kwargs.get("tools")
        if tools:
            payload["tools"] = tools

        async for chunk in self._run_stream(
            payload, messages, retry_without_tools=bool(tools)
        ):
            yield chunk

    async def _run_stream(
        self,
        payload: Dict[str, Any],
        messages: Sequence[Message],
        *,
        retry_without_tools: bool,
    ) -> AsyncIterator[StreamChunk]:
        """Execute the streaming request and yield parsed StreamChunks."""
        try:
            # ASYNC streaming (see ``stream``): shared ``AsyncClient`` +
            # ``aiter_lines`` so rich streaming never stalls the event loop and
            # honours ``timeout``.
            client = self._get_async_client()
            async with client.stream("POST", "/api/chat", json=payload) as resp:
                if resp.status_code == 400 and retry_without_tools:
                    # Model doesn't support tools — retry without them.
                    # PRESERVED: this specific 400 path must still trigger the
                    # tools-less retry; only OTHER non-2xx responses map to
                    # EngineConnectionError below.
                    payload.pop("tools", None)
                    async for c in self._run_stream(
                        payload, messages, retry_without_tools=False
                    ):
                        yield c
                    return
                # ``not is_success`` covers 3xx as well as 4xx/5xx and maps
                # to ``EngineConnectionError`` (matching the OpenAI-compat
                # path) instead of leaking a raw ``httpx.HTTPStatusError``.
                # With redirects off (the default) an unexpected 3xx would
                # otherwise fall through to ``aiter_lines`` and surface as a
                # silent EMPTY stream rather than a clean engine error.
                if not resp.is_success:
                    await resp.aread()
                    self._raise_stream_http_error(resp.status_code, resp.text)

                finish_reason: str | None = None
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    message = chunk.get("message", {}) or {}
                    content = message.get("content", "")
                    raw_tool_calls = message.get("tool_calls") or []

                    if content:
                        yield StreamChunk(content=content)

                    if raw_tool_calls:
                        # Ollama emits fully-formed tool_calls in a single
                        # chunk (not fragmented). Convert to the
                        # OpenAI-delta fragment shape that agent_manager_routes
                        # expects in _merge_tool_call_fragments.
                        fragments: List[Dict[str, Any]] = []
                        for tc in raw_tool_calls:
                            fn = tc.get("function", {}) or {}
                            raw_args = fn.get("arguments", "{}")
                            if _is_control_token_only_args(raw_args):
                                logger.warning(
                                    "Dropping Qwen3 control-token tool call %s(%r)",
                                    fn.get("name", ""),
                                    raw_args,
                                )
                                continue
                            args_str = (
                                json.dumps(raw_args)
                                if isinstance(raw_args, dict)
                                else str(raw_args)
                            )
                            i = len(fragments)
                            fragments.append(
                                {
                                    "index": i,
                                    "id": tc.get("id", f"call_{i}"),
                                    "type": "function",
                                    "function": {
                                        "name": fn.get("name", ""),
                                        "arguments": args_str,
                                    },
                                }
                            )
                        if fragments:
                            yield StreamChunk(tool_calls=fragments)
                            finish_reason = "tool_calls"

                    if chunk.get("done", False):
                        reported_prompt = chunk.get("prompt_eval_count", 0)
                        est_prompt = estimate_prompt_tokens(messages)
                        full_prompt = max(reported_prompt, est_prompt)
                        evaluated = (
                            reported_prompt if reported_prompt > 0 else full_prompt
                        )
                        comp = chunk.get("eval_count", 0)
                        self._last_stream_usage = {
                            "prompt_tokens": full_prompt,
                            "prompt_tokens_evaluated": evaluated,
                            "completion_tokens": comp,
                            "total_tokens": full_prompt + comp,
                        }
                        if finish_reason is None:
                            finish_reason = chunk.get("done_reason") or "stop"
                        yield StreamChunk(
                            finish_reason=finish_reason,
                            usage=dict(self._last_stream_usage),
                        )
                        break
        except STREAM_TRANSPORT_ERRORS as exc:
            # See ``stream``: transport failures (incl. a mid-stream server
            # disconnect) map to a clean error; the set is kept narrow so
            # cancellation still propagates.
            raise EngineConnectionError(
                f"Ollama not reachable at {self._host}"
            ) from exc

    def list_models(self) -> List[str]:
        try:
            resp = self._client.get("/api/tags")
            resp.raise_for_status()
        except (
            httpx.ConnectError,
            httpx.TimeoutException,
            httpx.HTTPStatusError,
        ) as exc:
            logger.warning(
                "Failed to list models from Ollama at %s: %s",
                self._host,
                exc,
            )
            return []
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]

    def health(self) -> bool:
        try:
            resp = self._client.get("/api/tags", timeout=2.0)
            return resp.status_code == 200
        except Exception as exc:
            logger.debug("Ollama health check failed at %s: %s", self._host, exc)
            return False

    def start_server(self, wait: float = 20.0) -> bool:
        """Liga o ``ollama serve`` em segundo plano quando ele está desligado.

        Sem isso, com o Ollama fora da inicialização do Windows, o Nicx
        abria sem modelo. Só vale para um Ollama nesta máquina;
        ``NICX_NO_AUTOSTART=1`` desliga (os testes usam).
        """
        if os.environ.get("NICX_NO_AUTOSTART"):
            return False
        host = httpx.URL(self._host).host
        if host not in ("localhost", "127.0.0.1", "::1"):
            return False
        exe = _find_ollama()
        if exe is None:
            return False
        import subprocess
        import sys
        import time

        # Console escondido, não DETACHED_PROCESS: o Ollama abre processos
        # filhos (detecção da CPU, carga do modelo) e, sem console para
        # herdar, cada um deles piscava uma janela de cmd na tela.
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        global _started
        try:
            # Na mesma porta que o Nicx vai procurar.
            url = httpx.URL(self._host)
            env = {**os.environ, "OLLAMA_HOST": f"{url.host}:{url.port or 11434}"}
            process = subprocess.Popen(
                [exe, "serve"],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
                start_new_session=sys.platform != "win32",
            )
        except OSError as exc:
            logger.warning("Não consegui ligar o Ollama (%s): %s", exe, exc)
            return False
        _started = process
        import atexit

        atexit.register(stop_started_server)
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            time.sleep(0.5)
            if self.health():
                logger.info("Ollama ligado pelo Nicx (%s)", exe)
                return True
        logger.warning("Liguei o Ollama, mas ele não respondeu em %.0f s", wait)
        return False

    def load(self, model: str) -> None:
        """Load the model's weights into RAM without reading any prompt.

        An empty request makes Ollama load the model and return. On CPU this
        moves the 5-30 s disk load out of the first question; prompt reading
        cannot be done ahead of time (qwen3.5 reuses no prompt cache here).
        """
        try:
            self._client.post(
                "/api/generate",
                json={"model": model, "keep_alive": _keep_alive()},
                timeout=300.0,
            )
        except Exception as exc:  # noqa: BLE001 - optional optimisation
            logger.debug("Could not preload %s: %s", model, exc)

    def unload(self, model: str) -> None:
        """Free the model's RAM now instead of after ``keep_alive``."""
        try:
            self._client.post(
                "/api/generate",
                json={"model": model, "keep_alive": 0},
                timeout=10.0,
            )
        except Exception as exc:  # noqa: BLE001 - best effort, usually on exit
            logger.debug("Could not unload %s from Ollama: %s", model, exc)

    def close(self) -> None:
        self._client.close()
        self._close_async_client()


def unload_configured_model() -> None:
    """Unload the configured default model, e.g. after stopping the server.

    The server may be force-killed (``taskkill /F`` on Windows), which skips
    its own cleanup; whoever stopped it calls this instead.
    """
    try:
        from nicx.nucleo.config import load_config

        cfg = load_config()
        model = cfg.intelligence.default_model
        if not model:
            return
        host = (
            cfg.engine.ollama.host
            or os.environ.get("OLLAMA_HOST")
            or OllamaEngine._DEFAULT_HOST
        )
        OllamaEngine(host=host).unload(model)
    except Exception as exc:  # noqa: BLE001 - best effort on exit
        logger.debug("Could not unload the configured model: %s", exc)


__all__ = ["OllamaEngine", "unload_configured_model"]
