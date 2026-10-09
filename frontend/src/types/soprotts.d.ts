// @soprotts/onnx-web ships no TypeScript types (plain .js) — minimal ambient declaration covering
// only what workers/soproWorker.ts uses.
declare module "@soprotts/onnx-web" {
  export class SoproTTS {
    static create(options?: {
      modelBaseUrl?: string | null;
      onProgress?: (progress: { loaded: number; total: number }) => void;
      backend?: "auto" | "webgpu" | "wasm";
      wasmPaths?: { wasm?: string; mjs?: string };
    }): Promise<SoproTTS>;
    /** The model profile in use, e.g. "webgpu-fp16" or "wasm-uint8". */
    readonly backend: string;
    readonly sampleRate: number;
    preload(onProgress?: (progress: { loaded: number; total: number }) => void): Promise<void>;
    prepareReference(audio: Float32Array | ArrayBuffer | Blob, options?: { sampleRate?: number }): Promise<unknown>;
    prepareStreaming(reference: unknown): Promise<void>;
    stream(text: string, reference: unknown, options?: { language?: string }): AsyncIterable<Float32Array<ArrayBuffer>>;
    dispose(): Promise<void>;
  }
}
