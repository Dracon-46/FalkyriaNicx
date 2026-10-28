"""Live smoke test — full pipeline with real markdown files.

NOT mocked. Uses the actual Nicx docs/ directory as an Obsidian-like vault.
Exercises: ObsidianConnector → SyncEngine → KnowledgeStore → knowledge_search tool.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nicx.conectores.obsidian import ObsidianConnector
from nicx.conectores.pipeline import IngestionPipeline
from nicx.conectores.store import KnowledgeStore
from nicx.conectores.sync_engine import SyncEngine
from nicx.ferramentas.conhecimento.knowledge_search import KnowledgeSearchTool

# Use the real Nicx docs directory
DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"


@pytest.mark.live
def test_live_obsidian_full_pipeline(tmp_path: Path) -> None:
    """Smoke test: index real .md files, then search them."""
    assert DOCS_DIR.is_dir(), f"Docs dir not found: {DOCS_DIR}"

    # 1. Set up the full pipeline
    store = KnowledgeStore(db_path=str(tmp_path / "live.db"))
    pipeline = IngestionPipeline(store=store, max_tokens=256)
    engine = SyncEngine(
        pipeline=pipeline,
        state_db=str(tmp_path / "state.db"),
    )
    connector = ObsidianConnector(vault_path=str(DOCS_DIR))

    # Windows does not delete open SQLite files: close both before cleanup.
    try:
        # 2. Verify connection
        assert connector.is_connected(), "Connector should see docs dir"

        # 3. Sync — this reads real files
        items = engine.sync(connector)
        print(f"\n  Synced {items} chunks from {DOCS_DIR}")
        assert items > 0, "Should have indexed some chunks"

        # 4. Verify checkpoint
        cp = engine.get_checkpoint("obsidian")
        assert cp is not None
        assert cp["items_synced"] > 0
        print(f"  Checkpoint: {cp['items_synced']} items synced")

        # 5. Search via knowledge_search tool
        tool = KnowledgeSearchTool(store=store)

        # Search for architecture concepts (should be in docs/)
        result = tool.execute(query="agent")
        assert result.success, f"Search failed: {result.content}"
        assert result.metadata["num_results"] > 0
        print(f"  'agent' query: {result.metadata['num_results']} results")

        # Search for engine/inference
        result = tool.execute(query="inference engine")
        assert result.success
        print(f"  'inference engine' query: {result.metadata['num_results']} results")

        # Search with source filter
        result = tool.execute(query="agent", source="obsidian")
        assert result.success
        assert result.metadata["num_results"] > 0

        # Search for nonexistent content
        result = tool.execute(query="xyzzy999nonexistent")
        assert result.success
        assert "No relevant results" in result.content

        # 6. Verify result quality — check that results have metadata
        result = tool.execute(query="registry pattern")
        if result.metadata["num_results"] > 0:
            # Results should have source attribution
            assert "[obsidian]" in result.content
            print("  'registry pattern': found with attribution")

        print(
            f"\n  SMOKE TEST PASSED — {items} chunks indexed, search working end-to-end"
        )
    finally:
        engine.close()
        store.close()
