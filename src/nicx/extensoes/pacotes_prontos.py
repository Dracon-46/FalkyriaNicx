# ruff: noqa: E501  (textos dos pacotes: uma linha por campo fica mais legível)
"""Pacotes prontos por profissão (Falkyria): assistentes, rotinas e habilidades.

Nada de servidor MCP aqui (rodam programas no PC: só o usuário escolhe). Nome
e descrição do pacote vêm das traduções do frontend pelo ``id``; o conteúdo vem
em português ou inglês (os outros idiomas usam o inglês, e o Nicx responde no
idioma da interface do mesmo jeito).
"""

from __future__ import annotations

from typing import Any, Optional

_AUTOR = "Falkyria"


def _a(nome, descricao, instrucoes, ferramentas=(), memoria=True, saudacao=""):
    return {
        "nome": nome,
        "descricao": descricao,
        "instrucoes": instrucoes,
        "ferramentas": list(ferramentas),
        "memoria": memoria,
        "saudacao": saudacao,
    }


def _h(nome, titulo, descricao, instrucoes):
    return {
        "nome": nome,
        "titulo": titulo,
        "descricao": descricao,
        "instrucoes": instrucoes,
    }


def _r(nome, passos, frases=()):
    return {"nome": nome, "passos": passos, "frases": list(frases)}


def _lembrete(texto, minutos):
    return {"kind": "remind", "target": texto, "minutos": minutos}


_PT: dict[str, dict[str, Any]] = {
    "professor": {
        "nome": "Professor",
        "descricao": "Planejar aulas, corrigir redações e montar avaliações.",
        "assistentes": [
            _a(
                "Planejador de aulas",
                "Monta planos de aula e atividades.",
                "Monte planos de aula com objetivo, duração, materiais, passo a passo e uma atividade de fixação. Pergunte a série e o tempo da aula se faltarem. Use linguagem adequada à idade dos alunos.",
                saudacao="Qual aula vamos planejar?",
            ),
            _a(
                "Corretor de redações",
                "Corrige redações com comentários e nota.",
                "Corrija a redação pelos critérios que o professor indicar (se não indicar, use: tema, estrutura, argumentação, coesão e norma culta). Dê uma nota por critério, aponte trechos com problema e termine com dois elogios e duas sugestões para o aluno.",
                memoria=False,
                saudacao="Cole a redação e diga os critérios.",
            ),
        ],
        "habilidades": [
            _h(
                "plano-de-aula",
                "Plano de aula",
                "Use quando pedirem um plano de aula, sequência didática ou roteiro de aula.",
                "Estrutura do plano:\n\n1. Tema e série\n2. Objetivos de aprendizagem (2 ou 3, com verbos observáveis)\n3. Duração e materiais\n4. Abertura (5 a 10 min)\n5. Desenvolvimento, em etapas com tempo\n6. Atividade de fixação\n7. Avaliação: como saber se aprenderam\n8. Adaptações para quem tem dificuldade",
            ),
            _h(
                "rubrica-de-avaliacao",
                "Rubrica de avaliação",
                "Use quando pedirem rubrica, critérios de correção ou grade de avaliação.",
                "Monte uma tabela com os critérios nas linhas e quatro níveis nas colunas (insuficiente, básico, bom, excelente). Descreva cada nível com algo observável no trabalho do aluno. Termine com a pontuação de cada nível.",
            ),
        ],
        "rotinas": [
            _r(
                "Hora de corrigir",
                [
                    {"kind": "close", "target": "whatsapp"},
                    {"kind": "volume", "op": "set", "value": 20},
                    _lembrete("Pausa: levante e beba água", 50),
                ],
                ["hora de corrigir"],
            ),
        ],
    },
    "estudante": {
        "nome": "Estudante",
        "descricao": "Estudar com tutor, resumos, flashcards e modo estudo.",
        "assistentes": [
            _a(
                "Tutor de estudos",
                "Explica passo a passo e faz perguntas.",
                "Explique a matéria passo a passo, com exemplos do dia a dia e palavras simples. Depois de cada explicação, faça uma pergunta curta para conferir se a pessoa entendeu. Se ela errar, explique de outro jeito. Em exercícios, dê uma dica antes da resposta.",
                saudacao="Qual matéria vamos estudar hoje?",
            ),
        ],
        "habilidades": [
            _h(
                "resumo-para-prova",
                "Resumo para prova",
                "Use quando pedirem um resumo para estudar, revisar ou fazer prova.",
                "Faça o resumo em tópicos curtos: conceitos principais em negrito, uma frase de explicação para cada, fórmulas ou datas importantes e, no fim, três perguntas que podem cair na prova.",
            ),
            _h(
                "flashcards",
                "Flashcards",
                "Use quando pedirem flashcards, cartões de memorização ou perguntas e respostas para decorar.",
                "Gere de 10 a 20 cartões no formato:\n\nP: pergunta curta\nR: resposta curta\n\nUma ideia por cartão. Misture perguntas de definição, de exemplo e de aplicação.",
            ),
        ],
        "rotinas": [
            _r(
                "Modo estudo",
                [
                    {"kind": "close", "target": "whatsapp"},
                    {"kind": "volume", "op": "set", "value": 25},
                    _lembrete("Pomodoro acabou: 5 minutos de pausa", 25),
                ],
                ["modo estudo", "hora de estudar"],
            ),
        ],
    },
    "programador": {
        "nome": "Programador",
        "descricao": "Parceiro de código, revisão e mensagens de commit.",
        "assistentes": [
            _a(
                "Parceiro de código",
                "Ajuda a programar e testa trechos.",
                "Ajude a programar. Responda direto, com o código primeiro e uma explicação de uma ou duas frases do porquê. Ao ver um erro, diga a causa provável e a correção. Quando der, teste o trecho com o interpretador de código antes de responder.",
                ["code_interpreter", "file_read"],
                saudacao="Bora programar. Qual é o problema?",
            ),
        ],
        "habilidades": [
            _h(
                "revisao-de-codigo",
                "Revisão de código",
                "Use quando pedirem para revisar código, um diff ou um pull request.",
                "Revise procurando, nesta ordem: bugs e casos de borda, segurança (entrada do usuário, segredos, permissões), desempenho e legibilidade. Para cada problema: arquivo ou trecho, o que está errado, por que importa e a correção sugerida. Não comente estilo que um formatador resolve.",
            ),
            _h(
                "mensagem-de-commit",
                "Mensagem de commit",
                "Use quando pedirem uma mensagem de commit ou descrição de mudança.",
                "Escreva no formato Conventional Commits (feat, fix, docs, refactor, test, chore), título com até 72 caracteres no imperativo e, se a mudança for grande, um corpo curto com o porquê.",
            ),
        ],
        "rotinas": [
            _r(
                "Começar a programar",
                [
                    {"kind": "open", "target": "code"},
                    {"kind": "open_url", "target": "https://github.com"},
                    {"kind": "close", "target": "whatsapp"},
                ],
                ["vamos programar"],
            ),
        ],
    },
    "criador": {
        "nome": "Criador de conteúdo",
        "descricao": "Ideias, roteiros de vídeo e legendas para redes.",
        "assistentes": [
            _a(
                "Roteirista",
                "Escreve roteiros de vídeo com gancho e chamada.",
                "Escreva roteiros de vídeo com: gancho nos primeiros 3 segundos, desenvolvimento em blocos curtos com indicação de cena, e uma chamada para ação no fim. Pergunte a plataforma e a duração se faltarem. Linguagem falada, frases curtas.",
                saudacao="Sobre o que é o vídeo?",
            ),
            _a(
                "Gerador de ideias",
                "Sugere ideias variadas de conteúdo.",
                "Sugira cinco ideias de conteúdo bem diferentes entre si, cada uma com título e uma frase do ângulo, e pergunte qual desenvolver. Depois, aprofunde a escolhida com formato, roteiro resumido e título chamativo.",
            ),
        ],
        "habilidades": [
            _h(
                "legenda-para-redes",
                "Legenda para redes",
                "Use quando pedirem legenda, descrição de post ou texto para Instagram, TikTok, YouTube ou LinkedIn.",
                "Escreva três versões da legenda (curta, média e com história). Primeira linha chama atenção, sem clichê. Termine com uma pergunta ou chamada. Sugira de 3 a 5 hashtags específicas, sem genéricas.",
            ),
        ],
        "rotinas": [
            _r(
                "Hora de gravar",
                [
                    {"kind": "close", "target": "whatsapp"},
                    {"kind": "close", "target": "spotify"},
                    _lembrete("Confira o áudio e a luz antes de gravar", 1),
                ],
                ["hora de gravar"],
            ),
        ],
    },
    "escritorio": {
        "nome": "Escritório",
        "descricao": "E-mails, atas de reunião e organização do dia.",
        "assistentes": [
            _a(
                "Redator de e-mails",
                "Escreve e responde e-mails no tom certo.",
                "Escreva e-mails claros e educados: assunto curto, primeira frase dizendo o que se quer, corpo em parágrafos curtos e fechamento com próximo passo. Pergunte o tom (formal ou informal) se não der para saber. Ofereça uma versão mais curta no fim.",
                memoria=False,
                saudacao="Para quem e sobre o quê é o e-mail?",
            ),
            _a(
                "Organizador do dia",
                "Transforma pedidos em lembretes e compromissos.",
                "Ajude a organizar o dia. Transforme pedidos em lembretes e compromissos com as ferramentas, confirmando dia e hora. Responda em poucas frases. Se faltar o horário, pergunte antes de criar.",
                ["lembrete", "agenda", "controle_pc"],
                saudacao="O que você precisa organizar?",
            ),
        ],
        "habilidades": [
            _h(
                "ata-de-reuniao",
                "Ata de reunião",
                "Use quando pedirem ata, resumo ou registro de uma reunião.",
                "Monte a ata com: data e participantes; assuntos tratados (um parágrafo curto cada); decisões; próximos passos em tabela com responsável e prazo; pendências sem dono.",
            ),
        ],
        "rotinas": [
            _r(
                "Começar o dia",
                [{"kind": "resumo"}, {"kind": "agenda_list"}, {"kind": "remind_list"}],
                ["começar o dia"],
            ),
        ],
    },
}

_EN: dict[str, dict[str, Any]] = {
    "professor": {
        "nome": "Teacher",
        "descricao": "Plan lessons, grade essays and build assessments.",
        "assistentes": [
            _a(
                "Lesson planner",
                "Builds lesson plans and activities.",
                "Build lesson plans with goal, duration, materials, step by step and one practice activity. Ask for the grade and class length if missing. Use language suited to the students' age.",
                saudacao="Which lesson are we planning?",
            ),
            _a(
                "Essay grader",
                "Grades essays with comments and a score.",
                "Grade the essay by the criteria the teacher gives (if none: topic, structure, argument, cohesion and grammar). Give a score per criterion, point out problem passages and end with two compliments and two suggestions for the student.",
                memoria=False,
                saudacao="Paste the essay and tell me the criteria.",
            ),
        ],
        "habilidades": [
            _h(
                "plano-de-aula",
                "Lesson plan",
                "Use when asked for a lesson plan, teaching sequence or class outline.",
                "Plan structure:\n\n1. Topic and grade\n2. Learning goals (2 or 3, with observable verbs)\n3. Duration and materials\n4. Opening (5 to 10 min)\n5. Development, in timed steps\n6. Practice activity\n7. Assessment: how to know they learned\n8. Adaptations for struggling students",
            ),
            _h(
                "rubrica-de-avaliacao",
                "Grading rubric",
                "Use when asked for a rubric, grading criteria or assessment grid.",
                "Build a table with criteria in rows and four levels in columns (insufficient, basic, good, excellent). Describe each level with something observable in the student's work. End with the points for each level.",
            ),
        ],
        "rotinas": [
            _r(
                "Grading time",
                [
                    {"kind": "close", "target": "whatsapp"},
                    {"kind": "volume", "op": "set", "value": 20},
                    _lembrete("Break: stand up and drink water", 50),
                ],
                ["grading time"],
            ),
        ],
    },
    "estudante": {
        "nome": "Student",
        "descricao": "Study with a tutor, summaries, flashcards and study mode.",
        "assistentes": [
            _a(
                "Study tutor",
                "Explains step by step and asks questions.",
                "Explain the subject step by step, with everyday examples and simple words. After each explanation, ask one short question to check understanding. If the person gets it wrong, explain it another way. For exercises, give a hint before the answer.",
                saudacao="What are we studying today?",
            ),
        ],
        "habilidades": [
            _h(
                "resumo-para-prova",
                "Exam summary",
                "Use when asked for a summary to study, review or prepare for an exam.",
                "Write the summary in short bullet points: key concepts in bold, one explanatory sentence each, important formulas or dates and, at the end, three questions that may be on the exam.",
            ),
            _h(
                "flashcards",
                "Flashcards",
                "Use when asked for flashcards, memory cards or Q&A to memorize.",
                "Generate 10 to 20 cards in the format:\n\nQ: short question\nA: short answer\n\nOne idea per card. Mix definition, example and application questions.",
            ),
        ],
        "rotinas": [
            _r(
                "Study mode",
                [
                    {"kind": "close", "target": "whatsapp"},
                    {"kind": "volume", "op": "set", "value": 25},
                    _lembrete("Pomodoro done: 5 minute break", 25),
                ],
                ["study mode"],
            ),
        ],
    },
    "programador": {
        "nome": "Developer",
        "descricao": "Coding partner, code review and commit messages.",
        "assistentes": [
            _a(
                "Coding partner",
                "Helps you program and tests snippets.",
                "Help with programming. Answer directly, code first, with a one or two sentence explanation of why. When you see an error, give the likely cause and the fix. When possible, test the snippet with the code interpreter before answering.",
                ["code_interpreter", "file_read"],
                saudacao="Let's code. What's the problem?",
            ),
        ],
        "habilidades": [
            _h(
                "revisao-de-codigo",
                "Code review",
                "Use when asked to review code, a diff or a pull request.",
                "Review looking, in this order, for: bugs and edge cases, security (user input, secrets, permissions), performance and readability. For each issue: file or snippet, what is wrong, why it matters and the suggested fix. Do not comment on style a formatter fixes.",
            ),
            _h(
                "mensagem-de-commit",
                "Commit message",
                "Use when asked for a commit message or change description.",
                "Write in Conventional Commits format (feat, fix, docs, refactor, test, chore), a title of up to 72 characters in the imperative and, for big changes, a short body with the why.",
            ),
        ],
        "rotinas": [
            _r(
                "Start coding",
                [
                    {"kind": "open", "target": "code"},
                    {"kind": "open_url", "target": "https://github.com"},
                    {"kind": "close", "target": "whatsapp"},
                ],
                ["start coding"],
            ),
        ],
    },
    "criador": {
        "nome": "Content creator",
        "descricao": "Ideas, video scripts and social media captions.",
        "assistentes": [
            _a(
                "Scriptwriter",
                "Writes video scripts with a hook and a call to action.",
                "Write video scripts with: a hook in the first 3 seconds, development in short blocks with scene notes, and a call to action at the end. Ask for the platform and length if missing. Spoken language, short sentences.",
                saudacao="What is the video about?",
            ),
            _a(
                "Idea generator",
                "Suggests varied content ideas.",
                "Suggest five content ideas that are very different from each other, each with a title and a one-line angle, and ask which to develop. Then expand the chosen one with format, short script and a catchy title.",
            ),
        ],
        "habilidades": [
            _h(
                "legenda-para-redes",
                "Social caption",
                "Use when asked for a caption, post description or text for Instagram, TikTok, YouTube or LinkedIn.",
                "Write three versions of the caption (short, medium and story-based). The first line grabs attention, no clichés. End with a question or call to action. Suggest 3 to 5 specific hashtags, no generic ones.",
            ),
        ],
        "rotinas": [
            _r(
                "Recording time",
                [
                    {"kind": "close", "target": "whatsapp"},
                    {"kind": "close", "target": "spotify"},
                    _lembrete("Check audio and lighting before recording", 1),
                ],
                ["recording time"],
            ),
        ],
    },
    "escritorio": {
        "nome": "Office",
        "descricao": "Emails, meeting minutes and organizing the day.",
        "assistentes": [
            _a(
                "Email writer",
                "Writes and answers emails in the right tone.",
                "Write clear, polite emails: short subject, first sentence saying what is wanted, body in short paragraphs and a closing with the next step. Ask for the tone (formal or informal) if unclear. Offer a shorter version at the end.",
                memoria=False,
                saudacao="Who is the email for and what is it about?",
            ),
            _a(
                "Day organizer",
                "Turns requests into reminders and events.",
                "Help organize the day. Turn requests into reminders and events with the tools, confirming day and time. Answer in a few sentences. If the time is missing, ask before creating anything.",
                ["lembrete", "agenda", "controle_pc"],
                saudacao="What do you need to organize?",
            ),
        ],
        "habilidades": [
            _h(
                "ata-de-reuniao",
                "Meeting minutes",
                "Use when asked for meeting minutes, a summary or record of a meeting.",
                "Write the minutes with: date and attendees; topics discussed (one short paragraph each); decisions; next steps in a table with owner and deadline; open items without an owner.",
            ),
        ],
        "rotinas": [
            _r(
                "Start the day",
                [{"kind": "resumo"}, {"kind": "agenda_list"}, {"kind": "remind_list"}],
                ["start the day"],
            ),
        ],
    },
}

IDS = tuple(_PT)


def pronto(pacote_id: str, idioma: Optional[str] = None) -> Optional[dict[str, Any]]:
    from nicx.acoes.textos import codigo

    tabela = _PT if codigo(idioma) == "pt-BR" else _EN
    dados = tabela.get(pacote_id)
    if dados is None:
        return None
    return {
        "formato": 1,
        "id": pacote_id,
        "versao": "1.0.0",
        "autor": _AUTOR,
        "pronto": True,
        "mcp": [],
        **dados,
    }


def prontos(idioma: Optional[str] = None) -> list[dict[str, Any]]:
    return [p for p in (pronto(i, idioma) for i in IDS) if p is not None]


__all__ = ["IDS", "pronto", "prontos"]
