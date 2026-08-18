// @met4citizen/talkinghead ships no TypeScript types (plain .mjs) — minimal ambient
// declaration covering only what TalkingHeadAvatar.tsx actually uses.
declare module "@met4citizen/talkinghead" {
  export interface TalkingHeadAvatarOptions {
    url: string;
    body?: "M" | "F";
    avatarMood?: string;
    lipsyncLang?: string;
    [key: string]: unknown;
  }

  export class TalkingHead {
    constructor(node: HTMLElement, options?: Record<string, unknown>);
    showAvatar(avatar: TalkingHeadAvatarOptions, onprogress?: (event: ProgressEvent) => void): Promise<void>;
    start(): void;
    stop(): void;
    // Für die HeadAudio-Integration (components/TalkingHeadAvatar/headAudioIntegration.ts):
    // audioCtx/audioSpeechGainNode sind öffentliche Properties, die TalkingHead selbst verwaltet.
    audioCtx: AudioContext;
    audioSpeechGainNode: AudioNode;
    mtAvatar: Record<string, { newvalue: number; needsUpdate: boolean }>;
    opt: { update?: () => void; [key: string]: unknown };
    speakAudio(r: { audio: AudioBuffer }, opt?: Record<string, unknown>): void;
  }
}
