"""Frase de ativação "Nicx, ligar": escuta local e mascote flutuante.

Fica fora de ``nicx.speech`` de propósito: aquele pacote carrega todos os
motores de voz (inclusive o Kokoro, com PyTorch) ao ser importado, e a escuta
em segundo plano precisa ser leve. Os módulos daqui importam só o necessário.
"""
