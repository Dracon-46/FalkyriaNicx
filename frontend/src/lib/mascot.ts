import { create } from 'zustand';

/** What Nicx is doing right now; drives the mascot's animation. */
export type MascotMood =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'happy'
  | 'error'
  /** A task runs in the background (modo Trabalho, agents). */
  | 'working'
  /** Something needs the person (approval, "posso apagar?"). */
  | 'waiting';

/** Background moods: shown only while nothing in the foreground is going on. */
export type AmbientMood = 'idle' | 'working' | 'waiting' | 'happy' | 'error';

interface MascotState {
  mood: MascotMood;
  /** What runs in the background; shown while `mood` is `idle`. */
  ambient: AmbientMood;
  /** Live audio level from 0 to 1: the mic while listening, playback while speaking. */
  level: number;
  setMood: (mood: MascotMood) => void;
  setAmbient: (ambient: AmbientMood) => void;
  setLevel: (level: number) => void;
}

/**
 * Shared mascot state. Voice code sets `listening`/`speaking` and feeds `level`;
 * the chat flow sets `thinking` while a reply streams, then `happy` or `error`.
 * The inbox sets `ambient` (working, waiting...), which shows through whenever
 * the foreground `mood` is `idle`. Outside React, call
 * `useMascot.getState().setMood(...)`.
 */
export const useMascot = create<MascotState>((set) => ({
  mood: 'idle',
  ambient: 'idle',
  level: 0,
  setMood: (mood) => set({ mood, level: 0 }),
  setAmbient: (ambient) => set({ ambient }),
  setLevel: (level) => set({ level: Math.max(0, Math.min(1, level)) }),
}));

/** The mood on screen: the foreground one, or the background one when idle. */
export function visibleMood(s: { mood: MascotMood; ambient: AmbientMood }): MascotMood {
  return s.mood === 'idle' ? s.ambient : s.mood;
}
