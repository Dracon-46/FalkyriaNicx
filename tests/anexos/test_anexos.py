"""Anexos do chat: imagens conferidas e reduzidas; vídeo vira quadros e fala."""

from __future__ import annotations

import base64
import io
from fractions import Fraction

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from nicx.anexos import AnexoInvalido, imagens  # noqa: E402


def _png(lado: tuple[int, int], cor=(200, 30, 30, 255), modo="RGBA") -> str:
    saida = io.BytesIO()
    Image.new(modo, lado, cor).save(saida, "PNG")
    return base64.b64encode(saida.getvalue()).decode()


def _abrir(b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64)))


def test_imagem_grande_e_reduzida_para_640():
    (saida,) = imagens.preparar([_png((2000, 1000))])
    img = _abrir(saida)
    assert max(img.size) == 640 and img.format == "JPEG"


def test_imagem_pequena_passa_como_veio():
    original = _png((100, 80), modo="RGB")
    assert imagens.preparar([original]) == [original]


def test_aceita_prefixo_data_url():
    (saida,) = imagens.preparar(["data:image/png;base64," + _png((50, 50))])
    assert _abrir(saida).size == (50, 50)


def test_foto_girada_pelo_exif_fica_em_pe():
    img = Image.new("RGB", (300, 100), (10, 10, 10))
    exif = img.getexif()
    exif[0x0112] = 6  # girar 90 graus
    saida = io.BytesIO()
    img.save(saida, "JPEG", exif=exif.tobytes())
    (pronta,) = imagens.preparar([base64.b64encode(saida.getvalue()).decode()])
    assert _abrir(pronta).size == (100, 300)


@pytest.mark.parametrize(
    ("lista", "mensagem"),
    [
        (["isso não é base64!!"], "base64"),
        ([base64.b64encode(b"texto qualquer").decode()], "abrir"),
        ([_png((10, 10))] * 5, "no máximo 4"),
    ],
)
def test_recusa_o_que_nao_serve(lista, mensagem):
    with pytest.raises(AnexoInvalido, match=mensagem):
        imagens.preparar(lista)


def test_recusa_imagem_de_mais_de_8_mb(monkeypatch):
    monkeypatch.setattr(imagens, "MAX_BYTES", 100)
    with pytest.raises(AnexoInvalido, match="grande demais"):
        imagens.preparar([_png((200, 200))])


# --- vídeo -------------------------------------------------------------------

av = pytest.importorskip("av")
np = pytest.importorskip("numpy")


def _video(caminho, segundos=2, com_audio=True):
    """Vídeo de teste: cada segundo de uma cor, com um tom de 440 Hz."""
    with av.open(str(caminho), "w", format="matroska") as saida:
        v = saida.add_stream("mpeg4", rate=10)
        v.width, v.height, v.pix_fmt = 320, 240, "yuv420p"
        a = None
        if com_audio:
            a = saida.add_stream("pcm_s16le", rate=16000)
            a.layout = "mono"
        for i in range(segundos * 10):
            cor = (255, 0, 0) if i < 10 else (0, 0, 255)
            quadro = av.VideoFrame.from_ndarray(
                np.full((240, 320, 3), cor, dtype=np.uint8), format="rgb24"
            )
            for pacote in v.encode(quadro):
                saida.mux(pacote)
        for pacote in v.encode():
            saida.mux(pacote)
        if a is not None:
            t = np.arange(segundos * 16000) / 16000
            tom = (np.sin(2 * np.pi * 440 * t) * 8000).astype(np.int16)
            som = av.AudioFrame.from_ndarray(
                tom.reshape(1, -1), format="s16", layout="mono"
            )
            som.sample_rate = 16000
            som.time_base = Fraction(1, 16000)
            for pacote in a.encode(som):
                saida.mux(pacote)
            for pacote in a.encode():
                saida.mux(pacote)


def test_video_vira_quadros_e_transcricao(tmp_path):
    from nicx.anexos import video

    caminho = tmp_path / "teste.mkv"
    _video(caminho)
    ouvido = {}

    def transcrever(som, language=None):
        ouvido["amostras"] = som.size
        ouvido["idioma"] = language
        return "olá do vídeo"

    resultado = video.extrair(caminho, transcrever=transcrever, idioma="pt")
    assert len(resultado.quadros) == 4
    assert 1.5 <= resultado.duracao <= 2.5
    assert resultado.tem_audio and resultado.transcricao == "olá do vídeo"
    assert ouvido["idioma"] == "pt"
    assert 16000 <= ouvido["amostras"] <= 2 * 16000 + 2000
    # Os quadros andam pelo vídeo: o primeiro é vermelho, o último azul.
    primeiro = _abrir(resultado.quadros[0]).convert("RGB").getpixel((10, 10))
    ultimo = _abrir(resultado.quadros[-1]).convert("RGB").getpixel((10, 10))
    assert primeiro[0] > 150 and ultimo[2] > 150


def test_video_sem_som_nao_transcreve(tmp_path):
    from nicx.anexos import video

    caminho = tmp_path / "mudo.mkv"
    _video(caminho, com_audio=False)
    chamado = []
    resultado = video.extrair(caminho, transcrever=lambda *a, **k: chamado.append(1))
    assert resultado.quadros and not resultado.tem_audio and chamado == []


def test_arquivo_que_nao_e_video(tmp_path):
    from nicx.anexos import video

    caminho = tmp_path / "x.mp4"
    caminho.write_bytes(b"nada de video aqui")
    with pytest.raises(AnexoInvalido):
        video.extrair(caminho)


def test_rota_do_video(tmp_path):
    pytest.importorskip("multipart")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.anexos import router

    caminho = tmp_path / "teste.mkv"
    _video(caminho)
    app = FastAPI()
    app.include_router(router)

    class _Fala:
        def transcrever_array(self, som, language=None):
            return f"fala em {language}"

    app.state.speech_backend = _Fala()
    client = TestClient(app)
    with caminho.open("rb") as arq:
        resposta = client.post(
            "/v1/anexos/video",
            files={"arquivo": ("teste.mkv", arq, "video/x-matroska")},
            data={"idioma": "pt-BR"},
        )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert len(corpo["quadros"]) == 4
    assert corpo["transcricao"] == "fala em pt" and corpo["transcrito"] is True
    # Nada fica no disco.
    import tempfile
    from pathlib import Path

    assert not list(Path(tempfile.gettempdir()).glob("nicx-video-*"))

    vazio = client.post(
        "/v1/anexos/video", files={"arquivo": ("v.mp4", b"", "video/mp4")}
    )
    assert vazio.status_code == 400
