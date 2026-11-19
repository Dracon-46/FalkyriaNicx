"""Modo Trabalho: o Nicx faz uma tarefa numa pasta do computador.

A pessoa escolhe a pasta e descreve a tarefa ("organiza essas notas por mês e
faz uma planilha resumo"). O modelo local monta um plano curto, a pessoa
aprova, e ele executa passo a passo com ferramentas presas àquela pasta.

- :mod:`pasta`: a guarda. Todo caminho é resolvido e tem que ficar dentro da
  pasta; arquivos e pastas de segredo nunca passam.
- :mod:`ferramentas`: listar, ler (texto, Word, PDF, Excel), escrever, criar
  planilha e documento, criar pasta, mover, apagar e pesquisar na web. Antes
  de mudar qualquer coisa, guarda como desfazer; apagar pede confirmação e vai
  para uma lixeira da tarefa.
- :mod:`modelo`: a tarefa (plano, passos, registro, diário de mudanças), salva
  em ``~/.nicx/trabalho/<id>/``.
- :mod:`executor`: planeja e executa com o modelo (Parar e Pausar valem a
  qualquer momento).
- :mod:`servico`: roda em segundo plano e responde à página Trabalho.
"""

from __future__ import annotations
