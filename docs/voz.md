# Voz

Tudo local, em português do Brasil.

| Parte | Como funciona |
|---|---|
| Ouvir | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) `small` int8 na conversa, com VAD e as palavras-chave "Nicx Falkyria". |
| Falar | [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M), voz `pf_dora`. |
| "Nicx, ligar" | Whisper `base` (mais rápido) ouvindo em segundo plano; reconhece a frase e abre o mascote flutuante. |

Os modelos são baixados na primeira vez para `~/.cache/huggingface`.

## Conversa por voz

No app, **Conversa por voz** ouve até você parar de falar, manda a frase,
lê a resposta em voz alta e volta a ouvir. Para não ouvir o próprio Nicx nem
ruídos curtos:

- só conta como fala depois de ~0,3 s de voz contínua;
- espera 0,6 s depois que o Nicx termina de falar antes de reabrir o microfone;
- a transcrição descarta trechos que o Whisper marca como "não é fala" e
  junta frases repetidas em laço.

Perguntas faladas pedem ao modelo no máximo duas frases, sem listas nem
markdown.

## "Nicx, ligar"

Desligado por padrão. Para ligar:

```toml
[speech]
wake_word = true
```

ou rode `nicx escuta` quando quiser. Frases reconhecidas: "Nicx, ligar",
"Nicx, acordar", "Nicx, aparece", "Nicx, abrir", "Ei Nicx", "Oi Nicx".
Um ícone aparece perto do relógio; o menu dele pausa ou encerra a escuta.
Para ver o que a escuta está entendendo: `nicx escuta -v`.

## Opções

| Chave `[speech]` | Padrão | Para que serve |
|---|---|---|
| `model` | `small` | Whisper da conversa (`base` é 3x mais rápido, mas erra mais em microfone de notebook). |
| `language` | `pt` | Idioma do reconhecimento. |
| `hotwords` | `Nicx Falkyria` | Palavras que o Whisper deve preferir. |
| `voice_id` | `pf_dora` | Voz do Kokoro (`pm_alex`, `pm_santa` também falam português). |
| `voice_speed` | `1.0` | Velocidade da fala. |
| `wake_word` | `false` | Liga o "Nicx, ligar" junto com o servidor. |
| `wake_model` | `base` | Whisper da escuta. |
