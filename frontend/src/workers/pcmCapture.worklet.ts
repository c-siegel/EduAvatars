// AudioWorklet that hands raw microphone samples to the main thread in ~100 ms batches, for live
// speech recognition (see lib/parakeetStt.ts). Runs on the browser's audio thread, which calls
// process() with only 128 samples at a time — far too small to post one message each.

// The AudioWorklet global scope isn't part of TypeScript's DOM types.
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
}
declare function registerProcessor(name: string, processor: typeof AudioWorkletProcessor): void;
declare const sampleRate: number;

class PcmCaptureProcessor extends AudioWorkletProcessor {
  private buffer = new Float32Array(Math.round(sampleRate / 10));
  private filled = 0;

  process(inputs: Float32Array[][]): boolean {
    const channel = inputs[0]?.[0]; // mono is enough for speech; channel 0 is the mic
    if (channel) {
      let read = 0;
      while (read < channel.length) {
        const n = Math.min(channel.length - read, this.buffer.length - this.filled);
        this.buffer.set(channel.subarray(read, read + n), this.filled);
        this.filled += n;
        read += n;
        if (this.filled === this.buffer.length) this.flush();
      }
    }
    return true;
  }

  private flush() {
    const batch = this.buffer.slice(0, this.filled);
    this.port.postMessage(batch, [batch.buffer]);
    this.filled = 0;
  }

  constructor() {
    super();
    // Sent on stop, so the last partial batch isn't lost.
    this.port.onmessage = () => {
      if (this.filled > 0) this.flush();
      this.port.postMessage("flushed");
    };
  }
}

registerProcessor("pcm-capture", PcmCaptureProcessor);

export {};
