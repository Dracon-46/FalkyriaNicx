"""setup-runtime.ps1 roda com Set-StrictMode: variável de script lida sem ter
sido definida derruba a instalação no fim.

Aconteceu com ``$script:OllamaFromSetup``: só era definida quando a própria
preparação ligava o Ollama. Com o Ollama já aberto (bandeja, ou o Nicx ligado
numa atualização pelo app), a instalação terminava em erro. Toda variável
``$script:`` lida no arquivo tem que receber um valor no nível de cima.
"""

from __future__ import annotations

import re
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2] / "packaging" / "windows" / "setup-runtime.ps1"
)


def test_variaveis_de_script_definidas_no_topo():
    texto = SCRIPT.read_text(encoding="utf-8-sig")
    nomes = set(re.findall(r"\$script:([A-Za-z_][A-Za-z0-9_]*)", texto))
    assert "OllamaFromSetup" in nomes
    sem_topo = [
        nome
        for nome in sorted(nomes)
        if not re.search(rf"(?m)^\$script:{nome}\s*[+]?=", texto)
        and not re.search(rf"(?m)^\${nome}\s*=", texto)
    ]
    assert sem_topo == []
