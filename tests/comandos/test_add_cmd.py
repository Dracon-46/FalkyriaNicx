"""Tests for the ``nicx add`` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from nicx.comandos.recursos.add import add
from nicx.extensoes import catalogo_mcp


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch) -> Path:
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def _servidores(home: Path) -> list[dict]:
    return json.loads((home / "mcp.json").read_text(encoding="utf-8"))


class TestAddCmd:
    def test_add_help(self) -> None:
        result = CliRunner().invoke(add, ["--help"])
        assert result.exit_code == 0
        assert "servidor MCP" in result.output

    def test_add_unknown_server(self) -> None:
        result = CliRunner().invoke(add, ["unknown_server"])
        assert result.exit_code != 0
        assert "Servidor MCP desconhecido" in result.output
        assert "github" in result.output
        assert "filesystem" in result.output

    def test_add_known_server(self, home: Path) -> None:
        result = CliRunner().invoke(add, ["filesystem", "--args", "C:/pasta"])
        assert result.exit_code == 0
        assert "Servidor MCP adicionado: filesystem" in result.output
        (dados,) = _servidores(home)
        assert dados["comando"] == "npx"
        assert "@modelcontextprotocol/server-filesystem" in dados["args"]
        assert dados["args"][-1] == "C:/pasta"

    def test_add_with_key_and_again_updates(self, home: Path) -> None:
        assert CliRunner().invoke(add, ["github", "--key", "t1"]).exit_code == 0
        assert CliRunner().invoke(add, ["github", "--key", "t2"]).exit_code == 0
        (dados,) = _servidores(home)
        assert dados["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "t2"

    def test_catalogo_completo(self) -> None:
        chaves = [m.chave for m in catalogo_mcp.CATALOGO]
        assert len(chaves) == len(set(chaves))
        assert all(m.args and m.descricao for m in catalogo_mcp.CATALOGO)
