import { forwardRef, useEffect, useImperativeHandle, useRef, useState, type ReactNode } from "react";
import type { TalkingHead } from "@met4citizen/talkinghead";
import { attachHeadAudio } from "./headAudioIntegration";
import styles from "./TalkingHeadAvatar.module.css";

// Selbst gehostet unter public/avatars/ (siehe ATTRIBUTION.md dort) statt live von GitHub
// nachgeladen — aus demselben Datenschutzgrund wie bei den Fonts (kein Drittanbieter-Request
// bei jedem Seitenaufruf). Alternative im selben Repo: david.glb.
const DEFAULT_AVATAR_URL = "/avatars/julia.glb";

type Status = "loading" | "ready" | "error" | "skipped";

export interface TalkingHeadAvatarHandle {
  /** Spielt vom Backend synthetisiertes Sprachaudio ab (siehe services/tts_service.py). */
  speak: (audioBase64: string) => Promise<void>;
}

interface TalkingHeadAvatarProps {
  /** Wird während des Ladens gezeigt, bei Fehlern, und wenn prefers-reduced-motion aktiv ist. */
  fallback: ReactNode;
  /** Für Konfigurator-Vorschau (1e) und öffentlichen Chat (1i) statt des Landingpage-Defaults. */
  avatarUrl?: string;
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
    { fallback, avatarUrl = DEFAULT_AVATAR_URL, speechEnabled = false, backgroundImageUrl },
    ref,
  ) {
    const containerRef = useRef<HTMLDivElement>(null);
    const headRef = useRef<TalkingHead | null>(null);
    const [status, setStatus] = useState<Status>("loading");

    useImperativeHandle(
      ref,
      () => ({
        async speak(audioBase64: string) {
          const head = headRef.current;
          if (!head) return;
          const bytes = Uint8Array.from(atob(audioBase64), (c) => c.charCodeAt(0));
          const audioBuffer = await head.audioCtx.decodeAudioData(bytes.buffer);
          // Kein words/wtimes/wdurations nötig — HeadAudio treibt die Mundbewegung live aus
          // dem hier abgespielten Audiosignal, unabhängig von diesem Aufruf.
          head.speakAudio({ audio: audioBuffer });
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
          });
          await head.showAvatar({ url: avatarUrl, body: "F" });
          if (cancelled) return;
          headRef.current = head;
          if (speechEnabled) {
            await attachHeadAudio(head);
          }
          if (!cancelled) setStatus("ready");
        } catch (error) {
          console.error("TalkingHead-Avatar konnte nicht geladen werden.", error);
          if (!cancelled) setStatus("error");
        }
      }

      load();

      return () => {
        cancelled = true;
        headRef.current = null;
        // TalkingHead hat kein dokumentiertes dispose() — stop() beendet zumindest die
        // Animationsschleife; der Canvas wird mit dem Container beim Unmount entfernt.
        head?.stop();
      };
    }, [avatarUrl, speechEnabled]);

    return (
      <div className={styles.stage}>
        <div
          className={styles.backdrop}
          style={backgroundImageUrl ? { backgroundImage: `url(${backgroundImageUrl})` } : undefined}
        />
        <div ref={containerRef} className={styles.canvasHost} />
        <div className={`${styles.fallback} ${status === "ready" ? styles.fallbackHidden : ""}`} aria-hidden={status === "ready"}>
          {fallback}
        </div>
      </div>
    );
  },
);
