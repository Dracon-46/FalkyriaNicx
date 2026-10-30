import React from 'react';
import { AbsoluteFill, Sequence, staticFile, useVideoConfig } from 'remotion';
import { Audio } from '@remotion/media';
import { Mundo } from './Mundo';
import { COR } from './estilo';
import { Divisao, Frase, LumenFontes, LumenIndicadores, LumenLema, LumenMapa, LumenNumeros, Marca, MetadeLumenFecha, NicxTitulo, Tipografia, Varredura } from './cenas';

export const Filme: React.FC<{ readonly comAudio: boolean }> = ({ comAudio }) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: COR.grafite }}>
      <Mundo />

      {/* Falkyria */}
      <Sequence name="Marca (logo)" from={Math.round(7.0 * fps)} durationInFrames={Math.round(1.55 * fps)}>
        <Marca top={800} px={62} fim={1.25} />
      </Sequence>
      <Sequence name="Luz (logo -> tipografia)" from={Math.round(8.4 * fps)} durationInFrames={Math.round(0.4 * fps)}>
        <Varredura dur={0.4} />
      </Sequence>
      <Sequence name="Tipografia" from={Math.round(8.55 * fps)} durationInFrames={Math.round(2.15 * fps)}>
        <Tipografia />
      </Sequence>

      {/* Lumen */}
      <Sequence name="Lumen: mapa" from={Math.round(14.3 * fps)} durationInFrames={Math.round(2.3 * fps)}>
        <LumenMapa />
      </Sequence>
      <Sequence name="Lumen: números" from={Math.round(16.6 * fps)} durationInFrames={Math.round(0.8 * fps)}>
        <LumenNumeros />
      </Sequence>
      <Sequence name="Lumen: indicadores" from={Math.round(17.4 * fps)} durationInFrames={Math.round(0.8 * fps)}>
        <LumenIndicadores />
      </Sequence>
      <Sequence name="Lumen: fontes" from={Math.round(18.2 * fps)} durationInFrames={Math.round(1.3 * fps)}>
        <LumenFontes />
      </Sequence>
      <Sequence name="Lumen: lema" from={Math.round(19.5 * fps)} durationInFrames={Math.round(2.1 * fps)}>
        <LumenLema />
      </Sequence>

      {/* Nicx */}
      <Sequence name="Nicx: título" from={Math.round(26.6 * fps)} durationInFrames={Math.round(2.2 * fps)}>
        <NicxTitulo />
      </Sequence>

      {/* Duas iniciativas, uma mesma visão */}
      <Sequence name="Divisão" from={Math.round(28.8 * fps)} durationInFrames={Math.round(2.8 * fps)}>
        <Divisao />
      </Sequence>
      <Sequence name="Frase: duas iniciativas" from={Math.round(30.05 * fps)} durationInFrames={Math.round(1.55 * fps)}>
        <Frase texto="DUAS INICIATIVAS." top={930} fim={1.2} px={38} />
      </Sequence>
      <Sequence name="Lumen fecha" from={Math.round(31.6 * fps)} durationInFrames={Math.round(0.8 * fps)}>
        <MetadeLumenFecha />
      </Sequence>
      <Sequence name="Frase: uma mesma visão" from={Math.round(31.85 * fps)} durationInFrames={Math.round(2.6 * fps)}>
        <Frase texto="UMA MESMA VISÃO." top={780} fim={2.2} px={40} cores={{ 9: COR.azul, 10: COR.azul, 11: COR.azul, 12: COR.azul, 13: COR.azul, 14: COR.azul, 15: COR.azul }} />
      </Sequence>

      {/* Assinatura */}
      <Sequence name="Marca final" from={Math.round(35.45 * fps)}>
        <Marca top={752} px={56} sub="TECNOLOGIA FEITA NO BRASIL" />
      </Sequence>

      {comAudio && <Audio src={staticFile('audio/mix_final.wav')} />}
    </AbsoluteFill>
  );
};
