"""Frases das ações rápidas, no idioma da interface.

Toda frase que as ações devolvem ao usuário mora aqui: um dicionário por
idioma (os mesmos códigos de ``nicx.nucleo.idiomas``) e a função ``texto``.
O português é a referência: se faltar uma chave em outro idioma, sai em
português. Datas e horas são montadas à mão, sem ``strftime`` (o ``%-d``
quebra no Windows e o ``%A`` depende do locale do sistema).

O idioma vale para a chamada inteira: ``handle(texto, "en")`` liga o inglês
com ``usando`` e as funções daqui leem o idioma atual sem precisar receber
o código em cada uma.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator, Optional

from nicx.nucleo.idiomas import PADRAO
from nicx.nucleo.idiomas import idioma as _idioma

_atual: contextvars.ContextVar[str] = contextvars.ContextVar(
    "nicx_acoes_idioma", default=PADRAO
)


def codigo(idioma: Optional[str] = None) -> str:
    """O código da tabela ("pt-BR", "en"...); sem código, o idioma atual."""
    if idioma is None:
        return _atual.get()
    return _idioma(idioma).codigo


@contextmanager
def usando(idioma: Optional[str]) -> Iterator[str]:
    """Liga o idioma das respostas dentro do ``with``.

    ``None`` mantém o idioma atual (o português, se ninguém mudou).
    """
    if idioma is None:
        yield _atual.get()
        return
    token = _atual.set(_idioma(idioma).codigo)
    try:
        yield _atual.get()
    finally:
        _atual.reset(token)


# ---------------------------------------------------------------------------
# Frases
# ---------------------------------------------------------------------------

_PT = {
    # Gerais
    "windows_only": "Isso eu só sei fazer no Windows por enquanto.",
    "falhou": "Não consegui fazer isso agora.",
    "nao_sei": "Não sei fazer isso ainda.",
    # Volume e mídia
    "mudo": "Pronto, alternei o mudo.",
    "volume_em": "Volume em {n}%.",
    "volume_mais": "Aumentei o volume.",
    "volume_menos": "Abaixei o volume.",
    "midia_alternar": "Pronto.",
    "midia_proxima": "Próxima.",
    "midia_anterior": "Voltei para a anterior.",
    # Abrir, pesquisar, hora, data, bateria, tela
    "abrindo": "Abrindo {alvo}.",
    "app_nao_encontrado": "Não encontrei {app} neste computador.",
    "pesquisando_google": "Pesquisando {q} no Google.",
    "pesquisando_youtube": "Pesquisando {q} no YouTube.",
    "hora": "São {hora}.",
    "hora_cheia": "São {h}h em ponto.",
    "data": "Hoje é {semana}, {dia} de {mes}.",
    "sem_bateria": "Não encontrei bateria neste computador.",
    "bateria": "Bateria em {n}%{carregando}.",
    "carregando": ", carregando",
    "tela_bloqueada": "Tela bloqueada.",
    # Lembretes e anotações
    "timer_marcado": "Timer marcado: aviso {quando}.",
    "alarme_marcado": "Alarme marcado {quando}.",
    "lembrete_marcado": "Combinado: {quando} eu te lembro de {o_que}.",
    "sem_lembretes": "Você não tem lembretes marcados.",
    "lista_lembretes": "Você tem {qtd}: {itens}{mais}.",
    "e_mais": " e mais {n}",
    "nome_timer": "timer",
    "nome_alarme": "alarme",
    "nada_cancelar_varios": "Não havia {nomes} para cancelar.",
    "nada_cancelar_um": "Não havia {nome} para cancelar.",
    "cancelei_qtd": "Cancelei {qtd}.",
    "cancelei_lembrete": "Cancelei o lembrete de {o_que}.",
    "cancelei_tipo": "Cancelei {o_nome} de {quando}.",
    "o_lembrete": "o lembrete",
    "o_timer": "o timer",
    "o_alarme": "o alarme",
    "anotado": "Anotado.",
    "sem_anotacoes": "Você ainda não tem anotações.",
    "sua_anotacao": "Sua anotação: {itens}.",
    "suas_anotacoes": "Suas últimas {n} anotações: {itens}.",
    "apaguei_qtd": "Apaguei {qtd}.",
    # Estado do PC
    "st_cpu": "processador em {n}%",
    "st_mem": "memória {n}% usada ({gb} GB livres)",
    "st_disco": "disco com {gb} GB livres",
    "st_bateria": "bateria em {n}%{carregando}",
    "st_agora": "Agora: {partes}.",
    "st_pesados": " O que mais usa memória: {top}.",
    "st_item": "{nome} ({gb} GB)",
    "sep": ", ",
    "e": " e ",
    # Pastas, print, fechar
    "pasta_nao_achei": "Não achei a pasta {pasta}.",
    "sem_pillow": "Para tirar print eu preciso do pacote Pillow.",
    "print_salvo": "Print salvo em {pasta}\\Nicx.",
    "nao_esta_aberto": "{App} não está aberto.",
    "fechando": "Fechando {app}.",
    # Energia (sempre com confirmação)
    "desligamento_cancelado": "Desligamento cancelado.",
    "pergunta_energia": (
        'Tem certeza que quer {acao}? Diga "confirmo" em até 30 segundos.'
    ),
    "acao_shutdown": "desligar o computador",
    "acao_restart": "reiniciar o computador",
    "acao_suspend": "suspender o computador",
    "nada_confirmar": "Não há nada esperando confirmação.",
    "desligando": (
        'Desligando em 30 segundos. Para cancelar, diga "cancela o desligamento".'
    ),
    "reiniciando": (
        'Reiniciando em 30 segundos. Para cancelar, diga "cancela o reinício".'
    ),
    "suspendendo": "Suspendendo em 3 segundos.",
    "nada_feito": "Tudo bem, não vou fazer nada.",
    # Agenda
    "horario_passou": "Esse horário já passou ({quando}). Me diz outro.",
    "aviso_8h": " Te aviso às 8h do dia.",
    "aviso_15min": " Te aviso 15 minutos antes.",
    "marquei_dia_todo": "Marquei {titulo} {dia}, o dia todo.{aviso}",
    "marquei": "Marquei {titulo} {quando}.{aviso}",
    "nada_no_dia": "Nada marcado para {dia}.",
    "item_dia_todo": "{titulo} o dia todo",
    "item_hora": "{titulo} às {hora}",
    "voce_tem_no_dia": "{Dia} você tem: {itens}.",
    "nada_7_dias": "Nada marcado nos próximos 7 dias.",
    "proximos_7_dias": "Nos próximos 7 dias",
    "proximos_compromissos": "Seus próximos compromissos",
    "lista": "{titulo}: {itens}{mais}.",
    "evento_dia_todo": "{titulo} {dia}, o dia todo",
    "evento": "{titulo} {quando}",
    "compromisso_nao_achei": "Não achei esse compromisso na agenda.",
    "desmarquei": "Desmarquei {evento}.",
    "nada_exportar": "Não há compromissos marcados para mandar.",
    "ics_salvo": "Salvei {qtd} em {caminho}. Abra no seu calendário.",
    "ics_aberto": "Abri {qtd} no calendário do Windows: é só confirmar por lá.",
    # Google Agenda, Outlook e avisos
    "o_que_pediu": "o que você pediu",
    "aviso_lembrete": "Lembrete: {o_que}.",
    "aviso_timer": "Lembrete: o tempo acabou.",
    "aviso_alarme": "Lembrete: alarme.",
    "aviso_atrasado": " (era para {hora}; o Nicx estava desligado)",
    "aviso_daqui_15": "Daqui a 15 minutos: {titulo}",
    "aviso_hoje": "Hoje: {titulo}",
    "cal_google": "Google Agenda",
    "cal_outlook": "Outlook",
    "cal_criado": "Pronto: {titulo} já está no {cal}.",
    "cal_criados": "Pronto: mandei {qtd} para o {cal}.",
    "cal_ja_estava": "{titulo} já estava no {cal}.",
    "cal_todos_ja_estavam": "Esses compromissos já estavam no {cal}.",
    "cal_link": "Abri {titulo} no {cal}: é só clicar em Salvar.",
    "cal_links": (
        "Abri {qtd} no {cal}, um em cada aba: é só clicar em Salvar em cada um."
    ),
    "cal_reconectar_google": (
        " Para eu criar direto, reconecte o Google Agenda dando permissão de escrita."
    ),
    "cal_reconectar_outlook": (
        " Para eu criar direto, reconecte o Outlook dando permissão de agenda."
    ),
    "item_origem": "{item} ({origem})",
    # Arquivos, organização e YouTube
    "nenhum_arquivo": "Não achei nenhum {nome} nas suas pastas.",
    "nao_achei_nome": 'Não achei {nome} com "{q}" no nome.',
    "outros_parecidos": "{msg} Achei outros {n} parecidos.",
    "achei": "Achei {qtd}: {nomes}.",
    "pasta_vazia": "A pasta {pasta} está vazia.",
    "na_pasta": "Em {pasta} (mais recentes): {nomes}{mais}.",
    "ja_organizada": "{pasta} já está organizada: nada solto para mover.",
    "vou_organizar": (
        "Vou separar {qtd} de {pasta} em pastas ({resumo}). Nada é apagado e dá"
        ' para desfazer. Diga "confirmo" em até 30 segundos.'
    ),
    "pasta_sumiu": "Não achei a pasta.",
    "organizado": (
        'Pronto: {qtd} em {pasta}. Se não gostar, diga "desfaz a organização".'
    ),
    "nada_desfazer": "Não há organização para desfazer.",
    "desfeito": "Desfeito: {qtd} para {pasta}.",
    "youtube_busca": "Abri a busca por {q} no YouTube.",
    "youtube_tocando": "Tocando {q} no YouTube.",
    # Quando ("em 5 minutos", "amanhã às 8h") e dias ("sexta (31/10)")
    "q_segundo": "em {n} segundo",
    "q_segundos": "em {n} segundos",
    "q_minuto": "em {n} minuto",
    "q_minutos": "em {n} minutos",
    "q_hoje": "às {hora}",
    "q_amanha": "amanhã às {hora}",
    "q_data": "dia {dd}/{mm} às {hora}",
    "d_hoje": "hoje",
    "d_amanha": "amanhã",
    "d_semana": "{semana} ({dd}/{mm})",
    "d_data": "dia {dd}/{mm}",
    "d_com_hora": "{dia} às {hora}",
}

_EN = {
    "windows_only": "I can only do that on Windows for now.",
    "falhou": "I couldn't do that right now.",
    "nao_sei": "I don't know how to do that yet.",
    "mudo": "Done, toggled mute.",
    "volume_em": "Volume at {n}%.",
    "volume_mais": "Turned the volume up.",
    "volume_menos": "Turned the volume down.",
    "midia_alternar": "Done.",
    "midia_proxima": "Next.",
    "midia_anterior": "Back to the previous one.",
    "abrindo": "Opening {alvo}.",
    "app_nao_encontrado": "I couldn't find {app} on this computer.",
    "pesquisando_google": "Searching Google for {q}.",
    "pesquisando_youtube": "Searching YouTube for {q}.",
    "hora": "It's {hora}.",
    "hora_cheia": "It's {hora} on the dot.",
    "data": "Today is {semana}, {mes} {dia}.",
    "sem_bateria": "I couldn't find a battery on this computer.",
    "bateria": "Battery at {n}%{carregando}.",
    "carregando": ", charging",
    "tela_bloqueada": "Screen locked.",
    "timer_marcado": "Timer set: I'll let you know {quando}.",
    "alarme_marcado": "Alarm set {quando}.",
    "lembrete_marcado": "Got it, I'll remind you {quando}: {o_que}.",
    "sem_lembretes": "You don't have any reminders set.",
    "lista_lembretes": "You have {qtd}: {itens}{mais}.",
    "e_mais": " and {n} more",
    "nome_timer": "timer",
    "nome_alarme": "alarm",
    "nada_cancelar_varios": "There were no {nomes} to cancel.",
    "nada_cancelar_um": "There was no {nome} to cancel.",
    "cancelei_qtd": "Canceled {qtd}.",
    "cancelei_lembrete": "Canceled the reminder: {o_que}.",
    "cancelei_tipo": "Canceled {o_nome} {quando}.",
    "o_lembrete": "the reminder",
    "o_timer": "the timer",
    "o_alarme": "the alarm",
    "anotado": "Noted.",
    "sem_anotacoes": "You don't have any notes yet.",
    "sua_anotacao": "Your note: {itens}.",
    "suas_anotacoes": "Your last {n} notes: {itens}.",
    "apaguei_qtd": "Deleted {qtd}.",
    "st_cpu": "CPU at {n}%",
    "st_mem": "memory {n}% used ({gb} GB free)",
    "st_disco": "disk with {gb} GB free",
    "st_bateria": "battery at {n}%{carregando}",
    "st_agora": "Right now: {partes}.",
    "st_pesados": " Using the most memory: {top}.",
    "st_item": "{nome} ({gb} GB)",
    "sep": ", ",
    "e": " and ",
    "pasta_nao_achei": "I couldn't find the {pasta} folder.",
    "sem_pillow": "To take a screenshot I need the Pillow package.",
    "print_salvo": "Screenshot saved in {pasta}\\Nicx.",
    "nao_esta_aberto": "{App} isn't open.",
    "fechando": "Closing {app}.",
    "desligamento_cancelado": "Shutdown canceled.",
    "pergunta_energia": (
        'Are you sure you want to {acao}? Say "confirm" within 30 seconds.'
    ),
    "acao_shutdown": "shut down the computer",
    "acao_restart": "restart the computer",
    "acao_suspend": "put the computer to sleep",
    "nada_confirmar": "There's nothing waiting for confirmation.",
    "desligando": (
        'Shutting down in 30 seconds. To cancel, say "cancel the shutdown".'
    ),
    "reiniciando": 'Restarting in 30 seconds. To cancel, say "cancel the restart".',
    "suspendendo": "Going to sleep in 3 seconds.",
    "nada_feito": "All right, I won't do anything.",
    "horario_passou": "That time has already passed ({quando}). Give me another one.",
    "aviso_8h": " I'll remind you at 8 AM that day.",
    "aviso_15min": " I'll remind you 15 minutes before.",
    "marquei_dia_todo": "Scheduled {titulo} {dia}, all day.{aviso}",
    "marquei": "Scheduled {titulo} {quando}.{aviso}",
    "nada_no_dia": "Nothing scheduled for {dia}.",
    "item_dia_todo": "{titulo} all day",
    "item_hora": "{titulo} at {hora}",
    "voce_tem_no_dia": "{Dia}, you have: {itens}.",
    "nada_7_dias": "Nothing scheduled for the next 7 days.",
    "proximos_7_dias": "In the next 7 days",
    "proximos_compromissos": "Your upcoming appointments",
    "lista": "{titulo}: {itens}{mais}.",
    "evento_dia_todo": "{titulo} {dia}, all day",
    "evento": "{titulo} {quando}",
    "compromisso_nao_achei": "I couldn't find that appointment in your calendar.",
    "desmarquei": "Canceled {evento}.",
    "nada_exportar": "There are no appointments to send.",
    "ics_salvo": "Saved {qtd} to {caminho}. Open it in your calendar.",
    "ics_aberto": "Opened {qtd} in the Windows calendar: just confirm there.",
    "o_que_pediu": "what you asked",
    "aviso_lembrete": "Reminder: {o_que}.",
    "aviso_timer": "Reminder: time's up.",
    "aviso_alarme": "Reminder: alarm.",
    "aviso_atrasado": " (it was due at {hora}; Nicx was off)",
    "aviso_daqui_15": "In 15 minutes: {titulo}",
    "aviso_hoje": "Today: {titulo}",
    "cal_google": "Google Calendar",
    "cal_outlook": "Outlook",
    "cal_criado": "Done: {titulo} is now in {cal}.",
    "cal_criados": "Done: I sent {qtd} to {cal}.",
    "cal_ja_estava": "{titulo} was already in {cal}.",
    "cal_todos_ja_estavam": "Those appointments were already in {cal}.",
    "cal_link": "I opened {titulo} in {cal}: just click Save.",
    "cal_links": "I opened {qtd} in {cal}, one per tab: just click Save on each.",
    "cal_reconectar_google": (
        " To create it directly, reconnect Google Calendar with write permission."
    ),
    "cal_reconectar_outlook": (
        " To create it directly, reconnect Outlook with calendar permission."
    ),
    "item_origem": "{item} ({origem})",
    "nenhum_arquivo": "I couldn't find any {nomes} in your folders.",
    "nao_achei_nome": 'I couldn\'t find a {nome} with "{q}" in the name.',
    "outros_parecidos": "{msg} I also found {n} similar ones.",
    "achei": "Found {qtd}: {nomes}.",
    "pasta_vazia": "The {pasta} folder is empty.",
    "na_pasta": "In {pasta} (most recent): {nomes}{mais}.",
    "ja_organizada": "{pasta} is already organized: nothing loose to move.",
    "vou_organizar": (
        "I'll sort {qtd} from {pasta} into folders ({resumo}). Nothing is deleted"
        ' and it can be undone. Say "confirm" within 30 seconds.'
    ),
    "pasta_sumiu": "I couldn't find the folder.",
    "organizado": (
        'Done: {qtd} in {pasta}. If you don\'t like it, say "undo the organization".'
    ),
    "nada_desfazer": "There's no organization to undo.",
    "desfeito": "Undone: {qtd} to {pasta}.",
    "youtube_busca": "Opened a YouTube search for {q}.",
    "youtube_tocando": "Playing {q} on YouTube.",
    "q_segundo": "in {n} second",
    "q_segundos": "in {n} seconds",
    "q_minuto": "in {n} minute",
    "q_minutos": "in {n} minutes",
    "q_hoje": "at {hora}",
    "q_amanha": "tomorrow at {hora}",
    "q_data": "on {mes} {d} at {hora}",
    "d_hoje": "today",
    "d_amanha": "tomorrow",
    "d_semana": "{semana} ({mes} {d})",
    "d_data": "{mes} {d}",
    "d_com_hora": "{dia} at {hora}",
}

_ES = {
    "windows_only": "Por ahora solo puedo hacer eso en Windows.",
    "falhou": "No pude hacerlo ahora.",
    "nao_sei": "Todavía no sé hacer eso.",
    "mudo": "Listo, alterné el silencio.",
    "volume_em": "Volumen al {n}%.",
    "volume_mais": "Subí el volumen.",
    "volume_menos": "Bajé el volumen.",
    "midia_alternar": "Listo.",
    "midia_proxima": "Siguiente.",
    "midia_anterior": "Volví a la anterior.",
    "abrindo": "Abriendo {alvo}.",
    "app_nao_encontrado": "No encontré {app} en este ordenador.",
    "pesquisando_google": "Buscando {q} en Google.",
    "pesquisando_youtube": "Buscando {q} en YouTube.",
    "hora": "{son_las} {hora}.",
    "hora_cheia": "{son_las} {hora} en punto.",
    "data": "Hoy es {semana}, {dia} de {mes}.",
    "sem_bateria": "No encontré batería en este ordenador.",
    "bateria": "Batería al {n}%{carregando}.",
    "carregando": ", cargando",
    "tela_bloqueada": "Pantalla bloqueada.",
    "timer_marcado": "Temporizador listo: te aviso {quando}.",
    "alarme_marcado": "Alarma programada {quando}.",
    "lembrete_marcado": "Hecho, te lo recuerdo {quando}: {o_que}.",
    "sem_lembretes": "No tienes recordatorios.",
    "lista_lembretes": "Tienes {qtd}: {itens}{mais}.",
    "e_mais": " y {n} más",
    "nome_timer": "temporizador",
    "nome_alarme": "alarma",
    "nada_cancelar_varios": "No había {nomes} para cancelar.",
    "nada_cancelar_um": "No había {nome} para cancelar.",
    "cancelei_qtd": "Cancelé {qtd}.",
    "cancelei_lembrete": "Cancelé el recordatorio: {o_que}.",
    "cancelei_tipo": "Cancelé {o_nome} {quando}.",
    "o_lembrete": "el recordatorio",
    "o_timer": "el temporizador",
    "o_alarme": "la alarma",
    "anotado": "Anotado.",
    "sem_anotacoes": "Todavía no tienes notas.",
    "sua_anotacao": "Tu nota: {itens}.",
    "suas_anotacoes": "Tus últimas {n} notas: {itens}.",
    "apaguei_qtd": "Borré {qtd}.",
    "st_cpu": "procesador al {n}%",
    "st_mem": "memoria al {n}% ({gb} GB libres)",
    "st_disco": "disco con {gb} GB libres",
    "st_bateria": "batería al {n}%{carregando}",
    "st_agora": "Ahora: {partes}.",
    "st_pesados": " Lo que más memoria usa: {top}.",
    "st_item": "{nome} ({gb} GB)",
    "sep": ", ",
    "e": " y ",
    "pasta_nao_achei": "No encontré la carpeta {pasta}.",
    "sem_pillow": "Para hacer una captura necesito el paquete Pillow.",
    "print_salvo": "Captura guardada en {pasta}\\Nicx.",
    "nao_esta_aberto": "{App} no está abierto.",
    "fechando": "Cerrando {app}.",
    "desligamento_cancelado": "Apagado cancelado.",
    "pergunta_energia": (
        '¿Seguro que quieres {acao}? Di "confirmo" en menos de 30 segundos.'
    ),
    "acao_shutdown": "apagar el ordenador",
    "acao_restart": "reiniciar el ordenador",
    "acao_suspend": "suspender el ordenador",
    "nada_confirmar": "No hay nada esperando confirmación.",
    "desligando": 'Apagando en 30 segundos. Para cancelar, di "cancela el apagado".',
    "reiniciando": (
        'Reiniciando en 30 segundos. Para cancelar, di "cancela el reinicio".'
    ),
    "suspendendo": "Suspendiendo en 3 segundos.",
    "nada_feito": "Está bien, no haré nada.",
    "horario_passou": "Esa hora ya pasó ({quando}). Dime otra.",
    "aviso_8h": " Te aviso a las 8:00 de ese día.",
    "aviso_15min": " Te aviso 15 minutos antes.",
    "marquei_dia_todo": "Agendé {titulo} {dia}, todo el día.{aviso}",
    "marquei": "Agendé {titulo} {quando}.{aviso}",
    "nada_no_dia": "Nada programado para {dia}.",
    "item_dia_todo": "{titulo} todo el día",
    "item_hora": "{titulo} {a_las} {hora}",
    "voce_tem_no_dia": "{Dia} tienes: {itens}.",
    "nada_7_dias": "Nada programado en los próximos 7 días.",
    "proximos_7_dias": "En los próximos 7 días",
    "proximos_compromissos": "Tus próximos compromisos",
    "lista": "{titulo}: {itens}{mais}.",
    "evento_dia_todo": "{titulo} {dia}, todo el día",
    "evento": "{titulo} {quando}",
    "compromisso_nao_achei": "No encontré ese compromiso en la agenda.",
    "desmarquei": "Cancelé {evento}.",
    "nada_exportar": "No hay compromisos para enviar.",
    "ics_salvo": "Guardé {qtd} en {caminho}. Ábrelo en tu calendario.",
    "ics_aberto": "Abrí {qtd} en el calendario de Windows: solo confirma allí.",
    "o_que_pediu": "lo que pediste",
    "aviso_lembrete": "Recordatorio: {o_que}.",
    "aviso_timer": "Recordatorio: se acabó el tiempo.",
    "aviso_alarme": "Recordatorio: alarma.",
    "aviso_atrasado": " (era para las {hora}; Nicx estaba apagado)",
    "aviso_daqui_15": "En 15 minutos: {titulo}",
    "aviso_hoje": "Hoy: {titulo}",
    "cal_google": "Google Calendar",
    "cal_outlook": "Outlook",
    "cal_criado": "Listo: {titulo} ya está en {cal}.",
    "cal_criados": "Listo: envié {qtd} a {cal}.",
    "cal_ja_estava": "{titulo} ya estaba en {cal}.",
    "cal_todos_ja_estavam": "Esos compromisos ya estaban en {cal}.",
    "cal_link": "Abrí {titulo} en {cal}: solo haz clic en Guardar.",
    "cal_links": (
        "Abrí {qtd} en {cal}, uno por pestaña: solo haz clic en Guardar en cada uno."
    ),
    "cal_reconectar_google": (
        " Para crearlo directamente, vuelve a conectar Google Calendar con permiso de "
        "escritura."
    ),
    "cal_reconectar_outlook": (
        " Para crearlo directamente, vuelve a conectar Outlook con permiso de "
        "calendario."
    ),
    "item_origem": "{item} ({origem})",
    "nenhum_arquivo": "No encontré {nomes} en tus carpetas.",
    "nao_achei_nome": 'No encontré {nomes} con "{q}" en el nombre.',
    "outros_parecidos": "{msg} Encontré otros {n} parecidos.",
    "achei": "Encontré {qtd}: {nomes}.",
    "pasta_vazia": "La carpeta {pasta} está vacía.",
    "na_pasta": "En {pasta} (más recientes): {nomes}{mais}.",
    "ja_organizada": "{pasta} ya está ordenada: no hay nada suelto para mover.",
    "vou_organizar": (
        "Voy a separar {qtd} de {pasta} en carpetas ({resumo}). No se borra nada"
        ' y se puede deshacer. Di "confirmo" en menos de 30 segundos.'
    ),
    "pasta_sumiu": "No encontré la carpeta.",
    "organizado": (
        'Listo: {qtd} en {pasta}. Si no te gusta, di "deshaz la organización".'
    ),
    "nada_desfazer": "No hay ninguna organización para deshacer.",
    "desfeito": "Deshecho: {qtd} a {pasta}.",
    "youtube_busca": "Abrí la búsqueda de {q} en YouTube.",
    "youtube_tocando": "Reproduciendo {q} en YouTube.",
    "q_segundo": "en {n} segundo",
    "q_segundos": "en {n} segundos",
    "q_minuto": "en {n} minuto",
    "q_minutos": "en {n} minutos",
    "q_hoje": "{a_las} {hora}",
    "q_amanha": "mañana {a_las} {hora}",
    "q_data": "el {dd}/{mm} {a_las} {hora}",
    "d_hoje": "hoy",
    "d_amanha": "mañana",
    "d_semana": "el {semana} ({dd}/{mm})",
    "d_data": "el {dd}/{mm}",
    "d_com_hora": "{dia} {a_las} {hora}",
}

_FR = {
    "windows_only": "Pour l'instant, je ne sais faire ça que sous Windows.",
    "falhou": "Je n'ai pas réussi à le faire.",
    "nao_sei": "Je ne sais pas encore faire ça.",
    "mudo": "C'est fait, j'ai basculé la sourdine.",
    "volume_em": "Volume à {n} %.",
    "volume_mais": "J'ai monté le volume.",
    "volume_menos": "J'ai baissé le volume.",
    "midia_alternar": "C'est fait.",
    "midia_proxima": "Suivant.",
    "midia_anterior": "Retour au précédent.",
    "abrindo": "J'ouvre {alvo}.",
    "app_nao_encontrado": "Je n'ai pas trouvé {app} sur cet ordinateur.",
    "pesquisando_google": "Je cherche {q} sur Google.",
    "pesquisando_youtube": "Je cherche {q} sur YouTube.",
    "hora": "Il est {hora}.",
    "hora_cheia": "Il est {hora} pile.",
    "data": "Nous sommes le {semana} {dia} {mes}.",
    "sem_bateria": "Je n'ai pas trouvé de batterie sur cet ordinateur.",
    "bateria": "Batterie à {n} %{carregando}.",
    "carregando": ", en charge",
    "tela_bloqueada": "Écran verrouillé.",
    "timer_marcado": "Minuteur réglé : je te préviens {quando}.",
    "alarme_marcado": "Alarme réglée {quando}.",
    "lembrete_marcado": "C'est noté, je te le rappelle {quando} : {o_que}.",
    "sem_lembretes": "Tu n'as aucun rappel.",
    "lista_lembretes": "Tu as {qtd} : {itens}{mais}.",
    "e_mais": " et {n} de plus",
    "nome_timer": "minuteur",
    "nome_alarme": "alarme",
    "nada_cancelar_varios": "Il n'y avait pas de {nomes} à annuler.",
    "nada_cancelar_um": "Il n'y avait pas de {nome} à annuler.",
    "cancelei_qtd": "J'ai annulé {qtd}.",
    "cancelei_lembrete": "J'ai annulé le rappel : {o_que}.",
    "cancelei_tipo": "J'ai annulé {o_nome} {quando}.",
    "o_lembrete": "le rappel",
    "o_timer": "le minuteur",
    "o_alarme": "l'alarme",
    "anotado": "C'est noté.",
    "sem_anotacoes": "Tu n'as pas encore de notes.",
    "sua_anotacao": "Ta note : {itens}.",
    "suas_anotacoes": "Tes {n} dernières notes : {itens}.",
    "apaguei_qtd": "J'ai supprimé {qtd}.",
    "st_cpu": "processeur à {n} %",
    "st_mem": "mémoire utilisée à {n} % ({gb} Go libres)",
    "st_disco": "disque avec {gb} Go libres",
    "st_bateria": "batterie à {n} %{carregando}",
    "st_agora": "En ce moment : {partes}.",
    "st_pesados": " Ce qui utilise le plus de mémoire : {top}.",
    "st_item": "{nome} ({gb} Go)",
    "sep": ", ",
    "e": " et ",
    "pasta_nao_achei": "Je n'ai pas trouvé le dossier {pasta}.",
    "sem_pillow": "Pour faire une capture d'écran, j'ai besoin du paquet Pillow.",
    "print_salvo": "Capture enregistrée dans {pasta}\\Nicx.",
    "nao_esta_aberto": "{App} n'est pas ouvert.",
    "fechando": "Je ferme {app}.",
    "desligamento_cancelado": "Extinction annulée.",
    "pergunta_energia": (
        "Tu es sûr de vouloir {acao} ? Dis « je confirme » dans les 30 secondes."
    ),
    "acao_shutdown": "éteindre l'ordinateur",
    "acao_restart": "redémarrer l'ordinateur",
    "acao_suspend": "mettre l'ordinateur en veille",
    "nada_confirmar": "Rien n'attend de confirmation.",
    "desligando": (
        "Extinction dans 30 secondes. Pour annuler, dis « annule l'extinction »."
    ),
    "reiniciando": (
        "Redémarrage dans 30 secondes. Pour annuler, dis « annule le redémarrage »."
    ),
    "suspendendo": "Mise en veille dans 3 secondes.",
    "nada_feito": "D'accord, je ne fais rien.",
    "horario_passou": "Cette heure est déjà passée ({quando}). Donne-m'en une autre.",
    "aviso_8h": " Je te préviens à 8 h le jour même.",
    "aviso_15min": " Je te préviens 15 minutes avant.",
    "marquei_dia_todo": "J'ai noté {titulo} {dia}, toute la journée.{aviso}",
    "marquei": "J'ai noté {titulo} {quando}.{aviso}",
    "nada_no_dia": "Rien de prévu pour {dia}.",
    "item_dia_todo": "{titulo} toute la journée",
    "item_hora": "{titulo} à {hora}",
    "voce_tem_no_dia": "{Dia}, tu as : {itens}.",
    "nada_7_dias": "Rien de prévu dans les 7 prochains jours.",
    "proximos_7_dias": "Dans les 7 prochains jours",
    "proximos_compromissos": "Tes prochains rendez-vous",
    "lista": "{titulo} : {itens}{mais}.",
    "evento_dia_todo": "{titulo} {dia}, toute la journée",
    "evento": "{titulo} {quando}",
    "compromisso_nao_achei": "Je n'ai pas trouvé ce rendez-vous dans l'agenda.",
    "desmarquei": "J'ai annulé {evento}.",
    "nada_exportar": "Il n'y a aucun rendez-vous à envoyer.",
    "ics_salvo": "J'ai enregistré {qtd} dans {caminho}. Ouvre-le dans ton calendrier.",
    "ics_aberto": (
        "J'ai ouvert {qtd} dans le calendrier de Windows : il suffit de confirmer"
        " là-bas."
    ),
    "o_que_pediu": "ce que tu as demandé",
    "aviso_lembrete": "Rappel : {o_que}.",
    "aviso_timer": "Rappel : le temps est écoulé.",
    "aviso_alarme": "Rappel : alarme.",
    "aviso_atrasado": " (c'était prévu à {hora} ; Nicx était éteint)",
    "aviso_daqui_15": "Dans 15 minutes : {titulo}",
    "aviso_hoje": "Aujourd'hui : {titulo}",
    "cal_google": "Google Agenda",
    "cal_outlook": "Outlook",
    "cal_criado": "C'est fait : {titulo} est dans {cal}.",
    "cal_criados": "C'est fait : j'ai envoyé {qtd} dans {cal}.",
    "cal_ja_estava": "{titulo} était déjà dans {cal}.",
    "cal_todos_ja_estavam": "Ces rendez-vous étaient déjà dans {cal}.",
    "cal_link": (
        "J'ai ouvert {titulo} dans {cal} : il suffit de cliquer sur Enregistrer."
    ),
    "cal_links": (
        "J'ai ouvert {qtd} dans {cal}, un par onglet : il suffit de cliquer sur "
        "Enregistrer pour chacun."
    ),
    "cal_reconectar_google": (
        " Pour le créer directement, reconnecte Google Agenda avec l'autorisation "
        "d'écriture."
    ),
    "cal_reconectar_outlook": (
        " Pour le créer directement, reconnecte Outlook avec l'autorisation d'agenda."
    ),
    "item_origem": "{item} ({origem})",
    "nenhum_arquivo": "Je n'ai pas trouvé de {nomes} dans tes dossiers.",
    "nao_achei_nome": "Je n'ai pas trouvé de {nomes} avec « {q} » dans le nom.",
    "outros_parecidos": "{msg} J'en ai trouvé {n} autres similaires.",
    "achei": "J'ai trouvé {qtd} : {nomes}.",
    "pasta_vazia": "Le dossier {pasta} est vide.",
    "na_pasta": "Dans {pasta} (les plus récents) : {nomes}{mais}.",
    "ja_organizada": "{pasta} est déjà rangé : rien à déplacer.",
    "vou_organizar": (
        "Je vais ranger {qtd} de {pasta} dans des dossiers ({resumo}). Rien n'est"
        " supprimé et c'est réversible. Dis « je confirme » dans les 30 secondes."
    ),
    "pasta_sumiu": "Je n'ai pas trouvé le dossier.",
    "organizado": (
        "C'est fait : {qtd} dans {pasta}. Si ça ne te plaît pas, dis"
        " « annule le rangement »."
    ),
    "nada_desfazer": "Il n'y a aucun rangement à annuler.",
    "desfeito": "Annulé : {qtd} dans {pasta}.",
    "youtube_busca": "J'ai ouvert la recherche de {q} sur YouTube.",
    "youtube_tocando": "Je lance {q} sur YouTube.",
    "q_segundo": "dans {n} seconde",
    "q_segundos": "dans {n} secondes",
    "q_minuto": "dans {n} minute",
    "q_minutos": "dans {n} minutes",
    "q_hoje": "à {hora}",
    "q_amanha": "demain à {hora}",
    "q_data": "le {dd}/{mm} à {hora}",
    "d_hoje": "aujourd'hui",
    "d_amanha": "demain",
    "d_semana": "{semana} ({dd}/{mm})",
    "d_data": "le {dd}/{mm}",
    "d_com_hora": "{dia} à {hora}",
}

_ZH = {
    "windows_only": "这个目前只能在 Windows 上做。",
    "falhou": "现在没能做到。",
    "nao_sei": "我还不会做这个。",
    "mudo": "好了，已切换静音。",
    "volume_em": "音量已调到 {n}%。",
    "volume_mais": "已调高音量。",
    "volume_menos": "已调低音量。",
    "midia_alternar": "好了。",
    "midia_proxima": "下一首。",
    "midia_anterior": "已回到上一首。",
    "abrindo": "正在打开{alvo}。",
    "app_nao_encontrado": "在这台电脑上没找到{app}。",
    "pesquisando_google": "正在 Google 上搜索 {q}。",
    "pesquisando_youtube": "正在 YouTube 上搜索 {q}。",
    "hora": "现在是 {hora}。",
    "hora_cheia": "现在是 {hora} 整。",
    "data": "今天是{mes}{dia}日，{semana}。",
    "sem_bateria": "这台电脑上没找到电池。",
    "bateria": "电池电量 {n}%{carregando}。",
    "carregando": "，正在充电",
    "tela_bloqueada": "屏幕已锁定。",
    "timer_marcado": "计时器已设好：{quando}提醒你。",
    "alarme_marcado": "闹钟已设好：{quando}。",
    "lembrete_marcado": "好的，{quando}提醒你：{o_que}。",
    "sem_lembretes": "你没有设置提醒。",
    "lista_lembretes": "你有{qtd}：{itens}{mais}。",
    "e_mais": "，还有 {n} 个",
    "nome_timer": "计时器",
    "nome_alarme": "闹钟",
    "nada_cancelar_varios": "没有可取消的{nomes}。",
    "nada_cancelar_um": "没有可取消的{nome}。",
    "cancelei_qtd": "已取消{qtd}。",
    "cancelei_lembrete": "已取消提醒：{o_que}。",
    "cancelei_tipo": "已取消{quando}的{o_nome}。",
    "o_lembrete": "提醒",
    "o_timer": "计时器",
    "o_alarme": "闹钟",
    "anotado": "记下了。",
    "sem_anotacoes": "你还没有笔记。",
    "sua_anotacao": "你的笔记：{itens}。",
    "suas_anotacoes": "你最近的 {n} 条笔记：{itens}。",
    "apaguei_qtd": "已删除{qtd}。",
    "st_cpu": "处理器 {n}%",
    "st_mem": "内存已用 {n}%（剩余 {gb} GB）",
    "st_disco": "磁盘剩余 {gb} GB",
    "st_bateria": "电池 {n}%{carregando}",
    "st_agora": "当前：{partes}。",
    "st_pesados": " 占用内存最多的是：{top}。",
    "st_item": "{nome}（{gb} GB）",
    "sep": "，",
    "e": "和",
    "pasta_nao_achei": "没找到“{pasta}”文件夹。",
    "sem_pillow": "截图需要 Pillow 包。",
    "print_salvo": "截图已保存到 {pasta}\\Nicx。",
    "nao_esta_aberto": "{App}没有打开。",
    "fechando": "正在关闭{app}。",
    "desligamento_cancelado": "已取消关机。",
    "pergunta_energia": "确定要{acao}吗？请在 30 秒内说“确认”。",
    "acao_shutdown": "关闭电脑",
    "acao_restart": "重启电脑",
    "acao_suspend": "让电脑睡眠",
    "nada_confirmar": "没有等待确认的操作。",
    "desligando": "30 秒后关机。要取消，请说“取消关机”。",
    "reiniciando": "30 秒后重启。要取消，请说“取消重启”。",
    "suspendendo": "3 秒后进入睡眠。",
    "nada_feito": "好的，我什么都不做。",
    "horario_passou": "这个时间已经过了（{quando}）。请换一个时间。",
    "aviso_8h": " 当天 8:00 我会提醒你。",
    "aviso_15min": " 我会提前 15 分钟提醒你。",
    "marquei_dia_todo": "已安排{titulo}：{dia}，全天。{aviso}",
    "marquei": "已安排{titulo}：{quando}。{aviso}",
    "nada_no_dia": "{dia}没有安排。",
    "item_dia_todo": "{titulo}（全天）",
    "item_hora": "{titulo}（{hora}）",
    "voce_tem_no_dia": "{Dia}你有：{itens}。",
    "nada_7_dias": "未来 7 天没有安排。",
    "proximos_7_dias": "未来 7 天",
    "proximos_compromissos": "你接下来的日程",
    "lista": "{titulo}：{itens}{mais}。",
    "evento_dia_todo": "{titulo}，{dia}，全天",
    "evento": "{titulo}，{quando}",
    "compromisso_nao_achei": "日程里没找到这个安排。",
    "desmarquei": "已取消：{evento}。",
    "nada_exportar": "没有可发送的日程。",
    "ics_salvo": "已把{qtd}保存到 {caminho}。请在你的日历中打开。",
    "ics_aberto": "已在 Windows 日历中打开{qtd}：在那里确认即可。",
    "o_que_pediu": "你要求的事",
    "aviso_lembrete": "提醒：{o_que}。",
    "aviso_timer": "提醒：时间到了。",
    "aviso_alarme": "提醒：闹钟。",
    "aviso_atrasado": "（原定 {hora}；当时 Nicx 未运行）",
    "aviso_daqui_15": "15 分钟后：{titulo}",
    "aviso_hoje": "今天：{titulo}",
    "cal_google": "Google 日历",
    "cal_outlook": "Outlook",
    "cal_criado": "好了：{titulo} 已添加到 {cal}。",
    "cal_criados": "好了：已将{qtd}发送到 {cal}。",
    "cal_ja_estava": "{titulo} 已经在 {cal} 中了。",
    "cal_todos_ja_estavam": "这些日程已经在 {cal} 中了。",
    "cal_link": "已在 {cal} 中打开 {titulo}：点击“保存”即可。",
    "cal_links": "已在 {cal} 中打开{qtd}，每个一个标签页：逐个点击“保存”即可。",
    "cal_reconectar_google": "如需直接创建，请重新连接 Google 日历并授予写入权限。",
    "cal_reconectar_outlook": "如需直接创建，请重新连接 Outlook 并授予日历权限。",
    "item_origem": "{item}（{origem}）",
    "nenhum_arquivo": "在你的文件夹里没找到{nome}。",
    "nao_achei_nome": "没找到名称包含“{q}”的{nome}。",
    "outros_parecidos": "{msg} 另外还找到 {n} 个相似的。",
    "achei": "找到{qtd}：{nomes}。",
    "pasta_vazia": "“{pasta}”文件夹是空的。",
    "na_pasta": "{pasta}（最新）：{nomes}{mais}。",
    "ja_organizada": "{pasta}已经整理好了：没有需要移动的文件。",
    "vou_organizar": (
        "我会把{pasta}里的{qtd}分到文件夹中（{resumo}）。不会删除任何东西，"
        "也可以撤销。请在 30 秒内说“确认”。"
    ),
    "pasta_sumiu": "没找到文件夹。",
    "organizado": "完成：{pasta}里整理了{qtd}。",
    "nada_desfazer": "没有可撤销的整理。",
    "desfeito": "已撤销：{qtd}回到了{pasta}。",
    "youtube_busca": "已在 YouTube 上打开 {q} 的搜索结果。",
    "youtube_tocando": "正在 YouTube 上播放 {q}。",
    "q_segundo": "{n} 秒后",
    "q_segundos": "{n} 秒后",
    "q_minuto": "{n} 分钟后",
    "q_minutos": "{n} 分钟后",
    "q_hoje": "今天 {hora}",
    "q_amanha": "明天 {hora}",
    "q_data": "{mes}{d}日 {hora}",
    "d_hoje": "今天",
    "d_amanha": "明天",
    "d_semana": "{semana}（{mes}{d}日）",
    "d_data": "{mes}{d}日",
    "d_com_hora": "{dia} {hora}",
}

_HI = {
    "windows_only": "अभी मैं यह सिर्फ़ Windows पर कर सकता हूँ।",
    "falhou": "अभी यह नहीं हो पाया।",
    "nao_sei": "मुझे अभी यह करना नहीं आता।",
    "mudo": "हो गया, म्यूट बदल दिया।",
    "volume_em": "वॉल्यूम {n}% पर है।",
    "volume_mais": "वॉल्यूम बढ़ा दिया।",
    "volume_menos": "वॉल्यूम कम कर दिया।",
    "midia_alternar": "हो गया।",
    "midia_proxima": "अगला।",
    "midia_anterior": "पिछले पर वापस गया।",
    "abrindo": "{alvo} खोल रहा हूँ।",
    "app_nao_encontrado": "इस कंप्यूटर पर {app} नहीं मिला।",
    "pesquisando_google": "Google पर {q} खोज रहा हूँ।",
    "pesquisando_youtube": "YouTube पर {q} खोज रहा हूँ।",
    "hora": "अभी {hora} बजे हैं।",
    "hora_cheia": "अभी ठीक {hora} बजे हैं।",
    "data": "आज {semana}, {dia} {mes} है।",
    "sem_bateria": "इस कंप्यूटर में बैटरी नहीं मिली।",
    "bateria": "बैटरी {n}%{carregando}।",
    "carregando": ", चार्ज हो रही है",
    "tela_bloqueada": "स्क्रीन लॉक हो गई।",
    "timer_marcado": "टाइमर लग गया: {quando} बताऊँगा।",
    "alarme_marcado": "अलार्म लग गया: {quando}।",
    "lembrete_marcado": "ठीक है, {quando} याद दिलाऊँगा: {o_que}।",
    "sem_lembretes": "आपका कोई रिमाइंडर नहीं है।",
    "lista_lembretes": "आपके {qtd} हैं: {itens}{mais}।",
    "e_mais": " और {n} और",
    "nome_timer": "टाइमर",
    "nome_alarme": "अलार्म",
    "nada_cancelar_varios": "रद्द करने के लिए कोई {nomes} नहीं था।",
    "nada_cancelar_um": "रद्द करने के लिए कोई {nome} नहीं था।",
    "cancelei_qtd": "{qtd} रद्द कर दिए।",
    "cancelei_lembrete": "रिमाइंडर रद्द कर दिया: {o_que}।",
    "cancelei_tipo": "{quando} वाला {o_nome} रद्द कर दिया।",
    "o_lembrete": "रिमाइंडर",
    "o_timer": "टाइमर",
    "o_alarme": "अलार्म",
    "anotado": "नोट कर लिया।",
    "sem_anotacoes": "आपके पास अभी कोई नोट नहीं है।",
    "sua_anotacao": "आपका नोट: {itens}।",
    "suas_anotacoes": "आपके आख़िरी {n} नोट: {itens}।",
    "apaguei_qtd": "{qtd} मिटा दिए।",
    "st_cpu": "प्रोसेसर {n}%",
    "st_mem": "मेमोरी {n}% इस्तेमाल में ({gb} GB खाली)",
    "st_disco": "डिस्क में {gb} GB खाली",
    "st_bateria": "बैटरी {n}%{carregando}",
    "st_agora": "अभी: {partes}।",
    "st_pesados": " सबसे ज़्यादा मेमोरी: {top}।",
    "st_item": "{nome} ({gb} GB)",
    "sep": ", ",
    "e": " और ",
    "pasta_nao_achei": "{pasta} फ़ोल्डर नहीं मिला।",
    "sem_pillow": "स्क्रीनशॉट के लिए मुझे Pillow पैकेज चाहिए।",
    "print_salvo": "स्क्रीनशॉट {pasta}\\Nicx में सेव हो गया।",
    "nao_esta_aberto": "{App} खुला नहीं है।",
    "fechando": "{app} बंद कर रहा हूँ।",
    "desligamento_cancelado": "शटडाउन रद्द हो गया।",
    "pergunta_energia": ('क्या आप सच में {acao} चाहते हैं? 30 सेकंड के अंदर "पुष्टि" कहें।'),
    "acao_shutdown": "कंप्यूटर बंद करना",
    "acao_restart": "कंप्यूटर रीस्टार्ट करना",
    "acao_suspend": "कंप्यूटर को स्लीप में डालना",
    "nada_confirmar": "पुष्टि के लिए कुछ भी बाकी नहीं है।",
    "desligando": ('30 सेकंड में बंद हो रहा है। रद्द करने के लिए "शटडाउन रद्द करो" कहें।'),
    "reiniciando": ('30 सेकंड में रीस्टार्ट हो रहा है। रद्द करने के लिए "रीस्टार्ट रद्द करो" कहें।'),
    "suspendendo": "3 सेकंड में स्लीप में जा रहा है।",
    "nada_feito": "ठीक है, मैं कुछ नहीं करूँगा।",
    "horario_passou": "यह समय निकल चुका है ({quando})। कोई और समय बताइए।",
    "aviso_8h": " उस दिन सुबह 8 बजे याद दिलाऊँगा।",
    "aviso_15min": " 15 मिनट पहले याद दिलाऊँगा।",
    "marquei_dia_todo": "{titulo} तय कर दिया: {dia}, पूरे दिन।{aviso}",
    "marquei": "{titulo} तय कर दिया: {quando}।{aviso}",
    "nada_no_dia": "{dia} के लिए कुछ तय नहीं है।",
    "item_dia_todo": "{titulo} (पूरे दिन)",
    "item_hora": "{titulo} ({hora} बजे)",
    "voce_tem_no_dia": "{Dia} आपके कार्यक्रम: {itens}।",
    "nada_7_dias": "अगले 7 दिनों में कुछ तय नहीं है।",
    "proximos_7_dias": "अगले 7 दिनों में",
    "proximos_compromissos": "आपके आने वाले कार्यक्रम",
    "lista": "{titulo}: {itens}{mais}।",
    "evento_dia_todo": "{titulo} {dia}, पूरे दिन",
    "evento": "{titulo} {quando}",
    "compromisso_nao_achei": "एजेंडा में यह कार्यक्रम नहीं मिला।",
    "desmarquei": "रद्द कर दिया: {evento}।",
    "nada_exportar": "भेजने के लिए कोई कार्यक्रम नहीं है।",
    "ics_salvo": "{qtd} को {caminho} में सेव कर दिया। इसे अपने कैलेंडर में खोलें।",
    "ics_aberto": "{qtd} Windows कैलेंडर में खोल दिए: वहाँ बस पुष्टि करें।",
    "o_que_pediu": "जो आपने कहा था",
    "aviso_lembrete": "रिमाइंडर: {o_que}।",
    "aviso_timer": "रिमाइंडर: समय पूरा हुआ।",
    "aviso_alarme": "रिमाइंडर: अलार्म।",
    "aviso_atrasado": " ({hora} बजे का था; Nicx बंद था)",
    "aviso_daqui_15": "15 मिनट में: {titulo}",
    "aviso_hoje": "आज: {titulo}",
    "cal_google": "Google कैलेंडर",
    "cal_outlook": "Outlook",
    "cal_criado": "हो गया: {titulo} अब {cal} में है।",
    "cal_criados": "हो गया: {qtd} {cal} में भेज दिए।",
    "cal_ja_estava": "{titulo} पहले से {cal} में था।",
    "cal_todos_ja_estavam": "ये कार्यक्रम पहले से {cal} में थे।",
    "cal_link": "{titulo} को {cal} में खोल दिया: बस Save पर क्लिक करें।",
    "cal_links": (
        "{qtd} को {cal} में खोल दिया, हर एक अलग टैब में: हर एक में Save पर क्लिक करें।"
    ),
    "cal_reconectar_google": (
        " सीधे बनाने के लिए, Google कैलेंडर को लिखने की अनुमति के साथ फिर से कनेक्ट करें।"
    ),
    "cal_reconectar_outlook": (
        " सीधे बनाने के लिए, Outlook को कैलेंडर की अनुमति के साथ फिर से कनेक्ट करें।"
    ),
    "item_origem": "{item} ({origem})",
    "nenhum_arquivo": "आपके फ़ोल्डरों में कोई {nome} नहीं मिला।",
    "nao_achei_nome": 'नाम में "{q}" वाला कोई {nome} नहीं मिला।',
    "outros_parecidos": "{msg} {n} और मिलते-जुलते मिले।",
    "achei": "{qtd} मिले: {nomes}।",
    "pasta_vazia": "{pasta} फ़ोल्डर खाली है।",
    "na_pasta": "{pasta} में (सबसे नए): {nomes}{mais}।",
    "ja_organizada": "{pasta} पहले से व्यवस्थित है: हटाने के लिए कुछ नहीं।",
    "vou_organizar": (
        "मैं {pasta} की {qtd} फ़ोल्डरों में बाँटूँगा ({resumo})। कुछ भी मिटाया नहीं"
        ' जाएगा और इसे वापस किया जा सकता है। 30 सेकंड के अंदर "पुष्टि" कहें।'
    ),
    "pasta_sumiu": "फ़ोल्डर नहीं मिला।",
    "organizado": "हो गया: {pasta} में {qtd}।",
    "nada_desfazer": "वापस करने के लिए कोई व्यवस्था नहीं है।",
    "desfeito": "वापस कर दिया: {qtd}, {pasta} में।",
    "youtube_busca": "YouTube पर {q} की खोज खोल दी।",
    "youtube_tocando": "YouTube पर {q} चला रहा हूँ।",
    "q_segundo": "{n} सेकंड में",
    "q_segundos": "{n} सेकंड में",
    "q_minuto": "{n} मिनट में",
    "q_minutos": "{n} मिनट में",
    "q_hoje": "आज {hora} बजे",
    "q_amanha": "कल {hora} बजे",
    "q_data": "{dd}/{mm} को {hora} बजे",
    "d_hoje": "आज",
    "d_amanha": "कल",
    "d_semana": "{semana} ({dd}/{mm})",
    "d_data": "{dd}/{mm}",
    "d_com_hora": "{dia} {hora} बजे",
}

_AR = {
    "windows_only": "لا أستطيع فعل ذلك إلا على Windows حاليًا.",
    "falhou": "لم أتمكن من فعل ذلك الآن.",
    "nao_sei": "لا أعرف كيف أفعل ذلك بعد.",
    "mudo": "تم، بدّلت كتم الصوت.",
    "volume_em": "مستوى الصوت {n}%.",
    "volume_mais": "رفعت مستوى الصوت.",
    "volume_menos": "خفضت مستوى الصوت.",
    "midia_alternar": "تم.",
    "midia_proxima": "التالي.",
    "midia_anterior": "عدت إلى السابق.",
    "abrindo": "أفتح {alvo}.",
    "app_nao_encontrado": "لم أجد {app} على هذا الكمبيوتر.",
    "pesquisando_google": "أبحث عن {q} في Google.",
    "pesquisando_youtube": "أبحث عن {q} في YouTube.",
    "hora": "الساعة الآن {hora}.",
    "hora_cheia": "الساعة الآن {hora} تمامًا.",
    "data": "اليوم {semana}، {dia} {mes}.",
    "sem_bateria": "لم أجد بطارية في هذا الكمبيوتر.",
    "bateria": "البطارية {n}%{carregando}.",
    "carregando": "، قيد الشحن",
    "tela_bloqueada": "تم قفل الشاشة.",
    "timer_marcado": "تم ضبط المؤقت: سأنبهك {quando}.",
    "alarme_marcado": "تم ضبط المنبه {quando}.",
    "lembrete_marcado": "حسنًا، سأذكّرك {quando}: {o_que}.",
    "sem_lembretes": "ليس لديك تذكيرات.",
    "lista_lembretes": "لديك {qtd}: {itens}{mais}.",
    "e_mais": " و{n} أخرى",
    "nome_timer": "مؤقت",
    "nome_alarme": "منبه",
    "nada_cancelar_varios": "لم يكن هناك {nomes} لإلغائها.",
    "nada_cancelar_um": "لم يكن هناك {nome} لإلغائه.",
    "cancelei_qtd": "ألغيت {qtd}.",
    "cancelei_lembrete": "ألغيت التذكير: {o_que}.",
    "cancelei_tipo": "ألغيت {o_nome} {quando}.",
    "o_lembrete": "التذكير",
    "o_timer": "المؤقت",
    "o_alarme": "المنبه",
    "anotado": "تم التدوين.",
    "sem_anotacoes": "ليس لديك ملاحظات بعد.",
    "sua_anotacao": "ملاحظتك: {itens}.",
    "suas_anotacoes": "آخر {n} ملاحظات: {itens}.",
    "apaguei_qtd": "حذفت {qtd}.",
    "st_cpu": "المعالج {n}%",
    "st_mem": "الذاكرة مستخدمة {n}% ({gb} GB متاحة)",
    "st_disco": "القرص فيه {gb} GB متاحة",
    "st_bateria": "البطارية {n}%{carregando}",
    "st_agora": "الآن: {partes}.",
    "st_pesados": " الأكثر استهلاكًا للذاكرة: {top}.",
    "st_item": "{nome} ({gb} GB)",
    "sep": "، ",
    "e": " و",
    "pasta_nao_achei": "لم أجد مجلد {pasta}.",
    "sem_pillow": "لالتقاط الشاشة أحتاج إلى حزمة Pillow.",
    "print_salvo": "تم حفظ لقطة الشاشة في {pasta}\\Nicx.",
    "nao_esta_aberto": "{App} ليس مفتوحًا.",
    "fechando": "أغلق {app}.",
    "desligamento_cancelado": "تم إلغاء إيقاف التشغيل.",
    "pergunta_energia": 'هل أنت متأكد أنك تريد {acao}؟ قل "أؤكد" خلال 30 ثانية.',
    "acao_shutdown": "إيقاف تشغيل الكمبيوتر",
    "acao_restart": "إعادة تشغيل الكمبيوتر",
    "acao_suspend": "وضع الكمبيوتر في السكون",
    "nada_confirmar": "لا يوجد شيء ينتظر التأكيد.",
    "desligando": 'سيتم إيقاف التشغيل خلال 30 ثانية. للإلغاء قل "إلغاء الإيقاف".',
    "reiniciando": (
        'ستتم إعادة التشغيل خلال 30 ثانية. للإلغاء قل "إلغاء إعادة التشغيل".'
    ),
    "suspendendo": "سيدخل في وضع السكون خلال 3 ثوانٍ.",
    "nada_feito": "حسنًا، لن أفعل شيئًا.",
    "horario_passou": "هذا الوقت مضى بالفعل ({quando}). اختر وقتًا آخر.",
    "aviso_8h": " سأذكّرك الساعة 8 صباح ذلك اليوم.",
    "aviso_15min": " سأذكّرك قبل 15 دقيقة.",
    "marquei_dia_todo": "حجزت {titulo} {dia}، طوال اليوم.{aviso}",
    "marquei": "حجزت {titulo} {quando}.{aviso}",
    "nada_no_dia": "لا شيء مُجدول {dia}.",
    "item_dia_todo": "{titulo} طوال اليوم",
    "item_hora": "{titulo} الساعة {hora}",
    "voce_tem_no_dia": "{Dia} لديك: {itens}.",
    "nada_7_dias": "لا شيء مُجدول في الأيام السبعة القادمة.",
    "proximos_7_dias": "في الأيام السبعة القادمة",
    "proximos_compromissos": "مواعيدك القادمة",
    "lista": "{titulo}: {itens}{mais}.",
    "evento_dia_todo": "{titulo} {dia}، طوال اليوم",
    "evento": "{titulo} {quando}",
    "compromisso_nao_achei": "لم أجد هذا الموعد في الأجندة.",
    "desmarquei": "ألغيت {evento}.",
    "nada_exportar": "لا توجد مواعيد لإرسالها.",
    "ics_salvo": "حفظت {qtd} في {caminho}. افتحه في تقويمك.",
    "ics_aberto": "فتحت {qtd} في تقويم Windows: فقط أكّد هناك.",
    "o_que_pediu": "ما طلبته",
    "aviso_lembrete": "تذكير: {o_que}.",
    "aviso_timer": "تذكير: انتهى الوقت.",
    "aviso_alarme": "تذكير: المنبه.",
    "aviso_atrasado": " (كان موعده {hora}؛ كان Nicx مطفأً)",
    "aviso_daqui_15": "بعد 15 دقيقة: {titulo}",
    "aviso_hoje": "اليوم: {titulo}",
    "cal_google": "تقويم Google",
    "cal_outlook": "Outlook",
    "cal_criado": "تم: أصبح {titulo} في {cal}.",
    "cal_criados": "تم: أرسلت {qtd} إلى {cal}.",
    "cal_ja_estava": "{titulo} موجود بالفعل في {cal}.",
    "cal_todos_ja_estavam": "هذه المواعيد موجودة بالفعل في {cal}.",
    "cal_link": "فتحت {titulo} في {cal}: فقط اضغط حفظ.",
    "cal_links": (
        "فتحت {qtd} في {cal}، كل واحد في علامة تبويب: فقط اضغط حفظ في كل منها."
    ),
    "cal_reconectar_google": " لإنشائه مباشرة، أعد ربط تقويم Google مع إذن الكتابة.",
    "cal_reconectar_outlook": " لإنشائه مباشرة، أعد ربط Outlook مع إذن التقويم.",
    "item_origem": "{item} ({origem})",
    "nenhum_arquivo": "لم أجد أي {nome} في مجلداتك.",
    "nao_achei_nome": 'لم أجد {nome} باسم يحتوي على "{q}".',
    "outros_parecidos": "{msg} وجدت {n} أخرى مشابهة.",
    "achei": "وجدت {qtd}: {nomes}.",
    "pasta_vazia": "مجلد {pasta} فارغ.",
    "na_pasta": "في {pasta} (الأحدث): {nomes}{mais}.",
    "ja_organizada": "{pasta} منظم بالفعل: لا شيء لنقله.",
    "vou_organizar": (
        "سأوزع {qtd} من {pasta} على مجلدات ({resumo}). لن يُحذف شيء ويمكن"
        ' التراجع. قل "أؤكد" خلال 30 ثانية.'
    ),
    "pasta_sumiu": "لم أجد المجلد.",
    "organizado": "تم: {qtd} في {pasta}.",
    "nada_desfazer": "لا يوجد تنظيم للتراجع عنه.",
    "desfeito": "تم التراجع: {qtd} إلى {pasta}.",
    "youtube_busca": "فتحت البحث عن {q} في YouTube.",
    "youtube_tocando": "أشغّل {q} على YouTube.",
    "q_segundo": "بعد {n} ثانية",
    "q_segundos": "بعد {n} ثانية",
    "q_minuto": "بعد {n} دقيقة",
    "q_minutos": "بعد {n} دقيقة",
    "q_hoje": "الساعة {hora}",
    "q_amanha": "غدًا الساعة {hora}",
    "q_data": "يوم {dd}/{mm} الساعة {hora}",
    "d_hoje": "اليوم",
    "d_amanha": "غدًا",
    "d_semana": "{semana} ({dd}/{mm})",
    "d_data": "{dd}/{mm}",
    "d_com_hora": "{dia} الساعة {hora}",
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


def texto(chave: str, idioma: Optional[str] = None, **valores: object) -> str:
    """A frase ``chave`` no idioma (ou no atual), com os ``valores`` no lugar."""
    modelo = FRASES.get(codigo(idioma), _PT).get(chave)
    if modelo is None:
        modelo = _PT[chave]
    return modelo.format(**valores) if valores else modelo


def maiuscula(s: str) -> str:
    """Primeira letra maiúscula, sem mexer no resto ('the browser' -> 'The...')."""
    return s[:1].upper() + s[1:]


# ---------------------------------------------------------------------------
# Nomes contáveis: (um, vários)
# ---------------------------------------------------------------------------

_NOMES: dict[str, dict[str, tuple[str, str]]] = {
    "pt-BR": {
        "lembrete": ("lembrete", "lembretes"),
        "timer": ("timer", "timers"),
        "alarme": ("alarme", "alarmes"),
        "anotacao": ("anotação", "anotações"),
        "compromisso": ("compromisso", "compromissos"),
        "arquivo": ("arquivo", "arquivos"),
        "arquivo_organizado": ("arquivo organizado", "arquivos organizados"),
        "arquivo_voltou": ("arquivo voltou", "arquivos voltaram"),
        "k_imagem": ("foto", "fotos"),
        "k_print": ("print", "prints"),
        "k_video": ("vídeo", "vídeos"),
        "k_musica": ("música", "músicas"),
        "k_pdf": ("PDF", "PDFs"),
        "k_documento": ("documento", "documentos"),
        "k_planilha": ("planilha", "planilhas"),
        "k_apresentacao": ("apresentação", "apresentações"),
        "k_": ("arquivo", "arquivos"),
        "k_download": ("download", "downloads"),
    },
    "en": {
        "lembrete": ("reminder", "reminders"),
        "timer": ("timer", "timers"),
        "alarme": ("alarm", "alarms"),
        "anotacao": ("note", "notes"),
        "compromisso": ("appointment", "appointments"),
        "arquivo": ("file", "files"),
        "arquivo_organizado": ("file organized", "files organized"),
        "arquivo_voltou": ("file moved back", "files moved back"),
        "k_imagem": ("photo", "photos"),
        "k_print": ("screenshot", "screenshots"),
        "k_video": ("video", "videos"),
        "k_musica": ("song", "songs"),
        "k_pdf": ("PDF", "PDFs"),
        "k_documento": ("document", "documents"),
        "k_planilha": ("spreadsheet", "spreadsheets"),
        "k_apresentacao": ("presentation", "presentations"),
        "k_": ("file", "files"),
        "k_download": ("download", "downloads"),
    },
    "es": {
        "lembrete": ("recordatorio", "recordatorios"),
        "timer": ("temporizador", "temporizadores"),
        "alarme": ("alarma", "alarmas"),
        "anotacao": ("nota", "notas"),
        "compromisso": ("compromiso", "compromisos"),
        "arquivo": ("archivo", "archivos"),
        "arquivo_organizado": ("archivo ordenado", "archivos ordenados"),
        "arquivo_voltou": ("archivo devuelto", "archivos devueltos"),
        "k_imagem": ("foto", "fotos"),
        "k_print": ("captura", "capturas"),
        "k_video": ("vídeo", "vídeos"),
        "k_musica": ("canción", "canciones"),
        "k_pdf": ("PDF", "PDF"),
        "k_documento": ("documento", "documentos"),
        "k_planilha": ("hoja de cálculo", "hojas de cálculo"),
        "k_apresentacao": ("presentación", "presentaciones"),
        "k_": ("archivo", "archivos"),
        "k_download": ("descarga", "descargas"),
    },
    "fr": {
        "lembrete": ("rappel", "rappels"),
        "timer": ("minuteur", "minuteurs"),
        "alarme": ("alarme", "alarmes"),
        "anotacao": ("note", "notes"),
        "compromisso": ("rendez-vous", "rendez-vous"),
        "arquivo": ("fichier", "fichiers"),
        "arquivo_organizado": ("fichier rangé", "fichiers rangés"),
        "arquivo_voltou": ("fichier remis en place", "fichiers remis en place"),
        "k_imagem": ("photo", "photos"),
        "k_print": ("capture d'écran", "captures d'écran"),
        "k_video": ("vidéo", "vidéos"),
        "k_musica": ("chanson", "chansons"),
        "k_pdf": ("PDF", "PDF"),
        "k_documento": ("document", "documents"),
        "k_planilha": ("feuille de calcul", "feuilles de calcul"),
        "k_apresentacao": ("présentation", "présentations"),
        "k_": ("fichier", "fichiers"),
        "k_download": ("téléchargement", "téléchargements"),
    },
    "zh": {
        "lembrete": ("提醒", "提醒"),
        "timer": ("计时器", "计时器"),
        "alarme": ("闹钟", "闹钟"),
        "anotacao": ("笔记", "笔记"),
        "compromisso": ("日程", "日程"),
        "arquivo": ("文件", "文件"),
        "arquivo_organizado": ("文件", "文件"),
        "arquivo_voltou": ("文件", "文件"),
        "k_imagem": ("照片", "照片"),
        "k_print": ("截图", "截图"),
        "k_video": ("视频", "视频"),
        "k_musica": ("歌曲", "歌曲"),
        "k_pdf": ("PDF", "PDF"),
        "k_documento": ("文档", "文档"),
        "k_planilha": ("表格", "表格"),
        "k_apresentacao": ("演示文稿", "演示文稿"),
        "k_": ("文件", "文件"),
        "k_download": ("下载", "下载"),
    },
    "hi": {
        "lembrete": ("रिमाइंडर", "रिमाइंडर"),
        "timer": ("टाइमर", "टाइमर"),
        "alarme": ("अलार्म", "अलार्म"),
        "anotacao": ("नोट", "नोट"),
        "compromisso": ("कार्यक्रम", "कार्यक्रम"),
        "arquivo": ("फ़ाइल", "फ़ाइलें"),
        "arquivo_organizado": ("फ़ाइल व्यवस्थित", "फ़ाइलें व्यवस्थित"),
        "arquivo_voltou": ("फ़ाइल", "फ़ाइलें"),
        "k_imagem": ("फ़ोटो", "फ़ोटो"),
        "k_print": ("स्क्रीनशॉट", "स्क्रीनशॉट"),
        "k_video": ("वीडियो", "वीडियो"),
        "k_musica": ("गाना", "गाने"),
        "k_pdf": ("PDF", "PDF"),
        "k_documento": ("दस्तावेज़", "दस्तावेज़"),
        "k_planilha": ("स्प्रेडशीट", "स्प्रेडशीट"),
        "k_apresentacao": ("प्रेज़ेंटेशन", "प्रेज़ेंटेशन"),
        "k_": ("फ़ाइल", "फ़ाइलें"),
        "k_download": ("डाउनलोड", "डाउनलोड"),
    },
    "ar": {
        "lembrete": ("تذكير", "تذكيرات"),
        "timer": ("مؤقت", "مؤقتات"),
        "alarme": ("منبه", "منبهات"),
        "anotacao": ("ملاحظة", "ملاحظات"),
        "compromisso": ("موعد", "مواعيد"),
        "arquivo": ("ملف", "ملفات"),
        "arquivo_organizado": ("ملف منظم", "ملفات منظمة"),
        "arquivo_voltou": ("ملف أُعيد", "ملفات أُعيدت"),
        "k_imagem": ("صورة", "صور"),
        "k_print": ("لقطة شاشة", "لقطات شاشة"),
        "k_video": ("فيديو", "فيديوهات"),
        "k_musica": ("أغنية", "أغانٍ"),
        "k_pdf": ("PDF", "PDF"),
        "k_documento": ("مستند", "مستندات"),
        "k_planilha": ("جدول بيانات", "جداول بيانات"),
        "k_apresentacao": ("عرض تقديمي", "عروض تقديمية"),
        "k_": ("ملف", "ملفات"),
        "k_download": ("تنزيل", "تنزيلات"),
    },
}


def nome(chave: str, n: int = 1, idioma: Optional[str] = None) -> str:
    """'lembrete' ou 'lembretes', conforme ``n``."""
    formas = _NOMES.get(codigo(idioma), _NOMES[PADRAO]).get(chave)
    if formas is None:
        formas = _NOMES[PADRAO][chave]
    return formas[0] if n == 1 else formas[1]


def contar(chave: str, n: int, idioma: Optional[str] = None) -> str:
    """'2 lembretes', '1 lembrete' ('2 个提醒' em chinês)."""
    palavra = nome(chave, n, idioma)
    if codigo(idioma) == "zh":
        return f"{n} 个{palavra}"
    return f"{n} {palavra}"


# ---------------------------------------------------------------------------
# Nomes de apps e pastas
# ---------------------------------------------------------------------------

# Rótulo em português -> nome em cada idioma (os de marca só perdem o artigo).
_APPS: dict[str, dict[str, str]] = {
    "o Bloco de Notas": {
        "en": "Notepad",
        "es": "el Bloc de notas",
        "fr": "le Bloc-notes",
        "zh": "记事本",
        "hi": "नोटपैड",
        "ar": "المفكرة",
    },
    "a Calculadora": {
        "en": "Calculator",
        "es": "la Calculadora",
        "fr": "la Calculatrice",
        "zh": "计算器",
        "hi": "कैलकुलेटर",
        "ar": "الآلة الحاسبة",
    },
    "o Explorador de Arquivos": {
        "en": "File Explorer",
        "es": "el Explorador de archivos",
        "fr": "l'Explorateur de fichiers",
        "zh": "文件资源管理器",
        "hi": "फ़ाइल एक्सप्लोरर",
        "ar": "مستكشف الملفات",
    },
    "as Configurações": {
        "en": "Settings",
        "es": "la Configuración",
        "fr": "les Paramètres",
        "zh": "设置",
        "hi": "सेटिंग्स",
        "ar": "الإعدادات",
    },
    "o Gerenciador de Tarefas": {
        "en": "Task Manager",
        "es": "el Administrador de tareas",
        "fr": "le Gestionnaire des tâches",
        "zh": "任务管理器",
        "hi": "टास्क मैनेजर",
        "ar": "مدير المهام",
    },
    "o terminal": {
        "en": "the terminal",
        "es": "la terminal",
        "fr": "le terminal",
        "zh": "终端",
        "hi": "टर्मिनल",
        "ar": "الطرفية",
    },
    "o navegador": {
        "en": "the browser",
        "es": "el navegador",
        "fr": "le navigateur",
        "zh": "浏览器",
        "hi": "ब्राउज़र",
        "ar": "المتصفح",
    },
}


def nome_app(rotulo: str, idioma: Optional[str] = None) -> str:
    """'o Bloco de Notas' -> 'Notepad'; 'o YouTube' -> 'YouTube'."""
    cod = codigo(idioma)
    if cod == PADRAO:
        return rotulo
    traduzido = _APPS.get(rotulo, {}).get(cod)
    if traduzido:
        return traduzido
    for artigo in ("o ", "a ", "os ", "as "):
        if rotulo.startswith(artigo):
            return rotulo[len(artigo) :]
    return rotulo


_PASTAS: dict[str, dict[str, str]] = {
    "downloads": {
        "en": "Downloads",
        "es": "Descargas",
        "fr": "Téléchargements",
        "zh": "下载",
        "hi": "डाउनलोड",
        "ar": "التنزيلات",
    },
    "documentos": {
        "en": "Documents",
        "es": "Documentos",
        "fr": "Documents",
        "zh": "文档",
        "hi": "दस्तावेज़",
        "ar": "المستندات",
    },
    "imagens": {
        "en": "Pictures",
        "es": "Imágenes",
        "fr": "Images",
        "zh": "图片",
        "hi": "चित्र",
        "ar": "الصور",
    },
    "musicas": {
        "en": "Music",
        "es": "Música",
        "fr": "Musique",
        "zh": "音乐",
        "hi": "संगीत",
        "ar": "الموسيقى",
    },
    "videos": {
        "en": "Videos",
        "es": "Vídeos",
        "fr": "Vidéos",
        "zh": "视频",
        "hi": "वीडियो",
        "ar": "الفيديوهات",
    },
    "area de trabalho": {
        "en": "Desktop",
        "es": "Escritorio",
        "fr": "Bureau",
        "zh": "桌面",
        "hi": "डेस्कटॉप",
        "ar": "سطح المكتب",
    },
}


def nome_pasta(chave: str, rotulo: str, idioma: Optional[str] = None) -> str:
    """Nome da pasta conhecida (``chave`` de ``rotinas.FOLDERS``) no idioma."""
    cod = codigo(idioma)
    if cod == PADRAO:
        return rotulo
    return _PASTAS.get(chave, {}).get(cod, rotulo)


# ---------------------------------------------------------------------------
# Números, horas e datas
# ---------------------------------------------------------------------------


def decimal(valor: float, idioma: Optional[str] = None) -> str:
    """'1,5' em português, espanhol e francês; '1.5' nos outros."""
    s = f"{valor:.1f}"
    return s.replace(".", ",") if codigo(idioma) in ("pt-BR", "es", "fr") else s


_SEMANA = {
    "pt-BR": (
        "segunda-feira",
        "terça-feira",
        "quarta-feira",
        "quinta-feira",
        "sexta-feira",
        "sábado",
        "domingo",
    ),
    "en": (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ),
    "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"),
    "fr": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
    "zh": ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"),
    "hi": ("सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"),
    "ar": ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"),
}
# Na agenda o português fala curto ("sexta (31/10)"); os outros, por extenso.
_SEMANA_CURTA = {
    "pt-BR": ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"),
}
_MESES = {
    "pt-BR": (
        "janeiro",
        "fevereiro",
        "março",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    ),
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
    "es": (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ),
    "fr": (
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
    "zh": tuple(f"{m}月" for m in range(1, 13)),
    "hi": (
        "जनवरी",
        "फ़रवरी",
        "मार्च",
        "अप्रैल",
        "मई",
        "जून",
        "जुलाई",
        "अगस्त",
        "सितंबर",
        "अक्टूबर",
        "नवंबर",
        "दिसंबर",
    ),
    "ar": (
        "يناير",
        "فبراير",
        "مارس",
        "أبريل",
        "مايو",
        "يونيو",
        "يوليو",
        "أغسطس",
        "سبتمبر",
        "أكتوبر",
        "نوفمبر",
        "ديسمبر",
    ),
}


def hora_curta(quando: datetime, idioma: Optional[str] = None) -> str:
    """'15h30' (pt), '3:30 PM' (en), '15 h 30' (fr), '15:30' (os outros)."""
    cod = codigo(idioma)
    h, m = quando.hour, quando.minute
    if cod == "pt-BR":
        return f"{h}h" if m == 0 else f"{h}h{m:02d}"
    if cod == "en":
        h12 = h % 12 or 12
        sufixo = "AM" if h < 12 else "PM"
        return f"{h12} {sufixo}" if m == 0 else f"{h12}:{m:02d} {sufixo}"
    if cod == "fr":
        return f"{h} h" if m == 0 else f"{h} h {m:02d}"
    return f"{h}:{m:02d}"


def _valores(quando: datetime, cod: str) -> dict[str, object]:
    """Pedaços de data e hora que as frases usam."""
    um = quando.hour == 1  # espanhol: "es la 1:00", "a la 1:00"
    return {
        "hora": hora_curta(quando, cod),
        "h": quando.hour,
        "dd": f"{quando.day:02d}",
        "mm": f"{quando.month:02d}",
        "d": quando.day,
        "mes": _MESES.get(cod, _MESES[PADRAO])[quando.month - 1],
        "a_las": "a la" if um else "a las",
        "son_las": "Es la" if um else "Son las",
    }


def frase_hora(agora: datetime, idioma: Optional[str] = None) -> str:
    """'São 21h05.', "It's 9:05 PM.", 'Il est 21 h 05.'..."""
    cod = codigo(idioma)
    chave = "hora_cheia" if agora.minute == 0 else "hora"
    return texto(chave, cod, **_valores(agora, cod))


def frase_data(agora: datetime, idioma: Optional[str] = None) -> str:
    """'Hoje é sexta-feira, 23 de outubro.', 'Today is Friday, October 23.'"""
    cod = codigo(idioma)
    valores = _valores(agora, cod)
    dia: object = agora.day
    if cod == "fr" and agora.day == 1:
        dia = "1er"
    semana = _SEMANA.get(cod, _SEMANA[PADRAO])[agora.weekday()]
    return texto("data", cod, **{**valores, "semana": semana, "dia": dia})


def quando(alvo: datetime, agora: datetime, idioma: Optional[str] = None) -> str:
    """Hora de um lembrete do jeito que se fala: 'em 5 minutos', 'amanhã às 8h'."""
    cod = codigo(idioma)
    valores = _valores(alvo, cod)
    # Perto: em minutos, mesmo virando o dia (timer às 23h57 = "em 5 minutos").
    delta = alvo - agora
    if delta < timedelta(minutes=1):
        secs = max(1, round(delta.total_seconds()))
        return texto("q_segundo" if secs == 1 else "q_segundos", cod, n=secs)
    if delta < timedelta(hours=1):
        mins = max(1, round(delta.total_seconds() / 60))
        return texto("q_minuto" if mins == 1 else "q_minutos", cod, n=mins)
    days = (alvo.date() - agora.date()).days
    if days == 0:
        return texto("q_hoje", cod, **valores)
    if days == 1:
        return texto("q_amanha", cod, **valores)
    return texto("q_data", cod, **valores)


def dia(
    alvo: datetime,
    agora: datetime,
    *,
    com_hora: bool = True,
    idioma: Optional[str] = None,
) -> str:
    """'hoje às 15h', 'amanhã', 'sexta (31/10) às 9h30' (agenda)."""
    cod = codigo(idioma)
    valores = _valores(alvo, cod)
    days = (alvo.date() - agora.date()).days
    if days == 0:
        rotulo = texto("d_hoje", cod)
    elif days == 1:
        rotulo = texto("d_amanha", cod)
    elif 1 < days < 7:
        nomes = _SEMANA_CURTA.get(cod) or _SEMANA.get(cod, _SEMANA[PADRAO])
        rotulo = texto("d_semana", cod, **valores, semana=nomes[alvo.weekday()])
    else:
        rotulo = texto("d_data", cod, **valores)
    if not com_hora:
        return rotulo
    return texto("d_com_hora", cod, **{**valores, "dia": rotulo})


__all__ = [
    "FRASES",
    "codigo",
    "contar",
    "decimal",
    "dia",
    "frase_data",
    "frase_hora",
    "hora_curta",
    "maiuscula",
    "nome",
    "nome_app",
    "nome_pasta",
    "quando",
    "texto",
    "usando",
]
