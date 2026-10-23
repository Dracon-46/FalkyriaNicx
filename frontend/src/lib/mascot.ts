import { create } from 'zustand';

/** What Nicx is doing right now; drives the mascot's animation. */
export type MascotMood =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'happy'
  | 'error';

interface MascotState {
  mood: MascotMood;
  /** Live audio level from 0 to 1: the mic while listening, playback while speaking. */
  level: number;
  setMood: (mood: MascotMood) => void;
  setLevel: (level: number) => void;
}

/**
 * Shared mascot state. Voice code sets `listening`/`speaking` and feeds `level`;
 * the chat flow sets `thinking` while a reply streams, then `happy` or `error`.
 * Outside React, call `useMascot.getState().setMood(...)`.
 */
export const useMascot = create<MascotState>((set) => ({
  mood: 'idle',
  level: 0,
  setMood: (mood) => set({ mood, level: 0 }),
  setLevel: (level) => set({ level: Math.max(0, Math.min(1, level)) }),
}));
