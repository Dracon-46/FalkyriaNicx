"""Storage primitive — persistent searchable storage."""

from __future__ import annotations

# Always-available backend
import nicx.memoria.armazenamento.sqlite  # noqa: F401

# Optional backends — import to trigger registration
try:
    import nicx.memoria.armazenamento.bm25  # noqa: F401
except ImportError:
    pass

try:
    import nicx.memoria.armazenamento.faiss_backend  # noqa: F401
except ImportError:
    pass

try:
    import nicx.memoria.armazenamento.colbert_backend  # noqa: F401
except ImportError:
    pass

try:
    import nicx.memoria.armazenamento.hybrid  # noqa: F401
except ImportError:
    pass

try:
    import nicx.memoria.armazenamento.dense  # noqa: F401
except ImportError:
    pass

from nicx.memoria.armazenamento._stubs import MemoryBackend, RetrievalResult
from nicx.memoria.armazenamento.chunking import Chunk, ChunkConfig, chunk_text
from nicx.memoria.armazenamento.context import ContextConfig, inject_context
from nicx.memoria.armazenamento.ingest import ingest_path, read_document

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
