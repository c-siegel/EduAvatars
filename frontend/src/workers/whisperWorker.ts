// Runs transformers.js's Whisper pipeline off the main thread, so a segment's transcription
// (real GPU/CPU work) never jank the avatar animation or chat UI. See lib/browserStt.ts, its only
// caller, for the protocol these messages implement.

import { env, pipeline, type AutomaticSpeechRecognitionPipeline } from "@huggingface/transformers";

// Multi-threaded WASM (onnxruntime-web's default off the WebGPU path too — WebGPU is a compute
// backend layered on top of the WASM-compiled ONNX Runtime, not a replacement for it) needs
// SharedArrayBuffer, which browsers only grant to a cross-origin-isolated page (COOP/COEP response
// headers on every document). Forcing single-threaded WASM avoids adding those site-wide — they'd
// also require every cross-origin embed (e.g. the Tally survey iframe, see components/SurveyEmbed)
// to send matching CORP headers, which isn't ours to control. Only affects CPU-side
// pre/post-processing speed (tokenization, feature extraction) — actual model inference still runs
// on the GPU via the "webgpu" device below.
env.backends.onnx.wasm!.numThreads = 1;

interface InitMessage {
  type: "init";
  model: string;
}

interface TranscribeMessage {
  type: "transcribe";
  id: number;
  audio: Float32Array;
  language: string;
}

type InboundMessage = InitMessage | TranscribeMessage;

// Whisper's "language" option wants a full name ("german"), not the project's two-letter
// spoken_language code ("de") — see types/project.ts's SpokenLanguage.
const LANGUAGE_NAMES: Record<string, string> = { de: "german", en: "english" };

let transcriberPromise: Promise<AutomaticSpeechRecognitionPipeline> | null = null;

function loadTranscriber(model: string): Promise<AutomaticSpeechRecognitionPipeline> {
  return pipeline("automatic-speech-recognition", model, {
    device: "webgpu",
    // "q4" (4-bit) — confirmed on the Hub that every configured model publishes this variant for
    // both encoder_model and decoder_model_merged. Needed for the encoder specifically: even a
    // "turbo" Whisper only prunes the *decoder* to 4 layers, so the encoder stays full-size
    // (large-v3's) regardless — on iPadOS Safari, q8 wasn't enough headroom and the whole tab got
    // silently OOM-killed and reloaded partway through loading (not something a try/catch can
    // recover from — the JS context itself is gone). q4 roughly halves that again over q8, at a
    // further small accuracy cost.
    dtype: "q4",
    progress_callback: (info) => {
      if (info.status === "progress_total") {
        postMessage({ type: "progress", progress: info.progress });
      }
    },
  });
}

self.onmessage = async (event: MessageEvent<InboundMessage>) => {
  const message = event.data;
  if (message.type === "init") {
    try {
      transcriberPromise = loadTranscriber(message.model);
      await transcriberPromise;
      postMessage({ type: "ready" });
    } catch (error) {
      transcriberPromise = null;
      postMessage({ type: "error", message: error instanceof Error ? error.message : String(error) });
    }
    return;
  }

  const { id, audio, language } = message;
  try {
    if (!transcriberPromise) throw new Error("Whisper worker received a transcribe request before init.");
    const transcriber = await transcriberPromise;
    const output = await transcriber(audio, {
      language: LANGUAGE_NAMES[language] ?? language,
      task: "transcribe",
      // Defense in depth alongside browserStt.ts's silence gate: caps how many times the decoder
      // may repeat the same 3-token sequence, so a borderline-quiet (not fully silent) segment
      // that still tempts Whisper into a hallucinated stock phrase can't loop it indefinitely.
      no_repeat_ngram_size: 3,
      // Without this, transformers.js feeds a segment's audio through Whisper's encoder as one
      // window — WhisperFeatureExtractor silently truncates anything past 30s (only a
      // console.warn, no error), so a student who speaks for longer than that in one pause-free
      // stretch (easy in a noisy room where watchForSpeechPauses never sees real silence, see
      // PublicChat/index.tsx) would lose the rest of what they said with no visible failure.
      // 30/5 mirrors transformers.js's own documented example for long-form audio.
      chunk_length_s: 30,
      stride_length_s: 5,
    });
    const text = Array.isArray(output) ? output.map((o) => o.text).join(" ") : output.text;
    postMessage({ type: "result", id, text: text.trim() });
  } catch (error) {
    postMessage({ type: "error", id, message: error instanceof Error ? error.message : String(error) });
  }
};
