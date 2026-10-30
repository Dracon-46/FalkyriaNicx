import { loadFont as loadSora } from '@remotion/google-fonts/Sora';
import { loadFont as loadInter } from '@remotion/google-fonts/Inter';
import { loadFont as loadGrotesk } from '@remotion/google-fonts/SpaceGrotesk';
import { loadFont as loadMono } from '@remotion/google-fonts/IBMPlexMono';

// Paleta oficial da Falkyria
export const COR = {
  grafite: '#0D1117',
  azul: '#00A6FF',
  branco: '#FFFFFF',
  cinza: '#57606A',
  cinzaClaro: '#8B949E',
  texto: '#C9D1D9',
} as const;

export const FONTE = {
  marca: loadSora('normal', { weights: ['600'], subsets: ['latin'] }).fontFamily,
  texto: loadInter('normal', { weights: ['400', '500'], subsets: ['latin'] }).fontFamily,
  rotulo: loadGrotesk('normal', { weights: ['500'], subsets: ['latin'] }).fontFamily,
  mono: loadMono('normal', { weights: ['400', '500'], subsets: ['latin'] }).fontFamily,
} as const;
