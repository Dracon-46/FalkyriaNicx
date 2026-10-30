# Filme institucional da Falkyria

Vídeo de ~38 s feito em [Remotion](https://www.remotion.dev) com um motor 3D próprio em three.js.

## Estrutura

- `src/linha.json`: a linha do tempo, com os tempos das falas e os planos 3D. A trilha também lê esse arquivo.
- `src/motor/motor.js`: o motor 3D (rajada de luz, rede, logo, fragmentos de dados, slime do Nicx). Tudo é função
  do tempo do plano; motion blur por subquadros e bloom.
- `src/Mundo.tsx`: liga o motor ao quadro atual do Remotion.
- `src/cenas.tsx`: cenas 2D (tipografia, Lumen, títulos, tela dividida) e o texto cinético.
- `src/Filme.tsx`: a montagem; `src/Root.tsx` registra a composição `FilmeFalkyria`.
- `scripts/trilha.py`: música, efeitos e mixagem (síntese própria). Gera `public/audio/`.
- `scripts/capturar-lumen.mjs` e `scripts/capturar-mapa.mjs`: capturas reais de falkyria-lumen.vercel.app.
- `scripts/quadros.mjs`: quadros soltos para revisão em `stills/`.

A logo é o desenho oficial (mesmo traçado do `FalkyriaLogo.tsx` do site).

## Comandos

```bash
npm i
npx remotion studio                       # prévia interativa
node scripts/quadros.mjs 6.9 23.4         # quadros soltos
python scripts/trilha.py                  # numpy, scipy e soundfile
npx remotion render FilmeFalkyria out/filme_v2.mp4 --props='{"comAudio":true}' --codec=h264 --crf=16 --gl=angle
```

## O que fica fora do git

`public/voz/` (narração gerada no ElevenLabs, plano sem licença comercial), `public/audio/`, `out/` e `stills/`.
Para trocar a voz: coloque as falas em `public/voz/fala1.wav` … `fala6.wav` e ajuste os tempos em `src/linha.json`.

Remotion é gratuito para equipes de até 3 pessoas; acima disso exige licença de empresa.
