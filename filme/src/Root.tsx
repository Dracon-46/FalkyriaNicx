import { Composition } from 'remotion';
import { Filme } from './Filme';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition id="FilmeFalkyria" component={Filme} durationInFrames={1140} fps={30} width={1920} height={1080} defaultProps={{ comAudio: false }} />
    </>
  );
};
