"""Atualizações do Nicx: novidades de cada versão e atualizar pelo app.

- :mod:`novidades`: o que mudou em cada versão (vai no app e no arquivo de
  versões da release).
- :mod:`manifesto`: o arquivo de versões ``nicx-atualizacao.json``, assinado
  pela Falkyria com a mesma chave Ed25519 da loja. O app só confia nele se a
  assinatura conferir; o instalador baixado ainda tem que bater com o sha256
  assinado.
- :mod:`servico`: procurar (uma vez por dia, se ``[atualizacao] automatica``),
  baixar e instalar. No Windows, o instalador novo roda por cima, sem tirar
  conversas nem configurações, e o Nicx volta sozinho.

Nada sobre o usuário vai no pedido: é só o download de um arquivo público.
"""

from __future__ import annotations
