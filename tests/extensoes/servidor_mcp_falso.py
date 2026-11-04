"""Servidor MCP mínimo (stdio, JSON por linha) para os testes das extensões.

Ferramentas: ``eco_falkyria`` (devolve o texto) e ``ambiente_falkyria`` (o
valor da variável ``NICX_TESTE``, para conferir o ``env``).
"""

import json
import os
import sys

FERRAMENTAS = [
    {
        "name": "eco_falkyria",
        "description": "Devolve o texto recebido.",
        "inputSchema": {"type": "object", "properties": {"texto": {"type": "string"}}},
    },
    {
        "name": "ambiente_falkyria",
        "description": "Lê a variável NICX_TESTE.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def responder(pedido):
    metodo = pedido.get("method")
    if metodo == "initialize":
        return {
            "protocolVersion": "2025-03-26",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "falso", "version": "1"},
        }
    if metodo == "tools/list":
        return {"tools": FERRAMENTAS}
    if metodo == "tools/call":
        nome = pedido["params"]["name"]
        args = pedido["params"].get("arguments") or {}
        texto = (
            args.get("texto", "")
            if nome == "eco_falkyria"
            else os.environ.get("NICX_TESTE", "")
        )
        return {"content": [{"type": "text", "text": texto}], "isError": False}
    return {}


for linha in sys.stdin:
    try:
        pedido = json.loads(linha)
    except ValueError:
        continue
    if "id" not in pedido:
        continue  # notificação
    resposta = {"jsonrpc": "2.0", "id": pedido["id"], "result": responder(pedido)}
    sys.stdout.write(json.dumps(resposta) + "\n")
    sys.stdout.flush()
