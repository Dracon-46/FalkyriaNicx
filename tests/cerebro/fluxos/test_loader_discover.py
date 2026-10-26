"""discover_workflows lê os fluxos de uma pasta e ignora arquivos quebrados."""

from __future__ import annotations

from nicx.cerebro.fluxos.loader import discover_workflows

_FLOW = """
[workflow]
name = "{name}"

[[workflow.nodes]]
id = "a"
type = "agent"
agent = "simple"
"""


def test_discover_reads_every_toml(tmp_path):
    (tmp_path / "um.toml").write_text(_FLOW.format(name="primeiro"), encoding="utf-8")
    (tmp_path / "dois.toml").write_text(_FLOW.format(name="segundo"), encoding="utf-8")
    (tmp_path / "quebrado.toml").write_text("isso não é toml [", encoding="utf-8")
    flows = discover_workflows(tmp_path)
    assert sorted(flows) == ["primeiro", "segundo"]


def test_missing_folder_means_no_workflows(tmp_path):
    assert discover_workflows(tmp_path / "nao-existe") == {}
