import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { HelpCircle, Loader2, Mic, MessageCircle, Play, Send, Square, LogOut, Lock, User, X } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { ChatBubble, TypingBubble } from "@/components/ChatBubble";
import { Input } from "@/components/Input";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { SurveyEmbed } from "@/components/SurveyEmbed";
import { TalkingHeadAvatar, type TalkingHeadAvatarHandle, type FpsTrackingResult } from "@/components/TalkingHeadAvatar";
import { PublicChatLayout } from "@/layouts/PublicChatLayout";
import { publicChatApi, type StreamChunkEvent, type StreamDoneEvent } from "@/api/publicChat";
import { ApiError, errorMessage } from "@/api/client";
import { setUnlockToken } from "@/lib/chatUnlockStorage";
import { getVisitorName, setVisitorName } from "@/lib/visitorNameStorage";
import { toAbsoluteAvatarUrl } from "@/lib/avatarUrl";
import { useAutoResizeTextarea } from "@/hooks/useAutoResizeTextarea";
import type { ChatMessage } from "@/types/chat";
import styles from "./PublicChat.module.css";

type Stage = "locked" | "name-gate" | "before-survey" | "chat" | "after-survey" | "done";

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
  reply: string;
  llmMs: number | null;
  ttsMs: number | null;
}

// Per-message speaking stats, tracked across both the streamed and plain paths (see mutationFn,
// playStreamedChunk) for the ?latencyTest=1 log below: how long until the avatar first actually
// spoke, how long it spoke in total, and how smoothly it animated while doing so.
interface SpeakingStats {
  firstSpeechAt: number | null;
  speakingDurationMs: number;
  fpsResult: FpsTrackingResult | null;
}

function newSpeakingStats(): SpeakingStats {
  return { firstSpeechAt: null, speakingDurationMs: 0, fpsResult: null };
}

const round = (n: number) => Math.round(n);

function wordCount(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).filter(Boolean).length : 0;
}

// Same role as setTimeout, but resolves immediately once `signal` aborts instead of waiting out the
// full duration — used for the playback pacing waits below, so interruptResponse() doesn't have to
// wait for the current chunk/reply's audio to finish before unblocking the composer.
function delay(ms: number, signal: AbortSignal | undefined): Promise<void> {
  return new Promise((resolve) => {
    if (signal?.aborted) {
      resolve();
      return;
    }
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      resolve();
    }, { once: true });
  });
}

// Drops local-only UI notices (see the "system" role on ChatMessage) before a message list is sent
// to the backend — its ChatHistoryEntry only accepts "user"/"assistant" and 422s on anything else.
function toApiHistory(history: ChatMessage[]): ChatMessage[] {
  return history.filter((message) => message.role !== "system");
}

// Pause-triggered incremental transcription while recording a voice message (see backend
// services/stt_service.py). Hardcoded constants, not project settings — same posture as the TTS
// chunker's thresholds (services/text_chunk_service.py).
const RECORDING_SEGMENT_MIN_MS = 2000; // shorter than this, a pause doesn't cut a segment yet
const SILENCE_PAUSE_MS = 700; // how long a pause must last before it counts as a cut point
// Empirical cutoff for "quiet" on normalized mic samples (RMS, root mean square) — not measured
// against real hardware/rooms, may need tuning for a very noisy classroom.
const SILENCE_RMS_THRESHOLD = 0.015;
// Mirrors the backend's own truncation (_MAX_INITIAL_PROMPT_CHARS in app/api/public_chat.py) —
// trimming here too avoids uploading an ever-growing prompt on every segment of a long recording,
// most of which the backend would immediately discard anyway.
const MAX_INITIAL_PROMPT_CHARS = 500;
// Mirrors the backend's own cap (_MAX_CHAT_MESSAGE_CHARS in app/models/schemas/chat.py) — caps
// typing here too so a too-long message shows as "can't type more" instead of a round trip to
// the backend just to get a 422 back.
const MAX_CHAT_MESSAGE_CHARS = 8000;

// Safety net for the avatar-reveal gate below (see greetingGraceExpired): how long to wait for the
// autoplayed greeting to resolve as audible before showing the avatar anyway. Generous relative to
// the actual fetch+decode+resume-check round trip (typically well under a second even on a slow
// connection, see speakFromUrl), but short enough a student on a browser that blocks autoplay
// without a prior gesture — the norm on iOS/iPadOS Safari — isn't left thinking the avatar itself
// failed to load, with only a small, easy-to-miss play button as the way to find out otherwise.
const GREETING_REVEAL_GRACE_MS = 2500;

// Calls `onPause` every time the stream has been quiet (RMS below threshold) for SILENCE_PAUSE_MS.
// Returns a cleanup function that stops watching and releases the AudioContext. Reuses the
// MediaStream the caller already holds (from getUserMedia) instead of requesting a new one — an
// AnalyserNode can tap the same stream any number of times.
function watchForSpeechPauses(stream: MediaStream, onPause: () => void): () => void {
  const audioCtx = new AudioContext();
  const source = audioCtx.createMediaStreamSource(stream);
  const analyser = audioCtx.createAnalyser();
  source.connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  let silenceSince: number | null = null;
  let frameId: number;

  function tick() {
    analyser.getFloatTimeDomainData(samples);
    let sumSquares = 0;
    for (const sample of samples) sumSquares += sample * sample;
    const rms = Math.sqrt(sumSquares / samples.length);
    const now = performance.now();
    if (rms < SILENCE_RMS_THRESHOLD) {
      if (silenceSince === null) silenceSince = now;
      else if (now - silenceSince >= SILENCE_PAUSE_MS) {
        silenceSince = now; // avoid firing again every frame while the pause continues
        onPause();
      }
    } else {
      silenceSince = null;
    }
    frameId = requestAnimationFrame(tick);
  }
  frameId = requestAnimationFrame(tick);

  return () => {
    cancelAnimationFrame(frameId);
    source.disconnect();
    void audioCtx.close();
  };
}

// Logs a spoken-message-to-audible-reply latency breakdown for manual testing (?latencyTest=1,
// see PublicChatPage). All durations come from a single clock per side (client performance.now()
// vs. backend time.perf_counter()) — no cross-machine clock sync is needed since none of these
// numbers are compared against each other, only summed/inspected independently.
function logLatency(
  latency: MutationLatency,
  res: SendMessageResult,
  replyReceivedAt: number,
  audioReadyAt: number,
  speaking: SpeakingStats,
) {
  const wps = speaking.speakingDurationMs > 0 ? wordCount(res.reply) / (speaking.speakingDurationMs / 1000) : null;
  console.log("[Latenz-Test] Sprechende → Audio hörbar", {
    totalMs: round(audioReadyAt - latency.micStopAt),
    sttRoundTripMs: round(latency.sendStartAt - latency.micStopAt),
    sttBackendMs: latency.sttMs != null ? round(latency.sttMs) : null,
    replyRoundTripMs: round(replyReceivedAt - latency.sendStartAt),
    llmBackendMs: res.llmMs != null ? round(res.llmMs) : null,
    ttsBackendMs: res.ttsMs != null ? round(res.ttsMs) : null,
    audioDecodeMs: round(audioReadyAt - replyReceivedAt),
    timeToFirstSpeechMs: speaking.firstSpeechAt != null ? round(speaking.firstSpeechAt - latency.sendStartAt) : null,
    speakingDurationMs: speaking.speakingDurationMs > 0 ? round(speaking.speakingDurationMs) : null,
    wordsPerSecond: wps != null ? Math.round(wps * 10) / 10 : null,
    avgFps: speaking.fpsResult?.avgFps != null ? Math.round(speaking.fpsResult.avgFps * 10) / 10 : null,
    droppedFrames: speaking.fpsResult?.droppedFrames ?? null,
    fpsSampleCount: speaking.fpsResult?.sampleCount ?? null,
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

  // Nothing to verify server-side (see PublicProject.requireVisitorName's comment in
  // api/publicChat.ts) — storing the trimmed name and flipping this flag is the whole flow, no
  // mutation/round-trip needed like the password unlock above.
  const [visitorNameInput, setVisitorNameInput] = useState("");
  const [visitorNameProvided, setVisitorNameProvided] = useState(() => Boolean(getVisitorName(slug)));

  function handleVisitorNameSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = visitorNameInput.trim();
    if (!trimmed) return;
    setVisitorName(slug, trimmed);
    setVisitorNameProvided(true);
  }

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [rateLimited, setRateLimited] = useState(false);
  // Translation key for the last getUserMedia failure (permission denied, no device, ...), or
  // null if the mic hasn't failed (yet) — see toggleRecording. Previously only console.error'd,
  // so a student who denied the permission prompt had no idea why voice input silently did
  // nothing.
  const [micErrorKey, setMicErrorKey] = useState<string | null>(null);
  // null = noch keine manuelle Stufen-Wahl getroffen; die tatsächliche Anfangsstufe hängt vom
  // geladenen Projekt ab (Vor-Umfrage konfiguriert?), siehe `stage` weiter unten.
  const [manualStage, setManualStage] = useState<Stage | null>(null);
  // null = noch nicht aus dem geladenen Projekt initialisiert (siehe useEffect unten); danach
  // steuert nur noch der eigene Klick der Besucherin, das Projekt-Default wirkt nur als Startwert.
  const [chatOpen, setChatOpen] = useState<boolean | null>(null);

  const avatarRef = useRef<TalkingHeadAvatarHandle>(null);
  const [avatarReady, setAvatarReady] = useState(false);
  // Ensures the spoken greeting is only ever autoplayed once per page load, not again on a later
  // re-render (e.g. after loadTutor refetches following an unlock).
  const autoplayedGreetingRef = useRef(false);
  // Until the greeting is actually audible, the avatar stays behind its static fallback (see
  // TalkingHeadAvatar's `revealed` prop) instead of idling in the background behind the play
  // button — like a paused video showing a poster frame instead of already-moving footage. Set
  // from playGreeting only once speakFromUrl confirms the audio is actually audible (an autoplay
  // attempt right on load can be silently suspended by the browser — decoding/scheduling still
  // "succeeds" in that case, so success alone isn't enough to reveal).
  const [greetingStarted, setGreetingStarted] = useState(false);
  // Forces `revealed` to true once GREETING_REVEAL_GRACE_MS has passed without greetingStarted —
  // a blocked autoplay attempt (no user gesture yet, essentially guaranteed on iOS/iPadOS Safari)
  // would otherwise leave a fully-loaded avatar hidden behind its static fallback indefinitely,
  // with no visible sign anything is wrong beyond a small play-button overlay. Started in
  // handleAvatarReady, right alongside the autoplay attempt itself.
  const [greetingGraceExpired, setGreetingGraceExpired] = useState(false);
  const greetingGraceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Hides the play button — either immediately on its own click (a real user gesture always
  // makes the audio audible), or via playGreeting's async result once a non-click autoplay
  // attempt is confirmed audible. Never on the mere attempt: a silently blocked autoplay must
  // leave this button up, since it's the only thing that can still make the greeting audible.
  const [playButtonDismissed, setPlayButtonDismissed] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  // True from the moment the mic button is released until the last segment's transcription (and
  // the resulting sendMessage) has been kicked off — drives the mic button's spinner/disabled state,
  // the same role transcribeMutation.isPending used to play before segmentation replaced it.
  const [isFinalizingRecording, setIsFinalizingRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const stopWatchingPausesRef = useRef<(() => void) | null>(null);
  // The specific MediaRecorder instance toggleRecording's stop click targeted — read inside each
  // recorder's own onstop handler (see startSegmentRecorder) via identity comparison, not a plain
  // boolean flag. A pause-triggered cut (cutSegment) starts a new recorder immediately and lets
  // the old one's onstop fire whenever the browser gets to it — if the student pauses and clicks
  // "stop recording" in quick succession, that earlier onstop can still be pending when the click
  // flips a *shared* boolean, making it ALSO see itself as "the final segment". Comparing against
  // the exact recorder instance instead means only the one actually stopped by the click ever is.
  const finalRecorderRef = useRef<MediaRecorder | null>(null);
  const segmentStartedAtRef = useRef(0);
  // Accumulates across every segment of the CURRENT recording — sent back as initial_prompt (see
  // stt_service.py) so each new segment gets cross-segment context, and used as the final message
  // text once recording stops.
  const transcriptSoFarRef = useRef("");
  // Chains every segment's transcribeSegment() call onto the one before it (same pattern as
  // playChainRef below), so segments are always folded into transcriptSoFarRef in the order they
  // were spoken. Without this, each pause-triggered segment's /transcribe request races the
  // others — usually resolving in order on a quiet server, but not guaranteed, and far more likely
  // to reorder once the shared, single-slot STT queue (see stt_service.py) is also busy with a
  // second visitor's recording. An out-of-order final segment would otherwise read/reset
  // transcriptSoFarRef before an earlier segment's words had been folded in, silently dropping
  // them from the sent message (or leaking them into the next recording instead).
  const transcriptionChainRef = useRef<Promise<void>>(Promise.resolve());
  // True if ANY segment of the CURRENT recording failed to transcribe (network error, or the
  // shared STT slot timing out under contention — see stt_service.py); reset at the start of each
  // new recording. Read once the final segment finishes, to decide whether to warn the student
  // their message may be missing words (or didn't send at all) — see transcribeSegment.
  const recordingHadFailureRef = useRef(false);
  // null = no segment has reported an sttMs yet this recording, as opposed to a legitimate sum of
  // exactly 0 — distinguishing the two matters so the final latency log reports null, not 0.
  const segmentSttMsSumRef = useRef<number | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);
  // Überlebt die Kette toggleRecording -> recorder.onstop -> transcribeSegment, die über mehrere
  // async Hops läuft — nur so lässt sich der ursprüngliche "Sprechende"-Zeitpunkt bis zum
  // Latenz-Log durchreichen. { micStopAt } statt nur eine Zahl, damit spätere Felder ergänzbar sind.
  const latencyRef = useRef<{ micStopAt: number } | null>(null);

  // One AbortController per in-flight turn, created in runSend() — read by mutationFn (passed into
  // the API calls) and by the playback code below (to cut a wait short) so interruptResponse() can
  // cancel both the network request and any audio still playing/queued with a single abort() call.
  const abortControllerRef = useRef<AbortController | null>(null);
  // Half of this becomes the composer/edit-textarea's max-height ("no higher than half the message
  // window") — measured off .chatColumn, not .thread, since .chatColumn's own height is fixed by the
  // page layout and doesn't shrink when the composer grows, unlike .thread's (which would feed back
  // into the very cap being computed).
  const [chatColumnHeight, setChatColumnHeight] = useState(0);
  const chatColumnObserverRef = useRef<ResizeObserver | null>(null);
  // A callback ref, not useRef+useEffect([]) — .chatColumn only mounts once the async tutor query
  // resolves into the "chat" stage, a commit later than an empty-deps effect already ran and found
  // nothing there. A callback ref fires exactly when the node itself mounts (and again on
  // collapse/expand of the chat column), so the observer never misses it.
  const chatColumnRef = useCallback((el: HTMLDivElement | null) => {
    chatColumnObserverRef.current?.disconnect();
    chatColumnObserverRef.current = null;
    if (!el) return;
    const observer = new ResizeObserver((entries) => setChatColumnHeight(entries[0].contentRect.height));
    observer.observe(el);
    chatColumnObserverRef.current = observer;
  }, []);
  const composerMaxHeight = chatColumnHeight > 0 ? chatColumnHeight / 2 : undefined;
  const composerTextareaRef = useRef<HTMLTextAreaElement>(null);
  useAutoResizeTextarea(composerTextareaRef, input, composerMaxHeight);

  // Keeps the thread pinned to its newest message whenever its own rendered size changes for any
  // reason — not just on a new message (see the messages/isPending effect below), but also when the
  // composer or an inline message-edit textarea grows/shrinks and eats into .thread's available height.
  useEffect(() => {
    const el = threadRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => el.scrollTo({ top: el.scrollHeight }));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Serializes playback of streamed chunks: each chunk's decode+speak+wait is chained onto this
  // promise instead of firing independently, so chunk N+1 never starts before chunk N finishes —
  // chunks can arrive over the wire faster than they can be spoken. Values from the "done" SSE
  // event (see api/publicChat.ts) for the latency-test log below.
  const playChainRef = useRef<Promise<void>>(Promise.resolve());
  const lastStreamDoneRef = useRef<StreamDoneEvent | null>(null);
  // Timestamp of the "done" SSE event (set in handleStreamDone), separate from lastStreamDoneRef's
  // payload — needed for the ping log below, since by the time onSuccess runs for a streamed reply,
  // playback has already finished and performance.now() would include speaking time too.
  const streamDoneReceivedAtRef = useRef<number | null>(null);
  // Reset at the top of every mutationFn call (the one point both the streamed and plain branches
  // pass through) — so a message where speaking never actually starts (interrupted, null audio, LLM
  // error) reports clean null/0 defaults instead of leaking the previous message's numbers.
  const speakingStatsRef = useRef<SpeakingStats>(newSpeakingStats());

  function revealStreamedChunk(chunk: StreamChunkEvent) {
    setMessages((prev) => {
      if (chunk.index === 0) return [...prev, { role: "assistant", content: chunk.text }];
      const next = [...prev];
      const last = next[next.length - 1];
      // Chunks come pre-trimmed (see text_chunk_service.py), so the original spacing/newlines
      // between them is already lost — a single space is a reasonable stand-in for the few
      // hundred ms until the "done" event replaces this with the exact original text below.
      next[next.length - 1] = { ...last, content: `${last.content} ${chunk.text}` };
      return next;
    });
  }

  async function playStreamedChunk(chunk: StreamChunkEvent): Promise<void> {
    // Already interrupted (see interruptResponse) — drop this chunk entirely: no text reveal, no
    // audio. Chunks already in flight when the student clicked stop still resolve and reach this
    // chained callback, so the check has to happen here, not just at the click itself.
    const signal = abortControllerRef.current?.signal;
    if (signal?.aborted) return;
    if (chunk.index === 0) avatarRef.current?.stopThinking();
    if (!chunk.audioBase64) {
      revealStreamedChunk(chunk);
      return;
    }
    let audioBuffer: AudioBuffer | null = null;
    try {
      audioBuffer = (await avatarRef.current?.decodeAudio(chunk.audioBase64)) ?? null;
    } catch (error) {
      console.error("Audio-Chunk konnte nicht dekodiert werden.", error);
    }
    // Revealed right as the audio is about to start (or right after we know it won't) — not
    // earlier — so the bubble text stays in step with what's actually audible.
    revealStreamedChunk(chunk);
    if (!audioBuffer) return;
    try {
      avatarRef.current?.speakBuffer(audioBuffer);
    } catch (error) {
      // Must not reject playChainRef: that would abort every remaining queued chunk, and make
      // mutationFn's `await playChainRef.current` below throw well after real audio has already
      // played — landing in the catch block that assumes nothing was spoken yet and falls back to
      // the plain endpoint, duplicating the spoken reply. Log and move on instead.
      console.error("Audio-Chunk konnte nicht abgespielt werden.", error);
      return;
    }
    // Tracked only once playback actually started — not necessarily chunk 0, since that chunk's
    // own audio could be null while a later one isn't.
    if (speakingStatsRef.current.firstSpeechAt === null) {
      speakingStatsRef.current.firstSpeechAt = performance.now();
      avatarRef.current?.startFpsTracking();
    }
    speakingStatsRef.current.speakingDurationMs += audioBuffer.duration * 1000;
    // A timer, not a real playback-ended signal — can drift by a fraction of a second on a long
    // reply. Accepted trade-off: wiring a real "ended" callback through TalkingHead/HeadAudio
    // would be a much bigger change for a rarely-noticeable amount of drift. Resolves early if
    // interrupted, via delay()'s own signal check, instead of waiting out the rest of this chunk.
    await delay(audioBuffer.duration * 1000, signal);
  }

  function handleStreamChunk(chunk: StreamChunkEvent) {
    playChainRef.current = playChainRef.current.then(() => playStreamedChunk(chunk));
  }

  function handleStreamDone(doneData: StreamDoneEvent) {
    lastStreamDoneRef.current = doneData;
    streamDoneReceivedAtRef.current = performance.now();
    // Queued onto the same chain so the exact final text only replaces the space-joined
    // approximation once every chunk has actually finished playing, not as soon as the SSE
    // stream itself ends (which happens as soon as the last chunk's TTS finishes, typically
    // before that last chunk has finished being spoken).
    playChainRef.current = playChainRef.current.then(() => {
      // In practice "done" never arrives after an abort (the stream is closed), but a stray race is
      // cheap to guard against: don't resurrect a message the student already interrupted.
      if (abortControllerRef.current?.signal.aborted) return;
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { ...next[next.length - 1], content: doneData.reply };
        return next;
      });
      // Ends exactly when speaking does — every playStreamedChunk() call for this message has, by
      // SSE ordering, already resolved by the time this runs (all "chunk" events precede "done").
      speakingStatsRef.current.fpsResult = avatarRef.current?.stopFpsTracking() ?? null;
    });
  }

  const sendMutation = useMutation({
    mutationFn: async ({
      message,
      history,
    }: {
      message: string;
      history: ChatMessage[];
      sendStartAt: number;
      latency?: MutationLatency;
    }) => {
      speakingStatsRef.current = newSpeakingStats();
      // Otherwise a stream that errors out after already playing >=1 chunk (receivedAnyChunk in
      // sendMessageStream) returns normally without a "done" event, and onSuccess's streamed
      // branch below would read this message's stats against the PREVIOUS message's doneData.
      lastStreamDoneRef.current = null;
      streamDoneReceivedAtRef.current = null;
      const signal = abortControllerRef.current!.signal;
      if (tutor.streamingEnabled && tutor.ttsEnabled) {
        try {
          await publicChatApi.sendMessageStream(
            slug,
            message,
            history,
            { onChunk: handleStreamChunk, onDone: handleStreamDone },
            signal,
          );
          await playChainRef.current;
          // playChainRef's own per-chunk delay() calls are a drifting estimate, not a real
          // "playback ended" signal (see playStreamedChunk) — wait for TalkingHead to actually
          // report idle before cutting it off, or a multi-chunk reply's tail can still be playing
          // here and get cut short. See stopSpeaking's own doc comment for why this call, not just
          // the interrupt path, is what actually puts the mouth back to idle once HeadAudio's
          // live-audio-driven lipsync goes quiet.
          await avatarRef.current?.waitUntilIdle(signal);
          avatarRef.current?.stopSpeaking();
          return { kind: "streamed" as const };
        } catch (error) {
          // Nothing was shown/spoken yet at this point (see sendMessageStream's contract) — safe
          // to retry via the always-available plain endpoint below instead of failing outright.
          console.error("Streaming-Chat fehlgeschlagen, falle auf normale Anfrage zurück.", error);
        }
      }
      const res = await publicChatApi.sendMessage(slug, message, history, signal);
      return { kind: "plain" as const, res };
    },
    onSuccess: async (result, variables) => {
      avatarRef.current?.stopThinking();
      if (result.kind === "streamed") {
        const doneData = lastStreamDoneRef.current;
        const doneReceivedAt = streamDoneReceivedAtRef.current;
        // The "ping": total time from firing the request to the full reply text being ready,
        // regardless of whether this was a typed or spoken message. Logged separately from the
        // more detailed voice-only breakdown below, since that one only fires for voice input.
        if (latencyTestEnabled && doneReceivedAt != null) {
          console.log("[Latency-Test] Ping (user input -> server answer, streamed)", {
            totalMs: round(doneReceivedAt - variables.sendStartAt),
          });
        }
        if (latencyTestEnabled && variables.latency && doneData) {
          const speaking = speakingStatsRef.current;
          const wps =
            speaking.speakingDurationMs > 0 ? wordCount(doneData.reply) / (speaking.speakingDurationMs / 1000) : null;
          console.log("[Latenz-Test] Sprechende → Audio hörbar (gestreamt)", {
            sttRoundTripMs: round(variables.latency.sendStartAt - variables.latency.micStopAt),
            sttBackendMs: variables.latency.sttMs != null ? round(variables.latency.sttMs) : null,
            firstChunkTextReadyMs: doneData.firstChunkTextReadyMs != null ? round(doneData.firstChunkTextReadyMs) : null,
            firstChunkMs: doneData.firstChunkMs != null ? round(doneData.firstChunkMs) : null,
            llmBackendMs: doneData.llmMs != null ? round(doneData.llmMs) : null,
            ttsBackendMs: doneData.ttsMs != null ? round(doneData.ttsMs) : null,
            timeToFirstSpeechMs:
              speaking.firstSpeechAt != null ? round(speaking.firstSpeechAt - variables.latency.sendStartAt) : null,
            speakingDurationMs: speaking.speakingDurationMs > 0 ? round(speaking.speakingDurationMs) : null,
            wordsPerSecond: wps != null ? Math.round(wps * 10) / 10 : null,
            avgFps: speaking.fpsResult?.avgFps != null ? Math.round(speaking.fpsResult.avgFps * 10) / 10 : null,
            droppedFrames: speaking.fpsResult?.droppedFrames ?? null,
            fpsSampleCount: speaking.fpsResult?.sampleCount ?? null,
          });
        }
        return;
      }
      const { res } = result;
      const replyReceivedAt = performance.now();
      if (latencyTestEnabled) {
        console.log("[Latency-Test] Ping (user input -> server answer)", {
          totalMs: round(replyReceivedAt - variables.sendStartAt),
        });
      }
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      let audioReadyAt = replyReceivedAt;
      if (res.audioBase64 && !abortControllerRef.current?.signal.aborted) {
        // Deliberately awaited (not fire-and-forget), so decode time and total speaking duration
        // are both measurable for the latency log below. Visible side effect: isPending now stays
        // true for the whole spoken reply, not just until the HTTP response arrives — confirmed by
        // reading @tanstack/query-core directly, dispatch({type:"success"}) only runs after
        // onSuccess resolves, so awaiting playback here was always going to extend it. This makes
        // the plain path's busy-state duration match the streamed path, which already awaits full
        // playback in mutationFn.
        try {
          const audioBuffer = await avatarRef.current?.decodeAudio(res.audioBase64);
          audioReadyAt = performance.now();
          if (audioBuffer) {
            avatarRef.current?.speakBuffer(audioBuffer);
            speakingStatsRef.current.firstSpeechAt = audioReadyAt;
            speakingStatsRef.current.speakingDurationMs = audioBuffer.duration * 1000;
            avatarRef.current?.startFpsTracking();
            await delay(audioBuffer.duration * 1000, abortControllerRef.current?.signal);
            // See waitUntilIdle's own doc comment — the duration-based delay() above is still just
            // an estimate of when TalkingHead's own playback actually ends.
            await avatarRef.current?.waitUntilIdle(abortControllerRef.current?.signal);
            speakingStatsRef.current.fpsResult = avatarRef.current?.stopFpsTracking() ?? null;
            // See stopSpeaking's own doc comment — nothing else puts the mouth back to idle once
            // this reply's audio goes quiet.
            avatarRef.current?.stopSpeaking();
          }
        } catch (error) {
          console.error("Audio konnte nicht abgespielt werden.", error);
        }
      }
      if (latencyTestEnabled && variables.latency) {
        logLatency(variables.latency, res, replyReceivedAt, audioReadyAt, speakingStatsRef.current);
      }
    },
    onError: (err) => {
      avatarRef.current?.stopThinking();
      // A user-initiated stop (see interruptResponse) — it already appended the notice and stopped
      // the avatar, nothing more to do here. Only the plain path can land here for an abort: the
      // streamed path's sendMessageStream swallows its own AbortError and resolves normally instead.
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (err instanceof ApiError && err.status === 429) {
        setRateLimited(true);
        return;
      }
      // Every other failure (LLM provider timeout/error, network drop, ...) used to end here
      // silently — the user's own message is already shown (added optimistically in sendMessage,
      // before this request even resolves), so with no notice it just sits there forever with no
      // reply and no explanation. More likely to actually happen with two people chatting on the
      // same project at once: a shared LLM key's own rate limit or a transient provider error
      // under doubled load isn't retried indefinitely (see llm_service.py's retry budget).
      setMessages((prev) => [...prev, { role: "system", content: t("publicChat.messageFailed") }]);
    },
  });

  // Transcribes one segment (see watchForSpeechPauses) and appends the result to the visible
  // input box; on the final segment (mic button released), sends the full accumulated text
  // instead — same "no manual send click needed" behavior the single-shot flow had before.
  // Always called chained onto transcriptionChainRef (see startSegmentRecorder) so segments never
  // read/reset transcriptSoFarRef out of order relative to each other.
  async function transcribeSegment(blob: Blob, isFinal: boolean) {
    if (blob.size > 0) {
      try {
        const initialPrompt = transcriptSoFarRef.current.slice(-MAX_INITIAL_PROMPT_CHARS) || undefined;
        const res = await publicChatApi.transcribe(slug, blob, initialPrompt);
        if (res.sttMs != null) {
          segmentSttMsSumRef.current = (segmentSttMsSumRef.current ?? 0) + res.sttMs;
        }
        if (res.text) {
          transcriptSoFarRef.current = `${transcriptSoFarRef.current} ${res.text}`.trim();
          setInput((prev) => `${prev} ${res.text}`.trim());
        }
      } catch (error) {
        // Swallowed here rather than re-thrown: this call is chained onto transcriptionChainRef,
        // and a rejection would break that chain for every later segment too (including the real
        // final one). Recorded on recordingHadFailureRef instead — this segment's words are
        // missing from what gets sent, surfaced as a system-message notice once the recording ends
        // (see the isFinal block below).
        console.error("Segment-Transkription fehlgeschlagen.", error);
        recordingHadFailureRef.current = true;
      }
    }
    if (isFinal) {
      setIsFinalizingRecording(false);
      const fullText = transcriptSoFarRef.current;
      transcriptSoFarRef.current = "";
      const micStopAt = latencyRef.current?.micStopAt;
      const sttMs = segmentSttMsSumRef.current;
      // Surfaced the same way interruptResponse() reports an interruption — inline in the thread,
      // right where the student is looking, instead of a generic banner elsewhere on the page.
      // Fires whenever ANY segment of this recording failed, even one that wasn't the final one,
      // since the sent (or unsent) text may be missing words the student actually said.
      if (recordingHadFailureRef.current) {
        setMessages((prev) => [...prev, { role: "system", content: t("publicChat.recordingFailed") }]);
      }
      if (fullText.trim()) {
        sendMessage(fullText, micStopAt != null ? { micStopAt, sttMs } : undefined);
      }
    }
  }

  // Starts one MediaRecorder segment on the given (already-open) stream. Cutting a segment means
  // stopping this recorder and immediately starting a new one on the same stream — MediaRecorder
  // has no "flush and keep recording" API, but a fresh instance yields an independently
  // decodable WebM blob per segment, which a mid-stream chunk from one long recording would not be.
  function startSegmentRecorder(stream: MediaStream) {
    const recorder = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => {
      // Identity check against the specific recorder toggleRecording's stop click targeted (see
      // finalRecorderRef's own comment) — not a shared flag, so a pause-cut segment whose onstop
      // is still pending when the student clicks stop can't mistake itself for the final one.
      const isFinal = recorder === finalRecorderRef.current;
      if (isFinal) stream.getTracks().forEach((track) => track.stop());
      const blob = new Blob(chunks, { type: "audio/webm" });
      // Chained, not fire-and-forget: keeps every segment's transcribeSegment() call — including
      // this one if it's final — from running before an earlier segment's is done reading/updating
      // transcriptSoFarRef (see transcriptionChainRef's own comment).
      transcriptionChainRef.current = transcriptionChainRef.current.then(() => transcribeSegment(blob, isFinal));
    };
    recorder.start();
    mediaRecorderRef.current = recorder;
    segmentStartedAtRef.current = performance.now();
  }

  // Called on a detected speech pause once the current segment is long enough (see
  // RECORDING_SEGMENT_MIN_MS) — too-short segments are left alone and simply carried into the
  // next one, since faster-whisper's accuracy on very short clips is poor.
  function cutSegment() {
    const recorder = mediaRecorderRef.current;
    const stream = recordingStreamRef.current;
    if (!recorder || !stream || recorder.state !== "recording") return;
    recorder.stop(); // triggers onstop above -> transcribes this segment
    startSegmentRecorder(stream); // continue recording the next one right away
  }

  // Funktion für Sprachaufnahme im Browser
  async function toggleRecording() {
    // Wird bereits aufgenommen -> Aufnahme stoppen
    if (isRecording) {
      // Frühestmöglicher, eindeutiger "Sprechende"-Zeitpunkt (Klick-Handler) fürs Latenz-Log —
      // Erfassen ist praktisch kostenlos, daher immer, nicht nur wenn latencyTestEnabled.
      latencyRef.current = { micStopAt: performance.now() };
      // Captures the exact recorder instance being stopped — see finalRecorderRef's own comment
      // for why this can't be a plain boolean shared across every segment's onstop handler.
      finalRecorderRef.current = mediaRecorderRef.current;
      setIsFinalizingRecording(true);
      stopWatchingPausesRef.current?.();
      stopWatchingPausesRef.current = null;
      mediaRecorderRef.current?.stop();
      avatarRef.current?.stopListening();
      setIsRecording(false);
      return;
    }
    // A reply from a previous message may still be in flight (or, for a streamed reply, still
    // being spoken — sendMutation stays pending for its whole duration, see mutationFn) — starting
    // a new recording now would let its final sendMessage() call silently no-op against the
    // pending-mutation guard below, dropping the just-recorded message with no feedback.
    if (sendMutation.isPending) return;
    // Wird nicht aufgenommen, Erlaubnis fürs Gerät einholen, aufnehmen und transkribieren
    setMicErrorKey(null);
    try {
      // Mikrofonanfrage mit warten auf Erlaubnis
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recordingStreamRef.current = stream;
      avatarRef.current?.startListening(stream);
      transcriptSoFarRef.current = "";
      segmentSttMsSumRef.current = null;
      finalRecorderRef.current = null;
      transcriptionChainRef.current = Promise.resolve();
      recordingHadFailureRef.current = false;
      startSegmentRecorder(stream);
      stopWatchingPausesRef.current = watchForSpeechPauses(stream, () => {
        if (performance.now() - segmentStartedAtRef.current >= RECORDING_SEGMENT_MIN_MS) {
          cutSegment();
        }
      });
      setIsRecording(true);
    } catch (error) {
      console.error("Mikrofonzugriff fehlgeschlagen.", error);
      // NotAllowedError: permission denied (or blocked by browser/site policy). Anything else
      // (NotFoundError, NotReadableError, SecurityError on an insecure origin, ...) means voice
      // input just isn't usable right now for a reason the student can't fix by granting access.
      const denied = error instanceof DOMException && error.name === "NotAllowedError";
      setMicErrorKey(denied ? "publicChat.micPermissionDenied" : "publicChat.micUnavailable");
    }
  }

  // Shared core of sendMessage/editMessage/regenerateFrom: creates the AbortController this turn's
  // interrupt button will act on, and kicks off the mutation against an explicit history (rather
  // than reading the `messages` closure) — editMessage/regenerateFrom need a *truncated* history,
  // not "everything so far".
  function runSend(text: string, history: ChatMessage[], latency?: SendLatency) {
    setRateLimited(false);
    avatarRef.current?.startThinking();
    abortControllerRef.current = new AbortController();
    const sendStartAt = performance.now();
    sendMutation.mutate({
      message: text,
      history: toApiHistory(history),
      sendStartAt,
      latency: latency ? { ...latency, sendStartAt } : undefined,
    });
  }

  function sendMessage(text: string, latency?: SendLatency) {
    const trimmed = text.trim();
    if (!trimmed || sendMutation.isPending) return;
    // history = der bisherige Verlauf VOR dieser neuen Nachricht (messages ist an dieser Stelle noch
    // der alte State-Wert, das setMessages darunter wirkt erst beim nächsten Render).
    runSend(trimmed, messages, latency);
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
  }

  // Edits an earlier user message in place: drops it and everything after it (including its old
  // reply), then resends the edited text as a fresh turn — only reachable while nothing is in
  // flight (see ChatBubble's `disabled` prop), so there's no running response to interrupt first.
  function editMessage(index: number, newText: string) {
    const trimmed = newText.trim();
    if (!trimmed) return;
    const before = messages.slice(0, index);
    runSend(trimmed, before);
    setMessages([...before, { role: "user", content: trimmed }]);
  }

  // Resends an earlier user message unchanged — same truncation as editMessage, just without a text
  // change. Useful when a past reply was unsatisfying and the student wants another attempt at the
  // same question.
  function regenerateFrom(index: number) {
    const original = messages[index];
    if (!original || original.role !== "user") return;
    const before = messages.slice(0, index);
    runSend(original.content, before);
    setMessages([...before, original]);
  }

  // Stops the current reply: cancels the in-flight request (or, if it already arrived, whatever
  // audio is still playing/queued), and leaves a visible trace of the interruption in the thread.
  function interruptResponse() {
    abortControllerRef.current?.abort();
    avatarRef.current?.stopSpeaking();
    speakingStatsRef.current.fpsResult = avatarRef.current?.stopFpsTracking() ?? null;
    setMessages((prev) => [...prev, { role: "system", content: t("publicChat.responseInterrupted") }]);
  }

  // Shared by the send button and the Enter key below. While a recording is still capturing audio,
  // `input` only holds the segments transcribed so far — sending it straight away would ship a
  // truncated message, drop the segment still being recorded, and leave the mic running in the
  // background (nothing would ever call stop() on it). Routing through toggleRecording() instead
  // makes a send-while-recording behave exactly like pressing "stop recording": it stops the mic,
  // transcribes the last segment, and sends the complete accumulated text once that's done (see
  // transcribeSegment's isFinal branch). While a stop is already in flight (isFinalizingRecording),
  // that pending finalization will send on its own — sending here too would double-send.
  function sendFromComposer() {
    if (isRecording) {
      toggleRecording();
      return;
    }
    if (isFinalizingRecording) return;
    sendMessage(input);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    sendFromComposer();
  }

  // Enter sends (matching the composer's <form> submit); Shift+Enter inserts a newline instead.
  // isComposing guards against submitting mid-IME-composition (e.g. typing Japanese/Chinese), where
  // the Enter that confirms a candidate word must not also send the message.
  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      sendFromComposer();
    }
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

  // Only cleans up on unmount — greetingGraceTimerRef itself is set from handleAvatarReady, not
  // from an effect (it needs to start at the exact moment the autoplay attempt does).
  useEffect(() => {
    return () => {
      if (greetingGraceTimerRef.current) clearTimeout(greetingGraceTimerRef.current);
    };
  }, []);

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

  // Locked takes priority over every other stage, and the name gate over everything past it — a
  // manual survey/chat choice made before either was satisfied can't have happened yet anyway
  // (see below: the header's End-chat button and everything past these gates only render later).
  // First stage depends on project: with survey it starts there, else withthe chat
  const stage: Stage =
    tutor.passwordProtected && !tutor.unlocked
      ? "locked"
      : tutor.requireVisitorName && !visitorNameProvided
        ? "name-gate"
        : (manualStage ?? (tutor.surveyBeforeUrl ? "before-survey" : "chat"));
  // Fallback nur für den allerersten Render, bevor der Initialisierungs-Effekt oben gelaufen ist.
  const isChatOpen = chatOpen ?? tutor.chatDefaultOpen;

  function endChat() {
    setManualStage(tutor.surveyAfterUrl ? "after-survey" : "done");
  }

  // Plays the project's pre-generated spoken greeting (see api/projects.ts::generateStartAudio) —
  // used both for the autoplay attempt below and the overlay play button. startAudioUrl is
  // router-relative (see api/projects.py's start-audio route), so it needs the API origin
  // prefixed before fetch() can reach it — same as avatarModelUrl/avatarBackgroundUrl below.
  function playGreeting() {
    const url = toAbsoluteAvatarUrl(tutor.startAudioUrl);
    if (!url) return;
    // Only reveal the avatar and hide the play button once speakFromUrl confirms the audio is
    // actually audible (not just successfully decoded/scheduled) — an autoplay attempt right as
    // the avatar loads can get silently suspended by the browser (no user gesture yet), in which
    // case both must stay as they are so the button remains the student's way to actually hear
    // it. A real click (see the button below) reliably resolves true, since clicking IS the
    // gesture that unblocks it.
    avatarRef.current
      ?.speakFromUrl(url)
      .then((audible) => {
        if (!audible) return;
        setGreetingStarted(true);
        setPlayButtonDismissed(true);
      })
      .catch((error) => {
        console.error("Begrüßung konnte nicht abgespielt werden.", error);
        // The button's own onClick already dismissed itself synchronously (clicking IS the
        // gesture that unblocks playback) — bring it back so a failed attempt (stale audio URL,
        // transient network blip) doesn't remove the student's only way to hear the greeting at
        // all, with no way to retry. A no-op when this was the autoplay attempt instead, which
        // never dismissed the button to begin with.
        setPlayButtonDismissed(false);
      });
  }

  function handleAvatarReady() {
    setAvatarReady(true);
    // Autoplay is frequently blocked by the browser without a prior user gesture — that's expected
    // and silently falls through to the overlay play button below, not an error state.
    if (!autoplayedGreetingRef.current && tutor.ttsEnabled && tutor.startAudioUrl) {
      autoplayedGreetingRef.current = true;
      playGreeting();
      // See greetingGraceExpired's own comment — a blocked attempt must not hide the avatar
      // forever just because nobody happens to tap the play button.
      greetingGraceTimerRef.current = setTimeout(() => setGreetingGraceExpired(true), GREETING_REVEAL_GRACE_MS);
    }
  }

  // Says what actually happens to the conversation, straight from the project's setting — the
  // page used to claim "chat isn't saved" unconditionally, which was untrue whenever the teacher
  // had recording switched on. A separate wording when a name/ID was also collected: "saved
  // anonymously" would be inaccurate once a name is attached to it.
  const privacyNotice = tutor.saveConversations
    ? tutor.requireVisitorName
      ? t("publicChat.privacySavedWithName")
      : t("publicChat.privacySaved")
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
              <LogOut size={24} />
            </button>
          )}
          {/* Speech bubble instead of a title attribute: it has to be reachable by keyboard and on
              touch (where hover doesn't exist), so it opens on hover AND focus via CSS. */}
          <span className={styles.infoTip}>
            <button type="button" className={styles.infoButton} aria-label={t("publicChat.whichModel")}>
              <HelpCircle size={24} />
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

      {stage === "name-gate" && (
        <div className={styles.centered}>
          <form className={styles.lockedForm} onSubmit={handleVisitorNameSubmit}>
            <User size={28} />
            <p className={styles.lockedText}>{t("publicChat.nameGate.description")}</p>
            <Input
              label={t("publicChat.nameGate.nameLabel")}
              type="text"
              autoComplete="off"
              required
              maxLength={100}
              value={visitorNameInput}
              onChange={(e) => setVisitorNameInput(e.target.value)}
            />
            <Button type="submit" variant="accent" fullWidth>
              {t("publicChat.nameGate.submit")}
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
              onReady={handleAvatarReady}
              // Stays behind the static fallback until the greeting has actually started, instead
              // of idling in the background behind the play button — nothing to wait for (no
              // greeting configured) reveals it immediately, as before. greetingGraceExpired is the
              // escape hatch once autoplay is confirmed blocked instead of just still pending (see
              // its own comment) — without it, a browser that never allows autoplay (essentially
              // every iOS/iPadOS Safari visit) would hide a fully-loaded avatar indefinitely.
              revealed={!(tutor.ttsEnabled && tutor.startAudioUrl) || greetingStarted || greetingGraceExpired}
              ref={avatarRef}
            />
            {/* Dismissed two ways: immediately (synchronously) on its own click — since clicking
                IS the gesture that guarantees audio actually plays — or by playGreeting's async
                result, once an autoplay attempt confirms the audio was actually audible (not
                silently suspended). Never tied to the mere ATTEMPT, or a blocked autoplay would
                hide the only control that could still make it audible. */}
            {avatarReady && tutor.ttsEnabled && tutor.startAudioUrl && !playButtonDismissed && (
              <button
                type="button"
                className={styles.playGreetingButton}
                onClick={() => {
                  setPlayButtonDismissed(true);
                  playGreeting();
                }}
                aria-label={t("publicChat.playGreeting")}
                title={t("publicChat.playGreeting")}
              >
                <Play size={24} fill="currentColor" />
              </button>
            )}
            {/* Mikro (Eingabe) + Stopp (Unterbrechen der Antwort) liegen bewusst hier, nicht im
                Composer der Chat-Spalte — wie die Steuerleiste unter dem Video in einer
                Videokonferenz bleiben sie so unabhängig vom Ein-/Ausklapp-Zustand des Chats immer
                erreichbar. */}
            {(tutor.sttEnabled || sendMutation.isPending) && (
              <div className={styles.stageControls}>
                {tutor.sttEnabled && (
                  <button
                    type="button"
                    className={`${styles.roundButton} ${isRecording ? styles.recording : ""}`}
                    onClick={toggleRecording}
                    disabled={isFinalizingRecording || (!isRecording && sendMutation.isPending)}
                    aria-label={
                      isFinalizingRecording
                        ? t("publicChat.transcribing")
                        : isRecording
                          ? t("publicChat.stopRecording")
                          : t("publicChat.voiceInput")
                    }
                    aria-pressed={isRecording}
                  >
                    {isFinalizingRecording ? (
                      <Loader2 size={22} className={styles.spinIcon} />
                    ) : isRecording ? (
                      <Square size={20} fill="currentColor" />
                    ) : (
                      <Mic size={22} />
                    )}
                  </button>
                )}
                {/* Not gated on tutor.ttsEnabled: even a text-only (no TTS) reply can be slow enough
                    to want stopping, since sendMutation.isPending already spans "waiting for the
                    LLM" too, not just "the avatar is speaking". */}
                {sendMutation.isPending && (
                  <button
                    type="button"
                    className={styles.roundButton}
                    onClick={interruptResponse}
                    aria-label={t("publicChat.stopResponse")}
                    title={t("publicChat.stopResponse")}
                  >
                    <Square size={20} fill="currentColor" />
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
            <div className={styles.chatColumn} ref={chatColumnRef}>
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
                {messages.map((message, index) =>
                  message.role === "system" ? (
                    <p key={index} className={styles.systemNotice}>
                      {message.content}
                    </p>
                  ) : (
                    <ChatBubble
                      key={index}
                      role={message.role}
                      content={message.content}
                      editable={message.role === "user"}
                      disabled={sendMutation.isPending}
                      onEdit={(text) => editMessage(index, text)}
                      onRegenerate={() => regenerateFrom(index)}
                      maxHeightPx={composerMaxHeight}
                      maxLengthChars={MAX_CHAT_MESSAGE_CHARS}
                    />
                  ),
                )}
                {sendMutation.isPending && <TypingBubble />}
              </div>

              {rateLimited && (
                <div className={styles.notice}>
                  <Callout variant="warning">{t("errors.RATE_LIMIT_CHAT")}</Callout>
                </div>
              )}

              {micErrorKey && (
                <div className={styles.notice}>
                  <Callout variant="warning">{t(micErrorKey)}</Callout>
                </div>
              )}

              <form className={styles.composer} onSubmit={handleSubmit}>
                <textarea
                  ref={composerTextareaRef}
                  className={styles.textInput}
                  rows={1}
                  placeholder={t("publicChat.messagePlaceholder")}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  aria-label={t("publicChat.messageAriaLabel")}
                  maxLength={MAX_CHAT_MESSAGE_CHARS}
                />
                <button
                  type={sendMutation.isPending ? "button" : "submit"}
                  className={`${styles.roundButton} ${styles.sendButton}`}
                  onClick={sendMutation.isPending ? interruptResponse : undefined}
                  disabled={!sendMutation.isPending && isFinalizingRecording}
                  aria-label={sendMutation.isPending ? t("publicChat.stopResponse") : t("publicChat.send")}
                >
                  {sendMutation.isPending ? <Square size={20} fill="currentColor" /> : <Send size={22} />}
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
