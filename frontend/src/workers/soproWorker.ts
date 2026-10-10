// Runs Sopro text-to-speech in the browser (@soprotts/onnx-web) off the main thread, so speech
// generation never blocks the avatar's render loop or the chat UI. Only used by the latency test
// page (pages/Dashboard/LatencyLab) through lib/soproTts.ts, which has the message protocol.
//
// Web Audio doesn't exist in workers, so the reference clip arrives already decoded to PCM (Sopro
// accepts that instead of a file).

import { SoproTTS } from "@soprotts/onnx-web";
// Imported as URLs so Vite emits them, for the same reason as in parakeetWorker.ts: onnxruntime-web's
// own lookup breaks once Vite has moved the bundle. Its WebGPU and plain WASM builds need
// different files, so the backend is picked here and passed to Sopro explicitly.
import ortWebGpuWasmUrl from "onnxruntime-web/ort-wasm-simd-threaded.asyncify.wasm?url";
import ortWasmUrl from "onnxruntime-web/ort-wasm-simd-threaded.wasm?url";

export type SoproInbound =
  | { type: "init"; modelBaseUrl: string | null }
  | { type: "reference"; pcm: Float32Array; sampleRate: number }
  | { type: "synthesize"; id: number; text: string; language: string };

export type SoproOutbound =
  | { type: "progress"; loadedBytes: number; totalBytes: number }
  | { type: "ready"; backend: string }
  | { type: "referenceReady"; prepareMs: number }
  | { type: "audio"; id: number; samples: Float32Array<ArrayBuffer>; sampleRate: number }
  | { type: "done"; id: number; synthMs: number; audioSeconds: number }
  | { type: "error"; id: number | null; message: string };

let tts: SoproTTS | null = null;
let reference: unknown = null;
// Requests run one after another, in the order the reply's chunks arrive.
let chain: Promise<void> = Promise.resolve();

function post(message: SoproOutbound, transfer: Transferable[] = []) {
  // The options form, because this project type-checks workers against the DOM lib.
  postMessage(message, { transfer });
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

// Sopro's own rule (see its create()): WebGPU on desktop browsers that hand out an adapter, WASM
// on phones and tablets and everywhere else.
async function canUseWebGpu(): Promise<boolean> {
  const mobile =
    /iP(?:hone|ad|od)|Android|Mobile/i.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const gpu = (navigator as Navigator & { gpu?: { requestAdapter: (o?: object) => Promise<unknown> } }).gpu;
  if (mobile || !gpu) return false;
  try {
    return (await gpu.requestAdapter({ powerPreference: "high-performance" })) != null;
  } catch {
    return false;
  }
}

async function init(modelBaseUrl: string | null) {
  const onProgress = ({ loaded, total }: { loaded: number; total: number }) =>
    post({ type: "progress", loadedBytes: loaded, totalBytes: total });
  const backend = (await canUseWebGpu()) ? "webgpu" : "wasm";
  tts = await SoproTTS.create({
    modelBaseUrl,
    onProgress,
    backend,
    // Phones and tablets ignore this: Sopro brings its own WASM runtime for them.
    wasmPaths: { wasm: backend === "webgpu" ? ortWebGpuWasmUrl : ortWasmUrl },
  });
  // Downloads every model file now, so loading and the first synthesis are measured separately.
  await tts.preload(onProgress);
  post({ type: "ready", backend: tts.backend });
}

async function prepareReference(pcm: Float32Array, sampleRate: number) {
  if (!tts) throw new Error("Sopro is not loaded.");
  const started = performance.now();
  reference = await tts.prepareReference(pcm, { sampleRate });
  await tts.prepareStreaming(reference);
  post({ type: "referenceReady", prepareMs: performance.now() - started });
}

async function synthesize(id: number, text: string, language: string) {
  if (!tts || !reference) throw new Error("Sopro has no reference voice yet.");
  const started = performance.now();
  let samples = 0;
  for await (const audio of tts.stream(text, reference, { language })) {
    samples += audio.length;
    post({ type: "audio", id, samples: audio, sampleRate: tts.sampleRate }, [audio.buffer]);
  }
  post({ type: "done", id, synthMs: performance.now() - started, audioSeconds: samples / tts.sampleRate });
}

self.onmessage = (event: MessageEvent<SoproInbound>) => {
  const message = event.data;
  const run = (id: number | null, task: () => Promise<void>) => {
    chain = chain.then(task).catch((error) => post({ type: "error", id, message: errorText(error) }));
  };
  switch (message.type) {
    case "init":
      run(null, () => init(message.modelBaseUrl));
      break;
    case "reference":
      run(null, () => prepareReference(message.pcm, message.sampleRate));
      break;
    case "synthesize":
      run(message.id, () => synthesize(message.id, message.text, message.language));
      break;
  }
};
