// Device test page for on-device speech recognition (/stt-test): loads the same model the public
// chat uses and shows how fast it runs on this device — load time, time to the first live text,
// re-decode times, and the delay between stopping and the final text. Used for the device runbook
// in docs/stt-device-test.md; not linked from anywhere in the app.

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { PublicLayout } from "@/layouts/PublicLayout";
import { ParakeetSttEngine, type DecodeStats, type LoadProgress, type StreamingSession } from "@/lib/parakeetStt";
import styles from "./SttTest.module.css";

const DEFAULT_MODEL_URL = "/models/parakeet-redux/v1/";

interface RunStats {
  firstPartialMs: number | null;
  decodes: DecodeStats[];
  finalizeMs: number | null;
}

const emptyRun = (): RunStats => ({ firstPartialMs: null, decodes: [], finalizeMs: null });
const ms = (n: number | null | undefined) => (n == null ? "–" : `${Math.round(n)} ms`);

/** Measures on-device speech recognition speed on the current device. */
export function SttTestPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const modelUrl = searchParams.get("model") ?? DEFAULT_MODEL_URL;

  const engineRef = useRef<ParakeetSttEngine | null>(null);
  const sessionRef = useRef<StreamingSession | null>(null);
  const startedAtRef = useRef(0);
  const stopFileRef = useRef<(() => void) | null>(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<LoadProgress | null>(null);
  const [loadSeconds, setLoadSeconds] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [partial, setPartial] = useState("");
  const [finalText, setFinalText] = useState("");
  const [run, setRun] = useState<RunStats>(emptyRun);

  useEffect(() => {
    const engine = new ParakeetSttEngine(modelUrl);
    engineRef.current = engine;
    const started = performance.now();
    setStatus("loading");
    engine.onStats = (stats) => setRun((prev) => ({ ...prev, decodes: [...prev.decodes, stats] }));
    void engine.ensureReady(setProgress).then(() => {
      setStatus(engine.status);
      setError(engine.errorMessage);
      if (engine.status === "ready") setLoadSeconds((performance.now() - started) / 1000);
    });
    return () => engine.dispose();
  }, [modelUrl]);

  function onPartial(text: string) {
    setPartial(text);
    setRun((prev) =>
      prev.firstPartialMs == null && text ? { ...prev, firstPartialMs: performance.now() - startedAtRef.current } : prev,
    );
  }

  async function start(stream: MediaStream, audioContext: AudioContext) {
    setPartial("");
    setFinalText("");
    setRun(emptyRun());
    startedAtRef.current = performance.now();
    sessionRef.current = await engineRef.current!.startStreaming(stream, audioContext, onPartial);
    setRunning(true);
  }

  async function startMic() {
    const audioContext = new AudioContext();
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    stopFileRef.current = () => stream.getTracks().forEach((track) => track.stop());
    await start(stream, audioContext);
  }

  // Plays a recorded clip through the speakers and the recognizer at real-time speed, so a device
  // can be measured with the same known audio every time.
  async function startFile(file: File) {
    const audioContext = new AudioContext();
    const playback = new AudioContext();
    const element = new Audio(URL.createObjectURL(file));
    const source = playback.createMediaElementSource(element);
    const destination = playback.createMediaStreamDestination();
    source.connect(destination);
    source.connect(playback.destination);
    stopFileRef.current = () => {
      element.pause();
      void playback.close();
    };
    element.onended = () => void stop();
    await start(destination.stream, audioContext);
    await element.play();
  }

  async function stop() {
    const session = sessionRef.current;
    if (!session) return;
    sessionRef.current = null;
    const stoppedAt = performance.now();
    try {
      const result = await session.stop();
      setFinalText(result.text);
      setRun((prev) => ({ ...prev, finalizeMs: performance.now() - stoppedAt }));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      stopFileRef.current?.();
      stopFileRef.current = null;
      setRunning(false);
    }
  }

  const decodeTimes = run.decodes.map((d) => d.decodeMs);
  const last = run.decodes[run.decodes.length - 1];
  const average = decodeTimes.length ? decodeTimes.reduce((a, b) => a + b, 0) / decodeTimes.length : null;
  const max = decodeTimes.length ? Math.max(...decodeTimes) : null;
  const percent = progress && progress.totalBytes ? Math.floor((progress.loadedBytes / progress.totalBytes) * 100) : 0;

  const report = [
    `userAgent: ${navigator.userAgent}`,
    `modelReadySeconds: ${loadSeconds?.toFixed(1) ?? "-"}`,
    `firstPartialMs: ${run.firstPartialMs != null ? Math.round(run.firstPartialMs) : "-"}`,
    `decodeMs last/avg/max: ${ms(last?.decodeMs)} / ${ms(average)} / ${ms(max)} (${run.decodes.length} decodes)`,
    `lastDecodedAudioSeconds: ${last ? last.audioSeconds.toFixed(1) : "-"}`,
    `finalizeMs: ${run.finalizeMs != null ? Math.round(run.finalizeMs) : "-"}`,
    `final: ${finalText}`,
  ].join("\n");

  return (
    <PublicLayout>
      <div className={styles.container}>
        <h1>{t("sttTest.title")}</h1>
        <p>{t("sttTest.intro")}</p>
        <p className={styles.mono}>
          {t("sttTest.status", { status })}
          {status === "loading" && ` — ${percent}%`}
        </p>
        {loadSeconds != null && <p>{t("sttTest.loadTime", { seconds: loadSeconds.toFixed(1) })}</p>}
        {error && <Callout variant="danger">{t("sttTest.error", { message: error })}</Callout>}

        {status === "ready" && (
          <div className={styles.controls}>
            {running ? (
              <Button variant="danger" onClick={() => void stop()}>
                {t("sttTest.stop")}
              </Button>
            ) : (
              <>
                <Button variant="accent" onClick={() => void startMic()}>
                  {t("sttTest.startMic")}
                </Button>
                <label className={styles.fileLabel}>
                  {t("sttTest.playFile")}
                  <input
                    type="file"
                    accept="audio/*"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = "";
                      if (file) void startFile(file);
                    }}
                  />
                </label>
              </>
            )}
          </div>
        )}

        <h2>{t("sttTest.partial")}</h2>
        <p className={styles.transcript}>{partial || "…"}</p>
        <h2>{t("sttTest.final")}</h2>
        <p className={styles.transcript}>{finalText || "…"}</p>

        <dl className={styles.stats}>
          <dt>{t("sttTest.firstPartial")}</dt>
          <dd>{ms(run.firstPartialMs)}</dd>
          <dt>{t("sttTest.decode")}</dt>
          <dd>
            {ms(last?.decodeMs)} / {ms(average)} / {ms(max)}
          </dd>
          <dt>{t("sttTest.decodedAudio")}</dt>
          <dd>{last ? `${last.audioSeconds.toFixed(1)} s` : "–"}</dd>
          <dt>{t("sttTest.finalize")}</dt>
          <dd>{ms(run.finalizeMs)}</dd>
        </dl>
        <Button onClick={() => void navigator.clipboard.writeText(report)}>{t("sttTest.copy")}</Button>
      </div>
    </PublicLayout>
  );
}
