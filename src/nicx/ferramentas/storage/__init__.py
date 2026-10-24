"""Storage primitive — persistent searchable storage."""

from __future__ import annotations

# Always-available backend
import nicx.ferramentas.storage.sqlite  # noqa: F401

# Optional backends — import to trigger registration
try:
    import nicx.ferramentas.storage.bm25  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.storage.faiss_backend  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.storage.colbert_backend  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.storage.hybrid  # noqa: F401
except ImportError:
    pass

try:
    import nicx.ferramentas.storage.dense  # noqa: F401
except ImportError:
    pass

from nicx.ferramentas.storage._stubs import MemoryBackend, RetrievalResult
from nicx.ferramentas.storage.chunking import Chunk, ChunkConfig, chunk_text
from nicx.ferramentas.storage.context import ContextConfig, inject_context
from nicx.ferramentas.storage.ingest import ingest_path, read_document

__all__ = [
    "Chunk",
    "ChunkConfig",
    "ContextConfig",
    "MemoryBackend",
    "RetrievalResult",
    "chunk_text",
    "inject_context",
    "ingest_path",
    "read_document",
]
