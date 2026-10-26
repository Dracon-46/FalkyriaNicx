"""Single point of contact between Python and the Rust ``nicx_rust`` module.

Every Python module that wants to delegate to Rust should import helpers from
here rather than importing ``nicx_rust`` directly.  The Rust backend is
mandatory — if it cannot be imported, a hard ``ImportError`` is raised.
"""

from __future__ import annotations

import functools
import json
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    import types as _types

# ---------------------------------------------------------------------------
# Mandatory import — Rust backend is required
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def get_rust_module() -> _types.ModuleType:
    """Return the ``nicx_rust`` module.

    Raises ``ImportError`` if the compiled extension is not available.
    The Rust backend is mandatory for all modules that have Rust
    implementations — there is no Python fallback.
    """
    import nicx_rust  # type: ignore[import-untyped]

    return nicx_rust


def _detect_rust() -> bool:
    """Return ``True`` if the compiled ``nicx_rust`` extension is importable.

    Computed once at import time. Modules with a Python fallback (e.g.
    ``security.ssrf``) consult this flag instead of hardcoding availability,
    so the fallback is actually reachable when the extension was not built.
    """
    try:
        get_rust_module()
    except ImportError:
        return False
    return True


RUST_AVAILABLE: bool = _detect_rust()


# ---------------------------------------------------------------------------
# JSON -> Python dataclass converters
# ---------------------------------------------------------------------------


def scan_result_from_json(json_str: str) -> object:
    """Convert a Rust scanner JSON string to a Python ``ScanResult``."""
    from nicx.seguranca.types import (
        ScanFinding,
        ScanResult,
        ThreatLevel,
    )

    data = json.loads(json_str)
    findings: List[ScanFinding] = []
    for f in data.get("findings", []):
        findings.append(
            ScanFinding(
                pattern_name=f.get("pattern_name", ""),
                matched_text=f.get("matched_text", ""),
                threat_level=ThreatLevel(
                    f.get("threat_level", "low").lower(),
                ),
                start=f.get("start", 0),
                end=f.get("end", 0),
                description=f.get("description", ""),
            )
        )
    return ScanResult(findings=findings)


def injection_result_from_json(json_str: str) -> object:
    """Convert Rust ``InjectionScanner.scan()`` JSON to dataclass."""
    from nicx.seguranca.injection_scanner import (
        InjectionScanResult,
    )
    from nicx.seguranca.types import ScanFinding, ThreatLevel

    data = json.loads(json_str)
    findings: List[ScanFinding] = []
    for f in data.get("findings", []):
        findings.append(
            ScanFinding(
                pattern_name=f.get("pattern_name", ""),
                matched_text=f.get("matched_text", ""),
                threat_level=ThreatLevel(
                    f.get("threat_level", "low").lower(),
                ),
                start=f.get("start", 0),
                end=f.get("end", 0),
                description=f.get("description", ""),
            )
        )

    threat_raw = data.get("threat_level", "low").lower()
    try:
        threat = ThreatLevel(threat_raw)
    except ValueError:
        threat = ThreatLevel.LOW

    return InjectionScanResult(
        is_clean=data.get("is_clean", True),
        findings=findings,
        threat_level=threat,
    )


def retrieval_results_from_json(json_str: str) -> list:
    """Convert Rust memory ``retrieve()`` JSON to a list of results."""
    from nicx.memoria.armazenamento._stubs import RetrievalResult

    items = json.loads(json_str)
    results: List[RetrievalResult] = []
    for item in items:
        meta = item.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        results.append(
            RetrievalResult(
                content=item.get("content", ""),
                score=float(item.get("score", 0.0)),
                source=item.get("source", ""),
                metadata=meta,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Phase 2 converters — optimization & engine types
# ---------------------------------------------------------------------------


def generate_result_from_json(json_str: str) -> dict:
    """Convert Rust GenerateResult JSON to a Python dict."""
    data = json.loads(json_str)
    return {
        "content": data.get("content", ""),
        "model": data.get("model", ""),
        "finish_reason": data.get("finish_reason", "stop"),
        "usage": data.get("usage", {}),
        "tool_calls": data.get("tool_calls"),
        "ttft": data.get("ttft", 0.0),
        "cost_usd": data.get("cost_usd", 0.0),
        "metadata": data.get("metadata", {}),
    }


__all__ = [
    "RUST_AVAILABLE",
    "generate_result_from_json",
    "get_rust_module",
    "injection_result_from_json",
    "retrieval_results_from_json",
    "scan_result_from_json",
]
