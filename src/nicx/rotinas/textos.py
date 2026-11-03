# ruff: noqa: E501  (tabela de frases: uma por linha fica mais legível)
"""Frases das rotinas no idioma da interface (português se faltar)."""

from __future__ import annotations

from typing import Optional

from nicx.nucleo.idiomas import PADRAO
from nicx.nucleo.idiomas import idioma as _idioma

_PT = {
    "executada": "Rotina {nome}: {passos}",
    "falhas": " Não deu: {lista}.",
    "criada": 'Rotina "{nome}" criada com {n} passos.{quando}',
    "quando": " Roda {dias} às {hora}.",
    "nao_entendi": 'Não entendi estes passos: {lista}. Diga cada um como um comando, separado por vírgula, por exemplo "abre o chrome, volume 30, timer de 25 minutos".',
    "proibidos": "Estes passos não podem ficar numa rotina: {lista}.",
    "sem_passos": 'Faltaram os passos. Exemplo: "cria a rotina modo foco: fecha o WhatsApp, volume 20, timer de 50 minutos".',
    "ja_existe": 'Já existe uma rotina chamada "{nome}".',
    "lista": "Suas rotinas: {lista}.",
    "lista_vazia": 'Você ainda não tem rotinas. Diga, por exemplo: "cria a rotina preparar estudo: abre o chrome, volume 30, timer de 50 minutos".',
    "apagada": 'Rotina "{nome}" apagada. Dá para desfazer com "desfaz".',
    "nao_achei": 'Não achei a rotina "{nome}".',
    "todos_os_dias": "todo dia",
    "dias_uteis": "de segunda a sexta",
    "fim_de_semana": "no fim de semana",
    "dia_seg": "segunda", "dia_ter": "terça", "dia_qua": "quarta", "dia_qui": "quinta", "dia_sex": "sexta", "dia_sab": "sábado", "dia_dom": "domingo",
    "e": " e ",
    "foco_nome": "modo foco",
    "foco_fim": "fim do modo foco",
    "notificacao": "Rotina {nome}: {passos}",
    "abrindo_site": "Abrindo {site}.",
    "site_invalido": "Endereço inválido: {site}.",
}  # fmt: skip

_EN = {
    "executada": "Routine {nome}: {passos}",
    "falhas": " Didn't work: {lista}.",
    "criada": 'Routine "{nome}" created with {n} steps.{quando}',
    "quando": " Runs {dias} at {hora}.",
    "nao_entendi": 'I didn\'t understand these steps: {lista}. Say each one as a command, separated by commas, for example "open chrome, volume 30, timer for 25 minutes".',
    "proibidos": "These steps can't be in a routine: {lista}.",
    "sem_passos": 'The steps are missing. Example: "create routine focus mode: close WhatsApp, volume 20, timer for 50 minutes".',
    "ja_existe": 'There is already a routine called "{nome}".',
    "lista": "Your routines: {lista}.",
    "lista_vazia": 'You have no routines yet. Say, for example: "create routine study time: open chrome, volume 30, timer for 50 minutes".',
    "apagada": 'Routine "{nome}" deleted. Say "undo" to bring it back.',
    "nao_achei": 'I couldn\'t find the routine "{nome}".',
    "todos_os_dias": "every day",
    "dias_uteis": "Monday to Friday",
    "fim_de_semana": "on weekends",
    "dia_seg": "Monday", "dia_ter": "Tuesday", "dia_qua": "Wednesday", "dia_qui": "Thursday", "dia_sex": "Friday", "dia_sab": "Saturday", "dia_dom": "Sunday",
    "e": " and ",
    "foco_nome": "focus mode",
    "foco_fim": "end of focus mode",
    "notificacao": "Routine {nome}: {passos}",
    "abrindo_site": "Opening {site}.",
    "site_invalido": "Invalid address: {site}.",
}  # fmt: skip

_ES = {
    "executada": "Rutina {nome}: {passos}",
    "falhas": " No funcionó: {lista}.",
    "criada": 'Rutina "{nome}" creada con {n} pasos.{quando}',
    "quando": " Se ejecuta {dias} a las {hora}.",
    "nao_entendi": 'No entendí estos pasos: {lista}. Di cada uno como un comando, separado por comas, por ejemplo "abre chrome, volumen 30, temporizador de 25 minutos".',
    "proibidos": "Estos pasos no pueden estar en una rutina: {lista}.",
    "sem_passos": 'Faltan los pasos. Ejemplo: "crea la rutina modo concentración: cierra WhatsApp, volumen 20, temporizador de 50 minutos".',
    "ja_existe": 'Ya existe una rutina llamada "{nome}".',
    "lista": "Tus rutinas: {lista}.",
    "lista_vazia": 'Todavía no tienes rutinas. Di, por ejemplo: "crea la rutina estudiar: abre chrome, volumen 30, temporizador de 50 minutos".',
    "apagada": 'Rutina "{nome}" eliminada. Di "deshaz" para recuperarla.',
    "nao_achei": 'No encontré la rutina "{nome}".',
    "todos_os_dias": "todos los días",
    "dias_uteis": "de lunes a viernes",
    "fim_de_semana": "los fines de semana",
    "dia_seg": "lunes", "dia_ter": "martes", "dia_qua": "miércoles", "dia_qui": "jueves", "dia_sex": "viernes", "dia_sab": "sábado", "dia_dom": "domingo",
    "e": " y ",
    "foco_nome": "modo concentración",
    "foco_fim": "fin del modo concentración",
    "notificacao": "Rutina {nome}: {passos}",
    "abrindo_site": "Abriendo {site}.",
    "site_invalido": "Dirección no válida: {site}.",
}  # fmt: skip

_FR = {
    "executada": "Routine {nome} : {passos}",
    "falhas": " Échec : {lista}.",
    "criada": "Routine « {nome} » créée avec {n} étapes.{quando}",
    "quando": " Elle tourne {dias} à {hora}.",
    "nao_entendi": "Je n'ai pas compris ces étapes : {lista}. Dites chacune comme une commande, séparées par des virgules, par exemple « ouvre chrome, volume 30, minuteur de 25 minutes ».",
    "proibidos": "Ces étapes ne peuvent pas faire partie d'une routine : {lista}.",
    "sem_passos": "Il manque les étapes. Exemple : « crée la routine mode concentration : ferme WhatsApp, volume 20, minuteur de 50 minutes ».",
    "ja_existe": "Il existe déjà une routine appelée « {nome} ».",
    "lista": "Vos routines : {lista}.",
    "lista_vazia": "Vous n'avez pas encore de routines. Dites par exemple : « crée la routine étude : ouvre chrome, volume 30, minuteur de 50 minutes ».",
    "apagada": "Routine « {nome} » supprimée. Dites « défais ça » pour la récupérer.",
    "nao_achei": "Je n'ai pas trouvé la routine « {nome} ».",
    "todos_os_dias": "tous les jours",
    "dias_uteis": "du lundi au vendredi",
    "fim_de_semana": "le week-end",
    "dia_seg": "lundi", "dia_ter": "mardi", "dia_qua": "mercredi", "dia_qui": "jeudi", "dia_sex": "vendredi", "dia_sab": "samedi", "dia_dom": "dimanche",
    "e": " et ",
    "foco_nome": "mode concentration",
    "foco_fim": "fin du mode concentration",
    "notificacao": "Routine {nome} : {passos}",
    "abrindo_site": "J'ouvre {site}.",
    "site_invalido": "Adresse invalide : {site}.",
}  # fmt: skip

_ZH = {
    "executada": "例程 {nome}：{passos}",
    "falhas": " 未完成：{lista}。",
    "criada": "已创建例程“{nome}”，共 {n} 个步骤。{quando}",
    "quando": "在{dias} {hora} 运行。",
    "nao_entendi": "我没有理解这些步骤：{lista}。请把每一步说成一个命令，用逗号分开。",
    "proibidos": "这些步骤不能放进例程：{lista}。",
    "sem_passos": "缺少步骤。请在例程页面添加步骤。",
    "ja_existe": "已经有名为“{nome}”的例程。",
    "lista": "你的例程：{lista}。",
    "lista_vazia": "你还没有例程。可以在例程页面创建。",
    "apagada": "已删除例程“{nome}”。说“撤销”可以恢复。",
    "nao_achei": "没有找到例程“{nome}”。",
    "todos_os_dias": "每天",
    "dias_uteis": "周一到周五",
    "fim_de_semana": "周末",
    "dia_seg": "周一", "dia_ter": "周二", "dia_qua": "周三", "dia_qui": "周四", "dia_sex": "周五", "dia_sab": "周六", "dia_dom": "周日",
    "e": "和",
    "foco_nome": "专注模式",
    "foco_fim": "专注模式结束",
    "notificacao": "例程 {nome}：{passos}",
    "abrindo_site": "正在打开 {site}。",
    "site_invalido": "地址无效：{site}。",
}  # fmt: skip

_HI = {
    "executada": "रूटीन {nome}: {passos}",
    "falhas": " यह नहीं हुआ: {lista}।",
    "criada": 'रूटीन "{nome}" {n} चरणों के साथ बनाया गया।{quando}',
    "quando": " यह {dias} {hora} बजे चलेगा।",
    "nao_entendi": "मैं ये चरण नहीं समझ पाया: {lista}। हर चरण को अल्पविराम से अलग करके एक आदेश की तरह कहें।",
    "proibidos": "ये चरण रूटीन में नहीं रखे जा सकते: {lista}।",
    "sem_passos": "चरण नहीं मिले। रूटीन पेज पर चरण जोड़ें।",
    "ja_existe": '"{nome}" नाम का रूटीन पहले से है।',
    "lista": "आपके रूटीन: {lista}।",
    "lista_vazia": "आपके पास अभी कोई रूटीन नहीं है। रूटीन पेज पर बनाएँ।",
    "apagada": 'रूटीन "{nome}" हटाया गया। वापस लाने के लिए "पूर्ववत करो" कहें।',
    "nao_achei": 'मुझे "{nome}" रूटीन नहीं मिला।',
    "todos_os_dias": "हर दिन",
    "dias_uteis": "सोमवार से शुक्रवार",
    "fim_de_semana": "सप्ताहांत में",
    "dia_seg": "सोमवार", "dia_ter": "मंगलवार", "dia_qua": "बुधवार", "dia_qui": "गुरुवार", "dia_sex": "शुक्रवार", "dia_sab": "शनिवार", "dia_dom": "रविवार",
    "e": " और ",
    "foco_nome": "फ़ोकस मोड",
    "foco_fim": "फ़ोकस मोड खत्म",
    "notificacao": "रूटीन {nome}: {passos}",
    "abrindo_site": "{site} खोल रहा हूँ।",
    "site_invalido": "अमान्य पता: {site}।",
}  # fmt: skip

_AR = {
    "executada": "الروتين {nome}: {passos}",
    "falhas": " لم ينجح: {lista}.",
    "criada": 'تم إنشاء الروتين "{nome}" بعدد {n} خطوات.{quando}',
    "quando": " يعمل {dias} الساعة {hora}.",
    "nao_entendi": "لم أفهم هذه الخطوات: {lista}. قل كل خطوة كأمر، مفصولة بفاصلة.",
    "proibidos": "لا يمكن وضع هذه الخطوات في روتين: {lista}.",
    "sem_passos": "الخطوات ناقصة. أضف الخطوات في صفحة الروتين.",
    "ja_existe": 'يوجد روتين باسم "{nome}" بالفعل.',
    "lista": "روتيناتك: {lista}.",
    "lista_vazia": "ليس لديك روتين بعد. يمكنك إنشاؤه في صفحة الروتين.",
    "apagada": 'تم حذف الروتين "{nome}". قل "تراجع" لاستعادته.',
    "nao_achei": 'لم أجد الروتين "{nome}".',
    "todos_os_dias": "كل يوم",
    "dias_uteis": "من الاثنين إلى الجمعة",
    "fim_de_semana": "في عطلة نهاية الأسبوع",
    "dia_seg": "الاثنين", "dia_ter": "الثلاثاء", "dia_qua": "الأربعاء", "dia_qui": "الخميس", "dia_sex": "الجمعة", "dia_sab": "السبت", "dia_dom": "الأحد",
    "e": " و",
    "foco_nome": "وضع التركيز",
    "foco_fim": "انتهاء وضع التركيز",
    "notificacao": "الروتين {nome}: {passos}",
    "abrindo_site": "جارٍ فتح {site}.",
    "site_invalido": "عنوان غير صالح: {site}.",
}  # fmt: skip

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


def dias(lista: list[str], idioma: Optional[str] = None) -> str:
    """['seg'...'sex'] -> 'de segunda a sexta'; ['seg', 'qua'] -> 'segunda e quarta'."""
    if len(lista) == 7:
        return texto("todos_os_dias", idioma)
    if lista == ["seg", "ter", "qua", "qui", "sex"]:
        return texto("dias_uteis", idioma)
    if lista == ["sab", "dom"]:
        return texto("fim_de_semana", idioma)
    nomes = [texto(f"dia_{d}", idioma) for d in lista]
    if len(nomes) == 1:
        return nomes[0]
    return ", ".join(nomes[:-1]) + texto("e", idioma) + nomes[-1]


def chaves() -> dict[str, set[str]]:
    return {codigo: set(tabela) for codigo, tabela in _TABELAS.items()}


__all__ = ["chaves", "dias", "texto"]
