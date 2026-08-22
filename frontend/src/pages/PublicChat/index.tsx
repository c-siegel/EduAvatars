import { useEffect, useRef, useState, type FormEvent } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { HelpCircle, Loader2, Mic, MessageCircle, Send, Square, Volume2, VolumeX, LogOut, Lock, X } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { ChatBubble, TypingBubble } from "@/components/ChatBubble";
import { Input } from "@/components/Input";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { SurveyEmbed } from "@/components/SurveyEmbed";
import { TalkingHeadAvatar, type TalkingHeadAvatarHandle } from "@/components/TalkingHeadAvatar";
import { PublicChatLayout } from "@/layouts/PublicChatLayout";
import { publicChatApi } from "@/api/publicChat";
import { ApiError, errorMessage } from "@/api/client";
import { setUnlockToken } from "@/lib/chatUnlockStorage";
import { toAbsoluteAvatarUrl } from "@/lib/avatarUrl";
import type { ChatMessage } from "@/types/chat";
import styles from "./PublicChat.module.css";

type Stage = "locked" | "before-survey" | "chat" | "after-survey" | "done";

// micStopAt: client timestamp (performance.now()) when the mic-stop button was clicked.
// sttMs: backend-only whisper duration, from the /transcribe response.
interface SendLatency {
  micStopAt: number;
  sttMs: number | null;
}

// SendLatency plus the moment sendMessage() actually fired the /message request — added there
// since that's the only place that knows it.
interface MutationLatency extends SendLatency {
  sendStartAt: number;
}

interface SendMessageResult {
  llmMs: number | null;
  ttsMs: number | null;
}

const round = (n: number) => Math.round(n);

// Logs a spoken-message-to-audible-reply latency breakdown for manual testing (?latencyTest=1,
// see PublicChatPage). All durations come from a single clock per side (client performance.now()
// vs. backend time.perf_counter()) — no cross-machine clock sync is needed since none of these
// numbers are compared against each other, only summed/inspected independently.
function logLatency(latency: MutationLatency, res: SendMessageResult, replyReceivedAt: number, audioReadyAt: number) {
  console.log("[Latenz-Test] Sprechende → Audio hörbar", {
    totalMs: round(audioReadyAt - latency.micStopAt),
    sttRoundTripMs: round(latency.sendStartAt - latency.micStopAt),
    sttBackendMs: latency.sttMs != null ? round(latency.sttMs) : null,
    replyRoundTripMs: round(replyReceivedAt - latency.sendStartAt),
    llmBackendMs: res.llmMs != null ? round(res.llmMs) : null,
    ttsBackendMs: res.ttsMs != null ? round(res.ttsMs) : null,
    audioDecodeMs: round(audioReadyAt - replyReceivedAt),
  });
}

// Screen 1i — Öffentliche Schüler-Chat-Seite (mobile-first, kein Login). Gesprochene Nachrichten
// werden nach der Transkription automatisch gesendet (kein manueller "Senden"-Klick nötig).
export function PublicChatPage() {
  const { t } = useTranslation();
  const { projectSlug } = useParams<{ projectSlug: string }>();
  const slug = projectSlug!;
  const [searchParams] = useSearchParams();
  // Schaltet NUR das Latenz-Konsolen-Log unten (nicht das Auto-Senden selbst) frei — sonst bekäme
  // jede echte Besucherin bei jeder Sprachnachricht eine technische Zeitaufschlüsselung in ihre
  // Browser-Konsole, ohne dass sie danach gefragt hat. Siehe frontend/README.md ("Debugging").
  const latencyTestEnabled = searchParams.get("latencyTest") === "1";

  const queryClient = useQueryClient();
  const tutorQuery = useQuery({
    queryKey: ["public-chat", slug],
    queryFn: () => publicChatApi.loadTutor(slug),
    retry: false,
  });

  const [passwordInput, setPasswordInput] = useState("");
  const unlockMutation = useMutation({
    mutationFn: (password: string) => publicChatApi.unlock(slug, password),
    onSuccess: (res) => {
      setUnlockToken(slug, res.unlockToken);
      setPasswordInput("");
      // Refetches loadTutor with the now-stored token attached, which flips `unlocked` and
      // reveals the real stage instead of the lock screen.
      queryClient.invalidateQueries({ queryKey: ["public-chat", slug] });
    },
  });

  function handleUnlockSubmit(event: FormEvent) {
    event.preventDefault();
    if (!passwordInput.trim() || unlockMutation.isPending) return;
    unlockMutation.mutate(passwordInput);
  }

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [rateLimited, setRateLimited] = useState(false);
  // null = noch keine manuelle Stufen-Wahl getroffen; die tatsächliche Anfangsstufe hängt vom
  // geladenen Projekt ab (Vor-Umfrage konfiguriert?), siehe `stage` weiter unten.
  const [manualStage, setManualStage] = useState<Stage | null>(null);
  // null = noch nicht aus dem geladenen Projekt initialisiert (siehe useEffect unten); danach
  // steuert nur noch der eigene Klick der Besucherin, das Projekt-Default wirkt nur als Startwert.
  const [chatOpen, setChatOpen] = useState<boolean | null>(null);

  const avatarRef = useRef<TalkingHeadAvatarHandle>(null);
  const [ttsMuted, setTtsMuted] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const threadRef = useRef<HTMLDivElement>(null);
  // Überlebt die Kette toggleRecording -> recorder.onstop -> transcribeMutation, die über mehrere
  // async Hops läuft — nur so lässt sich der ursprüngliche "Sprechende"-Zeitpunkt bis zum
  // Latenz-Log durchreichen. { micStopAt } statt nur eine Zahl, damit spätere Felder ergänzbar sind.
  const latencyRef = useRef<{ micStopAt: number } | null>(null);

  const sendMutation = useMutation({
    mutationFn: ({ message, history }: { message: string; history: ChatMessage[]; latency?: MutationLatency }) =>
      publicChatApi.sendMessage(slug, message, history),
    onSuccess: async (res, variables) => {
      avatarRef.current?.stopThinking();
      const replyReceivedAt = performance.now();
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      let audioReadyAt = replyReceivedAt;
      if (res.audioBase64 && !ttsMuted) {
        // Ansonsten "fire and forget" — hier bewusst awaiten, um den Zeitpunkt zu bekommen, ab dem
        // die Wiedergabe tatsächlich läuft (decodeAudioData ist der einzige nennenswert asynchrone
        // Schritt danach, siehe TalkingHeadAvatar.tsx). Ändert nichts sichtbar: isPending kippt
        // schon beim Eintreffen der HTTP-Antwort um, unabhängig davon, ob onSuccess noch läuft.
        await avatarRef.current?.speak(res.audioBase64);
        audioReadyAt = performance.now();
      }
      if (latencyTestEnabled && variables.latency) {
        logLatency(variables.latency, res, replyReceivedAt, audioReadyAt);
      }
    },
    onError: (err) => {
      avatarRef.current?.stopThinking();
      if (err instanceof ApiError && err.status === 429) setRateLimited(true);
    },
  });

  // Funktion zum Transkribieren des Audioblobs via Whisper
  const transcribeMutation = useMutation({
    mutationFn: (audio: Blob) => publicChatApi.transcribe(slug, audio),
    onSuccess: (res) => {
      const micStopAt = latencyRef.current?.micStopAt;
      sendMessage(res.text, micStopAt != null ? { micStopAt, sttMs: res.sttMs } : undefined);
    },
  });

  // Funktion für Sprachaufnahme im Browser
  async function toggleRecording() {
    // Wird bereits aufgenommen -> Aufnahme stoppen
    if (isRecording) {
      // Frühestmöglicher, eindeutiger "Sprechende"-Zeitpunkt (Klick-Handler) fürs Latenz-Log —
      // Erfassen ist praktisch kostenlos, daher immer, nicht nur wenn latencyTestEnabled.
      latencyRef.current = { micStopAt: performance.now() };
      mediaRecorderRef.current?.stop();
      avatarRef.current?.stopListening();
      setIsRecording(false);
      return;
    }
    // Wird nicht aufgenommen, Erlaubnis fürs Gerät einholen, aufnehmen und transkribieren
    try {
      // Mikrofonanfrage mit warten auf Erlaubnis
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      avatarRef.current?.startListening(stream);
      // Mikrofon läuft und sammelt Audio-Chunks
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      recorder.ondataavailable = (event) => audioChunksRef.current.push(event.data);
      // Nach Aufnahmeende werden die Chunks in einen Blob verpackt und zum Transkribieren gegeben
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        transcribeMutation.mutate(audioBlob);
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch (error) {
      console.error("Mikrofonzugriff fehlgeschlagen.", error);
    }
  }

  function sendMessage(text: string, latency?: SendLatency) {
    const trimmed = text.trim();
    if (!trimmed || sendMutation.isPending) return;
    setRateLimited(false);
    avatarRef.current?.startThinking();
    // history = der bisherige Verlauf VOR dieser neuen Nachricht (messages ist an dieser Stelle noch
    // der alte State-Wert, das setMessages darunter wirkt erst beim nächsten Render).
    sendMutation.mutate({
      message: trimmed,
      history: messages,
      latency: latency ? { ...latency, sendStartAt: performance.now() } : undefined,
    });
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    sendMessage(input);
  }

  // Nach jeder neuen Nachricht (und beim Erscheinen/Verschwinden der Typing-Bubble) automatisch ans
  // Ende des Threads scrollen, statt den Nutzer selbst nachscrollen zu lassen.
  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sendMutation.isPending]);

  // Einmalige Übernahme des im Konfigurator gesetzten Anfangszustands, sobald das Projekt geladen
  // ist — danach bestimmt nur noch setChatOpen (Klick auf den Griff) den Zustand.
  useEffect(() => {
    if (tutorQuery.data && chatOpen === null) {
      setChatOpen(tutorQuery.data.chatDefaultOpen);
    }
  }, [tutorQuery.data, chatOpen]);

  if (tutorQuery.isLoading) {
    return (
      <PublicChatLayout>
        <div className={styles.centered}>{t("common.loading")}</div>
      </PublicChatLayout>
    );
  }

  if (tutorQuery.isError || !tutorQuery.data) {
    return (
      <PublicChatLayout>
        <div className={styles.centered}>{t("publicChat.unavailable")}</div>
      </PublicChatLayout>
    );
  }

  const tutor = tutorQuery.data;

  // Locked takes priority over every other stage — a manual survey/chat choice made before the
  // password was entered can't have happened yet anyway (see below: the header's End-chat button
  // and everything else past the lock screen only render once unlocked).
  // First stage depends on project: with survey it starts there, else withthe chat
  const stage: Stage =
    tutor.passwordProtected && !tutor.unlocked ? "locked" : (manualStage ?? (tutor.surveyBeforeUrl ? "before-survey" : "chat"));
  // Fallback nur für den allerersten Render, bevor der Initialisierungs-Effekt oben gelaufen ist.
  const isChatOpen = chatOpen ?? tutor.chatDefaultOpen;

  function endChat() {
    setManualStage(tutor.surveyAfterUrl ? "after-survey" : "done");
  }

  // Says what actually happens to the conversation, straight from the project's setting — the
  // page used to claim "chat isn't saved" unconditionally, which was untrue whenever the teacher
  // had recording switched on.
  const privacyNotice = tutor.saveConversations
    ? t("publicChat.privacySaved")
    : t("publicChat.privacyNotSaved");

  return (
    <PublicChatLayout showLanguageSwitcher={false}>
      <header className={styles.header}>
        <Avatar name={tutor.title} size="md" />
        <div className={styles.headerInfo}>
          <h1>{tutor.title}</h1>
          <p className={styles.headerStatus}>{t("publicChat.online")}</p>
        </div>
        <div className={styles.headerActions}>
          <LanguageSwitcher />
          {stage === "chat" && (
            <button
              type="button"
              className={styles.infoButton}
              onClick={endChat}
              disabled={sendMutation.isPending}
              aria-label={t("publicChat.endChat")}
              title={t("publicChat.endChat")}
            >
              <LogOut size={20} />
            </button>
          )}
          {/* Speech bubble instead of a title attribute: it has to be reachable by keyboard and on
              touch (where hover doesn't exist), so it opens on hover AND focus via CSS. */}
          <span className={styles.infoTip}>
            <button type="button" className={styles.infoButton} aria-label={t("publicChat.whichModel")}>
              <HelpCircle size={20} />
            </button>
            <span className={styles.infoTipBubble} role="tooltip">
              {tutor.llmModel
                ? t("publicChat.modelTooltip", { model: tutor.llmModel })
                : t("publicChat.modelTooltipUnknown")}
            </span>
          </span>
        </div>
      </header>

      {stage === "locked" && (
        <div className={styles.centered}>
          <form className={styles.lockedForm} onSubmit={handleUnlockSubmit}>
            <Lock size={28} />
            <p className={styles.lockedText}>{t("publicChat.locked.description")}</p>
            <Input
              label={t("publicChat.locked.passwordLabel")}
              type="password"
              autoComplete="off"
              required
              value={passwordInput}
              onChange={(e) => setPasswordInput(e.target.value)}
            />
            {unlockMutation.isError && (
              <Callout variant="danger">
                {errorMessage(unlockMutation.error, t("publicChat.locked.genericError"))}
              </Callout>
            )}
            <Button type="submit" variant="accent" fullWidth disabled={unlockMutation.isPending}>
              {t("publicChat.locked.submit")}
            </Button>
          </form>
        </div>
      )}

      {stage === "before-survey" && tutor.surveyBeforeUrl && (
        <SurveyEmbed
          url={tutor.surveyBeforeUrl}
          title={t("publicChat.surveyBeforeTitle")}
          continueLabel={t("publicChat.continueToChat")}
          onContinue={() => setManualStage("chat")}
          onSkip={() => setManualStage("chat")}
        />
      )}

      {stage === "chat" && (
        <div className={styles.body}>
          <div className={`${styles.avatarStage} ${!isChatOpen ? styles.avatarStageFull : ""}`}>
            <TalkingHeadAvatar
              avatarUrl={toAbsoluteAvatarUrl(tutor.avatarModelUrl)}
              backgroundImageUrl={toAbsoluteAvatarUrl(tutor.avatarBackgroundUrl)}
              speechEnabled={tutor.ttsEnabled}
              fallback={<Avatar name={tutor.title} size="lg" />}
              ref={avatarRef}
            />
            {/* Mikro (Eingabe) + Stumm-Schalter (Ausgabe) liegen bewusst hier, nicht im Composer der
                Chat-Spalte — wie die Steuerleiste unter dem Video in einer Videokonferenz bleiben sie
                so unabhängig vom Ein-/Ausklapp-Zustand des Chats immer erreichbar. */}
            {(tutor.sttEnabled || tutor.ttsEnabled) && (
              <div className={styles.stageControls}>
                {tutor.sttEnabled && (
                  <button
                    type="button"
                    className={`${styles.roundButton} ${isRecording ? styles.recording : ""}`}
                    onClick={toggleRecording}
                    disabled={transcribeMutation.isPending}
                    aria-label={
                      transcribeMutation.isPending
                        ? t("publicChat.transcribing")
                        : isRecording
                          ? t("publicChat.stopRecording")
                          : t("publicChat.voiceInput")
                    }
                    aria-pressed={isRecording}
                  >
                    {transcribeMutation.isPending ? (
                      <Loader2 size={18} className={styles.spinIcon} />
                    ) : isRecording ? (
                      <Square size={16} fill="currentColor" />
                    ) : (
                      <Mic size={18} />
                    )}
                  </button>
                )}
                {tutor.ttsEnabled && (
                  <button
                    type="button"
                    className={styles.roundButton}
                    onClick={() => setTtsMuted((muted) => !muted)}
                    aria-label={ttsMuted ? t("publicChat.unmute") : t("publicChat.mute")}
                    aria-pressed={ttsMuted}
                  >
                    {ttsMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Ausziehbarer Griff am Rand der Chat-Spalte — horizontal unter dem Avatar auf Mobile,
              vertikal neben der Spalte auf Desktop (siehe CSS-Media-Query). Sitzt als normales
              Flex-Geschwister genau an der Nahtstelle zwischen Avatar und Chat-Spalte, in beiden
              Layouts, ohne eigene Positionierungslogik pro Breakpoint. */}
          <button
            type="button"
            className={styles.chatToggle}
            onClick={() => setChatOpen((open) => !(open ?? tutor.chatDefaultOpen))}
            aria-expanded={isChatOpen}
            aria-label={isChatOpen ? t("publicChat.collapseChat") : t("publicChat.expandChat")}
            title={isChatOpen ? t("publicChat.collapseChat") : t("publicChat.expandChat")}
          >
            {isChatOpen ? <X size={16} /> : <MessageCircle size={18} />}
          </button>

          {isChatOpen && (
            <div className={styles.chatColumn}>
              <div className={styles.chatColumnHeader}>
                <h2>{t("publicChat.chatTitle")}</h2>
                <p className={styles.privacyNote}>{privacyNotice}</p>
              </div>

              {/* Same sentence as the desktop subtitle above — only one of the two is ever visible
                  (see the media query in PublicChat.module.css), so students get it either way. */}
              <p className={`${styles.privacyNote} ${styles.privacyNoteMobile}`}>{privacyNotice}</p>

              <div className={styles.thread} ref={threadRef}>
                <ChatBubble
                  role="assistant"
                  content={tutor.startPrompt || t("configurator.step4.defaultGreeting", { name: tutor.title })}
                />
                {messages.map((message, index) => (
                  <ChatBubble key={index} role={message.role} content={message.content} />
                ))}
                {sendMutation.isPending && <TypingBubble />}
              </div>

              {rateLimited && (
                <div className={styles.notice}>
                  <Callout variant="warning">{t("errors.RATE_LIMIT_CHAT")}</Callout>
                </div>
              )}

              <form className={styles.composer} onSubmit={handleSubmit}>
                <input
                  className={styles.textInput}
                  type="text"
                  placeholder={t("publicChat.messagePlaceholder")}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  aria-label={t("publicChat.messageAriaLabel")}
                />
                <button
                  type="submit"
                  className={`${styles.roundButton} ${styles.sendButton}`}
                  disabled={sendMutation.isPending}
                  aria-label={t("publicChat.send")}
                >
                  <Send size={18} />
                </button>
              </form>
            </div>
          )}
        </div>
      )}

      {stage === "after-survey" && tutor.surveyAfterUrl && (
        <SurveyEmbed
          url={tutor.surveyAfterUrl}
          title={t("publicChat.surveyAfterTitle")}
          continueLabel={t("publicChat.done")}
          onContinue={() => setManualStage("done")}
          onSkip={() => setManualStage("done")}
        />
      )}

      {stage === "done" && <div className={styles.centered}>{t("publicChat.chatEnded")}</div>}
    </PublicChatLayout>
  );
}
