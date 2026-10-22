# Como contribuir com o Nicx

O Nicx é software proprietário da Falkyria. Contribuições são feitas pela equipe
da Falkyria ou por pessoas autorizadas por ela (veja [LICENSE](LICENSE)).

## Ambiente

```bash
git clone https://github.com/Dracon-46/FalkyriaNicx.git
cd FalkyriaNicx
uv sync --extra server --extra memory-bm25 --extra pdf --extra dev --group desktop-native
uv run pre-commit install
```

Detalhes de requisitos e uso no [README](README.md). Convenções de código e
estrutura do projeto em [docs/development/contributing.md](docs/development/contributing.md).

## Antes de abrir um PR

```bash
uv run pytest tests -n auto -q -m "not live and not cloud and not hub"
uv run ruff check src tests
uv run ruff format --check src tests
```

No frontend (`frontend/`): `npx tsc --noEmit` e `npm run build`.

- Um assunto por PR, com descrição do que muda e de como foi testado.
- Componentes novos (motores, ferramentas, agentes, canais) se registram pelo
  padrão de registro em `src/nicx/core/registry.py`.
- Arquivos de texto sempre com `encoding="utf-8"`: o Nicx roda no Windows.
- Nada de telemetria, atualizador automático ou envio de dados para serviços
  externos sem decisão explícita da Falkyria.
- O guia de revisão está em [REVIEW.md](REVIEW.md).
