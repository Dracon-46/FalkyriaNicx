"""O que mudou em cada versão do Nicx (a mais nova primeiro).

Vai junto no app (página Atualizações, mesmo sem internet) e no arquivo de
versões assinado (:func:`nicx.atualizacao.manifesto.montar`), para quem ainda
está numa versão antiga ver o que vem na nova. Ao lançar uma versão,
acrescente o item dela no topo.
"""

from __future__ import annotations

NOVIDADES: list[dict] = [
    {
        "versao": "0.2.1",
        "data": "2026-11-05",
        "titulo": "Respostas que chegam e atualização pelo app",
        "itens": [
            "Atualizações pelo próprio app: a página Atualizações mostra as novidades "
            "e instala a versão nova por cima, sem perder conversas nem configurações.",
            "Imagens e vídeos no chat: anexe pelo clipe, cole um print ou arraste. "
            "O Nicx enxerga as imagens e, nos vídeos, olha alguns quadros e ouve o "
            "áudio, tudo no seu PC.",
            "Quando o Ollama falha (por exemplo, a placa de vídeo cai), o erro aparece "
            "na tela e o Nicx tenta de novo só no processador, em vez de ficar sem "
            "responder.",
            "O botão Parar agora para o modelo de verdade: a próxima pergunta não "
            "espera mais atrás de uma resposta abandonada.",
            "O agente tem prazo e sempre termina com uma resposta; histórico longo e "
            "limite de resposta exagerado não deixam mais tudo lento.",
            "Instalação mais rápida, com o Ollama testado e as ferramentas padrão "
            "ligadas; downloads interrompidos continuam de onde pararam.",
            "Privacidade: se a política mudar, o app pergunta de novo; pacotes não "
            "escolhem mais a confiança dos servidores MCP nem levam chaves ao serem "
            "exportados.",
            "Erros com o motivo, Enter no login da Conta Falkyria, confirmação ao "
            "apagar conversa e opções da memória que valem de verdade.",
        ],
    },
    {
        "versao": "0.2.0",
        "data": "2026-11-04",
        "titulo": "Extensões, loja e Conta Falkyria",
        "itens": [
            "Extensões: servidores MCP, habilidades e pacotes por profissão.",
            "Loja da Falkyria com pacotes assinados.",
            "Conta Falkyria opcional, com backup criptografado no seu PC.",
            "Construtor de assistentes, rotinas, planejador e histórico com desfazer.",
        ],
    },
    {
        "versao": "0.1.0",
        "data": "2026-10-29",
        "titulo": "Primeira versão",
        "itens": [
            "O Nicx rodando no seu computador, com modelo local, voz em português e "
            "ações rápidas no Windows.",
        ],
    },
]


__all__ = ["NOVIDADES"]
