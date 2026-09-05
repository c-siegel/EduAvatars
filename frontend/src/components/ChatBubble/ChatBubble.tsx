import { useRef, useState, type KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { useTranslation } from "react-i18next";
import { Pencil, RotateCw } from "lucide-react";
import { useAutoResizeTextarea } from "@/hooks/useAutoResizeTextarea";
import styles from "./ChatBubble.module.css";
import "katex/dist/katex.min.css";

interface ChatBubbleProps {
  role: "user" | "assistant";
  content: string;
  /** Shows the edit/regenerate action row below the bubble — only meaningful for the student's own
   * ("user") messages, see pages/PublicChat/index.tsx. */
  editable?: boolean;
  /** Disables the action row while a reply is in flight, same posture as the mic/send buttons. */
  disabled?: boolean;
  /** Called with the edited text once the student submits the inline edit box. */
  onEdit?: (newText: string) => void;
  /** Called to resend this exact message unchanged (no edit box involved). */
  onRegenerate?: () => void;
  /** Caps the inline edit textarea's growth — same value the composer uses, see PublicChat/index.tsx. */
  maxHeightPx?: number;
  /** Caps the inline edit textarea's length — same limit the composer enforces and the backend
   * validates (see MAX_CHAT_MESSAGE_CHARS in PublicChat/index.tsx), so editing can't bypass it. */
  maxLengthChars?: number;
}

/** One chat message bubble; for editable user messages, also the pencil/regenerate action row and
 * the inline edit textarea it swaps in. */
export function ChatBubble({
  role,
  content,
  editable,
  disabled,
  onEdit,
  onRegenerate,
  maxHeightPx,
  maxLengthChars,
}: ChatBubbleProps) {
  const { t } = useTranslation();
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(content);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useAutoResizeTextarea(textareaRef, draft, maxHeightPx);

  function startEditing() {
    setDraft(content);
    setIsEditing(true);
  }

  function submitEdit() {
    const trimmed = draft.trim();
    if (!trimmed) return;
    setIsEditing(false);
    onEdit?.(trimmed);
  }

  function handleEditKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submitEdit();
    } else if (event.key === "Escape") {
      setIsEditing(false);
    }
  }

  const rowClass = [styles.row, role === "user" && styles.me].filter(Boolean).join(" ");

  if (isEditing) {
    return (
      <div className={rowClass}>
        <div className={`${styles.bubble} ${styles.bubbleEditing}`}>
          <textarea
            ref={textareaRef}
            className={styles.editTextarea}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleEditKeyDown}
            aria-label={t("publicChat.editMessage")}
            maxLength={maxLengthChars}
            autoFocus
          />
        </div>
      </div>
    );
  }

  return (
    <div className={rowClass}>
      <div className={styles.bubble}>
        <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
          {content}
        </ReactMarkdown>
      </div>
      {editable && (
        <div className={styles.messageActions}>
          <button
            type="button"
            onClick={startEditing}
            disabled={disabled}
            aria-label={t("publicChat.editMessage")}
            title={t("publicChat.editMessage")}
          >
            <Pencil size={14} />
          </button>
          <button
            type="button"
            onClick={onRegenerate}
            disabled={disabled}
            aria-label={t("publicChat.regenerateMessage")}
            title={t("publicChat.regenerateMessage")}
          >
            <RotateCw size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

// Tippindikator während auf die Bot-Antwort gewartet wird (Live-Vorschau 1e, Chat 1i)
export function TypingBubble() {
  const { t } = useTranslation();
  return (
    <div className={styles.row}>
      <div className={styles.bubble}>
        <span className={styles.typing} aria-label={t("common.replyBeingWritten")}>
          <span />
          <span />
          <span />
        </span>
      </div>
    </div>
  );
}
