"""Janela flutuante do mascote: pequena, sem moldura, sempre por cima, no
canto inferior direito, carregando a rota ``/flutuante`` da interface.

Usa o pywebview com o WebView2 que já vem no Windows. Enquanto o servidor
sobe, mostra "Iniciando o Nicx..."; depois carrega a interface, que liga a
conversa por voz sozinha. Se a janela não puder ser criada, abre a interface
no navegador já em "Conversa por voz".
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Any, Optional

from nicx.voz.escuta import runtime as rt

logger = logging.getLogger(__name__)

WIDTH = 300
HEIGHT = 420
MARGIN = 16

_LOADING_HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<style>
  html, body { margin: 0; height: 100%; background: #121211; color: #fcfcfb;
    font: 14px system-ui, sans-serif; overflow: hidden; }
  body { display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 14px; }
  .blob { width: 84px; height: 72px; border-radius: 50% 50% 46% 46%;
    background: radial-gradient(circle at 40% 35%, #b9f3ff, #5fd3e8 55%, #2aa7c4);
    box-shadow: 0 0 28px #5fd3e866; animation: b 1.6s ease-in-out infinite; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: #eda100;
    display: inline-block; margin-left: 4px; }
  p { margin: 0; color: #a8a7a2; }
  #msg { color: #fcfcfb; }
  @keyframes b { 50% { transform: scale(1.06, .94) translateY(3px); } }
</style></head>
<body class="pywebview-drag-region">
  <div class="blob"></div>
  <p id="msg">Iniciando o Nicx<span class="dot"></span></p>
  <p>Um instante, já vou te ouvir.</p>
</body></html>"""


def _work_area() -> Optional[tuple[int, int, int, int]]:
    """Área útil da tela principal (sem a barra de tarefas), em pixels lógicos."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
        rect = wintypes.RECT()
        if not user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
            return None
        try:
            scale = user32.GetDpiForSystem() / 96.0
        except Exception:
            scale = 1.0
        return (
            int(rect.left / scale),
            int(rect.top / scale),
            int(rect.right / scale),
            int(rect.bottom / scale),
        )
    except Exception as exc:
        logger.debug("Área de trabalho indisponível: %s", exc)
        return None


def _allow_microphone_for(origin: str) -> None:
    """Concede o microfone à interface local sem a pergunta do WebView2.

    Só para a origem do servidor do Nicx (127.0.0.1); qualquer outra página
    continua recebendo a pergunta padrão.
    """
    try:
        from webview.platforms import edgechromium
    except Exception:
        return
    original = edgechromium.EdgeChrome.on_webview_ready
    if getattr(original, "_nicx_patched", False):
        return

    def on_webview_ready(self: Any, sender: Any, args: Any) -> None:
        original(self, sender, args)
        if not args.IsSuccess:
            return
        try:
            from Microsoft.Web.WebView2.Core import (  # type: ignore[import-not-found]
                CoreWebView2PermissionKind,
                CoreWebView2PermissionState,
            )

            def on_permission(_sender: Any, event: Any) -> None:
                if (
                    str(event.Uri).startswith(origin)
                    and event.PermissionKind == CoreWebView2PermissionKind.Microphone
                ):
                    event.State = CoreWebView2PermissionState.Allow

            sender.CoreWebView2.PermissionRequested += on_permission
        except Exception as exc:
            logger.debug("Permissão do microfone não configurada: %s", exc)

    on_webview_ready._nicx_patched = True  # type: ignore[attr-defined]
    edgechromium.EdgeChrome.on_webview_ready = on_webview_ready


class _Api:
    """Exposto à página como ``window.pywebview.api``."""

    def __init__(self, since: Optional[float]) -> None:
        self._since = since
        # Privado: o pywebview expõe à página tudo que não começa com "_".
        self._window: Any = None

    def fechar(self) -> None:
        if self._window is not None:
            self._window.destroy()

    def problema(self, message: str) -> None:
        logger.warning("Mascote: %s", str(message)[:200])

    def pronto(self) -> None:
        if self._since:
            logger.info(
                "Mascote pronto para ouvir %.1f s após o fim da frase",
                time.time() - self._since,
            )


def run_mascot_window(
    base: str,
    *,
    since: Optional[float] = None,
    wait_timeout: float = 180.0,
) -> int:
    """Mostra a janela e bloqueia até ela fechar. Devolve o código de saída."""
    try:
        import webview
    except Exception as exc:
        logger.warning("Janela flutuante indisponível (%s): abrindo o navegador", exc)
        if rt.wait_for_server(base, wait_timeout):
            rt.open_in_browser(base)
            return 0
        return 1

    # A resposta é falada sem um clique antes: libera o autoplay só aqui.
    extra = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
    if "autoplay-policy" not in extra:
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
            f"{extra} --autoplay-policy=no-user-gesture-required".strip()
        )
    _allow_microphone_for(base)

    x = y = None
    area = _work_area()
    if area:
        left, top, right, bottom = area
        x = max(left, right - WIDTH - MARGIN)
        y = max(top, bottom - HEIGHT - MARGIN)

    api = _Api(since)
    window = webview.create_window(
        "Nicx",
        html=_LOADING_HTML,
        js_api=api,
        width=WIDTH,
        height=HEIGHT,
        x=x,
        y=y,
        resizable=False,
        frameless=True,
        easy_drag=False,
        on_top=True,
        background_color="#121211",
    )
    api._window = window

    def on_shown() -> None:
        if since:
            logger.info(
                "Janela visível %.1f s após o fim da frase", time.time() - since
            )

    window.events.shown += on_shown

    def load_interface() -> None:
        if rt.wait_for_server(base, wait_timeout):
            window.load_url(f"{base}{rt.FLOATING_ROUTE}")
            return
        window.evaluate_js(
            "document.getElementById('msg').textContent = "
            "'Não consegui iniciar o Nicx. Veja o arquivo server.log.'"
        )
        time.sleep(10)
        window.destroy()

    threading.Thread(target=load_interface, daemon=True).start()
    rt.WEBVIEW_DIR.mkdir(parents=True, exist_ok=True)
    try:
        webview.start(private_mode=False, storage_path=str(rt.WEBVIEW_DIR))
    except Exception as exc:
        logger.warning("Falha ao abrir a janela (%s): abrindo o navegador", exc)
        if rt.wait_for_server(base, wait_timeout):
            rt.open_in_browser(base)
            return 0
        return 1
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    """Entrada leve (``python -m nicx.voz.escuta.window``): sem carregar a CLI
    inteira, a janela aparece segundos antes."""
    import argparse

    parser = argparse.ArgumentParser(prog="nicx mascote")
    parser.add_argument("--url", default=None)
    parser.add_argument("--desde", type=float, default=None)
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logging.getLogger("pywebview").setLevel(logging.WARNING)
    base = (args.url or rt.server_base_url()).rstrip("/")
    if args.url is None and not rt.server_up(base, timeout=0.5):
        rt.start_server()
    return run_mascot_window(base, since=args.desde)


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main", "run_mascot_window"]
