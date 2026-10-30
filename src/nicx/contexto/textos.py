# ruff: noqa: E501  (tabela de frases: uma por linha fica mais legível)
"""Frases do contexto da tela no idioma da interface.

O português é a referência: se faltar uma chave em outro idioma, sai em
português. Os códigos são os de :mod:`nicx.nucleo.idiomas`.
"""

from __future__ import annotations

from typing import Optional

from nicx.nucleo.idiomas import PADRAO
from nicx.nucleo.idiomas import idioma as _idioma

_PT = {
    "sem_suporte": (
        "Por enquanto só consigo ver a área de transferência e a janela aberta"
        " no Windows."
    ),
    "clip_vazia": (
        "A área de transferência está vazia ou não tem texto. Copie o texto"
        " (Ctrl+C) e peça de novo."
    ),
    "clip_protegida": (
        "O que está copiado veio de um gerenciador de senhas; por segurança, não leio."
    ),
    "clip_ocupada": (
        "A área de transferência está ocupada por outro programa. Tente de novo"
        " em um instante."
    ),
    "sem_janela": (
        "Não sei qual janela você está vendo. Clique nela e me chame pelo atalho"
        ' ou pela voz, ou copie o texto (Ctrl+C) e peça "resume o que eu copiei".'
    ),
    "janela_sensivel": (
        "Essa janela parece ser de senhas ou de banco ({app}); por segurança,"
        " não leio o que tem nela."
    ),
    "janela_sem_texto": (
        "Estou vendo {onde}, mas não consegui ler o texto. Selecione, copie"
        ' (Ctrl+C) e peça "explica o que eu copiei".'
    ),
    "onde": "Você está no {app}{detalhe}.",
    "onde_arquivo": ", no arquivo {arquivo}",
    "onde_titulo": " ({titulo})",
    "nuvem": (
        "O que está na sua tela só vai para modelos locais. Escolha um modelo"
        " local para eu ler."
    ),
    "explorer": "Explorador de Arquivos",
}

_EN = {
    "sem_suporte": "For now I can only see the clipboard and the open window on Windows.",
    "clip_vazia": (
        "The clipboard is empty or has no text. Copy the text (Ctrl+C) and ask again."
    ),
    "clip_protegida": (
        "What you copied came from a password manager; for safety, I won't read it."
    ),
    "clip_ocupada": "Another program is using the clipboard. Try again in a moment.",
    "sem_janela": (
        "I don't know which window you're looking at. Click it and call me with"
        ' the shortcut or by voice, or copy the text (Ctrl+C) and ask "summarize'
        ' what I copied".'
    ),
    "janela_sensivel": (
        "That window looks like a password or banking app ({app}); for safety,"
        " I won't read it."
    ),
    "janela_sem_texto": (
        "I can see {onde}, but I couldn't read its text. Select it, copy (Ctrl+C)"
        ' and ask "explain what I copied".'
    ),
    "onde": "You're in {app}{detalhe}.",
    "onde_arquivo": ", in the file {arquivo}",
    "onde_titulo": " ({titulo})",
    "nuvem": (
        "What's on your screen only goes to local models. Pick a local model and"
        " I'll read it."
    ),
    "explorer": "File Explorer",
}

_ES = {
    "sem_suporte": (
        "Por ahora solo puedo ver el portapapeles y la ventana abierta en Windows."
    ),
    "clip_vazia": (
        "El portapapeles está vacío o no tiene texto. Copia el texto (Ctrl+C) y"
        " vuelve a pedirlo."
    ),
    "clip_protegida": (
        "Lo copiado viene de un gestor de contraseñas; por seguridad, no lo leo."
    ),
    "clip_ocupada": (
        "Otro programa está usando el portapapeles. Inténtalo de nuevo en un momento."
    ),
    "sem_janela": (
        "No sé qué ventana estás viendo. Haz clic en ella y llámame con el atajo"
        ' o por voz, o copia el texto (Ctrl+C) y pide "resume lo que copié".'
    ),
    "janela_sensivel": (
        "Esa ventana parece de contraseñas o de banco ({app}); por seguridad,"
        " no leo lo que contiene."
    ),
    "janela_sem_texto": (
        "Veo {onde}, pero no pude leer el texto. Selecciónalo, cópialo (Ctrl+C)"
        ' y pide "explica lo que copié".'
    ),
    "onde": "Estás en {app}{detalhe}.",
    "onde_arquivo": ", en el archivo {arquivo}",
    "onde_titulo": " ({titulo})",
    "nuvem": (
        "Lo que hay en tu pantalla solo va a modelos locales. Elige un modelo"
        " local para que lo lea."
    ),
    "explorer": "Explorador de archivos",
}

_FR = {
    "sem_suporte": (
        "Pour l'instant, je ne vois le presse-papiers et la fenêtre ouverte que"
        " sous Windows."
    ),
    "clip_vazia": (
        "Le presse-papiers est vide ou ne contient pas de texte. Copie le texte"
        " (Ctrl+C) et redemande."
    ),
    "clip_protegida": (
        "Ce que tu as copié vient d'un gestionnaire de mots de passe ; par"
        " sécurité, je ne le lis pas."
    ),
    "clip_ocupada": (
        "Un autre programme utilise le presse-papiers. Réessaie dans un instant."
    ),
    "sem_janela": (
        "Je ne sais pas quelle fenêtre tu regardes. Clique dessus et appelle-moi"
        " avec le raccourci ou à la voix, ou copie le texte (Ctrl+C) et demande"
        " « résume ce que j'ai copié »."
    ),
    "janela_sensivel": (
        "Cette fenêtre semble être celle de mots de passe ou d'une banque ({app}) ;"
        " par sécurité, je ne la lis pas."
    ),
    "janela_sem_texto": (
        "Je vois {onde}, mais je n'ai pas pu lire le texte. Sélectionne-le,"
        " copie-le (Ctrl+C) et demande « explique ce que j'ai copié »."
    ),
    "onde": "Tu es dans {app}{detalhe}.",
    "onde_arquivo": ", dans le fichier {arquivo}",
    "onde_titulo": " ({titulo})",
    "nuvem": (
        "Ce qui est à l'écran ne va qu'aux modèles locaux. Choisis un modèle"
        " local pour que je le lise."
    ),
    "explorer": "Explorateur de fichiers",
}

_ZH = {
    "sem_suporte": "目前我只能在 Windows 上查看剪贴板和打开的窗口。",
    "clip_vazia": "剪贴板是空的或没有文本。请复制文本（Ctrl+C）后再问一次。",
    "clip_protegida": "复制的内容来自密码管理器；为了安全，我不会读取。",
    "clip_ocupada": "另一个程序正在使用剪贴板。请稍后再试。",
    "sem_janela": (
        "我不知道你在看哪个窗口。点击它，再用快捷键或语音叫我，"
        "或者复制文本（Ctrl+C）然后说“总结我复制的内容”。"
    ),
    "janela_sensivel": "这个窗口看起来是密码或银行应用（{app}）；为了安全，我不会读取。",
    "janela_sem_texto": "我看到了{onde}，但读不到文本。请选中并复制（Ctrl+C），然后说“解释我复制的内容”。",
    "onde": "你在 {app}{detalhe}。",
    "onde_arquivo": "，文件 {arquivo}",
    "onde_titulo": "（{titulo}）",
    "nuvem": "屏幕上的内容只会发给本地模型。请选择一个本地模型。",
    "explorer": "文件资源管理器",
}

_HI = {
    "sem_suporte": "अभी मैं क्लिपबोर्ड और खुली विंडो सिर्फ़ Windows पर देख सकता हूँ।",
    "clip_vazia": "क्लिपबोर्ड खाली है या उसमें टेक्स्ट नहीं है। टेक्स्ट कॉपी करें (Ctrl+C) और फिर से पूछें।",
    "clip_protegida": "कॉपी किया गया टेक्स्ट पासवर्ड मैनेजर से आया है; सुरक्षा के लिए मैं इसे नहीं पढ़ता।",
    "clip_ocupada": "कोई दूसरा प्रोग्राम क्लिपबोर्ड इस्तेमाल कर रहा है। थोड़ी देर में फिर कोशिश करें।",
    "sem_janela": (
        "मुझे नहीं पता आप कौन-सी विंडो देख रहे हैं। उस पर क्लिक करें और शॉर्टकट या आवाज़ से"
        ' मुझे बुलाएँ, या टेक्स्ट कॉपी करें (Ctrl+C) और कहें "जो मैंने कॉपी किया उसका सार दो"।'
    ),
    "janela_sensivel": "यह विंडो पासवर्ड या बैंक की लगती है ({app}); सुरक्षा के लिए मैं इसे नहीं पढ़ता।",
    "janela_sem_texto": (
        "मुझे {onde} दिख रहा है, पर मैं टेक्स्ट नहीं पढ़ पाया। उसे चुनें, कॉपी करें (Ctrl+C)"
        ' और कहें "जो मैंने कॉपी किया उसे समझाओ"।'
    ),
    "onde": "आप {app}{detalhe} में हैं।",
    "onde_arquivo": ", फ़ाइल {arquivo}",
    "onde_titulo": " ({titulo})",
    "nuvem": "स्क्रीन की सामग्री सिर्फ़ लोकल मॉडल को जाती है। पढ़वाने के लिए कोई लोकल मॉडल चुनें।",
    "explorer": "फ़ाइल एक्सप्लोरर",
}

_AR = {
    "sem_suporte": "حاليًا أستطيع رؤية الحافظة والنافذة المفتوحة على Windows فقط.",
    "clip_vazia": "الحافظة فارغة أو لا تحتوي على نص. انسخ النص (Ctrl+C) واطلب مرة أخرى.",
    "clip_protegida": "ما نسخته جاء من مدير كلمات مرور؛ لأمانك لن أقرأه.",
    "clip_ocupada": "برنامج آخر يستخدم الحافظة. حاول مرة أخرى بعد لحظة.",
    "sem_janela": (
        "لا أعرف أي نافذة تشاهد. انقر عليها ثم نادني بالاختصار أو بالصوت،"
        ' أو انسخ النص (Ctrl+C) واطلب "لخّص ما نسخته".'
    ),
    "janela_sensivel": "تبدو هذه النافذة لكلمات المرور أو لبنك ({app})؛ لأمانك لن أقرأها.",
    "janela_sem_texto": (
        'أرى {onde}، لكني لم أستطع قراءة النص. حدّده وانسخه (Ctrl+C) واطلب "اشرح ما نسخته".'
    ),
    "onde": "أنت في {app}{detalhe}.",
    "onde_arquivo": "، في الملف {arquivo}",
    "onde_titulo": " ({titulo})",
    "nuvem": "ما على شاشتك يذهب إلى النماذج المحلية فقط. اختر نموذجًا محليًا لأقرأه.",
    "explorer": "مستكشف الملفات",
}

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
    """A frase *chave* no idioma (português se faltar)."""
    tabela = _TABELAS.get(_idioma(idioma).codigo, _PT)
    modelo = tabela.get(chave) or _TABELAS[PADRAO][chave]
    return modelo.format(**valores) if valores else modelo


__all__ = ["texto"]
