"""Rotas /v1/atalho: ler e salvar ``[atalho]`` e o estado do registro."""

from __future__ import annotations

import pytest
import tomllib
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.atalho import servico
from nicx.atalho.windows import ERROR_HOTKEY_ALREADY_REGISTERED, ResultadoRegistro
from nicx.nucleo.config import NicxConfig
from nicx.servidor.rotas.atalho import router


class FakeEscuta:
    resultado = ResultadoRegistro(True)

    def __init__(self, combinacao, _ao_apertar) -> None:
        self.combinacao = combinacao

    def iniciar(self) -> ResultadoRegistro:
        return type(self).resultado

    def parar(self) -> None:
        pass


@pytest.fixture
def app(tmp_path) -> FastAPI:
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '# minha config\n[engine]\ndefault = "ollama"\n\n[speech]\nwake_word = false\n',
        encoding="utf-8",
    )
    cfg = NicxConfig()
    cfg._config_path = config_file
    application = FastAPI()
    application.include_router(router)
    application.state.config = cfg
    application.state.atalho = servico.GerenciadorAtalho(
        object(), plataforma="win32", fabrica_escuta=FakeEscuta
    )
    FakeEscuta.resultado = ResultadoRegistro(True)
    return application


def test_le_padrao_desligado(app: FastAPI) -> None:
    resposta = TestClient(app).get("/v1/atalho")
    assert resposta.status_code == 200
    assert resposta.json() == {
        "ativo": False,
        "teclas": "ctrl+alt+n",
        "rotulo": "Ctrl + Alt + N",
        "acao": "flutuante",
        "estado": "desligado",
        "mensagem": "",
        "suportado": True,
    }


def test_salva_sem_apagar_o_resto_e_registra(app: FastAPI) -> None:
    resposta = TestClient(app).put(
        "/v1/atalho",
        json={"ativo": True, "teclas": "Shift + Ctrl + Space", "acao": "app"},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["estado"] == "registrado"
    assert corpo["teclas"] == "ctrl+shift+space"
    assert corpo["rotulo"] == "Ctrl + Shift + Espaço"

    path = app.state.config._config_path
    texto = path.read_text(encoding="utf-8")
    assert "# minha config" in texto
    gravado = tomllib.loads(texto)
    assert gravado["engine"]["default"] == "ollama"
    assert gravado["speech"]["wake_word"] is False
    assert gravado["atalho"] == {
        "ativo": True,
        "teclas": "ctrl+shift+space",
        "acao": "app",
    }

    # Só a chave enviada muda.
    TestClient(app).put("/v1/atalho", json={"ativo": False})
    gravado = tomllib.loads(path.read_text(encoding="utf-8"))
    assert gravado["atalho"] == {
        "ativo": False,
        "teclas": "ctrl+shift+space",
        "acao": "app",
    }
    assert TestClient(app).get("/v1/atalho").json()["estado"] == "desligado"


def test_combinacao_em_uso_aparece_no_estado(app: FastAPI) -> None:
    FakeEscuta.resultado = ResultadoRegistro(
        False,
        ERROR_HOTKEY_ALREADY_REGISTERED,
        "A combinação já está em uso por outro programa.",
    )
    corpo = TestClient(app).put("/v1/atalho", json={"ativo": True}).json()
    assert corpo["estado"] == "em_uso"
    assert "em uso" in corpo["mensagem"]
    assert corpo["ativo"] is True  # a escolha fica salva; o usuário troca a combinação


@pytest.mark.parametrize(
    ("corpo", "trecho"),
    [
        ({"teclas": "ctrl+alt+del"}, "do sistema"),
        ({"teclas": "win+l"}, "do sistema"),
        ({"teclas": "n"}, "Ctrl, Alt ou Win"),
        ({"acao": "explodir"}, "Ação desconhecida"),
    ],
)
def test_recusa_entrada_invalida_sem_gravar(
    app: FastAPI, corpo: dict, trecho: str
) -> None:
    antes = app.state.config._config_path.read_text(encoding="utf-8")
    resposta = TestClient(app).put("/v1/atalho", json=corpo)
    assert resposta.status_code == 400
    assert trecho in resposta.json()["detail"]
    assert app.state.config._config_path.read_text(encoding="utf-8") == antes
