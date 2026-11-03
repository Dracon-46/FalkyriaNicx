# ruff: noqa: E501  (tabela de frases: uma por linha fica mais legível)
"""Frases do controle de apps no idioma da interface (português se faltar)."""

from __future__ import annotations

from typing import Optional

from nicx.nucleo.idiomas import PADRAO
from nicx.nucleo.idiomas import idioma as _idioma

_PT = {
    "sem_suporte": "Por enquanto só consigo mexer em janelas no Windows.",
    "sem_janela": "Não sei em qual janela mexer. Clique nela e me chame pelo atalho ou pela voz.",
    "sensivel": "Essa janela parece ser de senhas ou de banco ({app}); por segurança, não mexo nela.",
    "sem_acessibilidade": "Não consegui ler os botões do {app}.",
    "demorou": "O {app} demorou demais para responder.",
    "nao_achei": 'Não achei "{alvo}" no {app}.{sugestao}',
    "sugestao": " Tem: {lista}.",
    "clicado": 'Cliquei em "{nome}" no {app}.',
    "clicado_talvez": 'Cliquei em "{nome}"; o {app} ainda está respondendo (talvez tenha aberto uma janela).',
    "menu": 'Abri o menu "{nome}".',
    "aba": 'Fui para a aba "{nome}".',
    "marcado": 'Marquei "{nome}".',
    "desmarcado": 'Desmarquei "{nome}".',
    "ja_marcado": '"{nome}" já estava marcado.',
    "ja_desmarcado": '"{nome}" já estava desmarcado.',
    "digitado": 'Escrevi no campo "{nome}".',
    "senha": "Esse é um campo de senha; senha eu não digito.",
    "nao_clicavel": 'Achei "{nome}", mas o {app} não deixa acionar isso pela acessibilidade.',
    "desativado": '"{nome}" está desativado agora.',
    "lista": "No {app} dá para usar: {lista}.",
    "lista_vazia": "Não achei nada para clicar no {app}.",
    "confirmar": 'Vou clicar em "{alvo}" no {app}. Isso pode apagar, enviar ou pagar algo. Diga "confirmo" para seguir.',
    "explorer": "Explorador de Arquivos",
}  # fmt: skip

_EN = {
    "sem_suporte": "For now I can only control windows on Windows.",
    "sem_janela": "I don't know which window to use. Click it and call me with the shortcut or by voice.",
    "sensivel": "That window looks like a password or banking app ({app}); for safety, I won't touch it.",
    "sem_acessibilidade": "I couldn't read the buttons in {app}.",
    "demorou": "{app} took too long to respond.",
    "nao_achei": 'I couldn\'t find "{alvo}" in {app}.{sugestao}',
    "sugestao": " There is: {lista}.",
    "clicado": 'Clicked "{nome}" in {app}.',
    "clicado_talvez": 'Clicked "{nome}"; {app} is still responding (it may have opened a window).',
    "menu": 'Opened the "{nome}" menu.',
    "aba": 'Switched to the "{nome}" tab.',
    "marcado": 'Checked "{nome}".',
    "desmarcado": 'Unchecked "{nome}".',
    "ja_marcado": '"{nome}" was already checked.',
    "ja_desmarcado": '"{nome}" was already unchecked.',
    "digitado": 'Typed into the "{nome}" field.',
    "senha": "That's a password field; I don't type passwords.",
    "nao_clicavel": 'I found "{nome}", but {app} doesn\'t let me use it through accessibility.',
    "desativado": '"{nome}" is disabled right now.',
    "lista": "In {app} you can use: {lista}.",
    "lista_vazia": "I found nothing to click in {app}.",
    "confirmar": 'I\'m about to click "{alvo}" in {app}. That may delete, send or pay for something. Say "confirm" to go ahead.',
    "explorer": "File Explorer",
}  # fmt: skip

_ES = {
    "sem_suporte": "Por ahora solo puedo controlar ventanas en Windows.",
    "sem_janela": "No sé qué ventana usar. Haz clic en ella y llámame con el atajo o por voz.",
    "sensivel": "Esa ventana parece de contraseñas o de banco ({app}); por seguridad, no la toco.",
    "sem_acessibilidade": "No pude leer los botones de {app}.",
    "demorou": "{app} tardó demasiado en responder.",
    "nao_achei": 'No encontré "{alvo}" en {app}.{sugestao}',
    "sugestao": " Hay: {lista}.",
    "clicado": 'Hice clic en "{nome}" en {app}.',
    "clicado_talvez": 'Hice clic en "{nome}"; {app} todavía está respondiendo (quizá abrió una ventana).',
    "menu": 'Abrí el menú "{nome}".',
    "aba": 'Fui a la pestaña "{nome}".',
    "marcado": 'Marqué "{nome}".',
    "desmarcado": 'Desmarqué "{nome}".',
    "ja_marcado": '"{nome}" ya estaba marcado.',
    "ja_desmarcado": '"{nome}" ya estaba desmarcado.',
    "digitado": 'Escribí en el campo "{nome}".',
    "senha": "Es un campo de contraseña; no escribo contraseñas.",
    "nao_clicavel": 'Encontré "{nome}", pero {app} no deja usarlo por accesibilidad.',
    "desativado": '"{nome}" está desactivado ahora.',
    "lista": "En {app} puedes usar: {lista}.",
    "lista_vazia": "No encontré nada para hacer clic en {app}.",
    "confirmar": 'Voy a hacer clic en "{alvo}" en {app}. Eso puede borrar, enviar o pagar algo. Di "confirmo" para seguir.',
    "explorer": "Explorador de archivos",
}  # fmt: skip

_FR = {
    "sem_suporte": "Pour l'instant, je ne peux contrôler les fenêtres que sous Windows.",
    "sem_janela": "Je ne sais pas quelle fenêtre utiliser. Clique dessus et appelle-moi avec le raccourci ou à la voix.",
    "sensivel": "Cette fenêtre semble être un gestionnaire de mots de passe ou une banque ({app}) ; par sécurité, je n'y touche pas.",
    "sem_acessibilidade": "Je n'ai pas pu lire les boutons de {app}.",
    "demorou": "{app} a mis trop de temps à répondre.",
    "nao_achei": "Je n'ai pas trouvé « {alvo} » dans {app}.{sugestao}",
    "sugestao": " Il y a : {lista}.",
    "clicado": "J'ai cliqué sur « {nome} » dans {app}.",
    "clicado_talvez": "J'ai cliqué sur « {nome} » ; {app} répond encore (il a peut-être ouvert une fenêtre).",
    "menu": "J'ai ouvert le menu « {nome} ».",
    "aba": "Je suis passé à l'onglet « {nome} ».",
    "marcado": "J'ai coché « {nome} ».",
    "desmarcado": "J'ai décoché « {nome} ».",
    "ja_marcado": "« {nome} » était déjà coché.",
    "ja_desmarcado": "« {nome} » était déjà décoché.",
    "digitado": "J'ai écrit dans le champ « {nome} ».",
    "senha": "C'est un champ de mot de passe ; je ne tape pas de mots de passe.",
    "nao_clicavel": "J'ai trouvé « {nome} », mais {app} ne permet pas de l'utiliser par l'accessibilité.",
    "desativado": "« {nome} » est désactivé pour le moment.",
    "lista": "Dans {app}, tu peux utiliser : {lista}.",
    "lista_vazia": "Je n'ai rien trouvé à cliquer dans {app}.",
    "confirmar": "Je vais cliquer sur « {alvo} » dans {app}. Cela peut supprimer, envoyer ou payer quelque chose. Dis « je confirme » pour continuer.",
    "explorer": "Explorateur de fichiers",
}  # fmt: skip

_ZH = {
    "sem_suporte": "目前我只能在 Windows 上控制窗口。",
    "sem_janela": "我不知道要操作哪个窗口。点击它，再用快捷键或语音叫我。",
    "sensivel": "这个窗口看起来是密码或银行应用（{app}）；为了安全，我不会操作它。",
    "sem_acessibilidade": "我读不到 {app} 的按钮。",
    "demorou": "{app} 响应太慢了。",
    "nao_achei": "在 {app} 中没有找到“{alvo}”。{sugestao}",
    "sugestao": "有：{lista}。",
    "clicado": "已在 {app} 中点击“{nome}”。",
    "clicado_talvez": "已点击“{nome}”；{app} 仍在响应（可能打开了一个窗口）。",
    "menu": "已打开“{nome}”菜单。",
    "aba": "已切换到“{nome}”标签页。",
    "marcado": "已勾选“{nome}”。",
    "desmarcado": "已取消勾选“{nome}”。",
    "ja_marcado": "“{nome}”本来就已勾选。",
    "ja_desmarcado": "“{nome}”本来就未勾选。",
    "digitado": "已在“{nome}”字段中输入。",
    "senha": "这是密码字段；我不输入密码。",
    "nao_clicavel": "找到了“{nome}”，但 {app} 不允许通过辅助功能操作它。",
    "desativado": "“{nome}”现在不可用。",
    "lista": "在 {app} 中可以使用：{lista}。",
    "lista_vazia": "在 {app} 中没有找到可点击的内容。",
    "confirmar": "我将在 {app} 中点击“{alvo}”。这可能会删除、发送或支付某些内容。说“确认”继续。",
    "explorer": "文件资源管理器",
}  # fmt: skip

_HI = {
    "sem_suporte": "अभी मैं सिर्फ़ Windows पर विंडो चला सकता हूँ।",
    "sem_janela": "मुझे नहीं पता किस विंडो में काम करना है। उस पर क्लिक करें और शॉर्टकट या आवाज़ से मुझे बुलाएँ।",
    "sensivel": "यह विंडो पासवर्ड या बैंक की लगती है ({app}); सुरक्षा के लिए मैं इसे नहीं छूता।",
    "sem_acessibilidade": "मैं {app} के बटन नहीं पढ़ पाया।",
    "demorou": "{app} ने जवाब देने में बहुत देर लगाई।",
    "nao_achei": '{app} में "{alvo}" नहीं मिला।{sugestao}',
    "sugestao": " ये हैं: {lista}।",
    "clicado": '{app} में "{nome}" पर क्लिक किया।',
    "clicado_talvez": '"{nome}" पर क्लिक किया; {app} अभी भी जवाब दे रहा है (शायद कोई विंडो खुली है)।',
    "menu": '"{nome}" मेन्यू खोला।',
    "aba": '"{nome}" टैब पर गया।',
    "marcado": '"{nome}" चुना।',
    "desmarcado": '"{nome}" हटाया।',
    "ja_marcado": '"{nome}" पहले से चुना हुआ था।',
    "ja_desmarcado": '"{nome}" पहले से हटा हुआ था।',
    "digitado": '"{nome}" फ़ील्ड में लिखा।',
    "senha": "यह पासवर्ड फ़ील्ड है; मैं पासवर्ड नहीं लिखता।",
    "nao_clicavel": '"{nome}" मिला, पर {app} इसे एक्सेसिबिलिटी से चलाने नहीं देता।',
    "desativado": '"{nome}" अभी बंद है।',
    "lista": "{app} में आप ये इस्तेमाल कर सकते हैं: {lista}।",
    "lista_vazia": "{app} में क्लिक करने लायक कुछ नहीं मिला।",
    "confirmar": '{app} में "{alvo}" पर क्लिक करने वाला हूँ। इससे कुछ मिट, भेजा या भुगतान हो सकता है। आगे बढ़ने के लिए "पुष्टि करता हूँ" कहें।',
    "explorer": "फ़ाइल एक्सप्लोरर",
}  # fmt: skip

_AR = {
    "sem_suporte": "حاليًا أستطيع التحكم في النوافذ على Windows فقط.",
    "sem_janela": "لا أعرف أي نافذة أستخدم. انقر عليها ثم نادني بالاختصار أو بالصوت.",
    "sensivel": "تبدو هذه النافذة لكلمات المرور أو لبنك ({app})؛ لأمانك لن ألمسها.",
    "sem_acessibilidade": "لم أستطع قراءة أزرار {app}.",
    "demorou": "استغرق {app} وقتًا طويلًا للرد.",
    "nao_achei": 'لم أجد "{alvo}" في {app}.{sugestao}',
    "sugestao": " يوجد: {lista}.",
    "clicado": 'نقرت على "{nome}" في {app}.',
    "clicado_talvez": 'نقرت على "{nome}"؛ ما زال {app} يستجيب (ربما فتح نافذة).',
    "menu": 'فتحت قائمة "{nome}".',
    "aba": 'انتقلت إلى علامة التبويب "{nome}".',
    "marcado": 'حددت "{nome}".',
    "desmarcado": 'ألغيت تحديد "{nome}".',
    "ja_marcado": '"{nome}" كان محددًا بالفعل.',
    "ja_desmarcado": '"{nome}" كان غير محدد بالفعل.',
    "digitado": 'كتبت في الحقل "{nome}".',
    "senha": "هذا حقل كلمة مرور؛ لا أكتب كلمات المرور.",
    "nao_clicavel": 'وجدت "{nome}"، لكن {app} لا يسمح باستخدامه عبر إمكانية الوصول.',
    "desativado": '"{nome}" معطّل الآن.',
    "lista": "في {app} يمكنك استخدام: {lista}.",
    "lista_vazia": "لم أجد شيئًا للنقر عليه في {app}.",
    "confirmar": 'سأنقر على "{alvo}" في {app}. قد يحذف ذلك شيئًا أو يرسله أو يدفع ثمنه. قل "أؤكد" للمتابعة.',
    "explorer": "مستكشف الملفات",
}  # fmt: skip

_TABELAS = {
    "pt-BR": _PT,
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
