# Instalador do Nicx para Windows (`NicxSetup.exe`)

Instalador para usuários finais no Windows 10 (1809+) e 11, x64. Não exige
administrador, git, Rust nem Visual Studio: os pacotes do Nicx vão prontos
dentro do instalador e o resto é baixado só se faltar no computador.

## Como funciona

1. O assistente (Inno Setup, em português) copia poucos arquivos para
   `%LOCALAPPDATA%\Programs\Nicx`: os wheels `nicx` e `nicx-rust`, as versões
   fixadas das dependências (`constraints.txt`), o `uv.exe`, o lançador e o
   ícone.
2. Em seguida roda `setup-runtime.ps1`, com o progresso dentro do assistente
   e um botão **Interromper**. O script verifica e faz só o que falta:
   - Windows, RAM (avisa abaixo de 8 GB e escolhe modelo/contexto menores) e
     espaço em disco;
   - Python 3.12 exclusivo do Nicx (`<app>\python`) e ambiente `<app>\venv`;
   - pacotes: os dois wheels + extras `server`, `memory-bm25` e `pdf` do PyPI
     (com `speech` e `voice` se o componente **Voz em português** for marcado),
     nas versões do `uv.lock` e com `--no-build`: nada é compilado no
     computador do usuário (dependências que o PyPI só tem como código-fonte,
     hoje apenas `docopt`, vão pré-geradas no instalador);
   - `~/.nicx/config.toml` só se ainda não existir (Ollama, modelo local, voz
     pt-BR, estatísticas de uso desligadas até o usuário decidir no app) e
     `SOUL.md`/`MEMORY.md`/`USER.md`;
   - Ollama: usa o que já existe; se não houver, baixa o instalador oficial,
     confere a assinatura digital e instala só para o usuário;
   - modelo `qwen3.5:4b` (ou `qwen3.5:2b`/`0.8b` com pouca RAM), baixado pela
     API do Ollama apenas se faltar;
   - modelos de voz (Whisper base e Kokoro), se a voz foi escolhida.
3. Atalhos **Nicx** e **Parar o Nicx** no menu Iniciar (e, opcionalmente,
   **Nicx** na Área de Trabalho). O atalho executa `nicx-launcher.pyw` com o
   `pythonw.exe` do ambiente (sem console): inicia o Ollama se preciso, sobe o
   servidor (`nicx start`, que serve a interface já compilada) e abre
   `http://127.0.0.1:8000` no navegador. Uma janela "Iniciando o Nicx..."
   aparece enquanto o servidor sobe.

A desinstalação remove o aplicativo e pergunta se deve apagar os dados em
`~/.nicx` (o padrão é manter). O Ollama e os modelos baixados continuam
instalados. Em modo silencioso os dados são mantidos, a menos que se passe
`/APAGARDADOS=1` ao desinstalador.

O instalador não pede nem guarda senhas ou chaves e não envia dados de uso.

## Como gerar

Requisitos na máquina de build: `uv`, Node.js 22+ (com `frontend/node_modules`
instalado), Rust (`%USERPROFILE%\.cargo\bin`) com as Build Tools do Visual
Studio e o ambiente de desenvolvimento do repositório (`.venv` com Python 3.12
e `maturin`). O Inno Setup 6 é instalado automaticamente com o winget se não
for encontrado.

```powershell
cd C:\dev\FalkyriaNicx
powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
```

Opções úteis:

| Opção | Efeito |
|-------|--------|
| `-Version 0.2.0` | Versão do pacote e do instalador (padrão: tag `vX.Y.Z` do commit, senão `0.1.0`) |
| `-SkipFrontend` | Reaproveita a interface já compilada em `src/nicx/servidor/static` |
| `-SkipRust` | Reaproveita o wheel `nicx_rust` mais recente (economiza ~4 min) |
| `-UvExe <caminho>` | `uv.exe` a embutir (padrão: o do PATH) |

Saídas (ignoradas pelo git):

- `packaging/windows/dist/NicxSetup.exe` e `NicxSetup.exe.sha256`
- `packaging/windows/dist/wheels/` (`nicx-*.whl`, `nicx_rust-*-cp312-*-win_amd64.whl`
  e wheels gerados para dependências sem wheel no PyPI)
- `packaging/windows/dist/constraints.txt` (versões do `uv.lock`)
- `packaging/windows/build/` (imagens, ícone, `uv.exe`, termos de uso em texto)

## Publicar uma versão (com atualização pelo app)

1. Cadastre as novidades da versão na tabela `nicx_novidades` do Supabase da
   Falkyria e marque como publicada: pelo Painel Falkyria (seção 10, Novidades)
   ou com um INSERT:

   ```sql
   insert into public.nicx_novidades (versao, data, titulo, itens, publicado)
   values ('0.2.2', '2026-11-10', 'Título curto',
           array['O que mudou, em uma frase.', 'Outra mudança.'], true);
   ```

   `uv run nicx atualizacao novidades` mostra o que está publicado.
2. Gere o instalador (`build-installer.ps1 -Version X.Y.Z`) e teste numa
   instalação descartável.
3. Assine o arquivo de versões (no PC da Falkyria, com a chave em
   `~/.falkyria-loja/`):

   ```powershell
   uv run nicx atualizacao assinar packaging\windows\dist\NicxSetup.exe --versao X.Y.Z
   ```

   Gera `packaging/windows/dist/nicx-atualizacao.json` (versão, endereço e
   sha256 do instalador, novidades lidas do banco), assinado com Ed25519. Sem
   internet, `--sem-banco` usa a lista de `src/nicx/atualizacao/novidades.py`.
4. Suba **os dois** arquivos na release `vX.Y.Z`: `NicxSetup.exe` e
   `nicx-atualizacao.json`. O app procura em
   `releases/latest/download/nicx-atualizacao.json`; sem esse arquivo, ninguém
   vê a versão nova pelo app.
   Suba também `packaging/windows/dist/nicx-vscode.vsix` (a extensão do VS
   Code, gerada de `vscode/` pelo build e já incluída no instalador).

Na atualização pelo app, o Nicx abre o instalador com
`/SILENT /SUPPRESSMSGBOXES /NORESTART /REABRIR=1`: o `setup-runtime.ps1` para o
servidor, troca os pacotes e o `[Run]` com `ReabrirDepois` religa o Nicx sem
abrir outra aba.

## Testar sem instalar

O script de preparação mostra o plano sem alterar nada:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\setup-runtime.ps1 -DryRun
powershell -ExecutionPolicy Bypass -File packaging\windows\setup-runtime.ps1 -DryRun -Voice
```

Instalação descartável (pasta e dados temporários, sem atalho na Área de
Trabalho), seguida da desinstalação. `NICX_LAUNCHER_HEADLESS=1` faz o lançador
não abrir navegador, janela nem caixas de mensagem; confira o servidor por HTTP:

```powershell
$env:NICX_HOME = "$env:TEMP\nicx-teste\home"
$env:NICX_LAUNCHER_HEADLESS = "1"
Start-Process -Wait .\packaging\windows\dist\NicxSetup.exe -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/COMPONENTS="nicx"','/TASKS=""',"/DIR=`"$env:TEMP\nicx-teste\app`""
& "$env:TEMP\nicx-teste\app\venv\Scripts\nicx.exe" --version
& "$env:TEMP\nicx-teste\app\venv\Scripts\python.exe" "$env:TEMP\nicx-teste\app\nicx-launcher.pyw" --port 8765
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/health
Start-Process -Wait "$env:TEMP\nicx-teste\app\unins000.exe" -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/APAGARDADOS=1'
```

Códigos de saída do instalador: `0` sucesso; `10` arquivos copiados, mas a
preparação falhou ou foi interrompida (o registro fica em `<app>\logs`).

## Arquivos

| Arquivo | Papel |
|---------|-------|
| `build-installer.ps1` | Gera wheels, constraints, imagens e compila o instalador |
| `nicx.iss` | Script do Inno Setup (assistente, atalhos, desinstalação) |
| `setup-runtime.ps1` | Preparação do ambiente (também roda sozinho; `-DryRun`) |
| `nicx-launcher.pyw` | Lançador dos atalhos (Ollama + servidor + navegador; `--stop`) |
