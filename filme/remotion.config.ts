// Configuração do Remotion (vale para `remotion studio` e `remotion render` pela CLI).
import { Config } from '@remotion/cli/config';

Config.setRspack(true);
Config.setVideoImageFormat('png');
Config.setOverwriteOutput(true);
Config.setDefaultPremountInSeconds(2);
// o motor 3D e os efeitos precisam de WebGL com GPU
Config.setChromiumOpenGlRenderer('angle');
// PC limitado: um quadro por vez
Config.setConcurrency(1);
