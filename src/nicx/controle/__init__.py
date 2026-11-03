"""Mexer nos apps pela acessibilidade do Windows (UI Automation).

"Clica em Salvar", "abre o menu Arquivo", "marca a caixa Lembrar",
"vai na aba Revisão", "escreve Falkyria no campo Pesquisar", "o que dá pra
clicar aqui?". O Nicx acha o controle pelo nome, na janela que você estava
usando, e aciona do jeito que o próprio app oferece (o mesmo caminho dos
leitores de tela): sem mover o mouse, sem foto da tela, em menos de 1 s.

Nunca mexe em janelas de senha ou de banco, nunca digita em campo de senha, e
botões que apagam, enviam ou pagam pedem "confirmo" antes. O que o modelo
decide clicar passa pelo nível de autonomia (:mod:`nicx.historico.autonomia`).
"""
