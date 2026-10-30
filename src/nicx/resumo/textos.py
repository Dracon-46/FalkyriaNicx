"""Frases do resumo do dia, nos 7 idiomas da interface.

Um dicionário por idioma (os códigos de ``nicx.nucleo.idiomas``). O
português é a referência: chave que faltar em outro idioma sai em português.
As horas usam ``nicx.acoes.textos.hora_curta`` ("15h30", "3:30 PM"...).
"""

from __future__ import annotations

from typing import Optional

from nicx.nucleo.idiomas import PADRAO
from nicx.nucleo.idiomas import idioma as _idioma

_PT = {
    "cab_hoje": "Resumo do seu dia.",
    "cab_ontem": "Resumo de ontem.",
    "cab_data": "Resumo de {dd}/{mm}.",
    "vazio": "Não encontrei nada registrado nesse dia.",
    "lembretes_feitos": "Lembretes que tocaram: {itens}.",
    "lembretes_restantes": "Lembretes que ainda vêm hoje: {itens}.",
    "comp_feitos": "Compromissos que você teve: {itens}.",
    "comp_restantes": "Ainda na agenda de hoje: {itens}.",
    "notas_uma": "Você fez 1 anotação: {itens}.",
    "notas_varias": "Você fez {n} anotações; as últimas: {itens}.",
    "organizei": "Organizei {itens}.",
    "org_item": "a pasta {pasta} ({n} arquivos)",
    "org_item_um": "a pasta {pasta} (1 arquivo)",
    "proj_atualizados": "Projetos em que você mexeu: {itens}.",
    "proj_concluidas": "Pendências concluídas: {itens}.",
    "proj_pendentes": "Ficou pendente: {itens}.",
    "proj_item": "{tarefa} ({projeto})",
    "amanha_tem": "Amanhã você tem: {itens}.",
    "amanha_livre": "Amanhã a agenda está livre.",
    "hoje_tem": "Hoje você tem: {itens}.",
    "hoje_livre": "Hoje a agenda está livre.",
    "pcab_hoje": "Ainda pendente hoje.",
    "pcab_ontem": "O que ficou pendente ontem.",
    "pcab_data": "O que ficou pendente em {dd}/{mm}.",
    "pend_nada_hoje": "Nada ficou pendente hoje.",
    "pend_nada_ontem": "Nada ficou pendente ontem.",
    "pend_nada_data": "Nada ficou pendente em {dd}/{mm}.",
    "item_hora": "{titulo} às {hora}",
    "item_dia_todo": "{titulo} (dia todo)",
    "e_mais": " e mais {n}",
    "sep": "; ",
    "refinar": (
        "Reescreva o resumo do dia abaixo para ser falado em voz alta: natural, "
        "curto e na segunda pessoa. Não invente nada e não tire nenhuma "
        "informação. Responda só com o texto, sem títulos nem listas."
    ),
}

_EN = {
    "cab_hoje": "Summary of your day.",
    "cab_ontem": "Summary of yesterday.",
    "cab_data": "Summary for {mm}/{dd}.",
    "vazio": "I found nothing recorded for that day.",
    "lembretes_feitos": "Reminders that went off: {itens}.",
    "lembretes_restantes": "Reminders still coming today: {itens}.",
    "comp_feitos": "Appointments you had: {itens}.",
    "comp_restantes": "Still on today's calendar: {itens}.",
    "notas_uma": "You took 1 note: {itens}.",
    "notas_varias": "You took {n} notes; the latest: {itens}.",
    "organizei": "I organized {itens}.",
    "org_item": "the {pasta} folder ({n} files)",
    "org_item_um": "the {pasta} folder (1 file)",
    "proj_atualizados": "Projects you worked on: {itens}.",
    "proj_concluidas": "Tasks completed: {itens}.",
    "proj_pendentes": "Still pending: {itens}.",
    "proj_item": "{tarefa} ({projeto})",
    "amanha_tem": "Tomorrow you have: {itens}.",
    "amanha_livre": "Tomorrow your calendar is free.",
    "hoje_tem": "Today you have: {itens}.",
    "hoje_livre": "Today your calendar is free.",
    "pcab_hoje": "Still pending today.",
    "pcab_ontem": "Left pending yesterday.",
    "pcab_data": "Left pending on {mm}/{dd}.",
    "pend_nada_hoje": "Nothing is pending today.",
    "pend_nada_ontem": "Nothing was left pending yesterday.",
    "pend_nada_data": "Nothing was left pending on {mm}/{dd}.",
    "item_hora": "{titulo} at {hora}",
    "item_dia_todo": "{titulo} (all day)",
    "e_mais": " and {n} more",
    "sep": "; ",
}

_ES = {
    "cab_hoje": "Resumen de tu día.",
    "cab_ontem": "Resumen de ayer.",
    "cab_data": "Resumen del {dd}/{mm}.",
    "vazio": "No encontré nada registrado ese día.",
    "lembretes_feitos": "Recordatorios que sonaron: {itens}.",
    "lembretes_restantes": "Recordatorios que aún vienen hoy: {itens}.",
    "comp_feitos": "Compromisos que tuviste: {itens}.",
    "comp_restantes": "Aún en la agenda de hoy: {itens}.",
    "notas_uma": "Hiciste 1 nota: {itens}.",
    "notas_varias": "Hiciste {n} notas; las últimas: {itens}.",
    "organizei": "Organicé {itens}.",
    "org_item": "la carpeta {pasta} ({n} archivos)",
    "org_item_um": "la carpeta {pasta} (1 archivo)",
    "proj_atualizados": "Proyectos en los que trabajaste: {itens}.",
    "proj_concluidas": "Pendientes completados: {itens}.",
    "proj_pendentes": "Quedó pendiente: {itens}.",
    "proj_item": "{tarefa} ({projeto})",
    "amanha_tem": "Mañana tienes: {itens}.",
    "amanha_livre": "Mañana tu agenda está libre.",
    "hoje_tem": "Hoy tienes: {itens}.",
    "hoje_livre": "Hoy tu agenda está libre.",
    "pcab_hoje": "Pendiente para hoy.",
    "pcab_ontem": "Lo que quedó pendiente ayer.",
    "pcab_data": "Lo que quedó pendiente el {dd}/{mm}.",
    "pend_nada_hoje": "No hay nada pendiente hoy.",
    "pend_nada_ontem": "No quedó nada pendiente ayer.",
    "pend_nada_data": "No quedó nada pendiente el {dd}/{mm}.",
    "item_hora": "{titulo} {a_las} {hora}",
    "item_dia_todo": "{titulo} (todo el día)",
    "e_mais": " y {n} más",
    "sep": "; ",
}

_FR = {
    "cab_hoje": "Résumé de ta journée.",
    "cab_ontem": "Résumé d'hier.",
    "cab_data": "Résumé du {dd}/{mm}.",
    "vazio": "Je n'ai rien trouvé d'enregistré ce jour-là.",
    "lembretes_feitos": "Rappels qui ont sonné : {itens}.",
    "lembretes_restantes": "Rappels encore prévus aujourd'hui : {itens}.",
    "comp_feitos": "Rendez-vous que tu as eus : {itens}.",
    "comp_restantes": "Encore à l'agenda aujourd'hui : {itens}.",
    "notas_uma": "Tu as pris 1 note : {itens}.",
    "notas_varias": "Tu as pris {n} notes ; les dernières : {itens}.",
    "organizei": "J'ai rangé {itens}.",
    "org_item": "le dossier {pasta} ({n} fichiers)",
    "org_item_um": "le dossier {pasta} (1 fichier)",
    "proj_atualizados": "Projets sur lesquels tu as travaillé : {itens}.",
    "proj_concluidas": "Tâches terminées : {itens}.",
    "proj_pendentes": "Encore en attente : {itens}.",
    "proj_item": "{tarefa} ({projeto})",
    "amanha_tem": "Demain, tu as : {itens}.",
    "amanha_livre": "Demain, ton agenda est libre.",
    "hoje_tem": "Aujourd'hui, tu as : {itens}.",
    "hoje_livre": "Aujourd'hui, ton agenda est libre.",
    "pcab_hoje": "Encore en attente aujourd'hui.",
    "pcab_ontem": "Resté en attente hier.",
    "pcab_data": "Resté en attente le {dd}/{mm}.",
    "pend_nada_hoje": "Rien n'est en attente aujourd'hui.",
    "pend_nada_ontem": "Rien n'est resté en attente hier.",
    "pend_nada_data": "Rien n'est resté en attente le {dd}/{mm}.",
    "item_hora": "{titulo} à {hora}",
    "item_dia_todo": "{titulo} (toute la journée)",
    "e_mais": " et {n} de plus",
    "sep": " ; ",
}

_ZH = {
    "cab_hoje": "今天的总结。",
    "cab_ontem": "昨天的总结。",
    "cab_data": "{m}月{d}日的总结。",
    "vazio": "这一天没有找到任何记录。",
    "lembretes_feitos": "已响起的提醒：{itens}。",
    "lembretes_restantes": "今天还有的提醒：{itens}。",
    "comp_feitos": "已经过去的日程：{itens}。",
    "comp_restantes": "今天还有的日程：{itens}。",
    "notas_uma": "你记了 1 条笔记：{itens}。",
    "notas_varias": "你记了 {n} 条笔记，最近的：{itens}。",
    "organizei": "我整理了{itens}。",
    "org_item": "{pasta} 文件夹（{n} 个文件）",
    "org_item_um": "{pasta} 文件夹（1 个文件）",
    "proj_atualizados": "你更新过的项目：{itens}。",
    "proj_concluidas": "已完成的待办：{itens}。",
    "proj_pendentes": "还未完成：{itens}。",
    "proj_item": "{tarefa}（{projeto}）",
    "amanha_tem": "明天你有：{itens}。",
    "amanha_livre": "明天没有安排。",
    "hoje_tem": "今天你有：{itens}。",
    "hoje_livre": "今天没有安排。",
    "pcab_hoje": "今天还未完成的事项。",
    "pcab_ontem": "昨天未完成的事项。",
    "pcab_data": "{m}月{d}日未完成的事项。",
    "pend_nada_hoje": "今天没有未完成的事项。",
    "pend_nada_ontem": "昨天没有未完成的事项。",
    "pend_nada_data": "{m}月{d}日没有未完成的事项。",
    "item_hora": "{hora} {titulo}",
    "item_dia_todo": "{titulo}（全天）",
    "e_mais": "，还有 {n} 项",
    "sep": "；",
}

_HI = {
    "cab_hoje": "आज का सारांश।",
    "cab_ontem": "कल का सारांश।",
    "cab_data": "{dd}/{mm} का सारांश।",
    "vazio": "इस दिन का कोई रिकॉर्ड नहीं मिला।",
    "lembretes_feitos": "जो रिमाइंडर बजे: {itens}।",
    "lembretes_restantes": "आज के बाकी रिमाइंडर: {itens}।",
    "comp_feitos": "आपके हो चुके कार्यक्रम: {itens}।",
    "comp_restantes": "आज अभी बाकी कार्यक्रम: {itens}।",
    "notas_uma": "आपने 1 नोट लिखा: {itens}।",
    "notas_varias": "आपने {n} नोट लिखे; आख़िरी: {itens}।",
    "organizei": "मैंने व्यवस्थित किया: {itens}।",
    "org_item": "{pasta} फ़ोल्डर ({n} फ़ाइलें)",
    "org_item_um": "{pasta} फ़ोल्डर (1 फ़ाइल)",
    "proj_atualizados": "जिन प्रोजेक्ट पर आपने काम किया: {itens}।",
    "proj_concluidas": "पूरे हुए काम: {itens}।",
    "proj_pendentes": "बाकी रह गया: {itens}।",
    "proj_item": "{tarefa} ({projeto})",
    "amanha_tem": "कल आपके पास है: {itens}।",
    "amanha_livre": "कल का कैलेंडर खाली है।",
    "hoje_tem": "आज आपके पास है: {itens}।",
    "hoje_livre": "आज का कैलेंडर खाली है।",
    "pcab_hoje": "आज के बाकी काम।",
    "pcab_ontem": "कल के बाकी काम।",
    "pcab_data": "{dd}/{mm} के बाकी काम।",
    "pend_nada_hoje": "आज कुछ भी बाकी नहीं है।",
    "pend_nada_ontem": "कल कुछ भी बाकी नहीं रहा।",
    "pend_nada_data": "{dd}/{mm} को कुछ भी बाकी नहीं रहा।",
    "item_hora": "{titulo} ({hora})",
    "item_dia_todo": "{titulo} (पूरा दिन)",
    "e_mais": " और {n} अन्य",
    "sep": "; ",
}

_AR = {
    "cab_hoje": "ملخص يومك.",
    "cab_ontem": "ملخص الأمس.",
    "cab_data": "ملخص يوم {dd}/{mm}.",
    "vazio": "لم أجد أي شيء مسجّل في هذا اليوم.",
    "lembretes_feitos": "التذكيرات التي رنّت: {itens}.",
    "lembretes_restantes": "تذكيرات ما زالت اليوم: {itens}.",
    "comp_feitos": "المواعيد التي كانت لديك: {itens}.",
    "comp_restantes": "ما زال في جدول اليوم: {itens}.",
    "notas_uma": "كتبت ملاحظة واحدة: {itens}.",
    "notas_varias": "كتبت {n} ملاحظات؛ آخرها: {itens}.",
    "organizei": "نظّمت {itens}.",
    "org_item": "مجلد {pasta} ({n} ملفات)",
    "org_item_um": "مجلد {pasta} (ملف واحد)",
    "proj_atualizados": "المشاريع التي عملت عليها: {itens}.",
    "proj_concluidas": "المهام المنجزة: {itens}.",
    "proj_pendentes": "ما زال معلّقًا: {itens}.",
    "proj_item": "{tarefa} ({projeto})",
    "amanha_tem": "غدًا لديك: {itens}.",
    "amanha_livre": "جدول الغد فارغ.",
    "hoje_tem": "اليوم لديك: {itens}.",
    "hoje_livre": "جدول اليوم فارغ.",
    "pcab_hoje": "ما زال معلّقًا اليوم.",
    "pcab_ontem": "ما بقي معلّقًا أمس.",
    "pcab_data": "ما بقي معلّقًا يوم {dd}/{mm}.",
    "pend_nada_hoje": "لا شيء معلّق اليوم.",
    "pend_nada_ontem": "لم يبقَ شيء معلّق أمس.",
    "pend_nada_data": "لم يبقَ شيء معلّق يوم {dd}/{mm}.",
    "item_hora": "{titulo} الساعة {hora}",
    "item_dia_todo": "{titulo} (طوال اليوم)",
    "e_mais": " و{n} أخرى",
    "sep": "؛ ",
}

FRASES: dict[str, dict[str, str]] = {
    "pt-BR": _PT,
    "en": _EN,
    "es": _ES,
    "fr": _FR,
    "zh": _ZH,
    "hi": _HI,
    "ar": _AR,
}


def codigo(idioma: Optional[str]) -> str:
    """O código da tabela ("pt-BR", "en"...); vazio ou desconhecido, português."""
    return _idioma(idioma).codigo if idioma else PADRAO


def texto(chave: str, idioma: Optional[str] = None, **valores: object) -> str:
    """A frase ``chave`` no idioma, com os ``valores`` no lugar."""
    modelo = FRASES.get(codigo(idioma), _PT).get(chave)
    if modelo is None:
        modelo = _PT[chave]
    return modelo.format(**valores) if valores else modelo


__all__ = ["FRASES", "codigo", "texto"]
