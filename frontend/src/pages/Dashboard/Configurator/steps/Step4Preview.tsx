import { useRef, useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
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
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const avatarRef = useRef<TalkingHeadAvatarHandle>(null);

  const sendMutation = useMutation({
    mutationFn: ({ message, history }: { message: string; history: ChatMessage[] }) =>
      projectsApi.previewMessage(projectId, message, history),
    onSuccess: (res) => {
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      if (res.audioBase64) avatarRef.current?.speak(res.audioBase64);
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || sendMutation.isPending) return;
    // history = der bisherige Verlauf VOR dieser neuen Nachricht, siehe PublicChat/index.tsx.
    sendMutation.mutate({ message: trimmed, history: messages });
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
  }

  return (
    <>
      {hasUnsavedChanges && (
        <Callout variant="info">
          Du hast ungespeicherte Änderungen — speichere oben rechts, damit die Vorschau sie berücksichtigt.
        </Callout>
      )}

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
          <h3 className={styles.headerTitle}>{title || "Live-Vorschau"}</h3>
          <Badge>Test</Badge>
        </header>

        <div className={styles.thread}>
          <ChatBubble
            role="assistant"
            content={startPrompt || `Hallo! Ich bin ${title || "dein Avatar"}. Wie kann ich dir helfen?`}
          />
          {messages.map((message, index) => (
            <ChatBubble key={index} role={message.role} content={message.content} />
          ))}
          {sendMutation.isPending && <TypingBubble />}
        </div>

        <form className={styles.composer} onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Nachricht testen …"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            aria-label="Testnachricht"
          />
          <Button type="submit" size="sm" disabled={sendMutation.isPending}>
            <Send size={16} />
          </Button>
        </form>
      </div>
    </>
  );
}
