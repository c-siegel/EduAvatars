// Shared microphone-level math for the voice-input pipeline (pages/PublicChat/index.tsx,
// lib/browserStt.ts): computing RMS (root mean square, the standard measure of a signal's
// average loudness) from raw samples, and turning a short ambient-noise measurement into a
// "count this as silence" threshold — instead of one hardcoded number. A fixed threshold can't
// work across real devices: mic sensitivity alone can differ by 10-20dB between a cheap
// classroom Chromebook and a MacBook, and getUserMedia's autoGainControl keeps adjusting gain
// through a session, so the same physical loudness doesn't map to the same RMS value twice.

// Used only as a starting value before a session's own calibration finishes (see
// calibrateSilenceThreshold) — the first RECORDING_SEGMENT_MIN_MS of any recording can't trigger
// a cut anyway (pages/PublicChat/index.tsx), so it's never actually load-bearing.
export const FALLBACK_SILENCE_RMS_THRESHOLD = 0.015;

// How far above the measured noise floor a level must be to count as speech, and the hard
// bounds on the resulting threshold — a bad calibration measurement (near-total silence, or a
// stray noise/early speech onset during the calibration window) must not make the threshold so
// low that any tiny sound looks like speech, or so high that real speech looks like silence.
// Starting points, not verified against real classroom hardware — see CLAUDE.md's guidance on
// this feature for how to validate and retune them from real device/room measurements.
const NOISE_FLOOR_MULTIPLIER = 2.5;
const MIN_SILENCE_RMS_THRESHOLD = 0.003;
const MAX_SILENCE_RMS_THRESHOLD = 0.06;

/** Root mean square of a batch of normalized (-1..1) audio samples. */
export function rms(samples: Float32Array): number {
  let sumSquares = 0;
  for (const sample of samples) sumSquares += sample * sample;
  return Math.sqrt(sumSquares / samples.length);
}

/** Derives a per-session silence threshold from RMS samples collected during a brief ambient-noise
 * calibration window (see watchForSpeechPauses). Uses the 90th percentile, not the mean/max, so
 * one stray loud moment (a cough, a chair scraping) during that window can't skew the estimate —
 * and falls back to FALLBACK_SILENCE_RMS_THRESHOLD if calibration collected nothing at all. */
export function calibrateSilenceThreshold(rmsSamples: number[]): number {
  if (rmsSamples.length === 0) return FALLBACK_SILENCE_RMS_THRESHOLD;
  const sorted = [...rmsSamples].sort((a, b) => a - b);
  const noiseFloor = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.9))];
  const scaled = noiseFloor * NOISE_FLOOR_MULTIPLIER;
  return Math.min(Math.max(scaled, MIN_SILENCE_RMS_THRESHOLD), MAX_SILENCE_RMS_THRESHOLD);
}
