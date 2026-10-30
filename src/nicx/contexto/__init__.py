"""Contexto do que o usuário está vendo: área de transferência e janela aberta.

"Resume o que eu copiei", "explica isso aqui", "o que é esse erro?",
"resume essa página", "onde eu tô?". O Nicx lê o texto copiado ou o da
janela que estava em uso antes dele (seleção, documento, arquivo aberto) e
manda ao modelo local junto com o pedido, no fim da mensagem, marcado como
dado e não como instrução.

- :mod:`.pedidos`: reconhece as frases (pt, en, es, fr);
- :mod:`.area_transferencia`: lê o texto copiado (Windows, só leitura);
- :mod:`.janela`: a janela de fora do Nicx, o arquivo no título, as
  janelas sensíveis (senhas, bancos) que não são lidas;
- :mod:`.selecao`: seleção e texto da janela pela acessibilidade (UI
  Automation) e, se o usuário ligar, Ctrl+C;
- :mod:`.arquivo_aberto`: acha e lê o arquivo só nas pastas do usuário;
- :mod:`.montagem`: o bloco de contexto, os marcadores e o corte por tokens;
- :mod:`.servico`: junta tudo; :mod:`.ferramenta`: a ferramenta ``contexto``.

Nada sai do PC, nada vai para a memória automática e o conteúdo nunca é
logado. Configuração em ``[contexto]`` (``ativo``, ``copiar_selecao``,
``max_caracteres``, ``pastas_extras``).

O pacote não importa nada por conta própria: ``montagem`` é usado pelos
rastros e pela memória sem puxar o resto.
"""
