// MotionEngine.js ships no TypeScript types — minimal declaration covering only what
// components/TalkingHeadAvatar uses.
import type { TalkingHead } from "@met4citizen/talkinghead";

export class MotionEngine {
  constructor(talkingHead: TalkingHead, options?: Record<string, number>);
  registerMotions(motions: Record<string, unknown>): number;
  play(name: string, dur?: number): Promise<void>;
  playSequence(names: string[]): Promise<void>;
  stop(): void;
  update(dt: number): void;
}
