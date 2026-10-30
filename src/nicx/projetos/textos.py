# ruff: noqa: E501  (tabela de frases: uma por linha fica mais legível)
"""Frases dos projetos no idioma da interface.

O português é a referência: se faltar uma chave em outro idioma, sai em
português. Os códigos são os de :mod:`nicx.nucleo.idiomas`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from nicx.nucleo.idiomas import PADRAO
from nicx.nucleo.idiomas import idioma as _idioma

_PT = {
    "sem_projetos": 'Você ainda não tem projetos. Diga "cria o projeto Nome" (ou "cria o projeto Nome na pasta C:\\caminho") para começar.',
    "nao_achei": 'Não achei o projeto "{nome}". Seus projetos: {lista}.',
    "lista": "Seus projetos: {lista}.",
    "item": "{nome} ({pendencias})",
    "pend_0": "sem pendências",
    "pend_1": "1 pendência",
    "pend_n": "{n} pendências",
    "criado": 'Projeto "{nome}" criado.',
    "criado_pasta": " Pasta: {pasta}.",
    "pasta_nao_achada": ' Não achei a pasta "{pasta}"; dá para anexar depois na página Projetos.',
    "ja_existe": 'O projeto "{nome}" já existe.',
    "ver_cabeca": "Projeto {nome}.",
    "ver_objetivo": "Objetivo: {texto}.",
    "ver_estado": "Estado: {texto}.",
    "ver_sem_estado": "Ainda sem estado anotado.",
    "ver_decisao": "Última decisão: {texto}.",
    "ver_abertas": "Pendências abertas: {lista}.",
    "ver_sem_abertas": "Nenhuma pendência aberta.",
    "ver_atividade": "Última atividade: {quando}.",
    "falta": "No projeto {nome} falta: {lista}.",
    "falta_nada": "No projeto {nome} não há pendências abertas.",
    "decisao_ok": "Anotado no projeto {nome}: {texto}.",
    "pendencia_ok": "Pendência adicionada ao projeto {nome}: {texto}.",
    "concluida_ok": "Pendência concluída no projeto {nome}: {texto}.",
    "pendencia_nao_achada": "Não achei essa pendência no projeto {nome}. Abertas: {lista}.",
    "estado_ok": "Estado do projeto {nome} atualizado: {texto}.",
    "arquivado": "Projeto {nome} arquivado.",
    "renomeado": "Projeto renomeado para {nome}.",
    "falta_texto": "O que eu anoto no projeto {nome}?",
    "nuvem": "Os dados dos seus projetos só vão para modelos locais. Escolha um modelo local para eu continuar.",
    "continuar_sem_projetos": 'Ainda não sei no que você está trabalhando: não há projetos. Diga "cria o projeto Nome na pasta C:\\caminho" e eu passo a acompanhar.',
    "quando_agora": "agora há pouco",
    "quando_min": "há {n} min",
    "quando_h": "há {n} h",
    "quando_ontem": "ontem",
    "quando_dias": "há {n} dias",
    "quando_data": "em {data}",
}

_EN = {
    "sem_projetos": 'You have no projects yet. Say "create project Name" (or "create project Name in folder C:\\path") to start.',
    "nao_achei": 'I couldn\'t find the project "{nome}". Your projects: {lista}.',
    "lista": "Your projects: {lista}.",
    "item": "{nome} ({pendencias})",
    "pend_0": "nothing pending",
    "pend_1": "1 open task",
    "pend_n": "{n} open tasks",
    "criado": 'Project "{nome}" created.',
    "criado_pasta": " Folder: {pasta}.",
    "pasta_nao_achada": ' I couldn\'t find the folder "{pasta}"; you can attach it later on the Projects page.',
    "ja_existe": 'The project "{nome}" already exists.',
    "ver_cabeca": "Project {nome}.",
    "ver_objetivo": "Goal: {texto}.",
    "ver_estado": "Status: {texto}.",
    "ver_sem_estado": "No status noted yet.",
    "ver_decisao": "Latest decision: {texto}.",
    "ver_abertas": "Open tasks: {lista}.",
    "ver_sem_abertas": "No open tasks.",
    "ver_atividade": "Last activity: {quando}.",
    "falta": "Still to do in {nome}: {lista}.",
    "falta_nada": "There are no open tasks in {nome}.",
    "decisao_ok": "Noted in project {nome}: {texto}.",
    "pendencia_ok": "Task added to project {nome}: {texto}.",
    "concluida_ok": "Task done in project {nome}: {texto}.",
    "pendencia_nao_achada": "I couldn't find that task in {nome}. Open: {lista}.",
    "estado_ok": "Status of {nome} updated: {texto}.",
    "arquivado": "Project {nome} archived.",
    "renomeado": "Project renamed to {nome}.",
    "falta_texto": "What should I note in project {nome}?",
    "nuvem": "Your project data only goes to local models. Pick a local model and I'll continue.",
    "continuar_sem_projetos": "I don't know what you're working on yet: there are no projects. Say \"create project Name in folder C:\\path\" and I'll keep track.",
    "quando_agora": "just now",
    "quando_min": "{n} min ago",
    "quando_h": "{n} h ago",
    "quando_ontem": "yesterday",
    "quando_dias": "{n} days ago",
    "quando_data": "on {data}",
}

_ES = {
    "sem_projetos": 'Aún no tienes proyectos. Di "crea el proyecto Nombre" (o "crea el proyecto Nombre en la carpeta C:\\ruta") para empezar.',
    "nao_achei": 'No encontré el proyecto "{nome}". Tus proyectos: {lista}.',
    "lista": "Tus proyectos: {lista}.",
    "item": "{nome} ({pendencias})",
    "pend_0": "sin pendientes",
    "pend_1": "1 pendiente",
    "pend_n": "{n} pendientes",
    "criado": 'Proyecto "{nome}" creado.',
    "criado_pasta": " Carpeta: {pasta}.",
    "pasta_nao_achada": ' No encontré la carpeta "{pasta}"; puedes añadirla luego en la página Proyectos.',
    "ja_existe": 'El proyecto "{nome}" ya existe.',
    "ver_cabeca": "Proyecto {nome}.",
    "ver_objetivo": "Objetivo: {texto}.",
    "ver_estado": "Estado: {texto}.",
    "ver_sem_estado": "Todavía sin estado anotado.",
    "ver_decisao": "Última decisión: {texto}.",
    "ver_abertas": "Pendientes: {lista}.",
    "ver_sem_abertas": "Ningún pendiente abierto.",
    "ver_atividade": "Última actividad: {quando}.",
    "falta": "En el proyecto {nome} falta: {lista}.",
    "falta_nada": "En el proyecto {nome} no hay pendientes abiertos.",
    "decisao_ok": "Anotado en el proyecto {nome}: {texto}.",
    "pendencia_ok": "Pendiente añadido al proyecto {nome}: {texto}.",
    "concluida_ok": "Pendiente completado en el proyecto {nome}: {texto}.",
    "pendencia_nao_achada": "No encontré ese pendiente en {nome}. Abiertos: {lista}.",
    "estado_ok": "Estado del proyecto {nome} actualizado: {texto}.",
    "arquivado": "Proyecto {nome} archivado.",
    "renomeado": "Proyecto renombrado a {nome}.",
    "falta_texto": "¿Qué anoto en el proyecto {nome}?",
    "nuvem": "Los datos de tus proyectos solo van a modelos locales. Elige un modelo local para que continúe.",
    "continuar_sem_projetos": 'Aún no sé en qué estás trabajando: no hay proyectos. Di "crea el proyecto Nombre en la carpeta C:\\ruta" y empiezo a seguirlo.',
    "quando_agora": "hace un momento",
    "quando_min": "hace {n} min",
    "quando_h": "hace {n} h",
    "quando_ontem": "ayer",
    "quando_dias": "hace {n} días",
    "quando_data": "el {data}",
}

_FR = {
    "sem_projetos": "Vous n'avez pas encore de projets. Dites « crée le projet Nom » (ou « crée le projet Nom dans le dossier C:\\chemin ») pour commencer.",
    "nao_achei": "Je n'ai pas trouvé le projet « {nome} ». Vos projets : {lista}.",
    "lista": "Vos projets : {lista}.",
    "item": "{nome} ({pendencias})",
    "pend_0": "rien en attente",
    "pend_1": "1 tâche ouverte",
    "pend_n": "{n} tâches ouvertes",
    "criado": "Projet « {nome} » créé.",
    "criado_pasta": " Dossier : {pasta}.",
    "pasta_nao_achada": " Je n'ai pas trouvé le dossier « {pasta} » ; vous pourrez l'ajouter plus tard dans la page Projets.",
    "ja_existe": "Le projet « {nome} » existe déjà.",
    "ver_cabeca": "Projet {nome}.",
    "ver_objetivo": "Objectif : {texto}.",
    "ver_estado": "État : {texto}.",
    "ver_sem_estado": "Pas encore d'état noté.",
    "ver_decisao": "Dernière décision : {texto}.",
    "ver_abertas": "Tâches ouvertes : {lista}.",
    "ver_sem_abertas": "Aucune tâche ouverte.",
    "ver_atividade": "Dernière activité : {quando}.",
    "falta": "Dans le projet {nome}, il reste : {lista}.",
    "falta_nada": "Aucune tâche ouverte dans le projet {nome}.",
    "decisao_ok": "Noté dans le projet {nome} : {texto}.",
    "pendencia_ok": "Tâche ajoutée au projet {nome} : {texto}.",
    "concluida_ok": "Tâche terminée dans le projet {nome} : {texto}.",
    "pendencia_nao_achada": "Je n'ai pas trouvé cette tâche dans {nome}. Ouvertes : {lista}.",
    "estado_ok": "État du projet {nome} mis à jour : {texto}.",
    "arquivado": "Projet {nome} archivé.",
    "renomeado": "Projet renommé en {nome}.",
    "falta_texto": "Que dois-je noter dans le projet {nome} ?",
    "nuvem": "Les données de vos projets ne vont qu'aux modèles locaux. Choisissez un modèle local pour que je continue.",
    "continuar_sem_projetos": "Je ne sais pas encore sur quoi vous travaillez : il n'y a aucun projet. Dites « crée le projet Nom dans le dossier C:\\chemin » et je le suivrai.",
    "quando_agora": "à l'instant",
    "quando_min": "il y a {n} min",
    "quando_h": "il y a {n} h",
    "quando_ontem": "hier",
    "quando_dias": "il y a {n} jours",
    "quando_data": "le {data}",
}

_ZH = {
    "sem_projetos": "你还没有项目。说“创建项目 名称”即可开始。",
    "nao_achei": "没有找到项目“{nome}”。你的项目：{lista}。",
    "lista": "你的项目：{lista}。",
    "item": "{nome}（{pendencias}）",
    "pend_0": "无待办",
    "pend_1": "1 项待办",
    "pend_n": "{n} 项待办",
    "criado": "已创建项目“{nome}”。",
    "criado_pasta": "文件夹：{pasta}。",
    "pasta_nao_achada": "没有找到文件夹“{pasta}”，可以稍后在“项目”页面添加。",
    "ja_existe": "项目“{nome}”已存在。",
    "ver_cabeca": "项目 {nome}。",
    "ver_objetivo": "目标：{texto}。",
    "ver_estado": "状态：{texto}。",
    "ver_sem_estado": "还没有记录状态。",
    "ver_decisao": "最近的决定：{texto}。",
    "ver_abertas": "待办：{lista}。",
    "ver_sem_abertas": "没有未完成的待办。",
    "ver_atividade": "最近活动：{quando}。",
    "falta": "项目 {nome} 还剩：{lista}。",
    "falta_nada": "项目 {nome} 没有未完成的待办。",
    "decisao_ok": "已记录到项目 {nome}：{texto}。",
    "pendencia_ok": "已为项目 {nome} 添加待办：{texto}。",
    "concluida_ok": "项目 {nome} 的待办已完成：{texto}。",
    "pendencia_nao_achada": "在项目 {nome} 中没有找到这项待办。未完成：{lista}。",
    "estado_ok": "项目 {nome} 的状态已更新：{texto}。",
    "arquivado": "项目 {nome} 已归档。",
    "renomeado": "项目已重命名为 {nome}。",
    "falta_texto": "要在项目 {nome} 中记录什么？",
    "nuvem": "你的项目数据只发送给本地模型。请选择本地模型后我再继续。",
    "continuar_sem_projetos": "我还不知道你在做什么：目前没有项目。说“创建项目 名称”，我就会开始跟进。",
    "quando_agora": "刚刚",
    "quando_min": "{n} 分钟前",
    "quando_h": "{n} 小时前",
    "quando_ontem": "昨天",
    "quando_dias": "{n} 天前",
    "quando_data": "{data}",
}

_HI = {
    "sem_projetos": 'आपके पास अभी कोई प्रोजेक्ट नहीं है। शुरू करने के लिए कहें "प्रोजेक्ट बनाओ नाम"।',
    "nao_achei": 'प्रोजेक्ट "{nome}" नहीं मिला। आपके प्रोजेक्ट: {lista}।',
    "lista": "आपके प्रोजेक्ट: {lista}।",
    "item": "{nome} ({pendencias})",
    "pend_0": "कोई बाकी काम नहीं",
    "pend_1": "1 बाकी काम",
    "pend_n": "{n} बाकी काम",
    "criado": 'प्रोजेक्ट "{nome}" बना दिया।',
    "criado_pasta": " फ़ोल्डर: {pasta}।",
    "pasta_nao_achada": ' फ़ोल्डर "{pasta}" नहीं मिला; बाद में प्रोजेक्ट पेज पर जोड़ सकते हैं।',
    "ja_existe": 'प्रोजेक्ट "{nome}" पहले से है।',
    "ver_cabeca": "प्रोजेक्ट {nome}।",
    "ver_objetivo": "लक्ष्य: {texto}।",
    "ver_estado": "स्थिति: {texto}।",
    "ver_sem_estado": "अभी कोई स्थिति नहीं लिखी गई।",
    "ver_decisao": "आख़िरी फ़ैसला: {texto}।",
    "ver_abertas": "बाकी काम: {lista}।",
    "ver_sem_abertas": "कोई बाकी काम नहीं।",
    "ver_atividade": "आख़िरी गतिविधि: {quando}।",
    "falta": "प्रोजेक्ट {nome} में बाकी है: {lista}।",
    "falta_nada": "प्रोजेक्ट {nome} में कोई बाकी काम नहीं है।",
    "decisao_ok": "प्रोजेक्ट {nome} में लिख लिया: {texto}।",
    "pendencia_ok": "प्रोजेक्ट {nome} में काम जोड़ा: {texto}।",
    "concluida_ok": "प्रोजेक्ट {nome} का काम पूरा: {texto}।",
    "pendencia_nao_achada": "प्रोजेक्ट {nome} में यह काम नहीं मिला। बाकी: {lista}।",
    "estado_ok": "प्रोजेक्ट {nome} की स्थिति अपडेट हुई: {texto}।",
    "arquivado": "प्रोजेक्ट {nome} आर्काइव किया।",
    "renomeado": "प्रोजेक्ट का नया नाम {nome} है।",
    "falta_texto": "प्रोजेक्ट {nome} में क्या लिखूँ?",
    "nuvem": "आपके प्रोजेक्ट का डेटा सिर्फ़ लोकल मॉडल को जाता है। जारी रखने के लिए लोकल मॉडल चुनें।",
    "continuar_sem_projetos": 'मुझे अभी नहीं पता कि आप किस पर काम कर रहे हैं: कोई प्रोजेक्ट नहीं है। कहें "प्रोजेक्ट बनाओ नाम" और मैं ध्यान रखूँगा।',
    "quando_agora": "अभी-अभी",
    "quando_min": "{n} मिनट पहले",
    "quando_h": "{n} घंटे पहले",
    "quando_ontem": "कल",
    "quando_dias": "{n} दिन पहले",
    "quando_data": "{data} को",
}

_AR = {
    "sem_projetos": 'ليست لديك مشاريع بعد. قل "أنشئ مشروع الاسم" للبدء.',
    "nao_achei": 'لم أجد المشروع "{nome}". مشاريعك: {lista}.',
    "lista": "مشاريعك: {lista}.",
    "item": "{nome} ({pendencias})",
    "pend_0": "لا مهام معلقة",
    "pend_1": "مهمة واحدة معلقة",
    "pend_n": "{n} مهام معلقة",
    "criado": 'تم إنشاء المشروع "{nome}".',
    "criado_pasta": " المجلد: {pasta}.",
    "pasta_nao_achada": ' لم أجد المجلد "{pasta}"؛ يمكنك إضافته لاحقًا من صفحة المشاريع.',
    "ja_existe": 'المشروع "{nome}" موجود بالفعل.',
    "ver_cabeca": "المشروع {nome}.",
    "ver_objetivo": "الهدف: {texto}.",
    "ver_estado": "الحالة: {texto}.",
    "ver_sem_estado": "لم تُسجَّل حالة بعد.",
    "ver_decisao": "آخر قرار: {texto}.",
    "ver_abertas": "المهام المعلقة: {lista}.",
    "ver_sem_abertas": "لا توجد مهام معلقة.",
    "ver_atividade": "آخر نشاط: {quando}.",
    "falta": "المتبقي في المشروع {nome}: {lista}.",
    "falta_nada": "لا توجد مهام معلقة في المشروع {nome}.",
    "decisao_ok": "سجلت في المشروع {nome}: {texto}.",
    "pendencia_ok": "أُضيفت مهمة إلى المشروع {nome}: {texto}.",
    "concluida_ok": "اكتملت مهمة في المشروع {nome}: {texto}.",
    "pendencia_nao_achada": "لم أجد هذه المهمة في المشروع {nome}. المعلقة: {lista}.",
    "estado_ok": "تم تحديث حالة المشروع {nome}: {texto}.",
    "arquivado": "تمت أرشفة المشروع {nome}.",
    "renomeado": "تمت إعادة تسمية المشروع إلى {nome}.",
    "falta_texto": "ماذا أسجل في المشروع {nome}؟",
    "nuvem": "بيانات مشاريعك تذهب إلى النماذج المحلية فقط. اختر نموذجًا محليًا لأتابع.",
    "continuar_sem_projetos": 'لا أعرف بعد على ماذا تعمل: لا توجد مشاريع. قل "أنشئ مشروع الاسم" وسأتابعه.',
    "quando_agora": "قبل قليل",
    "quando_min": "قبل {n} دقيقة",
    "quando_h": "قبل {n} ساعة",
    "quando_ontem": "أمس",
    "quando_dias": "قبل {n} أيام",
    "quando_data": "في {data}",
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
    """A frase *chave* no idioma (português se faltar)."""
    tabela = _TABELAS.get(_idioma(idioma).codigo, _PT)
    modelo = tabela.get(chave) or _TABELAS[PADRAO][chave]
    return modelo.format(**valores) if valores else modelo


def pendencias(n: int, idioma: Optional[str] = None) -> str:
    if n <= 0:
        return texto("pend_0", idioma)
    if n == 1:
        return texto("pend_1", idioma)
    return texto("pend_n", idioma, n=n)


def quando(
    iso: str, idioma: Optional[str] = None, agora: Optional[datetime] = None
) -> str:
    """ "há 10 min", "ontem", "há 3 dias"... a partir de uma data ISO local."""
    try:
        momento = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    agora = agora or datetime.now()
    segundos = (agora - momento).total_seconds()
    if segundos < 120:
        return texto("quando_agora", idioma)
    if segundos < 3600:
        return texto("quando_min", idioma, n=int(segundos // 60))
    dias = (agora.date() - momento.date()).days
    if dias <= 0:
        return texto("quando_h", idioma, n=int(segundos // 3600))
    if dias == 1:
        return texto("quando_ontem", idioma)
    if dias < 30:
        return texto("quando_dias", idioma, n=dias)
    return texto("quando_data", idioma, data=momento.date().isoformat())


def chaves() -> dict[str, set[str]]:
    """Chaves por idioma (para o teste que confere as tabelas)."""
    return {codigo: set(tabela) for codigo, tabela in _TABELAS.items()}


__all__ = ["chaves", "pendencias", "quando", "texto"]
