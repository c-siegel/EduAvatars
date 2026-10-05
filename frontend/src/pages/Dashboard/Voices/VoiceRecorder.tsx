// Records a voice clip with the microphone, right on the voice library page — an alternative to
// uploading a file. Hands the finished recording to its parent; uploading is the parent's job.

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Mic, Square } from "lucide-react";
import { Button } from "@/components/Button";
import styles from "./Voices.module.css";

// Same limit the backend enforces (MAX_SECONDS in features/media/voice_audio.py) — stopping
// here means a student-length rambling recording never fails only after uploading.
const MAX_RECORDING_SECONDS = 30;

// MediaRecorder picks its own container (WebM in Chrome/Firefox, MP4 in Safari); the backend
// recognizes all of them by content, the extension just keeps the filename honest.
function extensionFor(mimeType: string): string {
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("ogg")) return "ogg";
  return "webm";
}

export interface Recording {
  blob: Blob;
  filename: string;
}

interface VoiceRecorderProps {
  onRecorded: (recording: Recording | null) => void;
}

/** Microphone recorder with a running timer and an automatic stop at MAX_RECORDING_SECONDS. */
export function VoiceRecorder({ onRecorded }: VoiceRecorderProps) {
  const { t } = useTranslation();
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Releases the microphone and the last recording's object URL when the recorder goes away.
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      recorderRef.current?.stream.getTracks().forEach((track) => track.stop());
    };
  }, []);
  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  async function start() {
    setErrorKey(null);
    let stream: MediaStream;
    try {
      // No noise suppression: it changes the timbre of a voice, and the clone should sound like
      // the actual person. A quiet room is the better fix (see the tips next to the recorder).
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: false, autoGainControl: true },
      });
    } catch (error) {
      const denied = error instanceof DOMException && error.name === "NotAllowedError";
      setErrorKey(denied ? "publicChat.micPermissionDenied" : "publicChat.micUnavailable");
      return;
    }
    const recorder = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      const blob = new Blob(chunks, { type: recorder.mimeType });
      setPreviewUrl(URL.createObjectURL(blob));
      onRecorded({ blob, filename: `recording.${extensionFor(recorder.mimeType)}` });
    };
    recorderRef.current = recorder;
    recorder.start();
    onRecorded(null);
    setPreviewUrl(null);
    setSeconds(0);
    setRecording(true);
    const startedAt = Date.now();
    timerRef.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setSeconds(elapsed);
      if (elapsed >= MAX_RECORDING_SECONDS) stop();
    }, 250);
  }

  function stop() {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    setRecording(false);
  }

  return (
    <div className={styles.recorder}>
      <div className={styles.recorderRow}>
        {recording ? (
          <Button variant="danger" onClick={stop}>
            <Square size={14} fill="currentColor" /> {t("voices.recordStop")}
          </Button>
        ) : (
          <Button onClick={() => void start()}>
            <Mic size={14} /> {previewUrl ? t("voices.recordAgain") : t("voices.recordStart")}
          </Button>
        )}
        {recording && (
          <span className={styles.timer} aria-live="polite">
            {t("voices.recordTimer", { seconds, max: MAX_RECORDING_SECONDS })}
          </span>
        )}
      </div>
      {previewUrl && !recording && <audio controls src={previewUrl} className={styles.audio} />}
      {errorKey && <p className={styles.error}>{t(errorKey)}</p>}
    </div>
  );
}
