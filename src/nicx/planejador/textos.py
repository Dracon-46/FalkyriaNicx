# ruff: noqa: E501  (tabela de frases: uma por linha fica mais legível)
"""Frases do planejador no idioma da interface (português se faltar)."""

from __future__ import annotations

from typing import Optional

from nicx.nucleo.idiomas import PADRAO
from nicx.nucleo.idiomas import idioma as _idioma

_PT = {
    "lembrete": "Etapa do plano {plano}: {etapa}",
    "lembretes_plano": "Lembretes do plano {plano} ({n})",
    "criado": 'Plano "{plano}" criado com {n} etapas até {prazo}.',
    "primeira": " Primeira: {etapa}, até {prazo}.",
    "erro": "Não consegui montar o plano: {motivo}.",
    "nuvem": "Planos só são montados com modelos locais. Escolha um modelo local para eu continuar.",
    "sem_modelo": "Não há modelo local disponível para montar o plano.",
}
_EN = {
    "lembrete": "Step of the plan {plano}: {etapa}",
    "lembretes_plano": "Reminders for the plan {plano} ({n})",
    "criado": 'Plan "{plano}" created with {n} steps until {prazo}.',
    "primeira": " First: {etapa}, by {prazo}.",
    "erro": "I couldn't build the plan: {motivo}.",
    "nuvem": "Plans are only built with local models. Choose a local model so I can continue.",
    "sem_modelo": "There is no local model available to build the plan.",
}
_ES = {
    "lembrete": "Etapa del plan {plano}: {etapa}",
    "lembretes_plano": "Recordatorios del plan {plano} ({n})",
    "criado": 'Plan "{plano}" creado con {n} etapas hasta el {prazo}.',
    "primeira": " Primera: {etapa}, hasta el {prazo}.",
    "erro": "No pude armar el plan: {motivo}.",
    "nuvem": "Los planes solo se arman con modelos locales. Elige un modelo local para continuar.",
    "sem_modelo": "No hay un modelo local disponible para armar el plan.",
}
_FR = {
    "lembrete": "Étape du plan {plano} : {etapa}",
    "lembretes_plano": "Rappels du plan {plano} ({n})",
    "criado": "Plan « {plano} » créé avec {n} étapes jusqu'au {prazo}.",
    "primeira": " Première : {etapa}, avant le {prazo}.",
    "erro": "Je n'ai pas pu construire le plan : {motivo}.",
    "nuvem": "Les plans ne sont construits qu'avec des modèles locaux. Choisissez un modèle local pour continuer.",
    "sem_modelo": "Aucun modèle local n'est disponible pour construire le plan.",
}
_ZH = {
    "lembrete": "计划 {plano} 的步骤：{etapa}",
    "lembretes_plano": "计划 {plano} 的提醒（{n}）",
    "criado": "已创建计划“{plano}”，共 {n} 个步骤，截止 {prazo}。",
    "primeira": "第一步：{etapa}，截止 {prazo}。",
    "erro": "无法制定计划：{motivo}。",
    "nuvem": "计划只能用本地模型制定。请选择一个本地模型。",
    "sem_modelo": "没有可用的本地模型来制定计划。",
}
_HI = {
    "lembrete": "योजना {plano} का चरण: {etapa}",
    "lembretes_plano": "योजना {plano} के रिमाइंडर ({n})",
    "criado": 'योजना "{plano}" {n} चरणों के साथ {prazo} तक बनाई गई।',
    "primeira": " पहला चरण: {etapa}, {prazo} तक।",
    "erro": "मैं योजना नहीं बना सका: {motivo}।",
    "nuvem": "योजनाएँ केवल लोकल मॉडल से बनती हैं। आगे बढ़ने के लिए लोकल मॉडल चुनें।",
    "sem_modelo": "योजना बनाने के लिए कोई लोकल मॉडल उपलब्ध नहीं है।",
}
_AR = {
    "lembrete": "خطوة من الخطة {plano}: {etapa}",
    "lembretes_plano": "تذكيرات الخطة {plano} ({n})",
    "criado": 'تم إنشاء الخطة "{plano}" بعدد {n} خطوات حتى {prazo}.',
    "primeira": " الأولى: {etapa}، حتى {prazo}.",
    "erro": "لم أتمكن من إعداد الخطة: {motivo}.",
    "nuvem": "تُعد الخطط بالنماذج المحلية فقط. اختر نموذجًا محليًا للمتابعة.",
    "sem_modelo": "لا يوجد نموذج محلي متاح لإعداد الخطة.",
}
_TABELAS = {
    PADRAO: _PT,
    "en": _EN,
    "es": _ES,
    "fr": _FR,
    "zh": _ZH,
    "hi": _HI,
    "ar": _AR,
}


def texto(chave: str, idioma: Optional[str] = None, **valores: object) -> str:
    if idioma is None:
        from nicx.acoes.textos import codigo

        idioma = codigo()
    tabela = _TABELAS.get(_idioma(idioma).codigo, _PT)
    modelo = tabela.get(chave) or _TABELAS[PADRAO][chave]
    return modelo.format(**valores) if valores else modelo


def chaves() -> dict[str, set[str]]:
    return {codigo: set(tabela) for codigo, tabela in _TABELAS.items()}


__all__ = ["chaves", "texto"]
