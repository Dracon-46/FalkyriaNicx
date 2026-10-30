"""Ditado universal: atalho em qualquer programa, fala, e o texto é digitado
onde está o cursor.

Configurado em ``[ditado]`` (``ativo``, ``teclas``, ``modo``, ``idioma``,
``som``); desligado por padrão e só no Windows. Tudo local: microfone, VAD e
Whisper na própria máquina; nenhum áudio vai para o disco e o texto não vai
para a memória nem para os logs.

- :mod:`nicx.ditado.gravacao`: microfone até parar (atalho, silêncio, 60 s).
- :mod:`nicx.ditado.comandos`: "nova linha", "ponto final", "vírgula"...
- :mod:`nicx.ditado.digitar`: devolve o foco e digita (``SendInput`` Unicode).
- :mod:`nicx.ditado.servico`: estados, atalho e o fluxo de cada ditado.
"""
