"""Rotas /v1/ditado: ler e salvar ``[ditado]`` e o estado do ditado."""

from __future__ import annotations

import pytest
import tomllib
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.atalho import servico as atalho_servico
from nicx.atalho.windows import ERROR_HOTKEY_ALREADY_REGISTERED, ResultadoRegistro
from nicx.ditado.servico import ServicoDitado
from nicx.nucleo.config import NicxConfig
from nicx.servidor.rotas.atalho import router as atalho_router
from nicx.servidor.rotas.ditado import avisar_escuta, router


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
        '# minha config\n[engine]\ndefault = "ollama"\n\n[atalho]\nativo = true\n',
        encoding="utf-8",
    )
    cfg = NicxConfig()
    cfg._config_path = config_file
    application = FastAPI()
    application.include_router(router)
    application.include_router(atalho_router)
    application.state.config = cfg
    application.state.ditado = ServicoDitado(
        lambda: cfg, plataforma="win32", fabrica_escuta=FakeEscuta
    )
    application.state.atalho = atalho_servico.GerenciadorAtalho(
        object(), plataforma="win32", fabrica_escuta=FakeEscuta
    )
    FakeEscuta.resultado = ResultadoRegistro(True)
    return application


def test_le_padrao_desligado(app: FastAPI) -> None:
    corpo = TestClient(app).get("/v1/ditado").json()
    assert corpo == {
        "ativo": False,
        "teclas": "ctrl+alt+d",
        "rotulo": "Ctrl + Alt + D",
        "modo": "alternar",
        "idioma": "",
        "som": True,
        "modos": ["alternar", "segurar"],
        "idiomas": ["pt-BR", "en", "es", "zh", "hi", "ar", "fr"],
        "estado": "desligado",
        "mensagem": "",
        "suportado": True,
    }
    assert TestClient(app).get("/v1/ditado/estado").json() == {"estado": "desligado"}


def test_salva_sem_apagar_o_resto_e_fica_pronto(app: FastAPI) -> None:
    cliente = TestClient(app)
    resposta = cliente.put(
        "/v1/ditado",
        json={
            "ativo": True,
            "teclas": "Shift + Ctrl + F9",
            "modo": "segurar",
            "idioma": "en",
            "som": False,
        },
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["estado"] == "pronto"
    assert corpo["teclas"] == "ctrl+shift+f9"
    assert corpo["rotulo"] == "Ctrl + Shift + F9"

    path = app.state.config._config_path
    texto = path.read_text(encoding="utf-8")
    assert "# minha config" in texto
    gravado = tomllib.loads(texto)
    assert gravado["engine"]["default"] == "ollama"
    assert gravado["atalho"] == {"ativo": True}
    assert gravado["ditado"] == {
        "ativo": True,
        "teclas": "ctrl+shift+f9",
        "modo": "segurar",
        "idioma": "en",
        "som": False,
    }
    assert cliente.get("/v1/ditado/estado").json() == {"estado": "pronto"}

    # Só a chave enviada muda; idioma vazio volta ao de [speech].
    cliente.put("/v1/ditado", json={"ativo": False, "idioma": ""})
    gravado = tomllib.loads(path.read_text(encoding="utf-8"))
    assert gravado["ditado"]["ativo"] is False
    assert gravado["ditado"]["idioma"] == ""
    assert gravado["ditado"]["modo"] == "segurar"
    assert cliente.get("/v1/ditado").json()["estado"] == "desligado"


def test_combinacao_em_uso_aparece_no_estado(app: FastAPI) -> None:
    FakeEscuta.resultado = ResultadoRegistro(
        False,
        ERROR_HOTKEY_ALREADY_REGISTERED,
        "A combinação já está em uso por outro programa.",
    )
    corpo = TestClient(app).put("/v1/ditado", json={"ativo": True}).json()
    assert corpo["estado"] == "em_uso"
    assert corpo["ativo"] is True


@pytest.mark.parametrize(
    ("corpo", "trecho"),
    [
        ({"teclas": "ctrl+alt+n"}, "atalho que chama o Nicx"),
        ({"teclas": "Alt + Ctrl + N"}, "atalho que chama o Nicx"),
        ({"teclas": "ctrl+c"}, "do sistema"),
        ({"teclas": "d"}, "Ctrl, Alt ou Win"),
        ({"modo": "sussurrar"}, "Modo desconhecido"),
        ({"idioma": "klingon"}, "Idioma desconhecido"),
    ],
)
def test_recusa_entrada_invalida_sem_gravar(
    app: FastAPI, corpo: dict, trecho: str
) -> None:
    antes = app.state.config._config_path.read_text(encoding="utf-8")
    resposta = TestClient(app).put("/v1/ditado", json=corpo)
    assert resposta.status_code == 400
    assert trecho in resposta.json()["detail"]
    assert app.state.config._config_path.read_text(encoding="utf-8") == antes


def test_atalho_do_nicx_recusa_a_combinacao_do_ditado(app: FastAPI) -> None:
    resposta = TestClient(app).put("/v1/atalho", json={"teclas": "Ctrl+Alt+D"})
    assert resposta.status_code == 400
    assert "atalho do ditado" in resposta.json()["detail"]


def test_ditado_deixa_a_escuta_quieta(app: FastAPI) -> None:
    avisar_escuta(app, True)
    assert app.state.wake_busy.busy()
    avisar_escuta(app, False)
    assert not app.state.wake_busy.busy()
