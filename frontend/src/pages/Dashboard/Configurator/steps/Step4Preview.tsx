import { useRef, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Send } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import { Callout } from "@/components/Callout";
import { ChatBubble, TypingBubble } from "@/components/ChatBubble";
import { TalkingHeadAvatar, type TalkingHeadAvatarHandle } from "@/components/TalkingHeadAvatar";
import { projectsApi } from "@/api/projects";
import { toAbsoluteAvatarUrl } from "@/lib/avatarUrl";
import type { ChatMessage } from "@/types/chat";
import styles from "./Step4Preview.module.css";

interface Step4Props {
  projectId: string;
  title: string;
  startPrompt: string;
  avatarModelUrl: string | null;
  avatarBackgroundUrl: string | null;
  ttsEnabled: boolean;
  hasUnsavedChanges: boolean;
}

// Schritt 4 — Live-Vorschau: testet den Avatar mit dem zuletzt GESPEICHERTEN Preprompt/Modell
// (die Backend-Route arbeitet auf den persistierten Projektdaten, nicht auf dem Entwurf).
export function Step4Preview({
  projectId,
  title,
  startPrompt,
  avatarModelUrl,
  avatarBackgroundUrl,
  ttsEnabled,
  hasUnsavedChanges,
}: Step4Props) {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const avatarRef = useRef<TalkingHeadAvatarHandle>(null);

  const sendMutation = useMutation({
    mutationFn: ({ message, history }: { message: string; history: ChatMessage[] }) =>
      projectsApi.previewMessage(projectId, message, history),
    onSuccess: async (res) => {
      avatarRef.current?.stopThinking();
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      if (res.audioBase64) {
        // Same reasoning as PublicChat/index.tsx's plain path: decode+speak+wait instead of the
        // fire-and-forget speak() helper, so stopSpeaking() (see its own doc comment) can run once
        // this reply's audio actually finishes — otherwise HeadAudio's live-audio-driven lipsync
        // has nothing to put the mouth back to idle once it goes quiet.
        const audioBuffer = await avatarRef.current?.decodeAudio(res.audioBase64);
        if (audioBuffer) {
          avatarRef.current?.speakBuffer(audioBuffer);
          await new Promise((resolve) => setTimeout(resolve, audioBuffer.duration * 1000));
          avatarRef.current?.stopSpeaking();
        }
      }
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || sendMutation.isPending) return;
    avatarRef.current?.startThinking();
    // history = der bisherige Verlauf VOR dieser neuen Nachricht, siehe PublicChat/index.tsx.
    sendMutation.mutate({ message: trimmed, history: messages });
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
  }

  return (
    <>
      {hasUnsavedChanges && <Callout variant="info">{t("configurator.step4.unsavedChanges")}</Callout>}

      {ttsEnabled && (
        <div className={styles.avatarStage}>
          <TalkingHeadAvatar
            ref={avatarRef}
            avatarUrl={toAbsoluteAvatarUrl(avatarModelUrl)}
            backgroundImageUrl={toAbsoluteAvatarUrl(avatarBackgroundUrl)}
            speechEnabled
            fallback={<Avatar name={title} size="lg" />}
          />
        </div>
      )}

      <div className={styles.panel}>
        <header className={styles.header}>
          <Avatar name={title} size="sm" />
          <h3 className={styles.headerTitle}>{title || t("configurator.step4.livePreview")}</h3>
          <Badge>{t("configurator.step4.testBadge")}</Badge>
        </header>

        <div className={styles.thread}>
          <ChatBubble
            role="assistant"
            content={startPrompt || t("configurator.step4.defaultGreeting", { name: title || t("configurator.step4.yourAvatar") })}
          />
          {messages.map((message, index) =>
            // "system" is a local-only notice used by the public chat page's interrupt feature
            // (see types/chat.ts) — this preview never produces one, but the shared type allows it.
            message.role === "system" ? null : (
              <ChatBubble key={index} role={message.role} content={message.content} />
            ),
          )}
          {sendMutation.isPending && <TypingBubble />}
        </div>

        <form className={styles.composer} onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder={t("configurator.step4.testMessagePlaceholder")}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            aria-label={t("configurator.step4.testMessageAriaLabel")}
          />
          <Button type="submit" size="sm" disabled={sendMutation.isPending}>
            <Send size={16} />
          </Button>
        </form>
      </div>
    </>
  );
}
