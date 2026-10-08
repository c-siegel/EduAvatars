import type { TalkingHead } from "@met4citizen/talkinghead";

// HeadAudio (frontend/public/headaudio/, see ATTRIBUTION.md) computes lipsync visemes in real time
// directly from the audio being played — independent of language/TTS provider, without word
// timestamps. Replaces TalkingHead's own text-based viseme path (which would need word timing that
// litellm.speech() doesn't provide). Setup matches the official integration example from the
// HeadAudio docs 1:1.
//
// Known limitation: the only pretrained model (model-en-mixed.bin) was trained on English voices
// only — unverified for German.

interface HeadAudioNodeLike extends AudioNode {
  loadModel(url: string): Promise<void>;
  update(): void;
  onvalue: (key: string, value: number) => void;
}

// In the dev server, Vite blocks every import() that passes through its transform middleware
// (even dynamic/not statically analyzable ones) and points to a file under public/ ("This file is
// in /public ... should not be imported from source code"), even with @vite-ignore — that only
// suppresses the analysis warning, not this runtime block. new Function(...) creates a real,
// native browser import() outside Vite's module graph that the middleware never sees — verified
// with Playwright against the real dev server.
const nativeImport = new Function("specifier", "return import(specifier)") as (
  specifier: string,
) => Promise<{ HeadAudio: new (context: AudioContext, options: Record<string, unknown>) => HeadAudioNodeLike }>;

export async function attachHeadAudio(head: TalkingHead): Promise<void> {
  await head.audioCtx.audioWorklet.addModule("/headaudio/headworklet.mjs");
  // Runtime URL under public/, no Vite module graph entry (no npm package exists, see
  // ATTRIBUTION.md). The class is called "HeadAudio" (verified in the source) — the HeadAudio docs
  // themselves speak generically of an "audio worklet node", which is not an exact class name.
  // A fully resolved URL instead of "/headaudio/headaudio.mjs": code from new Function(...) has no
  // script URL of its own, and Firefox resolves a dynamic import() in it against a file:// base
  // instead of the document base. The browser then aborts with "Content at https://… may not load
  // or link to file:///…" — Chromium (and so the Playwright verification above) and WebKit use the
  // document base and were never affected. An absolute URL leaves the browser no base to choose.
  const { HeadAudio } = await nativeImport(new URL("/headaudio/headaudio.mjs", location.origin).href);
  const headaudio: HeadAudioNodeLike = new HeadAudio(head.audioCtx, {
    parameterData: { vadGateActiveDb: -40, vadGateInactiveDb: -60 },
  });
  await headaudio.loadModel("/headaudio/model-en-mixed.bin");
  head.audioSpeechGainNode.connect(headaudio);
  headaudio.onvalue = (key, value) => {
    Object.assign(head.mtAvatar[key], { newvalue: value, needsUpdate: true });
  };
  head.opt.update = headaudio.update.bind(headaudio);
}
