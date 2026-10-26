# Desenvolvimento

## Rodar os testes

```bash
uv run pytest tests -n 3 -q                 # tudo (~4 min)
uv run pytest tests/servidor -q             # uma área
uv run ruff check src tests && uv run ruff format --check src tests
cd frontend && npx vitest run && npx tsc --noEmit
cd rust && cargo fmt --all --check && cargo clippy --workspace --all-targets -- -D warnings
```

Use `-n 3` em notebook: mais processos que isso disputam CPU e memória com o
resto da máquina.

No Windows, ~110 testes falham por motivos de plataforma, não de código:
`/proc`, `chmod`, links simbólicos, sensores de energia (`intel-rapl`),
separador de caminho, bash ausente. Ao mexer em algo, compare as falhas com
as da versão anterior em vez de esperar zero.

## Extensão Rust

O Python acessa o Rust só por `nicx.nucleo.rust.get_rust_module()`. A ponte
está em `rust/crates/nicx-ponte` (gera o módulo `nicx_rust`):

```bash
CARGO_BUILD_JOBS=2 uv run maturin develop --release -m rust/crates/nicx-ponte/Cargo.toml
```

Para expor algo novo: implemente no crate certo (`nicx-ferramentas`,
`nicx-seguranca`...), crie a classe `Py...` no arquivo da ponte
correspondente (`ferramentas.rs`, `seguranca.rs`...) e registre em `lib.rs`.

## Convenções

- Arquivos de texto sempre com `encoding="utf-8"` (no Windows o padrão é
  cp1252).
- Texto que a pessoa lê (interface, CLI, mensagens de erro, voz) em português
  do Brasil.
- Nada de chamar serviços de terceiros sem a pessoa pedir; estatísticas só
  para o Supabase da Falkyria e só com consentimento.
- Uma ferramenta nova precisa de entrada em `DEFAULT_TOOL_CAPABILITIES`.
- Nunca engolir erros em silêncio: registre no log e devolva uma mensagem
  útil.

## CI

GitHub Actions roda a cada push: lint, testes no Linux e no Windows, Rust
(fmt, clippy, testes), interface (`npm audit`, vitest, tsc, build) e uma
análise de segurança. Os testes de instalação em Bash rodam quando
`scripts/` muda.

Alterar `.github/workflows/` exige o escopo `workflow` no `gh`
(`gh auth refresh -h github.com -s workflow`).
