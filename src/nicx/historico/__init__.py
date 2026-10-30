"""Leva C (confiança): histórico universal, desfazer unificado, auditoria e autonomia.

- :mod:`registro`: o banco único de atividades (``~/.nicx/historico.db``).
- :mod:`mudancas`: o que mudou em lembretes, agenda e projetos (e como voltar).
- :mod:`desfazer`: "desfaz" volta a última mudança, ou uma escolhida na tela.
- :mod:`autonomia`: observador, assistido e autônomo, aplicados no código.
"""

from nicx.historico.registro import Atividade, anotar, origem, registro

__all__ = ["Atividade", "anotar", "origem", "registro"]
