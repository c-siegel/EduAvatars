import { forwardRef, useEffect, useImperativeHandle, useRef, useState, type ReactNode } from "react";
import type { TalkingHead } from "@met4citizen/talkinghead";
import { Loader2 } from "lucide-react";
import { attachHeadAudio } from "./headAudioIntegration";
import styles from "./TalkingHeadAvatar.module.css";

// Selbst gehostet unter public/avatars/ (siehe ATTRIBUTION.md dort) statt live von GitHub
// nachgeladen — aus demselben Datenschutzgrund wie bei den Fonts (kein Drittanbieter-Request
// bei jedem Seitenaufruf). Alternative im selben Repo: david.glb.
const DEFAULT_AVATAR_URL = "/avatars/julia.glb";

type Status = "loading" | "ready" | "error" | "skipped";

// How long the "thinking" gaze cue holds before it self-clears back to idle (see startThinking).
// Not a measured value — a reasonable guess for a typical LLM+TTS round trip; if the real reply
// usually takes longer, the avatar just reads as idle again for the remainder of the wait.
const THINKING_LOOK_MS = 4000;

// TalkingHead throttles its own internal render loop to this rate (its "modelFPS" option,
// currently at its own default) — passed explicitly here so a future change to that library
// default can't silently desync the dropped-frame math in startFpsTracking/stopFpsTracking below.
const MODEL_FPS = 30;
const TARGET_FRAME_INTERVAL_MS = 1000 / MODEL_FPS;

interface FpsTracker {
  running: boolean;
  startedAt: number;
  lastTickAt: number;
  sampleCount: number;
  droppedFrames: number;
}

export interface FpsTrackingResult {
  avgFps: number | null;
  droppedFrames: number;
  sampleCount: number;
}

export interface TalkingHeadAvatarHandle {
  /**
   * Decodes base64 MP3 audio (from services/tts_service.py, one chunk for a streamed reply, see
   * api/publicChat.ts::sendMessageStream) into a playable buffer, without starting playback —
   * split from speakBuffer() so callers can time/sequence playback themselves (wait out
   * audioBuffer.duration, then call stopSpeaking() — see pages/PublicChat/index.tsx).
   */
  decodeAudio: (audioBase64: string) => Promise<AudioBuffer>;
  /** Plays an already-decoded buffer from decodeAudio(). */
  speakBuffer: (audioBuffer: AudioBuffer) => void;
  /** Immediately stops any audio currently playing (mid-sentence included), clears the speech
   * queue, and resets the mouth to its idle shape. Used both when the student interrupts a reply,
   * and — just as important — right after a reply's last chunk naturally finishes: HeadAudio drives
   * the mouth from the live audio signal (see headAudioIntegration.ts), not from TalkingHead's own
   * keyframe timeline, so nothing else puts the mouth back to idle once that signal goes quiet.
   * Safe to call even when nothing is playing. See pages/PublicChat/index.tsx. */
  stopSpeaking: () => void;
  /**
   * Waits until TalkingHead has actually finished playing everything it has queued — not just
   * the caller's own duration estimate. speakAudio() inserts a short pause between consecutive
   * speech-queue items (see the vendored talkinghead.mjs), so chaining playback purely off each
   * chunk's own AudioBuffer.duration (see playStreamedChunk in pages/PublicChat/index.tsx) drifts
   * increasingly behind real playback the more chunks a reply has. Calling stopSpeaking() as soon
   * as that drifted timer runs out then cuts off whatever TalkingHead is still catching up on —
   * typically the tail of the last chunk. Resolves early if `signal` aborts.
   */
  waitUntilIdle: (signal?: AbortSignal) => Promise<void>;
  /**
   * Fetches an audio file (e.g. a project's pre-generated start-prompt audio, see
   * api/projects.ts::generateStartAudio) and plays it directly — skips the base64 round trip
   * decodeAudio() needs, since here the audio never has to travel through a JSON response first.
   * Resolves to whether the audio is actually audible (the AudioContext is "running"), not just
   * whether decoding/scheduling succeeded — starting an audio source never throws even while the
   * browser has the context suspended pending a user gesture, so a plain success/failure result
   * can't tell a caller apart from silent playback that never actually made a sound.
   */
  speakFromUrl: (url: string) => Promise<boolean>;
  /** Startet den "hört zu"-Blickkontakt-Modus der Bibliothek, gespeist vom Mikrofon-Stream. */
  startListening: (stream: MediaStream) => void;
  /** Beendet den Zuhör-Modus (z. B. wenn die Aufnahme gestoppt wird). */
  stopListening: () => void;
  /** Kurzer Blick-Cue für die Wartezeit zwischen Senden und Antwort ("überlegt gerade") — keine
   * native TalkingHead-Funktion, aus lookAt() synthetisiert (siehe THINKING_LOOK_MS). */
  startThinking: () => void;
  /** Kein Gegenstück nötig, da lookAt() sich selbst nach THINKING_LOOK_MS zurücksetzt — als
   * benannte Stelle im Aufrufcode trotzdem vorhanden, für den Fall dass das später ein echtes
   * Zurücksetzen braucht (z. B. bei einem Fehler kurz nach dem Senden). */
  stopThinking: () => void;
  /** Starts (or restarts) one FPS/dropped-frame measurement window — see stopFpsTracking. */
  startFpsTracking: () => void;
  /** Ends the current measurement window and returns its stats, or null if never started or the
   * avatar never actually rendered a real (non-throttled) frame during it (failed to load,
   * prefers-reduced-motion, or speechEnabled was false — head.opt.update is only wrapped when
   * speech is enabled, see the load() effect below). */
  stopFpsTracking: () => FpsTrackingResult | null;
}

interface TalkingHeadAvatarProps {
  /** Wird während des Ladens gezeigt, bei Fehlern, und wenn prefers-reduced-motion aktiv ist. */
  fallback: ReactNode;
  /** Für Konfigurator-Vorschau (1e) und öffentlichen Chat (1i) statt des Landingpage-Defaults. */
  avatarUrl?: string;
  /** Called once the avatar has actually finished loading (status "ready") — e.g. to trigger
   * autoplay of a project's spoken greeting, see pages/PublicChat/index.tsx. */
  onReady?: () => void;
  /**
   * Keeps the `fallback` covering the avatar even once it's loaded (status "ready") — default
   * true. Set to false while something the avatar is about to do (e.g. speaking a greeting)
   * hasn't started yet, so students see a static "poster frame" instead of the avatar idling in
   * the background behind a play button, like a paused video — see pages/PublicChat/index.tsx.
   */
  revealed?: boolean;
  /**
   * Aktiviert HeadAudio (echtzeit-audiobasiertes Lipsync, siehe headAudioIntegration.ts) für
   * echtes Sprechen. Weggelassen (Landingpage-Nutzung): kein AudioWorklet-/Modell-Ladeoverhead,
   * da dort nie gesprochen wird.
   */
  speechEnabled?: boolean;
  /**
   * Optionales Hintergrundbild — wird HIER (nicht vom Elternelement) gerendert, als Geschwister-Div
   * direkt neben dem Canvas, beide mit identischem `position:absolute;inset:0` im selben Elternteil.
   * Dadurch haben beide IMMER exakt dieselbe Box, unabhängig davon, welche Größe der Canvas intern
   * gerade hat — ein Größen-Mismatch zwischen "Avatar-Fenster" und "Hintergrund-Fenster" (siehe
   * vorherige, gescheiterte Versuche mit dem Hintergrund auf dem äußeren .avatarStage-Element) ist
   * so strukturell ausgeschlossen statt nur zufällig zu passen.
   */
  backgroundImageUrl?: string;
}

// 3D-Avatar-Rendering (met4citizen/TalkingHead). Auf der Landingpage rein idle (kein Sprechen);
// in 1e/1i mit speechEnabled für echtes Sprechen über HeadAudio (siehe headAudioIntegration.ts).
export const TalkingHeadAvatar = forwardRef<TalkingHeadAvatarHandle, TalkingHeadAvatarProps>(
  function TalkingHeadAvatar(
    { fallback, avatarUrl = DEFAULT_AVATAR_URL, onReady, revealed = true, speechEnabled = false, backgroundImageUrl },
    ref,
  ) {
    const containerRef = useRef<HTMLDivElement>(null);
    const headRef = useRef<TalkingHead | null>(null);
    const [status, setStatus] = useState<Status>("loading");
    // Plain ref, not React state — ticked at ~MODEL_FPS Hz from inside TalkingHead's own render
    // loop, so must never trigger a re-render.
    const fpsTrackerRef = useRef<FpsTracker | null>(null);

    useImperativeHandle(
      ref,
      () => ({
        async decodeAudio(audioBase64: string) {
          const head = headRef.current;
          if (!head) throw new Error("Avatar noch nicht geladen.");
          const bytes = Uint8Array.from(atob(audioBase64), (c) => c.charCodeAt(0));
          return head.audioCtx.decodeAudioData(bytes.buffer);
        },
        speakBuffer(audioBuffer: AudioBuffer) {
          // Kein words/wtimes/wdurations nötig — HeadAudio treibt die Mundbewegung live aus
          // dem hier abgespielten Audiosignal, unabhängig von diesem Aufruf.
          headRef.current?.speakAudio({ audio: audioBuffer });
        },
        stopSpeaking() {
          headRef.current?.stopSpeaking();
        },
        async waitUntilIdle(signal?: AbortSignal) {
          const head = headRef.current;
          if (!head) return;
          const POLL_INTERVAL_MS = 50;
          while (head.isSpeaking && !signal?.aborted) {
            await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
          }
        },
        async speakFromUrl(url: string) {
          const head = headRef.current;
          if (!head) return false;
          const response = await fetch(url);
          // Without this, a stale URL (DB says the audio exists, the file was since removed) hits
          // decodeAudioData with an error page's body instead of audio — it still throws, just
          // with a cryptic browser-internal message instead of one that says what actually failed.
          if (!response.ok) {
            throw new Error(`speakFromUrl: ${url} responded with ${response.status}`);
          }
          const arrayBuffer = await response.arrayBuffer();
          const audioBuffer = await head.audioCtx.decodeAudioData(arrayBuffer);
          // Resume BEFORE scheduling playback, not after: a suspended AudioContext still lets a
          // source start without error, it just stays silent — so scheduling first and checking
          // second used to leave that silent source sitting in the graph whenever the resume below
          // failed (e.g. this call's own autoplay attempt, before any user gesture happened). A
          // later, real click would then schedule a SECOND source on top of the still-pending first
          // one, and once that click's gesture finally unblocked the context, both played at once —
          // audibly doubling the greeting. Checking/resuming first means a blocked attempt never
          // schedules anything to begin with. Only a call stack that actually originates from a user
          // gesture (e.g. a click handler) can successfully resume it; an unprompted autoplay
          // attempt's resume() call here simply no-ops and leaves the context suspended, which is
          // exactly the signal the caller needs.
          if (head.audioCtx.state === "suspended") {
            try {
              await head.audioCtx.resume();
            } catch {
              // Browser refused — treated the same as staying suspended, see the check below.
            }
          }
          if (head.audioCtx.state !== "running") return false;
          // A second concurrent call can still reach this point — the autoplay attempt on load
          // racing a real click on the overlay play button before the first call's own fetch/
          // decode/resume round trip has resolved (see playGreeting in pages/PublicChat/index.tsx,
          // which no longer guards against this itself). The moment either call's speakBuffer()
          // below runs, TalkingHead's isSpeaking flips true synchronously (see startSpeaking() in
          // the vendored talkinghead.mjs) — so whichever call gets here second sees it and skips,
          // instead of scheduling the same greeting audio a second time and audibly doubling it.
          if (!head.isSpeaking) {
            this.speakBuffer(audioBuffer);
          }
          return true;
        },
        startListening(stream: MediaStream) {
          const head = headRef.current;
          if (!head) return;
          // Selbe Quelle wie der MediaRecorder für die Aufnahme — kein zweiter getUserMedia-Aufruf,
          // und derselbe AudioContext, den TalkingHead ohnehin schon für die Sprachausgabe hält.
          const source = head.audioCtx.createMediaStreamSource(stream);
          const analyzer = head.audioCtx.createAnalyser();
          source.connect(analyzer);
          head.startListening(analyzer);
        },
        stopListening() {
          headRef.current?.stopListening();
        },
        startThinking() {
          // x/y = null: Blick geht zum Kamera-Augenpunkt statt zu festen Bildschirmkoordinaten —
          // braucht keine Viewport-Berechnung und passt zum ohnehin schon stärkeren Blickkontakt
          // der Bibliothek bei isSpeaking/isListening.
          headRef.current?.lookAt(null, null, THINKING_LOOK_MS);
        },
        stopThinking() {
          // Kein Aufruf nötig — siehe Kommentar am Interface oben.
        },
        startFpsTracking() {
          const now = performance.now();
          fpsTrackerRef.current = { running: true, startedAt: now, lastTickAt: now, sampleCount: 0, droppedFrames: 0 };
        },
        stopFpsTracking() {
          const tracker = fpsTrackerRef.current;
          fpsTrackerRef.current = null;
          if (!tracker || tracker.sampleCount === 0) return null;
          const elapsedMs = tracker.lastTickAt - tracker.startedAt;
          return {
            avgFps: elapsedMs > 0 ? (tracker.sampleCount / elapsedMs) * 1000 : null,
            droppedFrames: tracker.droppedFrames,
            sampleCount: tracker.sampleCount,
          };
        },
      }),
      [],
    );

    useEffect(() => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        setStatus("skipped");
        return;
      }

      let cancelled = false;
      let head: TalkingHead | undefined;

      async function load() {
        try {
          const { TalkingHead: TalkingHeadClass } = await import("@met4citizen/talkinghead");
          if (cancelled || !containerRef.current) return;

          head = new TalkingHeadClass(containerRef.current, {
            cameraView: "upper",
            cameraRotateEnable: false,
            cameraPanEnable: false,
            cameraZoomEnable: false,
            // "upper" zielt standardmäßig auf 2/3 der Körperhöhe (Brust) — das lässt in einem eher
            // breiten/kurzen Rahmen (wie hier) oben und unten sichtbaren Leerraum. cameraY schiebt
            // den Zielpunkt der Kamera nach unten (0 = Standard, größer = tiefer/mehr Oberkörper
            // und weniger Kopf-/Hintergrundraum oben sichtbar) — steuert die tatsächliche 3D-Kamera,
            // nicht nur einen nachträglichen Bildausschnitt (das war der vorherige, gescheiterte
            // CSS-transform-Ansatz auf .canvasHost — der konnte am eigentlichen Rahmenverhältnis
            // nichts ändern, siehe TalkingHeadAvatar.module.css).
            cameraY: 0,
            // Lipsync kommt entweder gar nicht (Landingpage, idle) oder über HeadAudio direkt aus
            // dem Audiosignal (siehe speechEnabled unten) — TalkingHeads eigener text-basierter
            // Lipsync-Pfad (lipsyncModules) wird nie gebraucht, da speakText() nie aufgerufen wird.
            lipsyncModules: [],
            modelFPS: MODEL_FPS,
          });
          await head.showAvatar({ url: avatarUrl, body: "F" });
          if (cancelled) return;
          headRef.current = head;
          if (speechEnabled) {
            try {
              await attachHeadAudio(head);
            } catch (error) {
              console.error("HeadAudio-Lipsync nicht verfügbar — Avatar läuft ohne Lippenbewegung.", error);
            }
            // Composes over (never replaces) the lip-sync update attachHeadAudio just installed —
            // lip-sync must keep running every tick regardless of our own FPS bookkeeping. Uses
            // only our own performance.now() deltas between calls, not the library's `dt`
            // argument, whose exact semantics aren't part of its documented/stable contract.
            // Runs even if attachHeadAudio above failed: head.opt.update is then simply undefined
            // (hence the optional call below), and the FPS measurement keeps working either way.
            const lipSyncUpdate = head.opt.update;
            head.opt.update = (dt: number) => {
              lipSyncUpdate?.(dt);
              const tracker = fpsTrackerRef.current;
              if (!tracker?.running) return;
              const now = performance.now();
              const delta = now - tracker.lastTickAt;
              tracker.lastTickAt = now;
              tracker.sampleCount += 1;
              tracker.droppedFrames += Math.max(0, Math.round(delta / TARGET_FRAME_INTERVAL_MS) - 1);
            };
          }
          if (!cancelled) {
            setStatus("ready");
            onReady?.();
          }
        } catch (error) {
          console.error("TalkingHead-Avatar konnte nicht geladen werden.", error);
          if (!cancelled) {
            setStatus("error");
          }
        }
      }

      load();

      return () => {
        cancelled = true;
        headRef.current = null;
        // stop() alone only pauses the render loop and suspends audioCtx — it leaves the WebGL
        // context and Three.js renderer alive. This component remounts a fresh TalkingHead on every
        // visit to any of its four call sites (Landing, Configurator Step1/Step4Preview,
        // PublicChat), so within one SPA session (no full page reload between them) those contexts
        // pile up — and browsers cap how many WebGL contexts a page may hold at once, Safari/iOS
        // notably tighter than desktop. Past that cap, a later new TalkingHead's own context
        // creation silently fails, which looks exactly like "the avatar doesn't load" — until a
        // hard refresh releases every context at once and the cap resets. dispose() actually
        // releases the WebGL context (WEBGL_lose_context) instead of just leaving it idle.
        head?.dispose();
      };
      // onReady absichtlich nicht in den Deps: eine neue Inline-Funktion bei jedem Render des
      // Elternteils darf keinen Avatar-Reload auslösen (siehe avatarUrl/speechEnabled oben, die
      // tatsächlichen Trigger).
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [avatarUrl, speechEnabled]);

    return (
      <div className={styles.stage}>
        <div
          className={styles.backdrop}
          style={backgroundImageUrl ? { backgroundImage: `url(${backgroundImageUrl})` } : undefined}
        />
        <div ref={containerRef} className={styles.canvasHost} />
        <div
          className={`${styles.fallback} ${status === "ready" && revealed ? styles.fallbackHidden : ""}`}
          aria-hidden={status === "ready" && revealed}
        >
          {status === "loading" ? <Loader2 size={32} className={styles.spinIcon} /> : fallback}
        </div>
      </div>
    );
  },
);
