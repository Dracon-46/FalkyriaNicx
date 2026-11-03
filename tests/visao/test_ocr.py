"""OCR do Windows e o uso dele no contexto (janela sem texto, imagem copiada)."""

from __future__ import annotations

import sys

import pytest

from nicx.contexto import area_transferencia, janela, selecao, servico
from nicx.contexto.montagem import Leitura as LeituraArea
from nicx.visao import ocr

windows = pytest.mark.skipif(sys.platform != "win32", reason="OCR do Windows")


@windows
def test_ocr_real_de_um_arquivo(tmp_path):
    """Gera uma imagem com texto (System.Drawing) e lê de volta."""
    import subprocess

    caminho = tmp_path / "texto.png"
    script = (
        "Add-Type -AssemblyName System.Drawing;"
        "$b = New-Object System.Drawing.Bitmap 900, 140;"
        "$g = [System.Drawing.Graphics]::FromImage($b);"
        "$g.Clear([System.Drawing.Color]::White);"
        "$f = New-Object System.Drawing.Font 'Segoe UI', 30;"
        "$g.DrawString('Relatorio de vendas 2026', $f,"
        " [System.Drawing.Brushes]::Black, 20, 30);"
        f"$g.Dispose(); $b.Save('{caminho}'); $b.Dispose()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=True,
        capture_output=True,
    )
    lido = ocr.ler_arquivo(caminho)
    if lido.motivo == "sem_idioma":
        pytest.skip("sem idioma de OCR instalado")
    assert lido.ok and "vendas" in lido.texto.lower() and "2026" in lido.texto


@windows
def test_arquivo_que_nao_existe(tmp_path):
    assert ocr.ler_arquivo(tmp_path / "nada.png").motivo == "sem_arquivo"


def test_fora_do_windows(monkeypatch):
    monkeypatch.setattr(ocr.sys, "platform", "linux")
    assert ocr.ler_janela(1) == ocr.Leitura(False, motivo="sem_suporte")


def test_idioma_do_ocr():
    assert ocr._idioma_ocr("en") == "en-US" and ocr._idioma_ocr(None) == "pt-BR"


# --------------------------------------------------------------------- contexto
def _janela_sem_texto(monkeypatch, rotulos=""):
    info = janela.InfoJanela(hwnd=42, titulo="Fotos", processo="Photos.exe", pid=1)
    monkeypatch.setattr(servico.sys, "platform", "win32")
    monkeypatch.setattr(janela, "sensivel", lambda _i: False)
    monkeypatch.setattr(janela, "esta_na_frente", lambda _i: False)
    monkeypatch.setattr(
        selecao,
        "ler_texto_da_janela",
        lambda *_a, **_k: selecao.TextoDaJanela(rotulos=rotulos),
    )
    return info


def test_janela_sem_texto_usa_ocr(monkeypatch):
    info = _janela_sem_texto(monkeypatch, rotulos="Arquivo Editar")
    monkeypatch.setattr(
        servico,
        "_ocr_janela",
        lambda hwnd, idioma: ocr.Leitura(True, texto="Nota fiscal 123\nTotal R$ 50,00"),
    )
    preparo = servico.capturar_janela(5000, achar_janela=lambda: info, ocr=True)
    assert preparo.captura.fonte == "tela" and "Nota fiscal" in preparo.captura.texto


def test_ocr_desligado_fica_com_os_rotulos(monkeypatch):
    info = _janela_sem_texto(monkeypatch, rotulos="Arquivo Editar")
    chamou = []
    monkeypatch.setattr(servico, "_ocr_janela", lambda *a: chamou.append(a))
    preparo = servico.capturar_janela(5000, achar_janela=lambda: info, ocr=False)
    assert preparo.captura.fonte == "janela" and chamou == []


def test_janela_sensivel_nunca_vai_para_o_ocr(monkeypatch):
    info = _janela_sem_texto(monkeypatch)
    monkeypatch.setattr(janela, "sensivel", lambda _i: True)
    monkeypatch.setattr(
        servico, "_ocr_janela", lambda *a: pytest.fail("não pode ler janela sensível")
    )
    preparo = servico.capturar_janela(5000, achar_janela=lambda: info, ocr=True)
    assert preparo.captura is None and preparo.resposta


def test_imagem_copiada(monkeypatch):
    monkeypatch.setattr(
        area_transferencia,
        "ler",
        lambda *_a, **_k: LeituraArea(motivo=area_transferencia.VAZIO),
    )
    monkeypatch.setattr(
        servico,
        "_ocr_area",
        lambda idioma: ocr.Leitura(True, texto="Erro 404: página não encontrada"),
    )
    preparo = servico.capturar_area(5000, ocr=True)
    assert preparo.captura.fonte == "imagem_copiada" and "404" in preparo.captura.texto
    monkeypatch.setattr(
        servico, "_ocr_area", lambda idioma: ocr.Leitura(False, motivo="sem_imagem")
    )
    assert servico.capturar_area(5000, ocr=True).captura is None
