"""Atalho global de teclado: chama o Nicx de qualquer janela.

Configurado em ``[atalho]`` (``ativo``, ``teclas``, ``acao``); desligado por
padrão. Só no Windows (``RegisterHotKey`` via ``ctypes``, sem dependências);
nos outros sistemas o servidor apenas registra no log que não há suporte.

- :mod:`nicx.atalho.teclas`: ler e validar combinações (``"ctrl+alt+n"``).
- :mod:`nicx.atalho.windows`: registro e laço de mensagens do Windows.
- :mod:`nicx.atalho.acao`: abrir o mascote flutuante ou o app (uma janela só).
- :mod:`nicx.atalho.servico`: liga/desliga junto com o servidor e grava o config.
"""
