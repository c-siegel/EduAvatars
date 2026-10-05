// In-browser speech-to-text via WebGPU (transformers.js's Whisper support, run inside
// workers/whisperWorker.ts). Used by pages/PublicChat/index.tsx as an alternative to uploading
// each recorded segment to the backend's /transcribe route — see backend
// services/api_key_service.py::browser_stt_model_for for when this is even offered to a visitor.

import { FALLBACK_SILENCE_RMS_THRESHOLD, rms } from "./audioLevel";

export type BrowserSttStatus = "idle" | "loading" | "ready" | "unsupported" | "error";

// navigator.gpu has no ambient TypeScript type in this project (no @webgpu/types dependency) —
// narrowly typed here just enough to call requestAdapter().
interface NavigatorWithGpu extends Navigator {
  gpu?: { requestAdapter: () => Promise<unknown> };
}

/** Whether this browser can actually run a WebGPU model, not just whether the API exists —
 * some browsers expose navigator.gpu but fail to produce a real adapter (disabled flag, no
 * compatible hardware). */
export async function isWebGpuAvailable(): Promise<boolean> {
  const gpu = (navigator as NavigatorWithGpu).gpu;
  if (!gpu) return false;
  try {
    return (await gpu.requestAdapter()) != null;
  } catch {
    return false;
  }
}

// Matches whisperWorker.ts's postMessage calls.
type WorkerOutboundMessage =
  | { type: "progress"; progress: number }
  | { type: "ready" }
  | { type: "result"; id: number; text: string }
  | { type: "error"; id?: number; message: string };

interface PendingTranscription {
  resolve: (text: string) => void;
  reject: (error: Error) => void;
}

// Resamples a recorded WebM/Opus blob down to the mono 16kHz PCM Float32Array Whisper expects —
// the standard technique for feeding browser-recorded audio to transformers.js (an OfflineAudioContext
// set to the target rate does the resampling for free while rendering).
const WHISPER_SAMPLE_RATE = 16000;

// Threshold is passed in per call (see transcribe's silenceThreshold param), calibrated per
// recording session from real mic/room data by pages/PublicChat/index.tsx's watchForSpeechPauses
// — see lib/audioLevel.ts. Applied here to the whole decoded segment instead of a live rolling
// window. Without this gate, a segment that's mostly/entirely silence (typically the last, short
// segment of a recording — whatever's left after the final pause before the mic button is
// released) reliably makes Whisper hallucinate a repeated stock training-data phrase ("Vielen
// Dank", "Thank you", "Untertitel von...", ...) instead of returning nothing — a well-known
// artifact of feeding it near-silent audio. The server path never hits this because
// faster-whisper's vad_filter=True (see backend services/stt_service.py) already discards
// silence before decoding; this is the browser path's equivalent guard.
function isSilent(samples: Float32Array, threshold: number): boolean {
  return rms(samples) < threshold;
}

async function decodeToMono16k(blob: Blob): Promise<Float32Array> {
  const arrayBuffer = await blob.arrayBuffer();
  const audioCtx = new AudioContext();
  let decoded: AudioBuffer;
  try {
    decoded = await audioCtx.decodeAudioData(arrayBuffer);
  } finally {
    void audioCtx.close();
  }
  const offlineCtx = new OfflineAudioContext(
    1,
    Math.ceil(decoded.duration * WHISPER_SAMPLE_RATE),
    WHISPER_SAMPLE_RATE,
  );
  const source = offlineCtx.createBufferSource();
  source.buffer = decoded;
  source.connect(offlineCtx.destination);
  source.start(0);
  const rendered = await offlineCtx.startRendering();
  return rendered.getChannelData(0);
}

/** Runs Whisper transcription entirely in the visitor's browser via a Web Worker, so the heavy
 * model download/inference never blocks the main thread (avatar animation, chat UI). One instance
 * per chat session — see pages/PublicChat/index.tsx, its only caller. */
export class BrowserSttEngine {
  status: BrowserSttStatus = "idle";

  private worker: Worker | null = null;
  private readyPromise: Promise<void> | null = null;
  private nextId = 0;
  private pending = new Map<number, PendingTranscription>();
  private onProgress: ((percent: number) => void) | undefined;

  // Public so callers can tell whether an existing engine already matches the model a project
  // wants (see pages/PublicChat/index.tsx) before building a second one.
  constructor(readonly model: string) {}

  /** Starts loading the model if it hasn't started yet (safe to call repeatedly); resolves once
   * `status` has settled to "ready", "unsupported", or "error" — never rejects. `onProgress`
   * (0-100) is only ever called for the very first call that actually starts loading. */
  ensureReady(onProgress?: (percent: number) => void): Promise<void> {
    if (!this.readyPromise) {
      this.onProgress = onProgress;
      this.readyPromise = this.init();
    }
    return this.readyPromise;
  }

  private async init(): Promise<void> {
    if (!(await isWebGpuAvailable())) {
      this.status = "unsupported";
      return;
    }
    this.status = "loading";
    return new Promise((resolve) => {
      const worker = new Worker(new URL("../workers/whisperWorker.ts", import.meta.url), { type: "module" });
      this.worker = worker;
      worker.onmessage = (event: MessageEvent<WorkerOutboundMessage>) => {
        const message = event.data;
        if (message.type === "progress") {
          this.onProgress?.(message.progress);
        } else if (message.type === "ready") {
          this.status = "ready";
          resolve();
        } else if (message.type === "error" && message.id === undefined) {
          // An id-less error only ever comes from the init step (see whisperWorker.ts) — a
          // transcribe error always carries the request's id and is handled below instead.
          this.status = "error";
          resolve();
        } else {
          this.handleTranscriptionMessage(message);
        }
      };
      worker.onerror = () => {
        this.status = "error";
        resolve();
      };
      worker.postMessage({ type: "init", model: this.model });
    });
  }

  private handleTranscriptionMessage(message: WorkerOutboundMessage): void {
    if (message.type !== "result" && message.type !== "error") return;
    const pending = this.pending.get(message.id!);
    if (!pending) return;
    this.pending.delete(message.id!);
    if (message.type === "result") pending.resolve(message.text);
    else pending.reject(new Error(message.message));
  }

  /** Transcribes one recorded segment. Throws if the engine isn't "ready" (caller should fall
   * back to the backend's /transcribe route instead — see pages/PublicChat/index.tsx).
   * `silenceThreshold` should be the current recording session's calibrated value (see
   * lib/audioLevel.ts); defaults to the fallback constant if the caller has none yet. */
  async transcribe(
    blob: Blob,
    language: string,
    silenceThreshold: number = FALLBACK_SILENCE_RMS_THRESHOLD,
  ): Promise<string> {
    if (this.status !== "ready" || !this.worker) {
      throw new Error(`Browser STT engine is not ready (status: ${this.status}).`);
    }
    const audio = await decodeToMono16k(blob);
    if (isSilent(audio, silenceThreshold)) return "";
    const id = this.nextId++;
    return new Promise<string>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker!.postMessage({ type: "transcribe", id, audio, language }, [audio.buffer]);
    });
  }

  /** Releases the worker — call on chat page unmount, not between recordings (loading the model
   * is the expensive part, and it's meant to be paid for once per visit). */
  dispose(): void {
    this.worker?.terminate();
    this.worker = null;
    this.pending.forEach(({ reject }) => reject(new Error("Browser STT engine disposed.")));
    this.pending.clear();
  }
}
