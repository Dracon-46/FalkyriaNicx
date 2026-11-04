"""Chaves públicas da Falkyria que assinam os pacotes da loja (id -> Ed25519 em base64).

A privada fica só no PC da Falkyria (``~/.falkyria-loja/``). Trocar de chave:
gerar outra, acrescentar aqui e lançar uma versão nova do Nicx; a antiga só sai
depois que os pacotes forem assinados de novo.
"""

CHAVES_CONFIAVEIS: dict[str, str] = {
    # Falkyria, 2026-11-04
    "c3288a738cbd09a1": "y8YRHMY1xCJszEw9VwKfiKxLaWeUGdd9Yk4RXgnttvI=",
}
