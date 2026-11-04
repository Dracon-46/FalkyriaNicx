"""Conta Falkyria: cripto, cofre, cadastro com aceite, sessão, backup e LGPD."""

from __future__ import annotations

import json
import sys
import time
import uuid
from types import SimpleNamespace

import httpx
import pytest

from nicx.conta import cofre, cripto, servico
from nicx.conta.cliente import ContaErro
from nicx.extensoes import habilidades


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(habilidades, "pasta", lambda: tmp_path / "home" / "skills")
    return tmp_path / "home"


class _Resposta:
    def __init__(self, status: int, corpo=None):
        self.status_code = status
        self._corpo = corpo
        self.content = b"" if corpo is None else json.dumps(corpo).encode()

    def json(self):
        return self._corpo


class _Supabase:
    """Auth e PostgREST em memória, com a regra de cada um ver só o seu."""

    def __init__(self):
        self.usuarios: dict[str, dict] = {}  # email -> usuário
        self.tokens: dict[str, str] = {}  # access token -> user id
        self.contas: dict[str, dict] = {}
        self.backups: list[dict] = []
        self.codigos: dict[str, str] = {}
        self.pedidos: list[tuple[str, str, dict]] = []

    def _sessao(self, u):
        token = uuid.uuid4().hex
        self.tokens[token] = u["id"]
        return {
            "access_token": token,
            "refresh_token": "r-" + token,
            "expires_in": 3600,
            "user": {"id": u["id"], "email": u["email"]},
        }

    def _uid(self, headers):
        token = headers.get("Authorization", "").removeprefix("Bearer ")
        return self.tokens.get(token)

    def request(self, metodo, url, json=None, params=None, headers=None, timeout=None):
        caminho = url.split(".supabase.co", 1)[1]
        params, headers, corpo = params or {}, headers or {}, json or {}
        self.pedidos.append((metodo, caminho, corpo))
        if caminho == "/auth/v1/signup":
            if corpo["email"] in self.usuarios:
                return _Resposta(422, {"error_code": "user_already_exists"})
            uid = str(uuid.uuid4())
            self.usuarios[corpo["email"]] = {
                "id": uid,
                "email": corpo["email"],
                "senha": corpo["password"],
                "ok": False,
            }
            meta = corpo.get("data", {})
            self.contas[uid] = {
                "id": uid,
                "nome": meta.get("nome", ""),
                "termos_versao": meta.get("termos_versao", ""),
                "politica_versao": meta.get("politica_versao", ""),
                "aceitou_em": "2026-11-04T10:00:00Z",
                "criado_em": "2026-11-04T10:00:00Z",
            }
            self.codigos[corpo["email"]] = "12345678"
            return _Resposta(200, {"id": uid})
        if caminho == "/auth/v1/verify":
            if self.codigos.get(corpo["email"]) != corpo["token"]:
                return _Resposta(403, {"error_code": "otp_expired"})
            u = self.usuarios[corpo["email"]]
            u["ok"] = True
            return _Resposta(200, self._sessao(u))
        if caminho == "/auth/v1/token":
            if params["grant_type"] == "password":
                u = self.usuarios.get(corpo["email"])
                if not u or u["senha"] != corpo["password"]:
                    return _Resposta(400, {"error_code": "invalid_credentials"})
                if not u["ok"]:
                    return _Resposta(400, {"error_code": "email_not_confirmed"})
                return _Resposta(200, self._sessao(u))
            uid = self.tokens.get(corpo["refresh_token"].removeprefix("r-"))
            if not uid:
                return _Resposta(400, {"error_code": "refresh_token_not_found"})
            u = next(x for x in self.usuarios.values() if x["id"] == uid)
            return _Resposta(200, self._sessao(u))
        if caminho in {"/auth/v1/recover", "/auth/v1/resend"}:
            return _Resposta(200, {})
        if caminho == "/auth/v1/logout":
            return _Resposta(204)
        if caminho == "/auth/v1/user":
            uid = self._uid(headers)
            u = next(x for x in self.usuarios.values() if x["id"] == uid)
            if metodo == "PUT":
                u["senha"] = corpo["password"]
            return _Resposta(200, {"id": uid, "email": u["email"], "created_at": "x"})
        uid = self._uid(headers)
        if uid is None:
            return _Resposta(401, {"code": "PGRST301"})
        if caminho == "/rest/v1/nicx_contas":
            if metodo == "GET":
                c = self.contas.get(uid)
                return _Resposta(200, [c] if c else [])
            self.contas.setdefault(uid, {"id": uid, "nome": ""}).update(
                {k: v for k, v in corpo.items() if k != "id"}
            )
            return _Resposta(204)
        if caminho == "/rest/v1/nicx_backups":
            if metodo == "POST":
                linha = {
                    "id": str(uuid.uuid4()),
                    "user_id": uid,
                    "tamanho": len(corpo["conteudo"]),
                    "criado_em": f"2026-11-04T10:{len(self.backups):02d}:00Z",
                    **corpo,
                }
                self.backups.append(linha)
                return _Resposta(201, [linha])
            meus = [b for b in self.backups if b["user_id"] == uid]
            if "id" in params:
                meus = [b for b in meus if b["id"] == params["id"].removeprefix("eq.")]
            if metodo == "DELETE":
                self.backups = [b for b in self.backups if b not in meus]
                return _Resposta(204)
            return _Resposta(200, meus)
        if caminho == "/rest/v1/rpc/nicx_apagar_conta":
            email = next(e for e, u in self.usuarios.items() if u["id"] == uid)
            del self.usuarios[email]
            self.contas.pop(uid, None)
            self.backups = [b for b in self.backups if b["user_id"] != uid]
            return _Resposta(204)
        raise AssertionError(caminho)


@pytest.fixture
def supabase(monkeypatch):
    falso = _Supabase()
    monkeypatch.setattr(httpx, "request", falso.request)
    return falso


EMAIL, SENHA = "pessoa@exemplo.com", "senhaforte123"


def _conta_pronta():
    servico.cadastrar(EMAIL, SENHA, "Pessoa", True)
    return servico.confirmar(EMAIL, "12345678")


# --------------------------------------------------------------------- cripto
def test_cripto_ida_e_volta_e_senha_errada():
    envelope = cripto.cifrar("Tutor de estudos", "senha-do-backup")
    assert "Tutor" not in envelope and json.loads(envelope)["kdf"] == "scrypt"
    assert cripto.decifrar(envelope, "senha-do-backup") == "Tutor de estudos"
    with pytest.raises(cripto.SenhaErrada, match="errada"):
        cripto.decifrar(envelope, "outra-senha")
    mexido = json.loads(envelope)
    mexido["dados"] = mexido["dados"][:-4] + "AAAA"
    with pytest.raises(cripto.SenhaErrada):
        cripto.decifrar(json.dumps(mexido), "senha-do-backup")
    with pytest.raises(ValueError):
        cripto.cifrar("x", "curta")


# ---------------------------------------------------------------------- cofre
def test_cofre_guarda_e_some(home):
    cofre.gravar({"access_token": "a", "refresh_token": "r"})
    assert cofre.ler()["access_token"] == "a"
    if sys.platform == "win32":  # DPAPI: o arquivo não tem o token em claro
        assert b"refresh_token" not in cofre.caminho().read_bytes()
    cofre.caminho().write_bytes(b"lixo")
    assert cofre.ler() is None and not cofre.caminho().exists()


# ----------------------------------------------------------- cadastro e login
def test_cadastro_exige_aceite_e_senha_forte(supabase):
    with pytest.raises(ContaErro, match="aceite"):
        servico.cadastrar(EMAIL, SENHA, "", False)
    with pytest.raises(ContaErro, match="senha fraca"):
        servico.cadastrar(EMAIL, "curta1", "", True)
    with pytest.raises(ContaErro, match="e-mail"):
        servico.cadastrar("sem-arroba", SENHA, "", True)
    assert supabase.pedidos == []


def test_cadastro_confirma_e_registra_o_aceite(supabase):
    assert servico.cadastrar(EMAIL, SENHA, "Pessoa", True) == {"confirmar": True}
    meta = supabase.pedidos[0][2]["data"]
    assert (
        meta["termos_versao"] and meta["politica_versao"] and meta["nome"] == "Pessoa"
    )
    with pytest.raises(ContaErro, match="confirme"):
        servico.entrar(EMAIL, SENHA)
    with pytest.raises(ContaErro, match="código errado"):
        servico.confirmar(EMAIL, "00000000")
    estado = servico.confirmar(EMAIL, "12345678")
    assert estado["conectado"] and estado["email"] == EMAIL
    assert estado["nome"] == "Pessoa" and not estado["precisa_aceitar"]


def test_entrar_sair_e_senha_errada(supabase):
    _conta_pronta()
    servico.sair()
    assert servico.estado()["conectado"] is False
    with pytest.raises(ContaErro, match="e-mail ou senha errados"):
        servico.entrar(EMAIL, "senhaerrada99")
    assert servico.entrar(EMAIL, SENHA)["conectado"]


def test_token_vencido_renova(supabase):
    _conta_pronta()
    sessao = cofre.ler()
    cofre.gravar({**sessao, "expires_at": int(time.time()) - 10})
    assert servico.estado()["conectado"]
    assert cofre.ler()["access_token"] != sessao["access_token"]


def test_conta_antiga_precisa_aceitar(supabase):
    _conta_pronta()
    uid = cofre.ler()["user_id"]
    supabase.contas[uid]["termos_versao"] = "2020-01-01"
    assert servico.estado()["precisa_aceitar"]
    with pytest.raises(ContaErro, match="aceite"):
        servico.fazer_backup("senha-do-backup")
    assert not servico.aceitar()["precisa_aceitar"]


def test_esqueci_a_senha(supabase):
    _conta_pronta()
    servico.sair()
    servico.esqueci(EMAIL)
    supabase.codigos[EMAIL] = "87654321"
    servico.redefinir(EMAIL, "87654321", "outrasenha456")
    servico.sair()
    assert servico.entrar(EMAIL, "outrasenha456")["conectado"]


# --------------------------------------------------------------------- backup
def _meus_itens():
    from nicx.assistentes import armazenamento as assistentes
    from nicx.assistentes.modelo import Assistente
    from nicx.extensoes import mcp

    assistentes.criar(Assistente(nome="Tutor secreto", instrucoes="Explique."))
    habilidades.salvar("Ata", "Para atas.", "Liste decisões.")
    mcp.criar(
        mcp.Servidor.de_dict(
            {
                "nome": "gh",
                "comando": "npx",
                "args": ["x"],
                "env": {"TOKEN": "segredo-gh"},
            }
        )
    )


def _apagar_tudo_local():
    from nicx.assistentes import armazenamento as assistentes
    from nicx.extensoes import mcp

    for a in assistentes.listar():
        assistentes.apagar(a.id)
    for h in habilidades.listar():
        habilidades.apagar(h.nome)
    for s in mcp.listar():
        mcp.apagar(s.id)


def test_backup_cifrado_e_restaurar_em_outro_pc(supabase):
    from nicx.assistentes import armazenamento as assistentes
    from nicx.extensoes import mcp, pacotes

    _conta_pronta()
    with pytest.raises(ValueError, match="guardar"):
        servico.fazer_backup("senha-do-backup")
    _meus_itens()
    feito = servico.fazer_backup("senha-do-backup", "Meu notebook")
    assert feito["resumo"]["assistentes"] == 1 and feito["rotulo"] == "Meu notebook"
    guardado = supabase.backups[0]["conteudo"]
    assert "Tutor secreto" not in guardado and "segredo-gh" not in guardado
    assert [b["rotulo"] for b in servico.listar_backups()] == ["Meu notebook"]

    _apagar_tudo_local()  # "outro PC"
    with pytest.raises(ContaErro, match="senha do backup errada"):
        servico.restaurar(feito["id"], "senha-errada!")
    assert servico.previa_backup(feito["id"], "senha-do-backup")["habilidades"] == 1
    servico.restaurar(feito["id"], "senha-do-backup")
    assert [a.nome for a in assistentes.listar()] == ["Tutor secreto"]
    assert habilidades.obter("ata").origem == "nicx"
    (servidor,) = mcp.listar()
    assert (
        servidor.env == {"TOKEN": ""} and not servidor.ativo and servidor.pacote == ""
    )
    assert pacotes.instalados() == []  # restaurado é seu, não de um pacote

    servico.restaurar(feito["id"], "senha-do-backup")  # de novo: nada duplica
    assert len(assistentes.listar()) == 1 and len(mcp.listar()) == 1


def test_outra_conta_nao_ve_o_backup(supabase):
    _conta_pronta()
    _meus_itens()
    feito = servico.fazer_backup("senha-do-backup")
    servico.sair()
    servico.cadastrar("outra@exemplo.com", SENHA, "", True)
    supabase.codigos["outra@exemplo.com"] = "11112222"
    servico.confirmar("outra@exemplo.com", "11112222")
    assert servico.listar_backups() == []
    with pytest.raises(ContaErro, match="não encontrado"):
        servico.restaurar(feito["id"], "senha-do-backup")


# ----------------------------------------------------------------------- LGPD
def test_exportar_e_apagar_conta(supabase):
    _conta_pronta()
    _meus_itens()
    servico.fazer_backup("senha-do-backup")
    dados = servico.exportar()
    assert dados["conta"]["email"] == EMAIL and dados["perfil"]["nome"] == "Pessoa"
    assert len(dados["backups"]) == 1 and "cifrados" in dados["observacao"]
    with pytest.raises(ContaErro, match="e-mail ou senha"):
        servico.apagar_conta("senhaerrada99")
    servico.apagar_conta(SENHA)
    assert supabase.usuarios == {} and supabase.backups == [] and supabase.contas == {}
    assert cofre.ler() is None and servico.estado()["conectado"] is False


def test_rotas(supabase):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.conta import router

    app = FastAPI()
    app.include_router(router)
    app.state = SimpleNamespace(agent=None, bus=None)  # o restaurar religa extensões
    client = TestClient(app)
    assert client.get("/v1/conta").json()["conectado"] is False
    corpo = {"email": EMAIL, "senha": SENHA, "nome": "P", "aceitou": False}
    assert client.post("/v1/conta/cadastrar", json=corpo).status_code == 400
    corpo["aceitou"] = True
    assert client.post("/v1/conta/cadastrar", json=corpo).json() == {"confirmar": True}
    confirmado = client.post(
        "/v1/conta/confirmar", json={"email": EMAIL, "codigo": "12345678"}
    )
    assert confirmado.json()["conectado"]
    assert client.get("/v1/conta/backups").json() == {"backups": []}
    resposta = client.post("/v1/conta/backups", json={"senha": "senha-do-backup"})
    assert resposta.status_code == 400  # nada para guardar
    assert client.post("/v1/conta/sair").json() == {"ok": True}
    assert client.get("/v1/conta/backups").status_code == 401
